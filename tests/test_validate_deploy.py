"""Tests for scripts/validate_deploy.py photo and title/meta expectations.

Network is never touched: curl_status / curl_body are monkeypatched.
"""

import html
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "wordpress"))

import validate_deploy as vd  # noqa: E402

RACE_INDEX = json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))
META = json.loads((ROOT / "seo" / "meta-descriptions.json").read_text(encoding="utf-8"))


@pytest.fixture
def v():
    return vd.Validator()


@pytest.fixture(autouse=True)
def not_quick(monkeypatch):
    monkeypatch.setattr(vd, "QUICK", False)


# ── Photo infrastructure ──────────────────────────────────────────────────

def _photo_repo(tmp_path, *, with_photos_dir, present=()):
    data = tmp_path / "race-data"
    data.mkdir()
    photos = [{"url": f"/race-photos/r/{i}.jpg"} for i in range(4)]
    (data / "r.json").write_text(json.dumps({"race": {"slug": "r", "photos": photos}}))
    if with_photos_dir:
        d = tmp_path / "race-photos" / "r"
        d.mkdir(parents=True)
        for i in present:
            (d / f"{i}.jpg").write_bytes(b"x")
    return tmp_path


def test_missing_photo_folder_skips_with_one_warning(tmp_path, v, monkeypatch, capsys):
    root = _photo_repo(tmp_path, with_photos_dir=False)
    monkeypatch.setattr(vd, "curl_status", lambda url, timeout=15: "200")
    vd.check_photo_infrastructure(v, project_root=root)
    out = capsys.readouterr().out
    assert v.failed == 0
    assert v.warnings == 1
    assert out.count("WARN") == 1
    assert "race-photos" in out and "4 configured photos not checked locally" in out
    assert "Photo exists" not in out


def test_present_photo_folder_still_fails_each_missing_file(tmp_path, v, monkeypatch):
    root = _photo_repo(tmp_path, with_photos_dir=True, present=(0, 1))
    monkeypatch.setattr(vd, "curl_status", lambda url, timeout=15: "200")
    vd.check_photo_infrastructure(v, project_root=root)
    assert v.failed == 2
    assert v.warnings == 0


def test_live_photo_sample_must_return_200(tmp_path, v, monkeypatch):
    root = _photo_repo(tmp_path, with_photos_dir=False)
    seen = []

    def fake_status(url, timeout=15):
        seen.append(url)
        return "404"

    monkeypatch.setattr(vd, "curl_status", fake_status)
    vd.check_photo_infrastructure(v, project_root=root)
    assert seen and all(u.startswith(f"{vd.BASE_URL}/race-photos/") for u in seen)
    assert v.failed == len(seen)


def test_directory_index_403_is_not_checked(tmp_path, v, monkeypatch):
    root = _photo_repo(tmp_path, with_photos_dir=False)
    seen = []
    monkeypatch.setattr(vd, "curl_status",
                        lambda url, timeout=15: seen.append(url) or "200")
    vd.check_photo_infrastructure(v, project_root=root)
    assert f"{vd.BASE_URL}/race-photos/" not in seen


# ── Title / meta expectations ─────────────────────────────────────────────

def _generated_pages():
    import generate_articles_index
    import generate_coaching
    import generate_homepage

    return {
        "/": generate_homepage.generate_homepage(
            RACE_INDEX, race_data_dir=ROOT / "race-data", substack_posts=[]),
        "/coaching/": generate_coaching.generate_coaching_page(),
        "/articles/": generate_articles_index.render_articles_index([]),
    }


def _wp_page(entry):
    title = html.escape(entry["title"], quote=True)
    desc = html.escape(entry["description"], quote=True)
    return (f'<html><head><title>{title}</title>'
            f'<meta name="description" content="{desc}"></head></html>')


@pytest.fixture(scope="module")
def site():
    pages = _generated_pages()
    by_id = {e["wp_id"]: e for e in META["entries"]}
    pages["/gravel-races/"] = _wp_page(by_id[5018])
    pages["/products/training-plans/"] = _wp_page(by_id[5016])
    return pages


def test_homepage_expectation_derives_race_count_from_index():
    meta = {path: (t, d) for path, t, d in vd.generated_page_meta(RACE_INDEX)}
    title, desc = meta["/"]
    assert f"{len(RACE_INDEX)} races" in desc
    assert f"{(len(RACE_INDEX) // 10) * 10}+" in title
    assert "328" not in title + desc


def test_expectations_match_what_generators_emit(site):
    for path, title, desc in vd.generated_page_meta(RACE_INDEX):
        assert vd.page_has_title(site[path], title), path
        assert vd.page_has_description(site[path], desc), path


def test_meta_check_passes_against_current_generator_output(site, v, monkeypatch):
    monkeypatch.setattr(vd, "curl_body", lambda url, timeout=15: site[url[len(vd.BASE_URL):]])
    vd.check_meta_descriptions(v)
    assert v.failed == 0, "current generator output must satisfy the deploy check"


@pytest.mark.parametrize("path", ["/", "/coaching/", "/articles/", "/gravel-races/"])
def test_meta_check_fails_a_stale_page(site, v, monkeypatch, path):
    stale = dict(site)
    stale[path] = (site[path]
                   .replace(f"{len(RACE_INDEX)} ", "328 ")
                   .replace("Coaching", "Coachng")
                   .replace("Articles", "Articels"))
    assert stale[path] != site[path]
    monkeypatch.setattr(vd, "curl_body", lambda url, timeout=15: stale[url[len(vd.BASE_URL):]])
    vd.check_meta_descriptions(v)
    assert v.failed >= 1


def test_race_count_claims_must_match_index(v):
    vd.check_race_counts(v, "x", "Compare 328 gravel races worldwide.", 384)
    vd.check_race_counts(v, "y", "Compare 384 gravel races worldwide.", 384)
    assert (v.passed, v.failed) == (1, 1)


def test_meta_descriptions_json_counts_match_index(v):
    for e in META["entries"]:
        for field in ("description", "og_description"):
            vd.check_race_counts(v, e["slug"], e.get(field), len(RACE_INDEX))
    assert v.failed == 0
    assert v.passed >= 4  # home + gravel-races, description + og_description
