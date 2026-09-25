

def test_every_description_fits_ga4s_150_char_limit():
    # The Admin API answers 400 above 150 characters; it bit entry_surface
    # and goal_type on real runs (Sep 24/25).
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from ga4_register_goals_dimensions import GOALS_FUNNEL_DIMENSIONS
    for dim in GOALS_FUNNEL_DIMENSIONS:
        assert len(dim["description"]) <= 150, dim["parameterName"]


def test_every_display_name_uses_only_characters_ga4_accepts():
    # Admin API: display_name must be alphanumeric, underscore or space
    # ("Race-page goal type" was rejected on a real run, Sep 25).
    import re
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from ga4_register_goals_dimensions import GOALS_FUNNEL_DIMENSIONS
    for dim in GOALS_FUNNEL_DIMENSIONS:
        assert re.fullmatch(r"[A-Za-z0-9_ ]+", dim["displayName"]), dim["displayName"]
