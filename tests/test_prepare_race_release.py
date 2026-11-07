"""Release behavior: bounded public inputs, exact scope and immutable publication."""
import hashlib
import io
import json
from pathlib import Path
import shutil
import urllib.error

import pytest

from scripts import prepare_race_release as release


def html(slug="test-race", plan=None):
    anchor = f'<a data-cta="approved_custom_plan" href="{plan}">Plan</a>' if plan else ""
    return (f'<html><head><link rel="canonical" href="{release.SITE}/race/{slug}/"></head>'
            f'<body><section id="race-calculator"><form action="{release.CALCULATOR}" method="get"><input name="source" value="gravel"><input name="race" value="{slug}"></form></section>{anchor}</body></html>')


def package(tmp_path, slugs=("test-race",)):
    root = tmp_path / "package"
    for folder in ["pages", "prep-kit", "markdown", "pages/assets"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
    for slug in slugs:
        (root / "pages" / (slug + ".html")).write_text(html(slug))
        (root / "prep-kit" / (slug + ".html")).write_text("<html>Kit</html>")
        (root / "markdown" / (slug + ".md")).write_text("# Race\n")
    for kind, extension, content in [("styles", "css", "body{}"), ("scripts", "js", "void 0;")]:
        digest = hashlib.md5(content.encode()).hexdigest()[:8]
        (root / f"pages/assets/gg-{kind}.{digest}.{extension}").write_text(content)
    return root


@pytest.mark.parametrize("slug", [None, "", "../race", "race/other", "Race", "race;bad", "race--name"])
def test_unsafe_slug_rejected(slug):
    with pytest.raises(ValueError):
        release.valid_slug(slug)


def test_scope_excludes_tombstones_and_requires_exact_single(tmp_path):
    (tmp_path / "config").mkdir(); (tmp_path / "race-data").mkdir()
    (tmp_path / "config/tombstones.json").write_text('{"tombstones":[{"slug":"retired"}]}')
    for slug in ["test-race", "retired"]:
        (tmp_path / "race-data" / (slug + ".json")).write_text("{}")
    assert release.selected_slugs("all", None, tmp_path) == ["test-race"]
    assert release.selected_slugs("single", "test-race", tmp_path) == ["test-race"]
    for scope, slug in [("all", "test-race"), ("single", "retired"), ("single", None)]:
        with pytest.raises(ValueError):
            release.selected_slugs(scope, slug, tmp_path)


def test_disk_guard_stops_below_five_gib(monkeypatch):
    monkeypatch.setattr(release.shutil, "disk_usage", lambda _: shutil._ntuple_diskusage(10, 6, 4))
    with pytest.raises(RuntimeError, match="5 GiB"):
        release.disk_guard()


def test_budget_fails_closed():
    budget = release.Budget(3); budget.consume(3)
    with pytest.raises(ValueError): budget.consume(1)
    assert budget.used == 3


class Response(io.BytesIO):
    status = 200
    url = release.SITE + "/race-photos/test-race/test.jpg"
    def __init__(self, data=b"\xff\xd8\xffbody", **headers):
        super().__init__(data)
        self.headers = {"Content-Type": "image/jpeg", "Content-Length": str(len(data)), **headers}


class Opener:
    def __init__(self, response): self.response = response
    def open(self, *args, **kwargs): return self.response


def test_download_verifies_exact_jpeg_bytes(tmp_path):
    response = Response(); target = tmp_path / "test.jpg"
    receipt = release.download(response.url, target, cap=20, budget=release.Budget(20), image=True, opener=Opener(response))
    assert target.read_bytes() == b"\xff\xd8\xffbody"
    assert receipt["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()


@pytest.mark.parametrize("case", ["redirect", "type", "length", "magic", "cap", "budget"])
def test_bad_public_response_never_leaves_a_valid_file(tmp_path, case):
    response = Response()
    if case == "redirect": response.url += "/changed"
    if case == "type": response.headers["Content-Type"] = "text/html"
    if case == "length": response.headers["Content-Length"] = "8"
    if case == "magic": response = Response(b"not-jpeg")
    target = tmp_path / "test.jpg"
    with pytest.raises(ValueError):
        release.download(release.SITE + "/race-photos/test-race/test.jpg", target, cap=3 if case == "cap" else 20, budget=release.Budget(1 if case == "budget" else 20), image=True, opener=Opener(response))
    assert not target.exists()
    assert not list(tmp_path.glob("*.part"))


def test_redirect_handler_refuses_following():
    assert release.NoRedirect().redirect_request(None, None, 302, "", {}, release.SITE) is None


@pytest.mark.parametrize("url", ["https://evil.test/x", "http://gravelgodcycling.com/x", release.SITE+"/x?key=bad"])
def test_foreign_or_query_recovery_url_rejected(tmp_path, url):
    with pytest.raises(ValueError): release.download(url, tmp_path/"x", cap=20, budget=release.Budget(20))


def test_manifest_rejects_extra_pages_missing_companions_and_symlinks(tmp_path):
    root = package(tmp_path)
    assert len(release.package_files(root, ["test-race"])) == 5
    extra = root/"pages/other.html"; extra.write_text("<html></html>")
    with pytest.raises(ValueError, match="Unexpected"): release.package_files(root, ["test-race"])
    extra.unlink(); md = root/"markdown/test-race.md"; md.unlink()
    with pytest.raises(ValueError, match="missing"): release.package_files(root, ["test-race"])
    md.symlink_to(root/"pages/test-race.html")
    with pytest.raises(ValueError, match="symlink"): release.package_files(root, ["test-race"])


def test_active_cta_preserved_and_suppression_respected():
    url = release.SITE + "/training-plans/start/?race=test-race"
    release.verify_page_contract(html(plan=url), "test-race", [url])
    release.verify_page_contract(html(), "test-race", [])
    with pytest.raises(ValueError, match="CTA"): release.verify_page_contract(html(), "test-race", [url])
    with pytest.raises(ValueError, match="CTA"): release.verify_page_contract(html(plan=url), "test-race", [])


def test_calculator_and_canonical_are_required():
    with pytest.raises(ValueError, match="navigation"):
        release.verify_page_contract(html().replace(release.CALCULATOR, "https://evil.test"), "test-race", [])
    with pytest.raises(ValueError, match="canonical"):
        release.verify_page_contract(html().replace(f'href="{release.SITE}/race/test-race/"', f'href="{release.SITE}/race/different/"'), "test-race", [])


def test_legacy_commerce_must_not_be_mounted():
    text = html().replace("</body>", '<a data-cta="plan_ladder_buy">Buy</a></body>')
    with pytest.raises(ValueError, match="Legacy"): release.verify_page_contract(text, "test-race", [])


def test_validation_mirror_uses_real_directories_and_refuses_overwrite(tmp_path):
    source = tmp_path/"source"; (source/"assets").mkdir(parents=True)
    (source/"assets/test.js").write_text("test")
    target = tmp_path/"target"; release.mirror_files(source, target)
    assert not (target/"assets").is_symlink()
    assert (target/"assets/test.js").is_symlink()
    assert [p.name for p in target.rglob("*.js")] == ["test.js"]
    with pytest.raises(ValueError): release.mirror_files(source, target)


def test_live_routes_cover_all_companions_and_assets():
    files = {k:{} for k in ["pages/test-race.html", "pages/assets/gg-scripts.12345678.js", "prep-kit/test-race.html", "markdown/test-race.md"]}
    assert release.live_urls(files) == {
        "pages/test-race.html": release.SITE+"/race/test-race/",
        "pages/assets/gg-scripts.12345678.js": release.SITE+"/race/assets/gg-scripts.12345678.js",
        "prep-kit/test-race.html": release.SITE+"/race/test-race/prep-kit/",
        "markdown/test-race.md": release.SITE+"/race/test-race.md",
    }


@pytest.mark.parametrize("problem", ["branch", "source", "main", "workflow", "gates"])
def test_publish_requires_validated_exact_main(monkeypatch, problem):
    source={"commit":"abc", "tree":"tree"}
    manifest={"source":source,"gates":"passed"}
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", "abc")
    monkeypatch.setattr(release, "source_identity", lambda: source)
    monkeypatch.setattr(release, "git", lambda *args: "abc\trefs/heads/main")
    release.assert_publish_source(manifest)
    if problem=="branch": monkeypatch.setenv("GITHUB_REF", "refs/heads/feature")
    if problem=="source": monkeypatch.setattr(release,"source_identity",lambda:{"commit":"other"})
    if problem=="main": monkeypatch.setattr(release,"git",lambda *args:"other\trefs/heads/main")
    if problem=="workflow": monkeypatch.setenv("GITHUB_SHA", "other")
    if problem=="gates": manifest["gates"]="failed"
    with pytest.raises(ValueError): release.assert_publish_source(manifest)


def test_workflow_validate_is_default_and_ssh_is_publish_only():
    text=(release.ROOT/".github/workflows/deploy-race-page.yml").read_text()
    assert "default: validate" in text
    assert "inputs.mode == 'publish' && 'publish-site'" in text
    assert "github.run_id" in text
    assert "token: ${{ secrets.GH_PAT }}" not in text
    assert text.index("Prepare exact scoped package") < text.index("Configure SSH")
    assert "if: inputs.mode == 'publish'" in text
    assert "if: always() && inputs.mode == 'publish'" in text
    assert "--deploy-all" not in text and "--deploy-content" not in text


def test_asset_hash_and_referenced_file_must_match(tmp_path):
    root = package(tmp_path)
    css = next((root/"pages/assets").glob("*.css"))
    css.write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        release.package_files(root, ["test-race"])
    css.write_text("body{}")
    page = root/"pages/test-race.html"
    page.write_text(page.read_text().replace("</head>", '<script src="/race/assets/missing.js"></script></head>'))
    with pytest.raises(ValueError, match="reference"):
        release.package_files(root, ["test-race"])


def test_calculator_cannot_handoff_a_different_race():
    with pytest.raises(ValueError, match="navigation"):
        release.verify_page_contract(html().replace('name="race" value="test-race"', 'name="race" value="other"'), "test-race", [])


def test_publish_rejects_changed_bytes_before_any_external_action(tmp_path, monkeypatch):
    root = package(tmp_path)
    manifest = {"scope": "single", "slugs": ["test-race"], "files": release.package_files(root, ["test-race"])}
    (tmp_path/"receipts").mkdir()
    (tmp_path/"receipts/release-manifest.json").write_text(json.dumps(manifest))
    (root/"markdown/test-race.md").write_text("changed after validation")
    monkeypatch.setattr(release, "selected_slugs", lambda *args: ["test-race"])
    calls=[]
    monkeypatch.setattr(release.subprocess, "run", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(ValueError, match="bytes changed"):
        release.publish(tmp_path)
    assert calls == []


def test_prepare_refuses_other_artifacts_before_public_recovery(tmp_path, monkeypatch):
    root = tmp_path/"repo"; (root/"wordpress/output").mkdir(parents=True)
    monkeypatch.setattr(release, "ROOT", root)
    monkeypatch.setattr(release, "disk_guard", lambda *args: None)
    monkeypatch.setattr(release, "source_identity", lambda: {"commit": "abc", "tree": "tree"})
    monkeypatch.setattr(release, "selected_slugs", lambda *args: ["test-race"])
    calls=[]
    monkeypatch.setattr(release, "recover_guides", lambda *args: calls.append(args))
    destination=tmp_path/"new-release"
    with pytest.raises(ValueError, match="fresh disposable"):
        release.prepare(destination, "single", "test-race")
    assert calls == []
    assert not destination.exists()


def test_multi_anchor_custom_offer_is_preserved():
    one = release.SITE + "/training-plans/start/?race=test-race"
    two = release.SITE + "/training-plans/start/?race=test-race&variant=two"
    text = html(plan=one).replace("</body>", f'<a data-cta="approved_custom_plan" href="{two}">Other</a></body>')
    release.verify_page_contract(text, "test-race", [one, two])


def test_marketplace_links_cannot_bypass_legacy_marker_check():
    text = html().replace("</body>", '<a href="https://www.trainingpeaks.com/training-plans/cycling/gravel/tp-123">Buy</a></body>')
    with pytest.raises(ValueError, match="Legacy"):
        release.verify_page_contract(text, "test-race", [])


def test_bounded_recovery_stops_enqueuing_after_first_failure(monkeypatch):
    import threading
    calls=[]; lock=threading.Lock(); started=threading.Barrier(4)
    release_others=threading.Event(); counts={"active":0,"maximum":0}
    real_wait=release.wait
    def worker(item):
        with lock:
            calls.append(item); counts["active"]+=1
            counts["maximum"]=max(counts["maximum"],counts["active"])
        try:
            started.wait(timeout=10)
            if item==0:raise ValueError("missing public input")
            assert release_others.wait(timeout=10)
            return item
        finally:
            with lock:counts["active"]-=1
    def observe_failure(*args,**kwargs):
        done,pending=real_wait(*args,**kwargs)
        # Other workers cannot finish until the first failed future has
        # definitely completed and been observed, so scheduling cannot race.
        assert any(f.exception() is not None for f in done)
        release_others.set()
        return done,pending
    monkeypatch.setattr(release,"wait",observe_failure)
    with pytest.raises(ValueError):list(release.bounded_batches(range(100),worker))
    assert len(calls)==4
    assert counts=={"active":0,"maximum":4}


def test_media_inventory_uses_only_exact_source_paths(tmp_path):
    (tmp_path/"race-data").mkdir()
    profile={"race":{"slug":"test-race","photos":[{"type":"video-1","file":"image.jpg","url":"/race-photos/test-race/image.jpg"}]}}
    path=tmp_path/"race-data/test-race.json"; path.write_text(json.dumps(profile))
    assert release.media_requests(tmp_path)==[(release.SITE+"/race-photos/test-race/image.jpg", "test-race/image.jpg")]
    profile["race"]["photos"][0]["url"]="/different/image.jpg"; path.write_text(json.dumps(profile))
    with pytest.raises(ValueError, match="exact file"): release.media_requests(tmp_path)


@pytest.mark.parametrize("problem", ["empty", "canonical"])
def test_guide_inventory_fails_for_empty_or_wrong_canonical(tmp_path, monkeypatch, problem):
    url=release.SITE+"/race/test-race/training-plan/"
    sitemap='<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+('' if problem=="empty" else f'<url><loc>{url}</loc></url>')+'</urlset>'
    def fake_download(requested,target,**kwargs):
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(sitemap if requested.endswith('.xml') else '<html><title>Training Plan</title><link rel="canonical" href="https://evil.test/"></html>')
        return {"url":requested,"sha256":"fixture"}
    monkeypatch.setattr(release,"download",fake_download)
    with pytest.raises(ValueError,match="inventory|canonical"):
        release.recover_guides(tmp_path)


def test_real_generator_active_and_suppressed_custom_ctas():
    import copy
    import sys
    sys.path.insert(0,str(release.ROOT/"wordpress"))
    import generate_neo_brutalist as generator
    normal=generator.load_race_data(release.ROOT/"race-data/barry-roubaix.json")
    assert normal.get("race_plan_eligible",True) and not normal.get("taking_a_break")
    offer=release.Markup(); offer.feed(generator.build_custom_plan_offer(normal))
    expected=[a["href"] for a in offer.anchors if a.get("data-cta")=="approved_custom_plan"]
    assert len(expected) >= 1
    release.verify_page_contract(generator.generate_page(normal),normal["slug"],expected)
    for field,value in [("taking_a_break",{"label":"Paused","line":"Not racing this year"}),("race_plan_eligible",False),("course_status","source_blocked")]:
        rd=copy.deepcopy(normal)
        if field=="course_status":rd["vitals"][field]=value
        else:rd[field]=value
        release.verify_page_contract(generator.generate_page(rd),rd["slug"],[])


def test_real_generator_shared_asset_layout(tmp_path):
    import sys
    sys.path.insert(0,str(release.ROOT/"wordpress"))
    import generate_neo_brutalist as generator
    generator.write_shared_assets(tmp_path/"pages")
    release.verify_assets(tmp_path)
    assert len(list((tmp_path/"pages/assets/fonts").glob("*.woff2")))==len(generator.FONT_FILES)


@pytest.mark.parametrize("script,flags", [
    ("wordpress/generate_neo_brutalist.py",["--all","--output-dir"]),
    ("wordpress/generate_prep_kit.py",["--all","--output-dir"]),
    ("scripts/generate_markdown_profiles.py",["--slug","--output-dir","--training-plan-dir"]),
    ("wordpress/generate_blog_preview.py",["--all","--output-dir"]),
    ("wordpress/generate_race_recap.py",["--all","--output-dir"]),
    ("wordpress/generate_season_roundup.py",["--all","--output-dir"]),
    ("wordpress/generate_blog_index_page.py",["--output-dir"]),
    ("scripts/push_wordpress.py",["--sync-pages","--pages-dir","--prep-kit-dir","--markdown-dir","--purge-cache"]),
])
def test_real_cli_argument_contracts(script,flags):
    import subprocess
    import sys
    release.disk_guard()
    result=subprocess.run([sys.executable,str(release.ROOT/script),"--help"],cwd=release.ROOT,capture_output=True,text=True,check=True,timeout=20)
    for flag in flags:assert flag in result.stdout


def test_preflight_test_stage_matches_explicit_full_pytest():
    import ast
    tree=ast.parse((release.ROOT/"scripts/preflight.py").read_text())
    calls=[node for node in ast.walk(tree) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=="run_step" and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value=="pytest"]
    assert len(calls)==1
    assert [node.value for node in calls[0].args[1].elts[1:]]==["-m","pytest","tests/","-q","--tb=short","-x"]


def test_parsed_workflow_separates_validate_from_publish_secrets():
    import yaml
    workflow=yaml.safe_load((release.ROOT/".github/workflows/deploy-race-page.yml").read_text())
    trigger=workflow.get("on",workflow.get(True))
    assert trigger["workflow_dispatch"]["inputs"]["mode"]["default"]=="validate"
    group=workflow["concurrency"]["group"]
    assert "inputs.mode == 'publish'" in group and "'publish-site'" in group and "github.run_id" in group
    steps=workflow["jobs"]["release"]["steps"]
    for step in steps:
        if any("secrets.SSH_" in str(v) for v in step.get("env",{}).values()) or step.get("name","").startswith("Publish only"):
            assert step["if"]=="inputs.mode == 'publish'"


@pytest.mark.parametrize("problem", ["mismatch","redirect","timeout","incomplete"])
def test_live_verification_failure_writes_a_receipt(tmp_path,monkeypatch,problem):
    (tmp_path/"receipts").mkdir()
    data=b"expected";rel="markdown/test-race.md";url=release.SITE+"/race/test-race.md"
    class LiveOpener:
        def open(self,*args,**kwargs):
            if problem=="timeout":raise TimeoutError("fixture")
            if problem=="incomplete":
                from http.client import IncompleteRead
                raise IncompleteRead(b"partial",8)
            response=Response(b"different")
            response.url=url if problem!="redirect" else release.SITE+"/different"
            return response
    monkeypatch.setattr(release.time,"sleep",lambda _:None)
    with pytest.raises(RuntimeError,match="verification failed"):
        release.verify_live(tmp_path,{rel:{"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}},opener=LiveOpener())
    receipt=json.loads((tmp_path/"receipts/live-verification.json").read_text())
    assert receipt["pending"]=={rel:url}
    assert receipt["verified"]=={}
    assert rel in receipt["errors"]


def test_publish_calls_only_scoped_publisher_once_after_guard(tmp_path,monkeypatch):
    root=package(tmp_path)
    manifest={"scope":"single","slugs":["test-race"],"files":release.package_files(root,["test-race"])}
    (tmp_path/"receipts").mkdir();(tmp_path/"receipts/release-manifest.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(release,"selected_slugs",lambda *args:["test-race"])
    events=[]
    monkeypatch.setattr(release,"assert_publish_source",lambda _:events.append("guard"))
    monkeypatch.setattr(release.subprocess,"run",lambda args,**kwargs:events.append(args))
    monkeypatch.setattr(release,"verify_live",lambda *args:events.append("verify"))
    release.publish(tmp_path)
    assert events[0]=="guard" and events[2]=="verify"
    command=events[1]
    assert command[2:]==["--sync-pages","--pages-dir",str(root/"pages"),"--prep-kit-dir",str(root/"prep-kit"),"--markdown-dir",str(root/"markdown"),"--purge-cache"]
    events.clear()
    def fail(_):raise ValueError("main moved")
    monkeypatch.setattr(release,"assert_publish_source",fail)
    with pytest.raises(ValueError,match="main moved"):release.publish(tmp_path)
    assert events==[]


def test_verification_deadline_stops_network_and_keeps_receipt(tmp_path):
    (tmp_path/"receipts").mkdir()
    class NeverOpen:
        def open(self,*args,**kwargs):raise AssertionError("deadline must stop network")
    with pytest.raises(RuntimeError):
        release.verify_live(tmp_path,{"markdown/test-race.md":{"bytes":1,"sha256":"x"}},deadline_seconds=0,opener=NeverOpen())
    receipt=json.loads((tmp_path/"receipts/live-verification.json").read_text())
    assert receipt["pending"]


def test_live_verification_admits_only_exact_success(tmp_path):
    (tmp_path/"receipts").mkdir()
    data=b"expected"; rel="markdown/test-race.md"; url=release.SITE+"/race/test-race.md"
    response=Response(data); response.url=url
    release.verify_live(tmp_path,{rel:{"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}},opener=Opener(response))
    receipt=json.loads((tmp_path/"receipts/live-verification.json").read_text())
    assert receipt["pending"]=={}
    assert receipt["verified"][rel]["url"]==url


def test_real_single_scope_generators_emit_page_assets_and_companion(tmp_path):
    import os
    import subprocess
    import sys
    package=tmp_path/"package"
    for script,folder in [("wordpress/generate_neo_brutalist.py","pages"),("wordpress/generate_prep_kit.py","prep-kit")]:
        release.disk_guard()
        result=subprocess.run([sys.executable,str(release.ROOT/script),"barry-roubaix","--output-dir",str(package/folder)],cwd=release.ROOT,env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1"},capture_output=True,text=True,check=True,timeout=30)
        assert (package/folder/"barry-roubaix.html").is_file(),result.stdout
        assert len(list((package/folder).glob("*.html")))==1
    release.verify_assets(package)
    parsed=release.Markup();parsed.feed((package/"pages/barry-roubaix.html").read_text())
    expected=[a["href"] for a in parsed.anchors if a.get("data-cta")=="approved_custom_plan"]
    assert expected
    release.verify_page_contract((package/"pages/barry-roubaix.html").read_text(),"barry-roubaix",expected)


def test_existing_publisher_reads_the_exported_ssh_variable_names(tmp_path,monkeypatch):
    import sys
    sys.path.insert(0,str(release.ROOT/"scripts"))
    import push_wordpress
    key=tmp_path/"fixture-key";key.write_text("fixture only")
    monkeypatch.setattr(push_wordpress,"SSH_KEY",key)
    monkeypatch.setenv("SSH_HOST","host.example")
    monkeypatch.setenv("SSH_USER","fixture")
    monkeypatch.setenv("SSH_PORT","2222")
    assert push_wordpress.get_ssh_credentials()==("host.example","fixture","2222")


def test_only_exact_source_backed_citation_can_reference_marketplace():
    url = "https://www.trainingpeaks.com/training-plans/cycling/tp-123/source-plan"
    citation = f'<section id="citations"><a class="gg-citation-link" href="{url}">Source</a></section>'
    text = html().replace("</body>", citation + "</body>")
    release.verify_page_contract(text, "test-race", [], [url])
    for changed, sources in [
        (text, []),
        (text.replace('id="citations"', 'id="other"'), [url]),
        (text.replace('class="gg-citation-link"', 'class="buy"'), [url]),
        (text.replace('class="gg-citation-link"', 'class="gg-citation-link" data-cta="buy"'), [url]),
        (text.replace("</body>", f'<a href="{url}">Buy</a></body>'), [url]),
        (text.replace("</body>", f'<iframe src="{url}"></iframe></body>'), [url]),
    ]:
        with pytest.raises(ValueError, match="Legacy"):
            release.verify_page_contract(changed, "test-race", [], sources)


@pytest.mark.parametrize("slug", ["iowa-wind-and-rock", "sea-otter-europe-gravel"])
def test_real_source_research_citation_does_not_become_a_commerce_failure(slug):
    import sys
    sys.path.insert(0, str(release.ROOT / "wordpress"))
    import generate_neo_brutalist as generator
    rd = generator.load_race_data(release.ROOT / "race-data" / (slug + ".json"))
    offer = release.Markup(); offer.feed(generator.build_custom_plan_offer(rd))
    expected = [a["href"] for a in offer.anchors if a.get("data-cta") == "approved_custom_plan"]
    release.verify_page_contract(generator.generate_page(rd), slug, expected, [c["url"] for c in rd["citations"]])
