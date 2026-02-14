.PHONY: generate test install setup validate check-gates check-tp check-all clean

INTAKE ?= tests/fixtures/sarah_printz.json
ATHLETE ?= athletes/sarah-printz-20260213

install:
	pip install -r requirements.txt
	playwright install chromium

setup: install

# Generate a full plan for an athlete
generate:
	python3 run_pipeline.py $(INTAKE) --skip-pdf --skip-deploy --skip-deliver

# Generate + validate (the correct workflow — use this, not just generate)
ship: generate validate check-tp
	@echo ""
	@echo "READY TO SHIP"

# Run all tests
test:
	python3 -m pytest tests/ -v

# Validate pipeline output independently of the pipeline
validate:
	python3 scripts/validate_pipeline_output.py $(ATHLETE)

# Check gate integrity (detects if gates were weakened)
check-gates:
	python3 scripts/gate_integrity_check.py

# Check trigger integrity (detects if conditional section logic was duplicated)
check-triggers:
	python3 scripts/trigger_integrity_check.py

# Check TrainingPeaks ZWO compatibility
check-tp:
	python3 scripts/zwo_tp_validator.py $(ATHLETE)/workouts

# Run ALL quality checks: tests + gate integrity + trigger integrity + output validation + TP check
check-all: test check-gates check-triggers validate check-tp
	@echo ""
	@echo "ALL QUALITY CHECKS PASSED"

# Compile check (syntax only)
lint:
	python3 -m py_compile run_pipeline.py
	python3 -m py_compile pipeline/step_01_validate.py
	python3 -m py_compile pipeline/step_02_profile.py
	python3 -m py_compile pipeline/step_03_classify.py
	python3 -m py_compile pipeline/step_04_schedule.py
	python3 -m py_compile pipeline/step_05_template.py
	python3 -m py_compile pipeline/step_06_workouts.py
	python3 -m py_compile pipeline/step_07_guide.py
	python3 -m py_compile pipeline/step_08_pdf.py
	python3 -m py_compile pipeline/step_09_deploy.py
	python3 -m py_compile pipeline/step_10_deliver.py
	python3 -m py_compile gates/quality_gates.py

clean:
	rm -rf athletes/
