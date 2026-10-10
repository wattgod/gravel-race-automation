"""Content restored into imported WordPress posts from an archived copy
(Matt, 2026-10-09: "1. try").

A post module's RESTORED figures hold what the live post lost (e.g. Elementor
tables that now render as empty columns). The batch tests skip them by id
(wp_post.restored_ids) in the word-for-word comparison with the snapshot; this
file checks the other direction: every restored cell equals the archived copy,
the restored figures are the only additions to the raw snapshot, the
provenance line appears once and the modified date is bumped.

A module's RESTORED_CORRECTIONS fix errors in the archived tables themselves
(Matt, 2026-10-09): the module still declares the archived cells verbatim,
the page shows them corrected, and every cell no correction names still
equals the archive.
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


def _key(row: list[str]) -> str:
    return wp_post.ROW_SEP.join(row)


def _corrected(rows: list[list[str]], fixes) -> list[list[str]]:
    """Archived rows with the module's row corrections applied, in order."""
    rows = [list(r) for r in rows]
    for c in fixes:
        hits = [i for i, r in enumerate(rows) if _key(r) == c.old]
        assert len(hits) == 1, c.old
        rows[hits[0]] = c.new.split(wp_post.ROW_SEP)
    return rows


def _same_rows(declared: list[list[str]], archived: list[list[str]]) -> bool:
    """Same header, same rows; the body order may differ (a re-sorted list)."""
    return declared[0] == archived[0] and sorted(declared[1:]) == sorted(archived[1:])


@pytest.mark.parametrize("pid", RESTORED)
def test_every_restored_cell_equals_the_archive(pid):
    """Module tables cell for cell against the archived tables (header
    included; rows in archive order, or re-sorted); the rendered tables equal
    the declared ones with the module's RESTORED_CORRECTIONS applied, and
    nothing else."""
    m = _module(pid)
    archived = _archived(pid)
    fixes = getattr(m, "RESTORED_CORRECTIONS", {})
    assert len(m.RESTORED) == len(archived)
    assert set(fixes) <= {f.id for f in m.RESTORED}
    page = _page(pid)
    for fig, want in zip(m.RESTORED, archived):
        declared = _declared(fig)
        assert declared == want or _same_rows(declared, want), fig.id
        rendered = _tables(_figure(page, fig.id))
        expected = [declared[0]] + _corrected(declared[1:], fixes.get(fig.id, ()))
        assert rendered == [expected], fig.id


def _secs(t: str) -> int:
    m, s = t.split(":")
    return int(m) * 60 + int(s)


def _rendered_rows(fid: str) -> list[list[str]]:
    return _tables(_figure(_page(3203), fid))[0][1:]


def test_best_bike_split_corrections_are_exactly_the_approved_ones():
    """Rendered vs archived, cell by cell: these changes and nothing else, so
    every other cell (and every header) is the archive's."""
    diffs = []
    for fig, want in zip(_module(3203).RESTORED, _archived(3203)):
        got = _tables(_figure(_page(3203), fig.id))[0]
        assert got[0] == want[0], fig.id
        body = got[1:]
        if fig.id == "fig-bbs-aero":  # re-sorted: pair rows by product
            by_name = {r[0]: r for r in body}
            body = [by_name[r[0]] for r in want[1:]]
        assert len(body) == len(want) - 1, fig.id
        for old, new in zip(want[1:], body):
            diffs += [(fig.id, o, n) for o, n in zip(old, new) if o != n]
    assert diffs == [
        ("fig-bbs-aero", "$100/watt", "$10/watt"),
        ("fig-bbs-ftp-1230", "26;47", "26:47"),
        ("fig-bbs-combined", "14:28", "17:04"),
        ("fig-bbs-combined", "37:18:00", "37:18"),
        ("fig-bbs-combined", "50:47:00", "54:22"),
        ("fig-bbs-combined", "35:00", "35:35"),
    ]
    page = _page(3203)
    for gone in (">26;47<", ">37:18:00<", ">50:47:00<", ">50:47<", ">14:28<", ">35:00<"):
        assert gone not in page.replace(" ", ""), gone
    assert page.count(wp_post.CORRECTION_NOTE) == 1


def test_best_bike_split_aero_list_is_sorted_and_its_arithmetic_holds():
    """"sorted by dollars/watt": ascending; and each $/watt = cost / watts."""
    rows = _rendered_rows("fig-bbs-aero")
    per_watt = [float(r[3].removeprefix("$").removesuffix("/watt")) for r in rows]
    assert per_watt == sorted(per_watt)
    for (name, watts, cost, _), pw in zip(rows, per_watt):
        assert float(cost.replace("$", "").replace(",", "")) / int(watts) == pw, name


def test_best_bike_split_combined_totals_are_the_sums_of_their_rows():
    rows = {r[0] + ("2" if r[0] == "Total" and i > 3 else ""): r[1:] for i, r in
            enumerate(_rendered_rows("fig-bbs-combined"))}
    for col in (0, 1):
        parts = ("-4% Drag", "-3% Weight", "-1% Rolling Resistance")
        assert _secs(rows["Total"][col]) == sum(_secs(rows[p][col]) for p in parts)
        assert _secs(rows["Total2"][col]) == _secs(rows["Total"][col]) + _secs(rows["10% FTP Increase"][col])
    assert rows["Total"] == ["17:04", "10:10"] and rows["Total2"] == ["54:22", "35:35"]
    # the 10% rows are the FTP tables' 10% rows (~12:30 and ~9:30 finishers)
    assert rows["10% FTP Increase"] == [_rendered_rows("fig-bbs-ftp-1230")[-1][1],
                                        _rendered_rows("fig-bbs-ftp-930")[-1][1]]


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
    with pytest.raises(ValueError, match="restored_corrections"):
        wp_post.render_post(m.SOURCE, alt=m.ALT, restored=(m.AERO,),
                            restored_corrections={"fig-nope": m.RESTORED_CORRECTIONS[m.AERO.id]})


def test_correct_table_needs_one_matching_row_and_the_same_width():
    m = _module(3203)
    fix = wp_post.Correction
    with pytest.raises(ValueError, match="found 0 times"):
        wp_post.correct_table(m.COMBINED, [fix("Total | 1:00 | 2:00", "Total | 1:01 | 2:00", "a b c d")])
    with pytest.raises(ValueError, match="cells"):
        wp_post.correct_table(m.COMBINED, [fix("Total | 14:28 | 10:10", "Total | 17:04", "a b c d")])
    with pytest.raises(ValueError, match="reason"):
        wp_post.correct_table(m.COMBINED, [fix("Total | 14:28 | 10:10", "Total | 17:04 | 10:10", " ")])
