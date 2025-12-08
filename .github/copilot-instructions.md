# GitHub Copilot Instructions for Email Unsubscribe System

## Python Command

- Always use `python` (not `python3` or `py`) when running Python commands
- The project uses a virtual environment located at `../unsub_venv/`
- Assume the venv is activated when working in this project

## Project Context

- This is a TDD (Test-Driven Development) project
- All new features should follow Red-Green-Refactor cycle
- Test suite uses pytest
- Current test count: 274 tests (all passing)

## Development Practices

- Follow the existing code structure in `src/` directory
- Database operations use SQLAlchemy ORM
- CLI commands are in `main.py` with sys.argv parsing (not Click)
- Always run tests after making changes: `python -m pytest tests/ --tb=no -q`

## Code Style

- Type hints are used throughout the codebase
- Comprehensive error handling with specific exception types
- Structured logging with sensitive data sanitization
- Follow existing patterns for new modules
