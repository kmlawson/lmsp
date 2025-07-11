# Deployment Instructions for PyPI Test Server

Based on the official Python Packaging Tutorial: https://packaging.python.org/en/latest/tutorials/packaging-projects/

## Prerequisites

1. Create an account on [TestPyPI](https://test.pypi.org/account/register/)
2. Generate an API token from your TestPyPI account settings
3. Install required build tools in a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   python3 -m pip install --upgrade build twine
   ```

## Build the Package

1. Clean previous builds:
   ```bash
   rm -rf build/ dist/ *.egg-info/
   ```

2. Build the distribution packages:
   ```bash
   python3 -m build
   ```

   This will create:
   - `dist/lmsp-0.1.0.tar.gz` (source distribution)
   - `dist/lmsp-0.1.0-py3-none-any.whl` (wheel distribution)

## Upload to TestPyPI

1. First, verify your package:
   ```bash
   twine check dist/*
   ```

2. Upload to TestPyPI:
   ```bash
   python3 -m twine upload --repository testpypi dist/*
   ```

   You'll be prompted for:
   - Username: `__token__`
   - Password: Your TestPyPI API token

## Test Installation from TestPyPI

1. Create a new virtual environment for testing:
   ```bash
   python3 -m venv test-env
   source test-env/bin/activate
   ```

2. Install from TestPyPI:
   ```bash
   python3 -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lmsp
   ```

   Note: The `--extra-index-url` ensures dependencies are fetched from the main PyPI.

3. Test the installed package:
   ```bash
   lmsp --help
   ```

## Configuration File (Optional)

Create a `.pypirc` file in your home directory for easier uploads:

```ini
[distutils]
index-servers =
    testpypi
    pypi

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = <your-test-pypi-token>

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = <your-pypi-token>
```

With this configuration, you can upload using:
```bash
python3 -m twine upload --repository testpypi dist/*
```

## Checklist Before Upload

- [ ] Version number is correct in `pyproject.toml`
- [ ] Author information is accurate
- [ ] Project URLs are correct
- [ ] README.md is up to date
- [ ] All tests pass
- [ ] Package builds without errors
- [ ] No sensitive files in the distribution

## Production PyPI

Once you've successfully tested on TestPyPI, you can upload to the production PyPI:
```bash
python3 -m twine upload dist/*
```

## Additional Resources

- [Python Packaging Tutorial](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [TestPyPI](https://test.pypi.org/)
- [PyPI](https://pypi.org/)
- [Packaging User Guide](https://packaging.python.org/)