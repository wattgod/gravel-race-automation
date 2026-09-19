import sys
import types
from types import SimpleNamespace

if "supabase" not in sys.modules or not hasattr(sys.modules["supabase"], "Client"):
    fake_supabase = types.ModuleType("supabase")
    fake_supabase.Client = object
    fake_supabase.create_client = lambda *_args, **_kwargs: None
    sys.modules["supabase"] = fake_supabase
if "dotenv" not in sys.modules:
    fake_dotenv = types.ModuleType("dotenv")
    fake_dotenv.load_dotenv = lambda *_args, **_kwargs: None
    sys.modules["dotenv"] = fake_dotenv

from mission_control.services import lead_nurture
from scripts import jev_client


def test_advisory_signal_does_not_change_deterministic_intent(monkeypatch):
    choice = SimpleNamespace(choice="conversation", confidence=0.91)
    response = SimpleNamespace(
        choices={"intent": choice},
        nouls={
            "health_constraint": SimpleNamespace(noul=0.02),
            "wants_human": SimpleNamespace(noul=0.8),
        },
    )
    monkeypatch.setattr(jev_client, "ask", lambda *_args, **_kwargs: response)
    result = lead_nurture.build_reply_suggestion(
        text="Training is going well, but I have a question.",
        seed="synthetic",
    )
    assert result["intent"] == "training_positive"
    assert result["needs_coach_answer"] is False
    assert result["jev"]["intent"] == "conversation"
    assert result["jev"]["agrees_with_rules"] is False
    assert result["jev"]["wants_human"] == 0.8


def test_no_key_returns_null_advisory_and_keeps_rules(monkeypatch):
    monkeypatch.setattr(jev_client, "get_client", lambda: None)
    result = lead_nurture.build_reply_suggestion(
        text="I was injured and need help.",
        seed="synthetic",
    )
    assert result["intent"] == "health_constraint"
    assert result["needs_coach_answer"] is False
    assert result["jev"] is None
