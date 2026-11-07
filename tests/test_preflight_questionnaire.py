"""The questionnaire quality gate must never treat checker failures as downtime."""
import sys
from pathlib import Path
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import preflight_quality as quality
import check_questionnaire_parity as checker


@pytest.mark.parametrize('error', [ImportError('missing'), AttributeError('bad attrs'), ValueError('bad contract'), FileNotFoundError('missing source')])
def test_internal_validator_errors_are_failures_not_warnings(monkeypatch, error):
    failed = []
    warned = []
    def broken(): raise error
    monkeypatch.setattr(checker, 'check_parity', broken)
    monkeypatch.setattr(quality, 'warn', lambda *args: warned.append(args))
    monkeypatch.setattr(quality, 'check', lambda name, condition, msg: failed.append((name, condition, msg)))
    quality.check_questionnaire_parity()
    assert warned == []
    assert failed == [('Questionnaire parity validator', False, f'Validator failed: {type(error).__name__}')]


def test_existing_transport_unavailability_warning_policy_is_preserved(monkeypatch):
    warned = []
    checked = []
    def unavailable(): raise urllib.error.URLError('offline')
    monkeypatch.setattr(checker, 'check_parity', unavailable)
    monkeypatch.setattr(quality, 'warn', lambda *args: warned.append(args))
    monkeypatch.setattr(quality, 'check', lambda *args: checked.append(args))
    quality.check_questionnaire_parity()
    assert len(warned) == 1
    assert checked == []
