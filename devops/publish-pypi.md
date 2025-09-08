# PyPI Publication Workflow

This document outlines the complete workflow for publishing oryxforge to PyPI.

## Prerequisites

### 1. PyPI Accounts
- Create account at https://pypi.org
- Create account at https://test.pypi.org (for testing)
- Generate API tokens for both accounts

### 2. Install Build Tools
```bash
pip install build twine
```

### 3. Authentication Setup

Create `~/.pypirc`:
```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = <your-pypi-api-token>

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = <your-testpypi-api-token>
```

**Security Note**: Never commit API tokens to version control.

## Manual Publication Process

### Step 1: Pre-Publication Checks

```bash
# Ensure you're in the project root
cd /path/to/oryx-forge-api-20250824

# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Update version in pyproject.toml if needed
# Edit: version = "0.1.1" (or appropriate version)

# Verify package structure
find oryxforge -name "*.py" | head -10
```

### Step 2: Build the Package

```bash
# Build both wheel and source distribution
python -m build

# Verify build artifacts
ls -la dist/
# Should see:
# oryxforge-0.1.0-py3-none-any.whl
# oryxforge-0.1.0.tar.gz
```

### Step 3: Validate Package

```bash
# Check package metadata and structure
python -m twine check dist/*

# Inspect wheel contents
unzip -l dist/oryxforge-*.whl

# Test local installation
pip install dist/oryxforge-*.whl
oryxforge --help
oryxforge mcp list-tools
pip uninstall oryxforge
```

### Step 4: Test on Test PyPI

```bash
# Upload to Test PyPI
python -m twine upload --repository testpypi dist/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ oryxforge[mcp-server]

# Verify functionality
oryxforge --help
oryxforge mcp serve --help

# Clean up test installation
pip uninstall oryxforge
```

**Note**: The `--extra-index-url https://pypi.org/simple/` allows dependencies to be installed from regular PyPI.

### Step 5: Publish to Production PyPI

```bash
# Upload to production PyPI
python -m twine upload dist/*

# Verify publication
pip install oryxforge[mcp-server]
oryxforge mcp serve --help
```

## Automated GitHub Actions Workflow

Create `.github/workflows/publish-pypi.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Environment to deploy to'
        required: true
        default: 'testpypi'
        type: choice
        options:
        - testpypi
        - pypi

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install build twine
    
    - name: Build package
      run: python -m build
    
    - name: Check package
      run: python -m twine check dist/*
    
    - name: Publish to Test PyPI
      if: github.event.inputs.environment == 'testpypi' || github.event_name == 'workflow_dispatch'
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.TEST_PYPI_API_TOKEN }}
      run: python -m twine upload --repository testpypi dist/*
    
    - name: Publish to PyPI
      if: github.event.inputs.environment == 'pypi' || github.event_name == 'release'
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
      run: python -m twine upload dist/*
```

### GitHub Secrets Setup

In your GitHub repository settings, add these secrets:
- `PYPI_API_TOKEN` - Your PyPI API token
- `TEST_PYPI_API_TOKEN` - Your Test PyPI API token

## Version Management

### Semantic Versioning
Follow semantic versioning (semver):
- `MAJOR.MINOR.PATCH` (e.g., 1.2.3)
- **MAJOR**: Breaking changes
- **MINOR**: New features, backward compatible
- **PATCH**: Bug fixes, backward compatible

### Version Update Process

1. Update version in `pyproject.toml`:
```toml
[project]
version = "0.2.0"
```

2. Update version in `oryxforge/__init__.py`:
```python
__version__ = "0.2.0"
```

3. Create git tag:
```bash
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0
```

## Testing Installation Options

After publication, test all installation variants:

```bash
# Basic installation
pip install oryxforge

# CLI support
pip install oryxforge[cli]

# MCP server support
pip install oryxforge[mcp-server]

# Development installation
pip install oryxforge[dev]

# All features
pip install oryxforge[all]
```

## Rollback Process

If you need to remove a version:

1. **PyPI doesn't allow re-uploading same version**
2. **You can "yank" a release** (makes it unavailable for new installs):
   ```bash
   # Via web interface at pypi.org
   # Go to project > Manage > Options > Yank release
   ```

3. **For critical issues, release a patch version immediately**

## Troubleshooting

### Common Issues

**Package name already taken**:
```bash
# Error: The name 'oryxforge' is already taken
# Solution: Choose different name in pyproject.toml
```

**Import errors after installation**:
```bash
# Check package structure in wheel
unzip -l dist/*.whl
# Verify all __init__.py files are included
```

**Missing dependencies**:
```bash
# Verify dependencies in pyproject.toml
# Test with fresh virtual environment
python -m venv test_env
source test_env/bin/activate  # or test_env\Scripts\activate on Windows
pip install oryxforge[mcp-server]
```

**Authentication errors**:
```bash
# Verify API tokens are correct
# Check ~/.pypirc format
# Try manual token entry: python -m twine upload --repository testpypi dist/*
```

## Post-Publication Checklist

- [ ] Verify package installs correctly: `pip install oryxforge[mcp-server]`
- [ ] Test CLI works: `oryxforge --help`
- [ ] Test MCP server starts: `oryxforge mcp serve --help`
- [ ] Check package page on PyPI for correct metadata
- [ ] Update documentation with new version
- [ ] Create GitHub release with changelog
- [ ] Announce release (if applicable)

## Release Notes Template

For GitHub releases, use this template:

```markdown
## What's Changed
- Feature: Added MCP server support
- Feature: New CLI interface
- Enhancement: Improved task management
- Fix: Resolved path handling issues

## Installation
```bash
pip install oryxforge[mcp-server]
```

## Breaking Changes
- None in this release

**Full Changelog**: https://github.com/user/repo/compare/v0.1.0...v0.2.0
```

## Security Considerations

- Never commit API tokens
- Use GitHub secrets for automated workflows
- Regularly rotate API tokens
- Use trusted publishing when available (GitHub OIDC)
- Review package contents before upload with `python -m twine check dist/*`