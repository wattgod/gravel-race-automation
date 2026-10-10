"""Content restored into imported WordPress posts from an archived copy
(Matt, 2026-10-09: "1. try").

A post module's RESTORED figures hold what the live post lost (e.g. Elementor
tables that now render as empty columns). The batch tests skip them by id
(wp_post.restored_ids) in the word-for-word comparison with the snapshot; this
file checks the other direction: every restored cell equals the archived copy,
the restored figures are the only additions to the raw snapshot, the
provenance line appears once and the modified date is bumped.
"""
from __future__ import annotations

import html as htmllib
import importlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "wp_posts"
for _p in ("scripts", "wordpress", "wordpress/post_sources"):
    if str(PROJECT_ROOT / _p) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT / _p))

import wp_post  # noqa: E402
import wp_post_import as imp  # noqa: E402

# post id -> (module, archived tables fixture, archive date as the note states it)
RESTORED = {
    3203: ("hacking_unbound_200_with_best_bike_split", "3203.archive-2024-07-17.tables.html", "July 17, 2024"),
}


def _module(pid):
    return importlib.import_module(RESTORED[pid][0])


def _page(pid) -> str:
    return _module(pid).OUTPUT_PATH.read_text(encoding="utf-8")


class _Cells(HTMLParser):
    """Each <table> as a list of rows, each row a list of cell texts
    (whitespace-normalized, entities decoded)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self.tables[-1].append([])
        elif tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.cell is not None:
            self.tables[-1][-1].append(" ".join("".join(self.cell).split()))
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def _tables(fragment: str) -> list[list[list[str]]]:
    p = _Cells()
    p.feed(fragment)
    p.close()
    return p.tables


def _archived(pid) -> list[list[list[str]]]:
    return _tables((FIXTURES / RESTORED[pid][1]).read_text(encoding="utf-8"))


def _figure(page: str, fid: str) -> str:
    return page.split(f'id="{fid}"', 1)[1].split("</figure>", 1)[0]


def _declared(fig) -> list[list[str]]:
    plain = lambda h: " ".join(htmllib.unescape(re.sub(r"<[^>]+>", "", h)).split())  # noqa: E731
    return [[c.label for c in fig.columns]] + [[plain(c.html) for c in r.cells] for r in fig.rows]


@pytest.mark.parametrize("pid", RESTORED)
def test_every_restored_cell_equals_the_archive(pid):
    """Module tables and the rendered page tables, cell for cell, header
    included, in order, against the archived tables (typos and all)."""
    m = _module(pid)
    archived = _archived(pid)
    assert len(m.RESTORED) == len(archived)
    page = _page(pid)
    for fig, want in zip(m.RESTORED, archived):
        assert _declared(fig) == want, fig.id
        rendered = _tables(_figure(page, fig.id))
        assert rendered == [want], fig.id


def test_best_bike_split_archive_typos_are_kept_verbatim():
    """Typos in the archived tables are Matt's call, not fixed on restore."""
    page = _page(3203)
    for typo in (">26;47<", ">37:18:00<", ">50:47:00<"):
        assert typo in page, typo
    skinsuit = [r for r in _module(3203).AERO.rows if r.cells[0].html == "Aero Skinsuit"][0]
    assert [c.html for c in skinsuit.cells] == ["Aero Skinsuit", "20", "$200", "$100/watt"]


@pytest.mark.parametrize("pid", RESTORED)
def test_restored_tables_are_the_only_additions(pid):
    """Against the raw snapshot, skipping only the restored figures (and any
    figure the batch test already declares), the page is word for word."""
    m = _module(pid)
    baseline = wp_post.corrected_baseline((FIXTURES / f"{pid}.txt").read_text(encoding="utf-8"),
                                          getattr(m, "CORRECTIONS", ()))
    assert imp.text_diff(baseline, _page(pid), wp_post.restored_ids(m)) == []
    # Without skipping them, the restored cells are extra text: the skip is doing the work.
    assert imp.text_diff(baseline, _page(pid)) != []


@pytest.mark.parametrize("pid", RESTORED)
def test_restored_post_says_so_once_and_bumps_its_modified_date(pid):
    m = _module(pid)
    page = _page(pid)
    note = f"Tables restored from the Internet Archive copy of this post ({RESTORED[pid][2]})."
    article = imp.article_of(page)
    assert " ".join(imp.visible_text(article).split()).count(note) == 1
    # inside a restored figure, so the word-for-word test skips it with the tables
    assert note not in " ".join(imp.visible_text(article, wp_post.restored_ids(m)).split())
    assert 'href="https://web.archive.org/web/' in _figure(page, m.RESTORED[0].id)
    head = page.split("</head>", 1)[0]
    assert f'<meta property="article:modified_time" content="{wp_post.RESTORED_MODIFIED}">' in head
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S).group(1))
    assert ld["dateModified"] == wp_post.RESTORED_MODIFIED
    assert ld["datePublished"] == m.SOURCE.data["live"]["published"]


def test_restored_needs_distinct_ids_and_an_anchor():
    m = _module(3203)
    with pytest.raises(ValueError, match="restored"):
        wp_post.render_post(m.SOURCE, alt=m.ALT, restored=(m.AERO, m.AERO))
