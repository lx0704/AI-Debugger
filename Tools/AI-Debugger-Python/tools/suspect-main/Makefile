# Handy one-liners for MBFL workflows
# Customize defaults by overriding variables, e.g.:
#   make mbfl PROJ=rich_sample_project TESTS="pytest -q -k mbfl"

SUSPECT ?= suspect
PROJ    ?= rich_sample_project
TESTS   ?= pytest -q

# Experimental budgets
KF_BUDGET       ?= 30
KF_MAX_MUTANTS  ?= 15
PTA_BUDGET      ?= 20
PTA_SAMPLE      ?= 0.5

.PHONY: help mbfl mbfl-kf mbfl-pta mbfl-clean clean

help:
	@echo "Targets:"
	@echo "  make mbfl        - Baseline MBFL (single run, suite green)."
	@echo "  make mbfl-kf     - MBFL + kf-detection (fail→pass repairs)."
	@echo "  make mbfl-pta    - MBFL + kf-detection + per-test attribution."
	@echo "  make mbfl-clean  - Remove MBFL artifacts (matrices, diagnostics)."
	@echo "  make clean       - Run scripts/clean_suspect_artifacts.py (see flags below)."
	@echo ""
	@echo "Variables (override as needed):"
	@echo "  SUSPECT=$(SUSPECT)"
	@echo "  PROJ=$(PROJ)"
	@echo "  TESTS=$(TESTS)"
	@echo "  KF_BUDGET=$(KF_BUDGET)  KF_MAX_MUTANTS=$(KF_MAX_MUTANTS)"
	@echo "  PTA_BUDGET=$(PTA_BUDGET)  PTA_SAMPLE=$(PTA_SAMPLE)"
	@echo "  CLEAN_PROJ=.  CLEAN_WITH_VENV=0  CLEAN_DRY=0  CLEAN_YES=1"

# Baseline MBFL: prefer green suite; focuses on MUSE/mkp
mbfl:
	MBFL_KF_FAIL=0 MBFL_INTENTIONAL_FAIL=0 \
	$(SUSPECT) run --project $(PROJ) --tests "$(TESTS)" \
	  --enable mbfl --print-top 10

# MBFL + kf-detection: surfaces mkf via fail→pass repairs
mbfl-kf:
	MBFL_KF_FAIL=1 MBFL_INTENTIONAL_FAIL=0 \
	$(SUSPECT) run --project $(PROJ) --tests "$(TESTS)" \
	  --enable mbfl --mbfl-allow-failing \
	  --mbfl-kf-detection on --mbfl-kf-budget $(KF_BUDGET) --mbfl-kf-max-mutants $(KF_MAX_MUTANTS) \
	  --print-top 10

# MBFL + kf-detection + per-test attribution (PTA)
mbfl-pta:
	MBFL_KF_FAIL=1 MBFL_INTENTIONAL_FAIL=0 \
	SUSPECT_MBFL_PTA=on SUSPECT_MBFL_PTA_BUDGET=$(PTA_BUDGET) SUSPECT_MBFL_PTA_SAMPLE=$(PTA_SAMPLE) \
	$(SUSPECT) run --project $(PROJ) --tests "$(TESTS)" \
	  --enable mbfl --mbfl-allow-failing \
	  --mbfl-kf-detection on --mbfl-kf-budget $(KF_BUDGET) --mbfl-kf-max-mutants $(KF_MAX_MUTANTS) \
	  --print-top 10

mbfl-clean:
	rm -f matrix.csv matrix.json mbfl.json \
	  $(PROJ)/.suspect.mbfl.pytest.xml $(PROJ)/.suspect.kf.pytest.xml \
	  $(PROJ)/.coverage \
	  .suspect.mutatest.json

# General cleanup using the Python script (defaults: project '.', yes=1)
CLEAN_PROJ       ?= .
CLEAN_WITH_VENV  ?= 0
CLEAN_DRY        ?= 0
CLEAN_YES        ?= 1

clean:
	python scripts/clean_suspect_artifacts.py \
	  --project $(CLEAN_PROJ) \
	  $(if $(filter 1,$(CLEAN_WITH_VENV)),--with-venv,) \
	  $(if $(filter 1,$(CLEAN_DRY)),--dry-run,) \
	  $(if $(filter 1,$(CLEAN_YES)),--yes,)
