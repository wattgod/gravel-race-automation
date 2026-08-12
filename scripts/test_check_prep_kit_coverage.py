from unittest.mock import patch

from scripts.check_prep_kit_coverage import USER_AGENT, check_coverage, check_url


def test_only_profiles_with_gate_are_checked_and_404_fails():
    index = [("gravelgod", "https://example.test", [
        {"slug": "has-gate", "has_profile": True},
        {"slug": "no-profile", "has_profile": False},
    ])]
    with patch("scripts.check_prep_kit_coverage.LEGACY_GATED_PATHS", ()), patch(
            "scripts.check_prep_kit_coverage.check_url", return_value=(404, "missing")) as call:
        rows, failed = check_coverage(index)
    assert failed is True
    assert [row["slug"] for row in rows] == ["has-gate"]
    assert call.call_args.args[0].endswith("/race/has-gate/prep-kit/")


def test_request_uses_mission_control_user_agent():
    response = type("Response", (), {"status": 200, "__enter__": lambda self: self, "__exit__": lambda *args: None})()
    with patch("scripts.check_prep_kit_coverage.urllib.request.urlopen", return_value=response) as opened:
        assert check_url("https://example.test/race/x/prep-kit/") == (200, "")
    request = opened.call_args.args[0]
    assert request.get_header("User-agent") == USER_AGENT
