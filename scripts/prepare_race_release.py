#!/usr/bin/env python3
"""Prepare or publish a validated, race-only release. Preparation needs no secrets."""
from __future__ import annotations

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
from html.parser import HTMLParser
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://gravelgodcycling.com"
CALCULATOR = "https://endurelabs.app/plan/races/calculator"
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
MIB = 1024 * 1024
MISSION_TESTS = ["analytics", "athlete_exit", "plan_debrief", "provider_ingestion", "race_debrief", "runtime_credentials", "stripe_provider_ingestion", "triage", "goal_2027", "lead_nurture", "race_countdown"]


def disk_guard(path: Path = ROOT) -> None:
    for checked in {path.resolve(), Path("/")}:
        if shutil.disk_usage(checked).free < 5 * 1024**3:
            raise RuntimeError("At least 5 GiB free is required before release work")


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def source_identity() -> dict:
    subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--"], check=True)
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}")}


def valid_slug(value: str) -> str:
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise ValueError("Invalid canonical race slug")
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Budget:
    def __init__(self, limit: int):
        self.limit, self.used, self.lock = limit, 0, threading.Lock()

    def consume(self, amount: int) -> None:
        with self.lock:
            if self.used + amount > self.limit:
                raise ValueError("Public recovery aggregate limit exceeded")
            self.used += amount


def bounded_batches(items, worker):
    """At most four requests in flight; cancel pending work on the first failure."""
    iterator = iter(items)
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = set()
        for _ in range(4):
            item = next(iterator, None)
            if item is not None:
                pending.add(pool.submit(worker, item))
        try:
            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                # Do not enqueue further requests until every completed result
                # has passed; one failed request cancels the remaining queue.
                batch = [future.result() for future in done]
                yield batch
                for _ in done:
                    item = next(iterator, None)
                    if item is not None:
                        pending.add(pool.submit(worker, item))
        finally:
            for future in pending:
                future.cancel()


def download(url: str, target: Path, *, cap: int, budget: Budget,
             image: bool = False, opener=None) -> dict:
    """Exact same-origin, bounded recovery. Never replace an existing file."""
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "gravelgodcycling.com" or parsed.query or parsed.fragment:
        raise ValueError("Only exact public GGC URLs are allowed")
    if target.exists() or target.is_symlink():
        raise ValueError("Recovery target already exists")
    opener = opener or build_opener(NoRedirect)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".part")
    try:
        with opener.open(Request(url, headers={"User-Agent": "GravelGodReleaseValidation/1"}), timeout=30) as response:
            if response.status != 200 or response.url != url:
                raise ValueError("Unexpected public response or redirect")
            kind = response.headers.get("Content-Type", "").split(";")[0].lower()
            declared = response.headers.get("Content-Length")
            if image and (kind not in {"image/jpeg", "image/gif"} or not declared or not declared.isdigit()):
                raise ValueError("Missing image type or declared size")
            length = int(declared) if declared and declared.isdigit() else None
            if length is not None and (length <= 0 or length > cap):
                raise ValueError("Declared size exceeds recovery limit")
            size, prefix, digest = 0, b"", hashlib.sha256()
            with temporary.open("xb") as handle:
                while chunk := response.read(65536):
                    size += len(chunk)
                    if size > cap or (length is not None and size > length):
                        raise ValueError("Response exceeds recovery limit")
                    budget.consume(len(chunk))
                    prefix = (prefix + chunk)[:12]
                    digest.update(chunk)
                    handle.write(chunk)
            if not size or (length is not None and size != length):
                raise ValueError("Response length mismatch")
            if image:
                jpeg = target.suffix == ".jpg" and kind == "image/jpeg" and prefix.startswith(b"\xff\xd8\xff")
                gif = target.suffix == ".gif" and kind == "image/gif" and prefix[:6] in {b"GIF87a", b"GIF89a"}
                if not (jpeg or gif):
                    raise ValueError("Image signature/type mismatch")
        temporary.rename(target)
        return {"url": url, "bytes": size, "sha256": digest.hexdigest(), "content_type": kind}
    finally:
        temporary.unlink(missing_ok=True)


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical, self.anchors, self.forms, self.calculators, self.planners = [], [], [], 0, 0
        self.active_form = None
        self.sections, self.citation_anchors = [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "section":
            self.sections.append(a.get("id"))
        if a.get("id") == "race-calculator":
            self.calculators += 1
        if tag == "section" and a.get("id") == "finish-time" and a.get("data-measure-section") == "finish-time-planner":
            self.planners += 1
        if tag == "link" and a.get("rel") == "canonical":
            self.canonical.append(a.get("href"))
        if tag == "a":
            self.anchors.append(a)
            if "citations" in self.sections and "gg-citation-link" in a.get("class", "").split() and not a.get("data-cta"):
                self.citation_anchors.append(a)
        if tag == "form":
            a["fields"] = {}
            self.forms.append(a)
            self.active_form = a
        if tag == "input" and self.active_form is not None and a.get("name"):
            self.active_form["fields"][a["name"]] = a.get("value", "")

    def handle_endtag(self, tag):
        if tag == "section" and self.sections:
            self.sections.pop()
        if tag == "form":
            self.active_form = None


def recover_guides(destination: Path) -> list[dict]:
    evidence, guides = destination / "receipts", destination / "guides"
    evidence.mkdir()
    receipt = download(SITE + "/race-sitemap.xml", evidence / "race-sitemap.xml", cap=5*MIB, budget=Budget(5*MIB))
    xml = ET.parse(evidence / "race-sitemap.xml")
    urls = sorted({node.text for node in xml.findall("{*}url/{*}loc") if node.text and re.fullmatch(re.escape(SITE) + r"/race/[a-z0-9]+(?:-[a-z0-9]+)*/training-plan/", node.text)})
    if not urls:
        raise ValueError("Public sitemap has no genuine training-guide inventory")
    budget = Budget(1024*MIB)

    def recover(url):
        slug = valid_slug(urlparse(url).path.split("/")[2])
        target = guides / (slug + ".html")
        result = download(url, target, cap=2*MIB, budget=budget)
        text = target.read_text(encoding="utf-8")
        parsed = Markup(); parsed.feed(text)
        if parsed.canonical != [url] or "Training Plan" not in text or not text.rstrip().lower().endswith("</html>"):
            raise ValueError("Not an intact exact canonical training guide")
        return {"slug": slug, **result}

    rows = sorted([row for batch in bounded_batches(urls, recover) for row in batch], key=lambda row: row["url"])
    (evidence / "training-guides.json").write_text(json.dumps({"sitemap": receipt, "guides": rows}, indent=2) + "\n")
    return rows


def media_requests(root: Path = ROOT) -> list[tuple[str, str]]:
    requests = set()
    for path in sorted((root / "race-data").glob("*.json")):
        race = json.loads(path.read_text())["race"]
        slug = valid_slug(race.get("slug") or path.stem)
        for photo in race.get("photos", []):
            if not (str(photo.get("type", "")).startswith("video-") or photo.get("type") == "preview-gif"):
                continue
            name = photo.get("file", "")
            if not re.fullmatch(r"[A-Za-z0-9_-]+\.(?:jpg|gif)", name):
                raise ValueError("Unsafe public media filename")
            relative = f"{slug}/{name}"
            if photo.get("url") != "/race-photos/" + relative:
                raise ValueError("Public media metadata does not match its exact file")
            requests.add((SITE + "/race-photos/" + relative, relative))
    return sorted(requests)


def recover_media(destination: Path) -> list[dict]:
    budget = Budget(2*1024*MIB)
    def recover(item):
        url, relative = item
        return {"file": relative, **download(url, destination / "media" / relative, cap=20*MIB, budget=budget, image=True)}
    rows = sorted([row for batch in bounded_batches(media_requests(), recover) for row in batch], key=lambda row: row["url"])
    (destination / "receipts/media.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def mirror_files(source: Path, target: Path) -> None:
    """Real directories, file links only: validators' rglob sees every input."""
    if target.exists() or target.is_symlink():
        raise ValueError("Validation path exists; refusing to overwrite it")
    target.mkdir(parents=True)
    for entry in sorted(source.rglob("*")):
        destination = target / entry.relative_to(source)
        if entry.is_symlink():
            raise ValueError("Validation source must contain genuine files")
        if entry.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        elif entry.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to(entry.resolve())


def run(args: list[str], log: Path) -> None:
    disk_guard()
    with log.open("w") as output:
        subprocess.run([sys.executable, *args], cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, stdout=output, stderr=subprocess.STDOUT, check=True)


def selected_slugs(scope: str, slug: str | None, root: Path = ROOT) -> list[str]:
    tombstones = {entry["slug"] for entry in json.loads((root / "config/tombstones.json").read_text())["tombstones"]}
    available = {valid_slug(p.stem) for p in (root / "race-data").glob("*.json")} - tombstones
    if scope == "single":
        selected = valid_slug(slug or "")
        if selected not in available:
            raise ValueError("Race is not in the active source catalog")
        return [selected]
    if scope != "all" or slug:
        raise ValueError("Choose all without a slug, or single with an active slug")
    if not available:
        raise ValueError("Active source catalog is empty")
    return sorted(available)


def _planner_slug(text: str):
    match = re.search(r'<script type="application/json" class="gg-planner-config">(.*?)</script>', text, re.S)
    try:
        return json.loads(match.group(1)).get("slug") if match else None
    except ValueError:
        return None


def verify_page_contract(text: str, slug: str, expected_plan_hrefs: list[str], expected_citation_hrefs: list[str] | None = None) -> None:
    parsed = Markup(); parsed.feed(text)
    forms = [f for f in parsed.forms if f.get("action") == CALCULATOR and f.get("method", "get").lower() == "get"]
    # A race with an eligible finish-time planner carries the planner in place
    # of the Endure Labs calculator handoff (one or the other, never both).
    planner_page = parsed.planners == 1 and parsed.calculators == 0 and not forms and _planner_slug(text) == slug
    calculator_page = (parsed.planners == 0 and parsed.calculators == 1 and len(forms) == 1
                       and forms[0]["fields"].get("source") == "gravel" and forms[0]["fields"].get("race") == slug)
    if not (planner_page or calculator_page):
        raise ValueError("Calculator navigation contract is missing")
    actual = [a.get("href") for a in parsed.anchors if a.get("data-cta") == "approved_custom_plan"]
    if actual != expected_plan_hrefs:
        raise ValueError("Active custom-plan CTA changed")
    marketplace = re.compile(r"https://(?:www\.)?trainingpeaks\.com/training-plans/[^\s\"\']*tp-[0-9]+")
    # Existing source citations are research references, not a mounted legacy
    # offer. Account for each exact source-backed citation occurrence; an extra
    # CTA, iframe, script or repeated link cannot borrow that exception.
    citations = set(expected_citation_hrefs or [])
    allowed = Counter(html.escape(match.group(), quote=True)
                      for anchor in parsed.citation_anchors
                      if anchor.get("href") in citations
                      for match in [marketplace.search(anchor["href"])] if match)
    if any(a.get("data-cta") == "plan_ladder_buy" for a in parsed.anchors) or Counter(marketplace.findall(text)) != allowed:
        raise ValueError("Legacy unmounted commerce must remain unmounted")
    if parsed.canonical != [SITE + f"/race/{slug}/"] or not text.rstrip().lower().endswith("</html>"):
        raise ValueError("Race page is not intact or has the wrong canonical URL")


def verify_assets(package: Path) -> None:
    pages = package / "pages"
    for kind, extension in [("styles", "css"), ("scripts", "js")]:
        assets = list((pages / "assets").glob(f"gg-{kind}.*.{extension}"))
        if len(assets) != 1 or assets[0].name.split(".")[1] != hashlib.md5(assets[0].read_bytes()).hexdigest()[:8]:
            raise ValueError("Shared asset filename/hash mismatch")
    for page in pages.glob("*.html"):
        text = page.read_text()
        for reference in re.findall(r'(?:href|src)=["\'](/race/assets/[^"\'?#]+)', text):
            relative = reference.removeprefix("/race/")
            resolved = (pages / relative).resolve()
            if not resolved.is_relative_to(pages.resolve()) or not resolved.is_file():
                raise ValueError("Missing or unsafe shared asset reference")


def package_files(package: Path, slugs: list[str]) -> dict[str, dict]:
    """Only declared races and their own companions/shared assets may ship."""
    if {p.name for p in package.iterdir()} != {"pages", "prep-kit", "markdown"}:
        raise ValueError("Unexpected top-level publishing content")
    for slug in slugs:
        valid_slug(slug)
    verify_assets(package)
    expected = {f"pages/{s}.html" for s in slugs} | {f"prep-kit/{s}.html" for s in slugs} | {f"markdown/{s}.md" for s in slugs}
    actual = set()
    rows = {}
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            raise ValueError("Publishing package contains a symlink")
        if not path.is_file():
            continue
        rel = path.relative_to(package).as_posix()
        planner_course = re.fullmatch(r"pages/assets/planner/([a-z0-9]+(?:-[a-z0-9]+)*)\.[0-9a-f]{8}\.json", rel)
        if rel not in expected and not (re.fullmatch(r"pages/assets/(?:gg-(?:styles|scripts)\.[0-9a-f]{8}\.(?:css|js)|fonts/[A-Za-z0-9_-]+\.woff2"
                                                     r"|planner/(?:engine7|gg-planner|gg-planner-core|gg-planner-worker)\.[0-9a-f]{8}\.(?:js|css))", rel)
                                        or (planner_course and planner_course.group(1) in slugs)):
            raise ValueError("Unexpected publishing file: " + rel)
        if not path.stat().st_size:
            raise ValueError("Empty publishing file")
        if path.suffix == ".html" and not path.read_text().rstrip().lower().endswith("</html>"):
            raise ValueError("Truncated publishing HTML")
        actual.add(rel)
        rows[rel] = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    if not expected <= actual or not any(p.startswith("pages/assets/") for p in actual):
        raise ValueError("Publishing package is missing races, companions or assets")
    return rows


def prepare(destination: Path, scope: str, slug: str | None) -> None:
    disk_guard(); destination = destination.resolve()
    disk_guard(destination.parent)
    source = source_identity(); slugs = selected_slugs(scope, slug)
    for alias in [ROOT / "wordpress/output", ROOT / "race-photos"]:
        if alias.exists() or alias.is_symlink():
            raise ValueError("Validation path exists; use a fresh disposable checkout")
    if destination.exists():
        raise ValueError("Release directory must be fresh")
    destination.mkdir(parents=True)
    package, receipts = destination / "package", destination / "receipts"
    recover_guides(destination); recover_media(destination)
    mirror_files(destination / "media", ROOT / "race-photos")
    argument = [slugs[0]] if scope == "single" else ["--all"]
    run(["wordpress/generate_neo_brutalist.py", *argument, "--output-dir", str(package / "pages")], receipts / "pages.log")
    run(["wordpress/generate_prep_kit.py", *argument, "--output-dir", str(package / "prep-kit")], receipts / "prep-kit.log")
    md_arg = ["--slug", slugs[0]] if scope == "single" else []
    run(["scripts/generate_markdown_profiles.py", *md_arg, "--output-dir", str(package / "markdown"), "--training-plan-dir", str(destination / "guides")], receipts / "markdown.log")
    validation = destination / "validation"
    shutil.copytree(package / "pages", validation)
    shutil.copytree(package / "prep-kit", validation / "prep-kit")
    for name, args in [
        ("blog-previews", ["wordpress/generate_blog_preview.py", "--all"]),
        ("blog-recaps", ["wordpress/generate_race_recap.py", "--all"]),
        ("blog-roundups", ["wordpress/generate_season_roundup.py", "--all"]),
    ]:
        run([*args, "--output-dir", str(validation / "blog")], receipts / (name + ".log"))
    run(["wordpress/generate_blog_index_page.py", "--output-dir", str(validation)], receipts / "blog-index.log")
    mirror_files(validation, ROOT / "wordpress/output")
    # Same active custom-plan behavior as generate_page; no legacy TP ladder.
    sys.path.insert(0, str(ROOT / "wordpress"))
    import generate_neo_brutalist as generator
    eligible_ctas = 0
    for selected in slugs:
        rd = generator.load_race_data(ROOT / "race-data" / (selected + ".json"))
        if not isinstance(rd.get("vitals"), dict):
            raise ValueError(f"Race {selected} has no valid vitals; repair its source profile")
        suppressed = rd["vitals"].get("course_status") == "source_blocked" or bool(rd.get("taking_a_break")) or not rd.get("race_plan_eligible", True)
        offer = Markup(); offer.feed("" if suppressed else generator.build_custom_plan_offer(rd))
        hrefs = [a["href"] for a in offer.anchors if a.get("data-cta") == "approved_custom_plan"]
        if not suppressed and not hrefs:
            raise ValueError("Eligible source offer has no active custom-plan CTA")
        eligible_ctas += bool(hrefs)
        verify_page_contract((package / "pages" / (selected + ".html")).read_text(), selected, hrefs,
                             [c["url"] for c in rd.get("citations", []) if isinstance(c, dict) and isinstance(c.get("url"), str)])
    if scope == "all" and not eligible_ctas:
        raise ValueError("All-race CTA check cannot pass without an eligible offer")
    run(["-m", "pytest", "tests/", "-q", "--tb=short", "-x"], receipts / "pytest.log")
    run(["-m", "pytest", *[f"mission_control/tests/test_{name}.py" for name in MISSION_TESTS], "-q", "--tb=short", "-x"], receipts / "mission-control-tests.log")
    run(["scripts/preflight.py", "--skip-tests"], receipts / "preflight.log")
    run(["scripts/preflight_quality.py"], receipts / "preflight-quality.log")
    if source_identity() != source:
        raise ValueError("Source changed during release preparation")
    manifest = {"version": 1, "source": source, "scope": scope, "slugs": slugs, "created_at_utc": datetime.now(timezone.utc).isoformat(), "files": package_files(package, slugs), "public_input_receipts": {name: hashlib.sha256((receipts / name).read_bytes()).hexdigest() for name in ["training-guides.json", "media.json"]}, "gates": "passed", "commerce": "active custom-plan CTA; legacy TP ladder unmounted; no private plan DB dependency"}
    (receipts / "release-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Validated {len(slugs)} races. No SSH or publishing action was performed.")


def assert_publish_source(manifest: dict) -> None:
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Publishing requires the main branch")
    if manifest.get("gates") != "passed" or source_identity() != manifest.get("source"):
        raise ValueError("Validated source does not match checkout")
    expected = manifest["source"]["commit"]
    if os.environ.get("GITHUB_SHA") != expected:
        raise ValueError("Workflow source does not match validated source")
    remote = git("ls-remote", "origin", "refs/heads/main").split()
    if not remote or remote[0] != expected:
        raise ValueError("Main moved after release validation; prepare again")


def live_urls(files: dict[str, dict]) -> dict[str, str]:
    result = {}
    for rel in files:
        parts = Path(rel).parts
        if parts[0] == "pages":
            route = "/race/" + (Path(parts[1]).stem + "/" if len(parts) == 2 else "/".join(parts[1:]))
        elif parts[0] == "prep-kit":
            route = "/race/" + Path(parts[1]).stem + "/prep-kit/"
        else:
            route = "/race/" + parts[1]
        result[rel] = SITE + route
    return result


def publish(destination: Path) -> None:
    destination = destination.resolve()
    manifest = json.loads((destination / "receipts/release-manifest.json").read_text())
    package = destination / "package"
    expected_slugs = selected_slugs(manifest["scope"], manifest["slugs"][0] if manifest["scope"] == "single" and len(manifest["slugs"]) == 1 else None)
    if manifest["slugs"] != expected_slugs:
        raise ValueError("Manifest scope does not match the active source catalog")
    if package_files(package, manifest["slugs"]) != manifest["files"]:
        raise ValueError("Validated publishing bytes changed")
    assert_publish_source(manifest)  # Immediately before the only mutation path.
    subprocess.run([sys.executable, str(ROOT / "scripts/push_wordpress.py"), "--sync-pages", "--pages-dir", str(package / "pages"), "--prep-kit-dir", str(package / "prep-kit"), "--markdown-dir", str(package / "markdown"), "--purge-cache"], cwd=ROOT, check=True)
    verify_live(destination, manifest["files"])


def verify_live(destination: Path, files: dict[str, dict], *, deadline_seconds: int = 600, opener=None) -> None:
    """Bounded parallel verification, with progress receipts before completion."""
    pending = live_urls(files)
    verified, errors = {}, {}
    deadline = time.monotonic() + deadline_seconds
    opener = opener or build_opener(NoRedirect)
    receipt = destination / "receipts/live-verification.json"

    def persist():
        temporary = receipt.with_suffix(".part")
        temporary.write_text(json.dumps({"verified": verified, "pending": pending, "errors": errors}, indent=2) + "\n")
        temporary.replace(receipt)

    def check(item):
        rel, url = item
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return rel, False, "Verification deadline reached"
        try:
            with opener.open(Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "GravelGodReleaseVerification/1"}), timeout=min(20, remaining)) as response:
                data = response.read(files[rel]["bytes"] + 1)
                success = response.status == 200 and response.url == url and len(data) == files[rel]["bytes"] and hashlib.sha256(data).hexdigest() == files[rel]["sha256"]
                return rel, success, "" if success else "Status, URL or exact bytes did not match"
        except (OSError, HTTPException) as exc:
            return rel, False, type(exc).__name__

    persist()
    last_write = time.monotonic()
    updates = 0
    for attempt in range(4):
        batches = bounded_batches(list(pending.items()), check)
        try:
            for batch in batches:
                for rel, success, error in batch:
                    if success:
                        verified[rel] = {"url": pending.pop(rel), **files[rel]}
                        errors.pop(rel, None)
                    else:
                        errors[rel] = error
                    updates += 1
                if updates >= 20 or time.monotonic() - last_write >= 5:
                    persist(); updates = 0; last_write = time.monotonic()
                if time.monotonic() >= deadline:
                    break
        finally:
            batches.close()
            persist()
        if not pending or time.monotonic() >= deadline:
            break
        if attempt < 3:
            time.sleep(min(10, max(0, deadline - time.monotonic())))
    if pending:
        raise RuntimeError(f"Exact live byte verification failed for {len(pending)} files")



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "publish"])
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--scope", choices=["single", "all"], default="all")
    parser.add_argument("--slug")
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare(args.release_dir, args.scope, args.slug)
    else:
        publish(args.release_dir)


if __name__ == "__main__":
    main()
