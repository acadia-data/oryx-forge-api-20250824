@echo off
REM OryxForge Test Suite Runner for Windows
REM This script provides convenient shortcuts for running tests on Windows

if "%1"=="" goto help
if "%1"=="help" goto help
if "%1"=="all" goto test_all
if "%1"=="unit" goto test_unit
if "%1"=="integration" goto test_integration
if "%1"=="slow" goto test_slow
if "%1"=="cov" goto test_cov
if "%1"=="cov-html" goto test_cov_html
if "%1"=="verbose" goto test_verbose
if "%1"=="io" goto test_io
if "%1"=="chat" goto test_chat
if "%1"=="project" goto test_project
if "%1"=="workflow" goto test_workflow
if "%1"=="repo" goto test_repo
if "%1"=="cli" goto test_cli
if "%1"=="iam" goto test_iam
if "%1"=="import" goto test_import
if "%1"=="mcp" goto test_mcp
if "%1"=="agent" goto test_agent
if "%1"=="config" goto test_config
if "%1"=="clean" goto clean_test
goto help

:help
echo OryxForge Test Suite Commands (Windows)
echo ========================================
echo.
echo Usage: run_tests.bat [command]
echo.
echo Main test commands:
echo   all                - Run all tests
echo   unit               - Run only unit tests
echo   integration        - Run only integration tests
echo   slow               - Run slow tests
echo.
echo Coverage commands:
echo   cov                - Run tests with coverage report
echo   cov-html           - Run tests and generate HTML coverage report
echo.
echo Service-specific tests:
echo   io                 - Run IO service tests
echo   chat               - Run chat service tests
echo   project            - Run project service tests
echo   workflow           - Run workflow service tests
echo   repo               - Run repo service tests
echo   cli                - Run CLI service tests
echo   iam                - Run IAM tests
echo   import             - Run import service tests
echo   mcp                - Run MCP tests
echo   agent              - Run Claude agent tests
echo   config             - Run config tests
echo.
echo Utility commands:
echo   verbose            - Run tests with verbose output
echo   clean              - Clean test artifacts and cache
echo.
goto end

:test_all
echo Running all tests...
pytest oryxforge/tests/
goto end

:test_unit
echo Running unit tests...
pytest oryxforge/tests/ -m unit
goto end

:test_integration
echo Running integration tests...
pytest oryxforge/tests/ -m integration
goto end

:test_slow
echo Running slow tests...
pytest oryxforge/tests/ -m slow
goto end

:test_cov
echo Running tests with coverage...
pytest oryxforge/tests/ --cov=oryxforge --cov-report=term-missing
goto end

:test_cov_html
echo Running tests with HTML coverage report...
pytest oryxforge/tests/ --cov=oryxforge --cov-report=html
echo Coverage report generated in htmlcov\index.html
goto end

:test_verbose
echo Running tests with verbose output...
pytest oryxforge/tests/ -vv -s
goto end

:test_io
echo Running IO service tests...
pytest oryxforge/tests/test_io_service.py -v
goto end

:test_chat
echo Running chat service tests...
pytest oryxforge/tests/test_chat_service.py -v
goto end

:test_project
echo Running project service tests...
pytest oryxforge/tests/test_project_service.py -v
goto end

:test_workflow
echo Running workflow service tests...
pytest oryxforge/tests/test_workflow_service.py -v
goto end

:test_repo
echo Running repo service tests...
pytest oryxforge/tests/test_repo_service.py -v
goto end

:test_cli
echo Running CLI service tests...
pytest oryxforge/tests/test_cli_service.py -v
goto end

:test_iam
echo Running IAM tests...
pytest oryxforge/tests/test_iam.py -v
goto end

:test_import
echo Running import service tests...
pytest oryxforge/tests/test_import_service.py -v
goto end

:test_mcp
echo Running MCP tests...
pytest oryxforge/tests/test_mcp.py -v
goto end

:test_agent
echo Running Claude agent tests...
pytest oryxforge/tests/test_claude_agent.py -v
goto end

:test_config
echo Running config tests...
pytest oryxforge/tests/test_config.py -v
goto end

:clean_test
echo Cleaning test artifacts...
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist oryxforge\tests\__pycache__ rmdir /s /q oryxforge\tests\__pycache__
if exist oryxforge\tests\.pytest_cache rmdir /s /q oryxforge\tests\.pytest_cache
if exist oryxforge\tests\htmlcov rmdir /s /q oryxforge\tests\htmlcov
if exist oryxforge\tests\.coverage del /q oryxforge\tests\.coverage
if exist htmlcov rmdir /s /q htmlcov
if exist .coverage del /q .coverage
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
del /s /q *.pyc 2>nul
echo Test artifacts cleaned.
goto end

:end
