"""Pick'em: generator output, lock constant, scoring, race-page CTA, worker."""

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_pickem  # noqa: E402
import pickem  # noqa: E402
import score_pickem  # noqa: E402

WORKER = ROOT / "workers" / "pickem-intake" / "worker.js"
WRANGLER = ROOT / "workers" / "pickem-intake" / "wrangler.toml"
GAME = pickem.game_for_race("unbound-200")


@pytest.fixture(scope="module")
def page():
    return generate_pickem.build_page(GAME)


# --- Generator output ---

class TestGeneratorOutput:
    def test_ga4_snippet(self, page):
        assert generate_pickem.get_ga4_head_snippet() in page

    def test_font_face(self, page):
        assert "@font-face" in page
        assert generate_pickem.get_font_face_css() in page

    def test_shared_header(self, page):
        assert generate_pickem.get_site_header_html(active="races") in page
        assert generate_pickem.get_site_header_js() in page

    def test_honeypot(self, page):
        assert 'name="website"' in page
        assert 'tabindex="-1"' in page

    def test_posts_to_worker(self, page):
        assert 'data-worker="https://pickem-intake.gravelgodcoaching.workers.dev"' in page

    def test_no_inline_handlers(self, page):
        assert not re.search(r"\son[a-z]+\s*=", page, re.I)

    def test_no_innerhtml(self, page):
        assert "innerHTML" not in generate_pickem.PAGE_JS

    def test_six_pick_inputs_with_datalists(self, page):
        assert len(re.findall(r'data-pick="(women|men)"', page)) == 6
        assert 'list="gg-pk-riders-women"' in page and 'list="gg-pk-riders-men"' in page
        assert '<option value="Sofía Gómez Villafañe">' in page

    def test_required_email_and_name_unchecked_optin(self, page):
        assert re.search(r'id="gg-pk-email"[^>]*required', page)
        assert re.search(r'id="gg-pk-name"[^>]*required', page)
        optin = re.search(r'<input id="gg-pk-optin"[^>]*>', page).group(0)
        assert "checked" not in optin

    def test_success_only_after_worker_confirms(self):
        js = generate_pickem.PAGE_JS
        assert js.index("res.body.success") < js.index("Saved.")
        assert js.index("res.body.success") < js.index("gtag('event', 'pickem_submit'")

    def test_neo_brutalist(self, page):
        assert re.search(r"border-radius:\s*0 !important", page)
        css = generate_pickem.PAGE_CSS
        assert not re.search(r"border-radius:\s*[1-9]", css)
        assert not re.search(r"box-shadow:(?!\s*none)", css)

    def test_leaderboard_replaces_form_and_escapes_names(self):
        board = {"results": {"women": ["A", "B", "C"], "men": ["D", "E", "F"]},
                 "entries": [{"rank": 1, "display_name": "<script>x</script>", "points": 9}]}
        html = generate_pickem.build_page(GAME, board)
        assert 'id="gg-pk-form"' not in html
        assert "&lt;script&gt;x&lt;/script&gt;" in html
        assert "@" not in html.split('id="leaderboard"')[1].split("</section>")[0]

    def test_rider_lists_have_sources(self):
        for cat, _ in pickem.CATEGORIES:
            for group in GAME["riders"][cat]:
                assert group["sources"], group["list"]
                assert all(u.startswith("https://") for u in group["sources"])
        assert len(pickem.rider_names(GAME, "women")) > 20
        assert len(pickem.rider_names(GAME, "men")) > 20


# --- Lock: one constant ---

class TestLock:
    def test_page_uses_game_lock(self, page):
        assert f'data-lock="{GAME["lock_utc"]}"' in page

    def test_worker_lock_matches_game_file(self):
        source = WORKER.read_text()
        match = re.search(r"'%s':\s*'([^']+)'" % re.escape(GAME["game"]), source)
        assert match, "game missing from worker GAMES"
        assert match.group(1) == GAME["lock_utc"]

    def test_lock_is_race_day_start(self):
        from generate_race_dates import parse_date_specific
        race = json.loads((ROOT / "race-data" / "unbound-200.json").read_text())["race"]
        race_day = parse_date_specific(race["vitals"]["date_specific"])
        assert pickem.lock_time(GAME) == datetime(2027, 6, 5, 11, 0, tzinfo=timezone.utc)
        assert pickem.lock_time(GAME).date().isoformat() == race_day

    def test_lock_literal_appears_once_per_language(self):
        literal = GAME["lock_utc"]
        assert WORKER.read_text().count(literal) == 1
        for path in (ROOT / "wordpress" / "generate_pickem.py", ROOT / "wordpress" / "pickem.py",
                     ROOT / "scripts" / "score_pickem.py"):
            assert literal not in path.read_text()


# --- Scoring ---

RESULTS = {"women": ["Ann", "Bea", "Cat"], "men": ["Dan", "Eli", "Fox"]}


class TestScoring:
    def test_exact_podium_is_18(self):
        assert score_pickem.score_entry(RESULTS, RESULTS) == 18

    def test_wrong_place_is_1(self):
        picks = {"women": ["Bea", "Ann", "Zed"], "men": ["Fox", "Xav", "Yan"]}
        assert score_pickem.score_entry(picks, RESULTS) == 3

    def test_accent_case_and_alias_matching(self):
        results = {"women": ["Sofía Gómez Villafañe", "Bea", "Cat"], "men": ["Dan", "Eli", "Fox"],
                   "aliases": {"Sofía Gómez Villafañe": ["Sofia Gomez"]}}
        assert score_pickem.score_entry({"women": ["sofia gomez villafane"], "men": []}, results) == 3
        assert score_pickem.score_entry({"women": ["Sofia Gomez"], "men": []}, results) == 3
        assert score_pickem.score_entry({"women": ["", "sofia gomez"], "men": []}, results) == 1

    def test_ties_go_to_earlier_final_entry(self):
        entries = [
            {"display_name": "Late", "picks": RESULTS, "submitted_at": "2027-06-01T10:00:00Z"},
            {"display_name": "Early", "picks": RESULTS, "submitted_at": "2027-05-01T10:00:00Z"},
            {"display_name": "Low", "picks": {"women": [], "men": []}, "submitted_at": "2027-04-01T10:00:00Z"},
        ]
        rows = score_pickem.build_leaderboard(entries, RESULTS)
        assert [r["display_name"] for r in rows] == ["Early", "Late", "Low"]
        assert [r["rank"] for r in rows] == [1, 2, 3]

    def test_entries_after_lock_dropped_and_no_emails(self):
        entries = [
            {"display_name": "Ok", "email": "a@b.co", "picks": RESULTS, "submitted_at": "2027-06-05T10:59:59Z"},
            {"display_name": "Late", "email": "c@d.co", "picks": RESULTS, "submitted_at": "2027-06-05T11:00:00Z"},
        ]
        rows = score_pickem.build_leaderboard(entries, RESULTS, pickem.lock_time(GAME))
        assert [r["display_name"] for r in rows] == ["Ok"]
        assert set(rows[0]) == {"rank", "display_name", "points"}


# --- Race-page CTA ---

class TestRaceCta:
    def test_cta_only_on_unbound_200(self):
        import generate_neo_brutalist as gnb
        cta = gnb.build_pickem_cta({"slug": "unbound-200"})
        assert GAME["path"] in cta and 'data-cta="pickem"' in cta
        slugs = [p.stem for p in (ROOT / "race-data").glob("*.json")]
        assert [s for s in slugs if gnb.build_pickem_cta({"slug": s})] == ["unbound-200"]

    def test_cta_sits_after_results(self):
        source = (ROOT / "wordpress" / "generate_neo_brutalist.py").read_text()
        assert "results_sec, pickem_cta," in source


# --- Worker ---

HARNESS = r"""
const mod = await import(process.argv[1]);
const worker = mod.default;
const store = new Map();
const env = {
  ALLOWED_ORIGINS: 'https://gravelgodcycling.com',
  EXPORT_TOKEN: 'secret',
  PICKEM: {
    async get(k) { return store.has(k) ? store.get(k).value : null; },
    async put(k, value, opts) { store.set(k, { value, metadata: opts && opts.metadata }); },
    async list({ prefix }) {
      return { keys: [...store.entries()].filter(([k]) => k.startsWith(prefix))
        .map(([name, v]) => ({ name, metadata: v.metadata })), list_complete: true };
    }
  }
};
const base = { game: 'unbound-200-2027', email: 'Rider@Example.com', display_name: 'Rider',
  opt_in: true, picks: { women: ['A', 'B', 'C'], men: ['D', 'E', 'F'] } };
async function post(body, origin = 'https://gravelgodcycling.com') {
  const r = await worker.fetch(new Request('https://w.dev/', { method: 'POST',
    headers: { 'Content-Type': 'application/json', Origin: origin }, body: JSON.stringify(body) }), env);
  return { status: r.status, body: await r.json().catch(() => null) };
}
const out = {};
out.first = await post(base);
out.second = await post({ ...base, email: 'rider@example.com ', picks: { women: ['C', 'B', 'A'], men: ['D', 'E', 'F'] } });
out.honeypot = await post({ ...base, website: 'x' });
out.noName = await post({ ...base, display_name: ' ' });
out.dupe = await post({ ...base, picks: { women: ['A', 'a', 'C'], men: ['D', 'E', 'F'] } });
out.shortPicks = await post({ ...base, picks: { women: ['A', 'B'], men: ['D', 'E', 'F'] } });
out.badOrigin = (await worker.fetch(new Request('https://w.dev/', { method: 'POST',
  headers: { Origin: 'https://gravelgodcycling.com.evil.com' }, body: '{}' }), env)).status;
out.unknownGame = await post({ ...base, game: 'nope' });
const realNow = Date.now;
Date.now = () => Date.parse('2027-06-05T11:00:00Z');
out.locked = await post(base);
Date.now = realNow;
out.exportNoAuth = (await worker.fetch(new Request('https://w.dev/export'), env)).status;
const exp = await worker.fetch(new Request('https://w.dev/export',
  { headers: { Authorization: 'Bearer secret' } }), env);
out.export = await exp.json();
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def worker_run(tmp_path_factory):
    if not shutil.which("node"):
        pytest.skip("node not installed")
    tmp = tmp_path_factory.mktemp("worker")
    mjs = tmp / "worker.mjs"
    shutil.copy(WORKER, mjs)
    result = subprocess.run(["node", "--input-type=module", "-e", HARNESS, mjs.as_uri()],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


class TestWorker:
    def test_parses(self):
        result = subprocess.run(["node", "--check", str(WORKER)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    def test_first_save_then_replace(self, worker_run):
        assert worker_run["first"] == {"status": 200, "body": {"success": True, "replaced": False,
                                                                "locks_at": GAME["lock_utc"]}}
        assert worker_run["second"]["body"]["replaced"] is True

    def test_one_entry_per_email_latest_picks(self, worker_run):
        export = worker_run["export"]
        assert export["count"] == 1 and export["opt_in_count"] == 1
        entry = export["entries"][0]
        assert entry["email"] == "rider@example.com"
        assert entry["picks"]["women"] == ["C", "B", "A"]
        assert entry["first_submitted_at"] <= entry["submitted_at"]

    def test_rejections(self, worker_run):
        assert worker_run["honeypot"]["status"] == 400
        assert worker_run["noName"]["status"] == 400
        assert worker_run["dupe"]["status"] == 400
        assert worker_run["shortPicks"]["status"] == 400
        assert worker_run["badOrigin"] == 403
        assert worker_run["unknownGame"]["status"] == 400

    def test_lock_enforced(self, worker_run):
        assert worker_run["locked"]["status"] == 403
        assert worker_run["locked"]["body"]["locked"] is True

    def test_export_needs_token(self, worker_run):
        assert worker_run["exportNoAuth"] == 401
        source = WORKER.read_text()
        assert "env.EXPORT_TOKEN" in source

    def test_wrangler_binds_kv(self):
        toml = WRANGLER.read_text()
        assert 'binding = "PICKEM"' in toml
        assert "https://gravelgodcycling.com" in toml
