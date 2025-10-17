.PHONY: test test-all test-unit test-integration test-slow test-cov test-cov-html test-service test-verbose clean-test help

# Default target
help:
	@echo "OryxForge Test Suite Commands"
	@echo "=============================="
	@echo ""
	@echo "Main test commands:"
	@echo "  make test              - Run all tests"
	@echo "  make test-unit         - Run only unit tests"
	@echo "  make test-integration  - Run only integration tests"
	@echo "  make test-slow         - Run slow tests"
	@echo ""
	@echo "Coverage commands:"
	@echo "  make test-cov          - Run tests with coverage report"
	@echo "  make test-cov-html     - Run tests and generate HTML coverage report"
	@echo ""
	@echo "Service-specific tests:"
	@echo "  make test-io           - Run IO service tests"
	@echo "  make test-chat         - Run chat service tests"
	@echo "  make test-project      - Run project service tests"
	@echo "  make test-workflow     - Run workflow service tests"
	@echo "  make test-repo         - Run repo service tests"
	@echo "  make test-cli          - Run CLI service tests"
	@echo "  make test-iam          - Run IAM tests"
	@echo "  make test-import       - Run import service tests"
	@echo "  make test-mcp          - Run MCP tests"
	@echo "  make test-agent        - Run Claude agent tests"
	@echo ""
	@echo "Utility commands:"
	@echo "  make test-verbose      - Run tests with verbose output"
	@echo "  make clean-test        - Clean test artifacts and cache"

# Run all tests
test:
	pytest oryxforge/tests/

# Alias for test
test-all: test

# Run only unit tests
test-unit:
	pytest oryxforge/tests/ -m unit

# Run only integration tests
test-integration:
	pytest oryxforge/tests/ -m integration

# Run slow tests
test-slow:
	pytest oryxforge/tests/ -m slow

# Run tests with coverage
test-cov:
	pytest oryxforge/tests/ --cov=oryxforge --cov-report=term-missing

# Run tests with HTML coverage report
test-cov-html:
	pytest oryxforge/tests/ --cov=oryxforge --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

# Run tests with verbose output
test-verbose:
	pytest oryxforge/tests/ -vv -s

# Service-specific test targets
test-io:
	pytest oryxforge/tests/test_io_service.py -v

test-chat:
	pytest oryxforge/tests/test_chat_service.py -v

test-project:
	pytest oryxforge/tests/test_project_service.py -v

test-workflow:
	pytest oryxforge/tests/test_workflow_service.py -v

test-repo:
	pytest oryxforge/tests/test_repo_service.py -v

test-cli:
	pytest oryxforge/tests/test_cli_service.py -v

test-iam:
	pytest oryxforge/tests/test_iam.py -v

test-import:
	pytest oryxforge/tests/test_import_service.py -v

test-mcp:
	pytest oryxforge/tests/test_mcp.py -v

test-agent:
	pytest oryxforge/tests/test_claude_agent.py -v

test-config:
	pytest oryxforge/tests/test_config.py -v

# Clean test artifacts
clean-test:
	rm -rf .pytest_cache
	rm -rf oryxforge/tests/__pycache__
	rm -rf oryxforge/tests/.pytest_cache
	rm -rf oryxforge/tests/htmlcov
	rm -f oryxforge/tests/.coverage
	rm -rf htmlcov
	rm -f .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
