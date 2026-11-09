"""Publish Site ships each post's and article's img/ folder with its page.

Before Nov 2026 the workflow pushed only index.html, so the Character art
v6.7 redraw (new -v67 file names) went live pointing at images that were
never uploaded.
"""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = (ROOT / ".github" / "workflows" / "publish-site.yml").read_text(encoding="utf-8")

spec = importlib.util.spec_from_file_location(
    "check_post_images_live", ROOT / "scripts" / "check_post_images_live.py")
chk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chk)


def _push_step() -> str:
    start = WF.index("- name: Push imported posts and articles")
    return WF[start:WF.index("- name: Push pages", start)]


def test_pushes_post_and_article_img_folders():
    step = _push_step()
    assert 'scp "${O[@]}" -r "$d/img" "$R/$s/"' in step
    assert 'scp "${O[@]}" -r "$d/img" "$R/articles/$s/"' in step


def test_images_go_up_before_their_page():
    step = _push_step()
    assert step.index('-r "$d/img" "$R/$s/"') < step.index('"$R/$s/index.html"')
    assert (step.index('-r "$d/img" "$R/articles/$s/"')
            < step.index('"$R/articles/$s/index.html"'))


def test_live_check_looks_for_missing_post_images():
    check = WF[WF.index("- name: Check the live site"):]
    assert "python3 scripts/check_post_images_live.py" in check


def test_every_referenced_image_exists_in_the_repo():
    missing = []
    for url in chk.all_images():
        rel = url.removeprefix(chk.BASE + "/")
        local = (ROOT / "wordpress" / "posts" / rel
                 if not rel.startswith("articles/")
                 else ROOT / "wordpress" / rel)
        if not local.is_file():
            missing.append(rel)
    assert not missing, missing[:10]


def test_page_images_reads_src_srcset_poster_and_og(tmp_path):
    page = tmp_path / "index.html"
    page.write_text(
        '<meta property="og:image" content="https://gravelgodcycling.com/p/img/a-og.jpg">'
        '<img src="img/b.webp" srcset="img/b-m.webp 660w, img/b@2x.webp 2x">'
        '<video poster="img/c.webp"></video>'
        '<img src="https://elsewhere.example/x.png">', encoding="utf-8")
    got = chk.page_images(page, "/p/")
    base = "https://gravelgodcycling.com/p/img/"
    assert got == {base + n for n in ("a-og.jpg", "b.webp", "b-m.webp", "b@2x.webp", "c.webp")}
