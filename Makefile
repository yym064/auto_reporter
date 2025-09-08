PYTHON ?= python3
PIP ?= pip3
CONDA ?= conda
ENV_NAME ?= paper-analyzer

.PHONY: setup dev test lint build run

setup:
	$(PIP) install -r requirements.txt

dev:
	$(PYTHON) -m src.paper_analyzer.cli --help

test:
	pytest -q || true

lint:
	ruff check || true
	black --check . || true

build:
	echo "Nothing to build; Python project."

run:
	$(PYTHON) -m src.paper_analyzer.cli --input-dir ./sample_data

# --- Clean outputs ---
.PHONY: clean clean-artifacts clean-report

# Remove generated artifacts (figures, text, metadata, cache)
clean-artifacts:
	rm -rf artifacts
	@echo "Removed artifacts/"

# Remove generated reports
clean-report:
	rm -rf report
	@echo "Removed report/"

# Remove both artifacts and report
clean: clean-artifacts clean-report

# --- Conda helpers ---
.PHONY: conda-check conda-setup conda-dev conda-run activate

conda-check:
	@$(CONDA) --version

# Install deps into conda env (paper-analyzer)
conda-setup: conda-check
	$(CONDA) run -n $(ENV_NAME) python -m pip install -r requirements.txt

# Show CLI help inside conda env
conda-dev: conda-check
	$(CONDA) run -n $(ENV_NAME) python -m src.paper_analyzer.cli --help

# Run the app inside conda env
conda-run: conda-check
	$(CONDA) run -n $(ENV_NAME) python -m src.paper_analyzer.cli --input-dir ./sample_data

# Note: `conda activate` does not persist in Make; run this in your shell
activate:
	@echo "Run in your shell:"
	@echo "  conda activate $(ENV_NAME)"
