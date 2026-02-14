#!/usr/bin/env python3
"""
ENDURE Plan Engine — Single-command training plan pipeline.

Usage:
    python run_pipeline.py intake.json
    python run_pipeline.py intake.json --skip-deploy --skip-deliver

Each step writes artifacts to athletes/{athlete_id}/.
If any quality gate fails, the pipeline HALTS with a clear error.
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

from pipeline.step_01_validate import validate_intake
from pipeline.step_02_profile import create_profile
from pipeline.step_03_classify import classify_athlete
from pipeline.step_04_schedule import build_schedule
from pipeline.step_05_template import select_template
from pipeline.step_06_workouts import generate_workouts
from pipeline.step_07_guide import generate_guide
from pipeline.step_08_pdf import generate_pdf
from pipeline.step_09_deploy import deploy_guide
from pipeline.step_10_deliver import deliver

from gates.quality_gates import (
    gate_1_intake,
    gate_2_profile,
    gate_3_classification,
    gate_4_schedule,
    gate_5_template,
    gate_6_workouts,
    gate_7_guide,
    gate_8_pdf,
    gate_9_deploy,
    gate_10_deliver,
)


def run_pipeline(intake_path: str, skip_pdf: bool = False, skip_deploy: bool = False, skip_deliver: bool = False):
    """Run the full plan generation pipeline."""
    print("=" * 60)
    print("ENDURE PLAN ENGINE")
    print("=" * 60)

    base_dir = Path(__file__).parent

    # ── Load intake ──────────────────────────────────────────
    intake_file = Path(intake_path)
    if not intake_file.exists():
        print(f"FATAL: Intake file not found: {intake_file}")
        sys.exit(1)

    with open(intake_file) as f:
        intake = json.load(f)

    # Generate athlete ID and clean up previous runs
    athlete_id = _make_athlete_id(intake["name"])
    athlete_dir = base_dir / "athletes" / athlete_id
    _cleanup_old_runs(intake["name"], athlete_dir, base_dir)
    athlete_dir.mkdir(parents=True, exist_ok=True)

    # Save raw intake
    with open(athlete_dir / "intake.json", "w") as f:
        json.dump(intake, f, indent=2)

    print(f"\nAthlete: {intake['name']}")
    print(f"ID:      {athlete_id}")
    print(f"Output:  {athlete_dir}\n")

    # ── Step 1: Validate Intake ──────────────────────────────
    _step("1", "VALIDATE INTAKE")
    validated = validate_intake(intake)
    gate_1_intake(validated)
    _ok()

    # ── Step 2: Create Profile ───────────────────────────────
    _step("2", "CREATE PROFILE")
    profile = create_profile(validated)
    gate_2_profile(profile)
    _save_yaml(athlete_dir / "profile.yaml", profile)
    _ok()

    # ── Step 3: Classify ─────────────────────────────────────
    _step("3", "CLASSIFY")
    derived = classify_athlete(profile)
    gate_3_classification(derived, profile)
    _save_yaml(athlete_dir / "derived.yaml", derived)
    _ok()

    print(f"   Tier:  {derived['tier']}")
    print(f"   Level: {derived['level']}")
    print(f"   Weeks: {derived['plan_weeks']} (template: {derived['plan_duration']})")

    # ── Step 4: Build Schedule ───────────────────────────────
    _step("4", "BUILD SCHEDULE")
    schedule = build_schedule(profile, derived)
    gate_4_schedule(schedule, validated)
    _save_yaml(athlete_dir / "weekly_structure.yaml", schedule)
    _ok()

    # ── Step 5: Select Template ──────────────────────────────
    _step("5", "SELECT TEMPLATE")
    plan_config = select_template(derived, base_dir)
    gate_5_template(plan_config, derived)
    _save_yaml(athlete_dir / "plan_config.yaml", {
        "template_key": plan_config["template_key"],
        "plan_duration": plan_config["plan_duration"],
        "extended": plan_config["extended"],
    })
    _ok()

    # ── Step 6: Generate Workouts ────────────────────────────
    _step("6", "GENERATE WORKOUTS")
    workouts_dir = athlete_dir / "workouts"
    if workouts_dir.exists():
        import shutil
        shutil.rmtree(workouts_dir)
    workouts_dir.mkdir(parents=True)
    generate_workouts(plan_config, profile, derived, schedule, workouts_dir, base_dir)
    gate_6_workouts(workouts_dir, derived)
    _ok()

    zwo_count = len(list(workouts_dir.glob("*.zwo")))
    print(f"   ZWO files: {zwo_count}")

    # ── Step 7: Generate Guide ───────────────────────────────
    _step("7", "GENERATE GUIDE")
    guide_path = athlete_dir / "guide.html"
    generate_guide(profile, derived, plan_config, schedule, guide_path, base_dir)
    gate_7_guide(guide_path, validated, derived)
    _ok()

    # ── Step 8: Generate PDF ─────────────────────────────────
    pdf_path = athlete_dir / "guide.pdf"
    if skip_pdf:
        _step("8", "GENERATE PDF [SKIPPED]")
        _ok()
    else:
        _step("8", "GENERATE PDF")
        generate_pdf(guide_path, pdf_path)
        gate_8_pdf(pdf_path)
        _ok()

    # ── Step 9: Deploy Guide ─────────────────────────────────
    if skip_deploy:
        _step("9", "DEPLOY GUIDE [SKIPPED]")
        guide_url = f"file://{guide_path.resolve()}"
        _ok()
    else:
        _step("9", "DEPLOY GUIDE")
        guide_url = deploy_guide(athlete_id, guide_path, base_dir)
        gate_9_deploy(guide_url)
        _ok()

    # ── Step 10: Deliver ─────────────────────────────────────
    if skip_deliver:
        _step("10", "DELIVER [SKIPPED]")
        receipt = {
            "email_sent": False,
            "recipient": validated["email"],
            "guide_url": guide_url,
            "skipped": True,
            "timestamp": datetime.now().isoformat(),
        }
        _ok()
    else:
        _step("10", "DELIVER")
        receipt = deliver(validated, guide_url, pdf_path, workouts_dir)
        gate_10_deliver(receipt, validated)
        _ok()

    # Save receipt
    with open(athlete_dir / "receipt.json", "w") as f:
        json.dump(receipt, f, indent=2)

    # ── Copy deliverables to Downloads ────────────────────────
    _copy_to_downloads(intake, athlete_dir, pdf_path, workouts_dir, skip_pdf)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print(f"  Athlete: {intake['name']}")
    print(f"  Output:  {athlete_dir}")
    print(f"  Guide:   {guide_url}")
    print("=" * 60)


# ── Helpers ──────────────────────────────────────────────────

def _copy_to_downloads(intake: dict, athlete_dir: Path, pdf_path: Path, workouts_dir: Path, skip_pdf: bool):
    """Copy PDF + workouts to ~/Downloads/{Name} - {Race}/."""
    import shutil

    downloads = Path.home() / "Downloads"
    if not downloads.exists():
        return

    name = intake["name"]
    race_name = intake["races"][0]["name"] if intake.get("races") else "Plan"
    folder_name = f"{name} - {race_name}"
    dest = downloads / folder_name

    # Clean previous delivery for same athlete/race
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    # Copy PDF
    if not skip_pdf and pdf_path.exists():
        safe_name = name.replace(" ", "_")
        safe_race = race_name.replace(" ", "_")
        shutil.copy(pdf_path, dest / f"{safe_name}_{safe_race}_Training_Guide.pdf")

    # Copy workouts
    if workouts_dir.exists():
        shutil.copytree(workouts_dir, dest / "workouts")

    zwo_count = len(list((dest / "workouts").glob("*.zwo"))) if (dest / "workouts").exists() else 0
    print(f"\n  Copied to ~/Downloads/{folder_name}/")
    print(f"    PDF:      {'yes' if not skip_pdf and pdf_path.exists() else 'skipped'}")
    print(f"    Workouts: {zwo_count} ZWO files")


def _cleanup_old_runs(name: str, current_dir: Path, base_dir: Path):
    """Remove previous pipeline runs for the same athlete.

    Matches on the slug prefix (e.g. sarah-printz-*) so re-runs
    don't accumulate stale folders.
    """
    import re
    import shutil

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    athletes_dir = base_dir / "athletes"
    if not athletes_dir.exists():
        return

    for old_dir in athletes_dir.glob(f"{slug}-*"):
        if old_dir != current_dir and old_dir.is_dir():
            shutil.rmtree(old_dir)
            print(f"  Cleaned up previous run: {old_dir.name}")


def _make_athlete_id(name: str) -> str:
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    ts = datetime.now().strftime("%Y%m%d")
    return f"{slug}-{ts}"


def _step(num: str, label: str):
    print(f"[Step {num}] {label} ", end="", flush=True)


def _ok():
    print("... OK")


def _save_yaml(path: Path, data: dict):
    import yaml
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


# ── CLI ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ENDURE Plan Engine")
    parser.add_argument("intake", help="Path to intake JSON file")
    parser.add_argument("--skip-pdf", action="store_true", help="Skip PDF generation (requires Playwright)")
    parser.add_argument("--skip-deploy", action="store_true", help="Skip GitHub Pages deployment")
    parser.add_argument("--skip-deliver", action="store_true", help="Skip email delivery")
    args = parser.parse_args()

    run_pipeline(args.intake, skip_pdf=args.skip_pdf, skip_deploy=args.skip_deploy, skip_deliver=args.skip_deliver)


if __name__ == "__main__":
    main()
