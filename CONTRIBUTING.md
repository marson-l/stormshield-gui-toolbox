# Contributing to Stormshield CLI GUI

First off, thank you for considering contributing to Stormshield CLI GUI! 

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the existing issues as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title** for the issue
* **Describe the exact steps which reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include screenshots and animated GIFs** if possible

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

* **Use a clear and descriptive title** for the issue
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior** and **explain which behavior you expected to see instead**
* **Explain why this enhancement would be useful**

### Pull Requests

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. Ensure the test suite passes
4. Make sure your code lints
5. Issue that pull request!

## Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/stormshield-cli-gui.git
   cd stormshield-cli-gui
   ```

2. **Set up development environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python src/main_gui.py
   ```

## Coding Guidelines

### Python Style Guide

* Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/)
* Use meaningful variable and function names
* Add docstrings to all functions and classes
* Keep functions small and focused
* Use type hints where appropriate

### Git Commit Messages

* Use the present tense ("Add feature" not "Added feature")
* Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
* Limit the first line to 72 characters or less
* Reference issues and pull requests liberally after the first line

Example:
```
Add connection retry mechanism

- Implement exponential backoff for failed connections
- Add maximum retry limit configuration
- Update UI to show retry attempts

Fixes #123
```

### PyQt6 Guidelines

* Follow Qt naming conventions for UI elements
* Use signals and slots properly
* Implement proper error handling for UI operations
* Test UI changes on different screen resolutions

## Project Structure

```
stormshield-cli-gui/
 src/                    # Source code
    main_gui.py        # Main GUI application
    main.py            # CLI application
 scripts/               # Build and deployment scripts
 docs/                  # Documentation
 assets/                # Images and resources
 tests/                 # Test files (future)
```

## Testing

Currently, the project relies on manual testing. We welcome contributions to add automated testing:

* Unit tests for core functionality
* Integration tests for Stormshield communication
* UI tests for PyQt6 components

## Documentation

* Update README.md if needed
* Add docstrings to new functions and classes
* Update inline comments for complex logic
* Add examples for new features

## Questions?

Don't hesitate to ask questions by creating an issue with the "question" label.

Thank you for contributing! 
