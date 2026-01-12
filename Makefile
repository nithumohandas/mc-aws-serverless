# ================================
# Project Configuration
# ================================
PROJECT_NAME=image-service
PYTHON=python3
VENV=.venv
PIP=$(VENV)/bin/pip
PYTHON_VENV=$(VENV)/bin/python

AWS_ENDPOINT_URL=http://localhost:4566

# ================================
# Default Target
# ================================
.DEFAULT_GOAL := help

# ================================
# Targets
# ================================

help:
	@echo ""
	@echo "Available commands:"
	@echo "  make venv            Create Python virtual environment"
	@echo "  make install         Install project dependencies"
	@echo "  make install-dev     Install dev dependencies"
	@echo "  make test            Run unit tests"
	@echo "  make lint            Run linting checks"
	@echo "  make localstack-up   Start LocalStack"
	@echo "  make localstack-down Stop LocalStack"
	@echo "  make clean           Remove virtual env and cache"
	@echo ""

# ================================
# Virtual Environment
# ================================

venv:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@echo "Virtual environment created at $(VENV)"

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt


# ================================
# Quality & Tests
# ================================

test:
	$(PYTHON_VENV) -m pytest -v

lint:
	$(PYTHON_VENV) -m flake8 .

# ================================
# LocalStack
# ================================

localstack-up:
	docker-compose up -d
	@echo "LocalStack started at $(AWS_ENDPOINT_URL)"

localstack-down:
	docker-compose down

# ================================
# Cleanup
# ================================

clean:
	rm -rf $(VENV)
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf *.egg-info
