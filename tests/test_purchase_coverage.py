"""Run the browser quote's date arithmetic and verify the rendered offer."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
from datetime import date

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'web/training-plans-form.js').read_text()
VECTORS = [
    ('2026-10-15', '2026-12-13', 8, 4, '2026-10-19'),
    ('2026-10-19', '2026-12-13', 8, 0, '2026-10-19'),
    ('2026-10-15', '2026-10-18', 0, 4, None),
    ('2026-10-15', '2026-10-15', 0, 1, None),
    ('2026-10-15', '2026-10-14', 0, 0, None),
    ('2026-12-31', '2027-02-07', 5, 4, '2027-01-04'),
    ('2026-10-30', '2026-11-08', 1, 3, '2026-11-02'),
    ('2026-10-15', '2026-11-12', 4, 4, '2026-10-19'),
    ('2026-10-15', '2027-10-17', 52, 4, '2026-10-19'),
]


def function(name):
    start = SOURCE.index('  function ' + name + '(')
    end = SOURCE.index('\n  function ', start + 3)
    return SOURCE[start:end]


@pytest.mark.parametrize('zone', ['UTC', 'America/Denver', 'Europe/Oslo'])
@pytest.mark.parametrize('today,race,weeks,early,start', VECTORS)
def test_quote_calendar_and_unchanged_charge_units(zone, today, race, weeks, early, start):
    # The clock is controlled; native Date still handles the timezone/DST.
    code = '''const NativeDate=Date;
class Clock extends NativeDate { constructor(...args) { super(...(args.length ? args : [TODAY+'T12:00:00'])); } }
global.Date=Clock;
var PRICE_PER_WEEK=15, PRICE_CAP=249, MIN_WEEKS=4;
''' .replace('TODAY', json.dumps(today))
    code += '\n'.join(function(name) for name in ['computePrice', 'computeCoverage', 'coverageDescription'])
    code += '\nconst race=' + json.dumps(race) + ';const c=computeCoverage(race);console.log(JSON.stringify({coverage:c,price:computePrice(race),copy:coverageDescription(c)}));'
    result = subprocess.run(['node', '-e', code], env={**os.environ, 'TZ': zone}, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output['coverage'] == {'quoted_on': today, 'race_date': race, 'available_training_weeks': weeks,
                                   'lead_in_days': early, 'earliest_week_start': start}
    units = max(4, math.ceil((date.fromisoformat(race) - date.fromisoformat(today)).days / 7))
    assert output['price'] == {'weeks': units, 'price': min(249, units * 15)}
    assert 'Final training dates are confirmed during review.' in output['copy']


def test_quote_is_visible_before_payment_even_on_existing_live_markup():
    assert "totalEl = document.createElement('p')" in SOURCE
    assert "submitBtn.parentNode.insertBefore(totalEl, submitBtn)" in SOURCE
    assert "rounded-up weeks until your race" in SOURCE
    assert "Pricing weeks can differ from scheduled training weeks." in SOURCE
    assert "' for ' + pricing.weeks + ' weeks'" not in SOURCE


def test_landing_discloses_rounding_and_training_dates_without_full_week_promise():
    sys.path.insert(0, str(ROOT / 'wordpress'))
    import generate_training_plans as page
    pricing = page.build_pricing()
    faq = str(page.FAQ_ITEMS)
    for text in (pricing, faq):
        assert 'rounded up to whole weeks' in text
        assert 'Four-week minimum' in text
        assert 'Training weeks start on Mondays' in text
        assert 'per week of training' not in text
        assert 'pay for exactly what you need' not in text.lower()
