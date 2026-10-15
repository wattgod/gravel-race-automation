"""Receipts ledger loader and validator (schema ``gg-receipts-v2``).

docs/specs/receipts-social-proof-2026.md §6.2. The ledger holds real athletes
and lives only in a private checkout (``gravel-god-training-plans/db/
receipts.json`` plus its ``media/`` folder). Generators read it at build time
through ``GG_RECEIPTS_PATH``. This public repo holds the loader, the
validator and an obviously synthetic fixture (``tests/fixtures/
receipts_synthetic.json``) that CI renders instead.

Rules:
  - An entry renders only with a consent id, a render approval, an approval
    of every text it shows (quote, story), an unexpired consent, no
    withdrawal, and the requested channel in its ``channels``.
  - ``identity_tier == "count_only"`` entries are counted, never rendered.
  - Health data never enters a render path: a health-shaped key anywhere in
    an entry, or a weight / W/kg / heart-rate pattern in its text, fails the
    whole load (``ReceiptValidationError``), because it means private data
    reached the ledger's public fields.
  - Every result links to an official page (``official_url``, https).
  - Every exchange (a TrainingPeaks comment screenshot) has a verbatim
    transcript as ``alt``, its own render approval, its own channels and an
    image file inside the ledger's directory.
  - ``source_ref`` and ``consent_id`` are private. They are read for
    validation and dropped: a ``Receipt`` has no field that could carry them
    into HTML or a marketing export.
  - ``GG_BUILD=production`` refuses to fall back to the synthetic fixture.

Usage:
    from receipts_data import load_receipts, resolve_receipt_id
    receipts = load_receipts(channel="gravelgod")
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCHEMA = "gg-receipts-v2"
ENV_PATH = "GG_RECEIPTS_PATH"
ENV_BUILD = "GG_BUILD"
PRODUCTION = "production"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "receipts_synthetic.json"

IDENTITY_TIERS = ("full_name", "first_last_initial", "first_age_group", "count_only")
PRODUCTS = ("tp_plan", "custom_plan", "coaching", "consult")
ABILITIES = ("first_timer", "enthusiast", "competitive_amateur", "elite")
CHANNELS = ("gravelgod", "roadie", "social", "email", "tp")
STORY_VOICES = ("athlete", "editorial")
# Spec §3.4 standard disclosure copy. "none" needs no display line.
MATERIAL_CONNECTION_KINDS = ("none", "comped", "friend", "colleague",
                             "business_partner", "other")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp")

ABILITY_LABELS = {
    "first_timer": "First-timer",
    "enthusiast": "Enthusiast",
    "competitive_amateur": "Competitive amateur",
    "elite": "Elite",
}
PRODUCT_LABELS = {
    "tp_plan": "Training plan",
    "custom_plan": "Custom plan",
    "coaching": "1:1 coaching",
    "consult": "Consult",
}
AGE_BANDS = ("Under 30", "30s", "40s", "50+")
# Tags are exported to marketing tools, so they are an allow-list: free text
# here could carry family or health detail the athlete never approved.
TAGS = ("time_crunched_parent", "masters", "gravel_ultra", "road_racer", "multi_year",
        "mtb", "cyclocross", "bikepacking", "triathlete", "first_gravel_race")
EXCHANGE_KEYS = frozenset({
    "id", "image", "alt", "date", "theme", "rank", "render_approved_at", "channels",
    "redaction_checked_at", "withdrawn_at", "consent_expires",
})
# display_name shape per identity tier (count_only never renders).
_NAME_SHAPES = {
    "full_name": re.compile(r"^\S+(?: \S+)+$"),
    "first_last_initial": re.compile(r"^\S+ [A-Z]\.$"),
    "first_age_group": re.compile(r"^\S+$"),
}
# Production refuses ledgers that still hold fixture or template content.
_PLACEHOLDER_ID_RE = re.compile(r"^(?:synthetic|example)-")
_PLACEHOLDER_NAME_RE = re.compile(r"^(?:Test ?Rider|Example)", re.IGNORECASE)
_PLACEHOLDER_URL_RE = re.compile(r"^https?://(?:[^/]*\.)?example\.(?:com|org|net)(?:[/:?#]|$)",
                                 re.IGNORECASE)
TEMPLATE_PLACEHOLDER_TEXTS = (
    "Example quote text. Replace with the athlete's exact approved words.",
    "Example story paragraph one.",
    "Example coach comment.",
)

# Health data (spec principle 5): keys that must never appear in an entry.
# Matched by token ("avg_hr", "hr_max", "hrv_rmssd", "notes_medical"), plus a
# few substrings that are never innocent in a key.
_HEALTH_KEY_TOKEN_RE = re.compile(
    r"(?:^|_)(?:hr|hrv|rhr|rmssd|sdnn|pulse|bpm|bmi|kg|lthr|spo2|vo2\w*|blood\w*|"
    r"med(?!ia(?:_|$)|al(?:s)?(?:_|$))\w*|health\w*|injur\w*|diagnos\w*|illness\w*|"
    r"weight\w*|wkg|w_kg|body_?fat|body_?mass|mass|heart\w*|sleep\w*|symptom\w*)(?:_|$)",
    re.IGNORECASE,
)
_HEALTH_KEY_SUBSTR_RE = re.compile(r"weight|wkg|w/kg|heart|rmssd|medic|diagnos|injur",
                                   re.IGNORECASE)


def _is_health_key(key: str) -> bool:
    key = str(key).lstrip("/")
    return bool(_HEALTH_KEY_TOKEN_RE.search(key) or _HEALTH_KEY_SUBSTR_RE.search(key))


# Medical words that never belong in public proof copy.
_MEDICAL_WORDS = (
    r"meds?|medications?|medicines?|medical|prescri\w*|doctors?|cardiolog\w*|cardiac|"
    r"asthma\w*|a-?fib|atrial\s+fibrillation|arrhythmi\w*|beta[\s-]?blockers?|"
    r"diabet\w*|insulin|diagnos\w*|surger\w*|cancer|chemo\w*|pregnan\w*|"
    r"injur\w*|concussion\w*|fractur\w*|illness\w*|blood\s+pressure|cholesterol|"
    r"thyroid\w*|anemi\w*|anaemi\w*|eating\s+disorder\w*|depression"
)
# The same, in prose: a quote, story or transcript that mentions body weight,
# W/kg, heart data or medical context.
_HEALTH_TEXT_PATTERNS = (
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:kg|kgs|kilos?|kilograms?|lbs?|pounds)\b", re.I),
    re.compile(r"(?<![a-z])w\s*/\s*kg\b|\bwkg\b|\bwatts?\s*(?:/|per)\s*(?:kilo\w*|kg)\b",
               re.I),
    re.compile(r"\b\d+\s*bpm\b|\bhrv\b|\bheart[\s-]?rate\b|\bresting\s+hr\b|"
               r"\bpulse\b|\brmssd\b", re.I),
    # Upper-case HR only, so "a 3 hr ride" stays fine.
    re.compile(r"\bHRs?\b"),
    re.compile(r"\bbody[\s-]?fat\b|\bbmi\b|\bweigh(?:t|ed|s|ing)?\s*(?:in|loss|\d)", re.I),
    re.compile(rf"\b(?:{_MEDICAL_WORDS})\b", re.I),
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_AGE_GROUP_RE = re.compile(r"^(?:U(\d{2})|(\d{2})-(\d{2})|(\d{2})\+)$")


class ReceiptsConfigError(RuntimeError):
    """The ledger can't be located or used for this build."""


class ReceiptValidationError(ValueError):
    """The ledger holds data that must never reach a render path."""


@dataclass(frozen=True)
class Result:
    event: str
    date: str
    official_url: str
    placing: str = ""
    field: Optional[int] = None
    time: str = ""


@dataclass(frozen=True)
class MaterialConnection:
    kind: str
    display: str = ""


@dataclass(frozen=True)
class Story:
    text: str
    voice: str
    text_approved_at: str


@dataclass(frozen=True)
class Exchange:
    id: str
    receipt_id: str
    image_path: Path
    alt: str
    date: str
    theme: str
    rank: int
    width: int
    height: int
    render_approved_at: str
    channels: Tuple[str, ...]
    redaction_checked_at: str = ""

    @property
    def media_name(self) -> str:
        """Published filename: an opaque hash of receipt and exchange id."""
        return f"{opaque_key(self.receipt_id + '/' + self.id)}{self.image_path.suffix.lower()}"


@dataclass(frozen=True)
class Receipt:
    """One approved athlete, as a page may render it. No private fields."""
    id: str
    identity_tier: str
    display_name: str
    age_group: str
    age_band: str
    ability: str
    tags: Tuple[str, ...]
    hours_per_week: Optional[float]
    product: str
    coached_since: str
    results: Tuple[Result, ...]
    quote: str
    quote_approved_at: str
    render_approved_at: str
    material_connection: MaterialConnection
    channels: Tuple[str, ...]
    consent_expires: str
    story: Optional[Story]
    exchanges: Tuple[Exchange, ...]

    @property
    def public_name(self) -> str:
        """The name as the athlete's identity tier allows it to be shown."""
        if self.identity_tier == "first_age_group":
            return f"{self.display_name}, {self.age_group}"
        return self.display_name

    @property
    def anchor(self) -> str:
        """Page anchor for the story block: opaque, not the ledger id."""
        return f"athlete-{opaque_key(self.id)}"


@dataclass
class Ledger:
    path: Path
    synthetic: bool
    channel: str
    coached_count: Optional[int]
    coached_count_as_of: str
    coached_since: str
    receipts: List[Receipt] = field(default_factory=list)
    # (entry id, reason) for every entry or exchange left out of this build.
    rejected: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def exchanges(self) -> List[Exchange]:
        """Every renderable exchange, best first (rank ascending, then date)."""
        out = [ex for r in self.receipts for ex in r.exchanges]
        return sorted(out, key=lambda ex: (ex.rank, ex.date, ex.receipt_id, ex.id))


# ── Path resolution ──────────────────────────────────────────────────────


def opaque_key(value: str) -> str:
    """Stable, non-descriptive key for URLs and anchors."""
    return hashlib.sha256(f"gg-receipts-v2:{value}".encode("utf-8")).hexdigest()[:16]


def is_production() -> bool:
    return os.environ.get(ENV_BUILD, "").strip().lower() == PRODUCTION


def resolve_ledger_path(path: Optional[os.PathLike] = None) -> Path:
    """Explicit path > $GG_RECEIPTS_PATH > the synthetic fixture (never in
    production)."""
    if path is not None:
        resolved = Path(path)
    elif os.environ.get(ENV_PATH, "").strip():
        resolved = Path(os.environ[ENV_PATH].strip()).expanduser()
    elif is_production():
        raise ReceiptsConfigError(
            f"{ENV_BUILD}=production needs {ENV_PATH} pointing at the private "
            "ledger (gravel-god-training-plans/db/receipts.json); refusing to "
            "fall back to the synthetic fixture")
    else:
        resolved = FIXTURE_PATH
    if not resolved.is_file():
        raise ReceiptsConfigError(f"receipts ledger not found: {resolved}")
    return resolved


# ── Validation helpers ───────────────────────────────────────────────────


def _parse_date(value: Any) -> Optional[_dt.date]:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        return None
    try:
        return _dt.date.fromisoformat(value)
    except ValueError:
        return None


def _is_month(value: Any) -> bool:
    if not isinstance(value, str) or not _MONTH_RE.match(value):
        return False
    return 1 <= int(value[5:7]) <= 12


def age_band(age_group: str) -> Optional[str]:
    """Map an age group ("U25", "35-39", "60+") to a grid band, or None when
    it is malformed or straddles two bands."""
    m = _AGE_GROUP_RE.match(age_group or "")
    if not m:
        return None
    under, lo, hi, plus = m.groups()
    if under:
        return "Under 30" if int(under) <= 30 else None
    if plus:
        return "50+" if int(plus) >= 50 else None
    lo_i, hi_i = int(lo), int(hi)
    if hi_i < lo_i:
        return None

    def band(age: int) -> str:
        if age < 30:
            return "Under 30"
        if age < 40:
            return "30s"
        if age < 50:
            return "40s"
        return "50+"

    return band(lo_i) if band(lo_i) == band(hi_i) else None


def _health_keys(node: Any, trail: str = "") -> List[str]:
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{trail}.{key}" if trail else str(key)
            if _is_health_key(key):
                found.append(here)
            found += _health_keys(value, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            found += _health_keys(item, f"{trail}[{i}]")
    return found


def health_text_findings(text: str) -> List[str]:
    """Weight, W/kg or heart-data mentions in a piece of rendered text."""
    out = []
    for pattern in _HEALTH_TEXT_PATTERNS:
        m = pattern.search(text or "")
        if m:
            out.append(m.group(0))
    return out


def _public_texts(entry: dict) -> List[Tuple[str, str]]:
    """(label, text) for every field that can reach a page."""
    texts = [("display_name", entry.get("display_name")), ("quote", entry.get("quote"))]
    for i, tag in enumerate(entry.get("tags") or []):
        texts.append((f"tags[{i}]", tag))
    story = entry.get("story")
    if isinstance(story, dict):
        texts.append(("story.text", story.get("text")))
    mc = entry.get("material_connection")
    if isinstance(mc, dict):
        texts.append(("material_connection.display", mc.get("display")))
    for i, res in enumerate(entry.get("results") or []):
        if isinstance(res, dict):
            for k in ("event", "placing", "time"):
                texts.append((f"results[{i}].{k}", res.get(k)))
    for i, ex in enumerate(entry.get("exchanges") or []):
        if isinstance(ex, dict):
            texts.append((f"exchanges[{i}].alt", ex.get("alt")))
            texts.append((f"exchanges[{i}].theme", ex.get("theme")))
    return [(label, t) for label, t in texts if isinstance(t, str) and t]


def image_size(path: Path) -> Optional[Tuple[int, int]]:
    """(width, height) of a PNG, JPEG or WebP, read from its header."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seg_len = struct.unpack(">H", data[i + 2:i + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return (w, h)
            i += 2 + seg_len
        return None
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) >= 30:
        chunk = data[12:16]
        if chunk == b"VP8X":
            w = 1 + int.from_bytes(data[24:27], "little")
            h = 1 + int.from_bytes(data[27:30], "little")
            return (w, h)
        if chunk == b"VP8 ":
            w, h = struct.unpack("<HH", data[26:30])
            return (w & 0x3FFF, h & 0x3FFF)
        if chunk == b"VP8L":
            b = data[21:25]
            w = 1 + (((b[1] & 0x3F) << 8) | b[0])
            h = 1 + (((b[3] & 0x0F) << 10) | (b[2] << 2) | ((b[1] & 0xC0) >> 6))
            return (w, h)
    return None


def _str_list(value: Any) -> Optional[Tuple[str, ...]]:
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None
    return tuple(value)


# ── Entry validation ─────────────────────────────────────────────────────


def _check_exchange(ex: Any, entry_id: str, base_dir: Path, channel: str,
                    today: Optional[_dt.date] = None
                    ) -> Tuple[Optional[Exchange], Optional[str]]:
    """(Exchange, None) when renderable on `channel`, else (None, reason)."""
    if not isinstance(ex, dict):
        return None, "exchange is not an object"
    ex_id = ex.get("id")
    if not isinstance(ex_id, str) or not _ID_RE.match(ex_id):
        return None, f"exchange id {ex_id!r} is not a lowercase slug"
    label = f"exchange {ex_id}"
    unknown_keys = sorted(k for k in ex if not str(k).startswith("//") and k not in EXCHANGE_KEYS)
    if unknown_keys:
        return None, f"{label}: unknown key(s) {unknown_keys}"
    if ex.get("withdrawn_at"):
        return None, f"{label}: withdrawn"
    if ex.get("consent_expires") is not None:
        ex_expires = _parse_date(ex.get("consent_expires"))
        if ex_expires is None:
            return None, f"{label}: consent_expires must be YYYY-MM-DD"
        if ex_expires < (today or _dt.date.today()):
            return None, f"{label}: consent expired {ex['consent_expires']}"
    alt = ex.get("alt")
    if not isinstance(alt, str) or not alt.strip():
        return None, f"{label}: missing alt (the verbatim comment transcript)"
    if _parse_date(ex.get("render_approved_at")) is None:
        return None, f"{label}: missing render_approved_at"
    if _parse_date(ex.get("redaction_checked_at")) is None:
        # A regex can't read a screenshot: someone has to look at it for
        # metrics, other people and names the identity tier doesn't allow.
        return None, f"{label}: missing redaction_checked_at (screenshot not checked by eye)"
    channels = _str_list(ex.get("channels"))
    if channels is None:
        return None, f"{label}: channels must be a list"
    unknown = [c for c in channels if c not in CHANNELS]
    if unknown:
        return None, f"{label}: unknown channel(s) {unknown}"
    if channel not in channels:
        return None, f"{label}: not approved for channel {channel!r}"
    if _parse_date(ex.get("date")) is None:
        return None, f"{label}: date must be YYYY-MM-DD"
    rank = ex.get("rank")
    if not isinstance(rank, int) or isinstance(rank, bool):
        return None, f"{label}: rank must be an integer"
    image = ex.get("image")
    if not isinstance(image, str) or not image or Path(image).is_absolute():
        return None, f"{label}: image must be a path relative to the ledger"
    image_path = (base_dir / image).resolve()
    try:
        image_path.relative_to(base_dir.resolve())
    except ValueError:
        return None, f"{label}: image {image!r} is outside the ledger directory"
    if image_path.suffix.lower() not in IMAGE_SUFFIXES:
        return None, f"{label}: image must be one of {IMAGE_SUFFIXES}"
    if not image_path.is_file():
        return None, f"{label}: image file missing: {image}"
    size = image_size(image_path)
    if not size or size[0] <= 0 or size[1] <= 0:
        return None, f"{label}: can't read image dimensions: {image}"
    theme = ex.get("theme") or ""
    if not isinstance(theme, str):
        return None, f"{label}: theme must be a string"
    return Exchange(
        id=ex_id, receipt_id=entry_id, image_path=image_path, alt=alt.strip(),
        date=ex["date"], theme=theme, rank=rank, width=size[0], height=size[1],
        render_approved_at=ex["render_approved_at"], channels=channels,
        redaction_checked_at=ex["redaction_checked_at"],
    ), None


def check_entry(entry: dict, *, channel: str, today: _dt.date, base_dir: Path
                ) -> Tuple[Optional[Receipt], List[Tuple[str, str]]]:
    """Validate one ledger entry for one channel.

    Returns (Receipt or None, rejections). Raises ReceiptValidationError on
    health data, which must never be in the ledger's public fields at all.
    """
    entry_id = entry.get("id") if isinstance(entry.get("id"), str) else "?"
    health = _health_keys(entry)
    if health:
        raise ReceiptValidationError(
            f"receipt {entry_id}: health field(s) {health} — performance and "
            "results only (spec principle 5)")
    for label, text in _public_texts(entry):
        hits = health_text_findings(text)
        if hits:
            raise ReceiptValidationError(
                f"receipt {entry_id}: {label} mentions health data {hits} — "
                "never weight, W/kg or heart data in public (spec principle 5)")

    def reject(reason: str):
        return None, [(entry_id, reason)]

    if not _ID_RE.match(entry_id):
        return reject(f"id {entry_id!r} is not a lowercase slug")
    tier = entry.get("identity_tier")
    if tier not in IDENTITY_TIERS:
        return reject(f"identity_tier {tier!r} not in {IDENTITY_TIERS}")
    if not isinstance(entry.get("consent_id"), str) or not entry["consent_id"].strip():
        return reject("missing consent_id")
    if entry.get("withdrawn_at"):
        return reject("withdrawn")
    expires = _parse_date(entry.get("consent_expires"))
    if expires is None:
        return reject("consent_expires must be YYYY-MM-DD")
    if expires < today:
        return reject(f"consent expired {entry['consent_expires']}")
    channels = _str_list(entry.get("channels"))
    if channels is None:
        return reject("channels must be a list")
    unknown = [c for c in channels if c not in CHANNELS]
    if unknown:
        return reject(f"unknown channel(s) {unknown}")
    if channel not in channels:
        return reject(f"not approved for channel {channel!r}")
    if tier == "count_only":
        return reject("count_only: counted, never rendered")
    if _parse_date(entry.get("render_approved_at")) is None:
        return reject("missing render_approved_at")
    name = entry.get("display_name")
    if not isinstance(name, str) or not name.strip():
        return reject("missing display_name")
    if not _NAME_SHAPES[tier].match(name.strip()):
        return reject(f"display_name {name!r} doesn't fit identity_tier {tier!r} "
                      "(first_last_initial: 'First L.'; first_age_group: one word; "
                      "full_name: two or more words)")
    age_group = entry.get("age_group")
    band = age_band(age_group) if isinstance(age_group, str) else None
    if band is None:
        return reject(f"age_group {age_group!r} must be like U25, 35-39 or 60+, "
                      "inside one band (Under 30 / 30s / 40s / 50+)")
    ability = entry.get("ability")
    if ability not in ABILITIES:
        return reject(f"ability {ability!r} not in {ABILITIES}")
    tags = _str_list(entry.get("tags", []))
    if tags is None:
        return reject("tags must be a list of strings")
    bad_tags = [t for t in tags if t not in TAGS]
    if bad_tags:
        return reject(f"tag(s) {bad_tags} not in the allow-list {TAGS}")
    product = entry.get("product")
    if product not in PRODUCTS:
        return reject(f"product {product!r} not in {PRODUCTS}")
    if not _is_month(entry.get("coached_since")):
        return reject("coached_since must be YYYY-MM")
    hours = entry.get("hours_per_week")
    if hours is not None and (isinstance(hours, bool) or not isinstance(hours, (int, float))
                              or hours < 0):
        return reject("hours_per_week must be a non-negative number")

    quote = entry.get("quote") or ""
    if not isinstance(quote, str):
        return reject("quote must be a string")
    if quote.strip() and _parse_date(entry.get("quote_approved_at")) is None:
        return reject("quote present without quote_approved_at")

    story = None
    raw_story = entry.get("story")
    if raw_story:
        if not isinstance(raw_story, dict) or not isinstance(raw_story.get("text"), str) \
                or not raw_story["text"].strip():
            return reject("story must be {text, voice, text_approved_at}")
        if _parse_date(raw_story.get("text_approved_at")) is None:
            return reject("story present without story.text_approved_at")
        if raw_story.get("voice") not in STORY_VOICES:
            return reject(f"story.voice must be one of {STORY_VOICES}")
        story = Story(text=raw_story["text"].strip(), voice=raw_story["voice"],
                      text_approved_at=raw_story["text_approved_at"])

    mc_raw = entry.get("material_connection")
    if not isinstance(mc_raw, dict) or mc_raw.get("kind") not in MATERIAL_CONNECTION_KINDS:
        return reject(f"material_connection.kind must be one of {MATERIAL_CONNECTION_KINDS}")
    mc_display = mc_raw.get("display") or ""
    if mc_raw["kind"] != "none" and not (isinstance(mc_display, str) and mc_display.strip()):
        return reject("material_connection.display is required when kind isn't 'none'")
    mc = MaterialConnection(kind=mc_raw["kind"], display=str(mc_display).strip())

    results = []
    raw_results = entry.get("results") or []
    if not isinstance(raw_results, list):
        return reject("results must be a list")
    for i, res in enumerate(raw_results):
        if not isinstance(res, dict):
            return reject(f"results[{i}] is not an object")
        url = res.get("official_url")
        if not isinstance(url, str) or not url.startswith("https://"):
            return reject(f"results[{i}] has no official_url (https) — the link is the proof")
        if not isinstance(res.get("event"), str) or not res["event"].strip():
            return reject(f"results[{i}] has no event")
        if _parse_date(res.get("date")) is None:
            return reject(f"results[{i}].date must be YYYY-MM-DD")
        fld = res.get("field")
        if fld is not None and (isinstance(fld, bool) or not isinstance(fld, int) or fld < 1):
            return reject(f"results[{i}].field must be a positive integer")
        results.append(Result(event=res["event"].strip(), date=res["date"], official_url=url,
                              placing=str(res.get("placing") or ""), field=fld,
                              time=str(res.get("time") or "")))

    rejections: List[Tuple[str, str]] = []
    exchanges = []
    raw_exchanges = entry.get("exchanges") or []
    if not isinstance(raw_exchanges, list):
        return reject("exchanges must be a list")
    seen_ex = set()
    for ex in raw_exchanges:
        built, why = _check_exchange(ex, entry_id, base_dir, channel, today)
        if built is not None and built.id in seen_ex:
            built, why = None, f"exchange {built.id}: duplicate id"
        if built is None:
            rejections.append((entry_id, why))
        else:
            seen_ex.add(built.id)
            exchanges.append(built)

    return Receipt(
        id=entry_id, identity_tier=tier, display_name=name.strip(), age_group=age_group,
        age_band=band, ability=ability, tags=tags, hours_per_week=hours, product=product,
        coached_since=entry["coached_since"], results=tuple(results), quote=quote.strip(),
        quote_approved_at=entry.get("quote_approved_at") or "",
        render_approved_at=entry["render_approved_at"], material_connection=mc,
        channels=channels, consent_expires=entry["consent_expires"], story=story,
        exchanges=tuple(sorted(exchanges, key=lambda e: (e.rank, e.date, e.id))),
    ), rejections


# ── Loading ──────────────────────────────────────────────────────────────


def placeholder_findings(entries: Any) -> List[str]:
    """Fixture or template content left in a ledger (ids, names, URLs,
    template text). Production builds refuse any of it."""
    out = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        eid = str(entry.get("id") or "")
        if _PLACEHOLDER_ID_RE.match(eid):
            out.append(f"id {eid!r}")
        name = entry.get("display_name")
        if isinstance(name, str) and _PLACEHOLDER_NAME_RE.match(name.strip()):
            out.append(f"{eid}: display_name {name!r}")
        for res in entry.get("results") or []:
            url = res.get("official_url") if isinstance(res, dict) else None
            if isinstance(url, str) and _PLACEHOLDER_URL_RE.match(url):
                out.append(f"{eid}: official_url {url!r}")
        for label, text in _public_texts(entry):
            if any(t in text for t in TEMPLATE_PLACEHOLDER_TEXTS):
                out.append(f"{eid}: template text in {label}")
    return out


def parse_ledger(data: Any, *, path: Path, channel: str = "gravelgod",
                 today: Optional[_dt.date] = None) -> Ledger:
    """Validate an already-parsed ledger document."""
    if channel not in CHANNELS:
        raise ValueError(f"channel {channel!r} not in {CHANNELS}")
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ReceiptValidationError(f"{path}: schema must be {SCHEMA!r}")
    entries = data.get("receipts")
    if not isinstance(entries, list):
        raise ReceiptValidationError(f"{path}: 'receipts' must be a list")
    synthetic = bool(data.get("synthetic"))
    if is_production() and (synthetic or path.resolve() == FIXTURE_PATH.resolve()):
        raise ReceiptsConfigError(
            f"{ENV_BUILD}=production refuses the synthetic fixture ({path})")
    today = today or _dt.date.today()
    if is_production():
        leftovers = placeholder_findings(entries)
        if leftovers:
            raise ReceiptsConfigError(
                f"{ENV_BUILD}=production refuses fixture/template content in {path}: "
                + "; ".join(leftovers[:10]))

    count = data.get("coached_count")
    if count is not None and (isinstance(count, bool) or not isinstance(count, int)
                              or count < len(entries)):
        raise ReceiptValidationError(
            f"{path}: coached_count must be an integer >= the {len(entries)} ledger entries")
    as_of = data.get("coached_count_as_of") or ""
    if count is not None and _parse_date(as_of) is None:
        raise ReceiptValidationError(f"{path}: coached_count needs coached_count_as_of YYYY-MM-DD")
    since = data.get("coached_since") or ""
    if count is not None and not _is_month(since):
        raise ReceiptValidationError(f"{path}: coached_count needs coached_since YYYY-MM")

    ledger = Ledger(path=path, synthetic=synthetic, channel=channel, coached_count=count,
                    coached_count_as_of=as_of, coached_since=since)
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ReceiptValidationError(f"{path}: every receipt must be an object")
        eid = entry.get("id")
        if eid in seen:
            raise ReceiptValidationError(f"{path}: duplicate receipt id {eid!r}")
        seen.add(eid)
        receipt, rejections = check_entry(entry, channel=channel, today=today,
                                          base_dir=path.parent)
        ledger.rejected += rejections
        if receipt is not None:
            ledger.receipts.append(receipt)
    return ledger


def load_ledger(channel: str = "gravelgod", *, path: Optional[os.PathLike] = None,
                today: Optional[_dt.date] = None, verbose: bool = False) -> Ledger:
    resolved = resolve_ledger_path(path)
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ReceiptValidationError(f"{resolved}: not valid JSON ({e})") from e
    ledger = parse_ledger(data, path=resolved, channel=channel, today=today)
    if verbose:
        for eid, why in ledger.rejected:
            print(f"  receipts: left out {eid}: {why}", file=sys.stderr)
    return ledger


def load_receipts(channel: str = "gravelgod", *, path: Optional[os.PathLike] = None,
                  today: Optional[_dt.date] = None) -> List[Receipt]:
    """Every receipt approved for `channel`, in ledger order."""
    return load_ledger(channel, path=path, today=today).receipts


def known_receipt_ids(channel: Optional[str] = None, *,
                      path: Optional[os.PathLike] = None) -> frozenset:
    """Ids a page may emit as data-receipt-id. channel=None: any channel."""
    channels = (channel,) if channel else CHANNELS
    ids = set()
    for ch in channels:
        ids.update(r.id for r in load_receipts(ch, path=path))
    return frozenset(ids)


def resolve_receipt_id(receipt_id: str, *, channel: Optional[str] = None,
                       path: Optional[os.PathLike] = None) -> bool:
    """True when `receipt_id` is an approved, renderable ledger entry."""
    return receipt_id in known_receipt_ids(channel, path=path)


def export_receipts(channel: str, *, path: Optional[os.PathLike] = None) -> List[Dict]:
    """JSON-safe records for marketing tools (social cards, email). Only
    receipts approved for that channel; no private fields; image paths are
    the published media filenames."""
    out = []
    for r in load_receipts(channel, path=path):
        out.append({
            "id": r.id,
            "name": r.public_name,
            "age_group": r.age_group,
            "ability": r.ability,
            "tags": list(r.tags),
            "product": r.product,
            "coached_since": r.coached_since,
            "results": [{"event": x.event, "date": x.date, "placing": x.placing,
                         "field": x.field, "time": x.time, "official_url": x.official_url}
                        for x in r.results],
            "quote": r.quote,
            "story": ({"text": r.story.text, "voice": r.story.voice} if r.story else None),
            "disclosure": r.material_connection.display,
            "exchanges": [{"id": e.id, "media": e.media_name, "alt": e.alt, "date": e.date,
                           "theme": e.theme, "width": e.width, "height": e.height}
                          for e in r.exchanges],
        })
    return out
