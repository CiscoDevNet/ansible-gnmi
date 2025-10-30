# Contributing to Cisco IOS XE gNMI Ansible Collection

Thank you for your interest in contributing to this project! This document provides guidelines for contributing.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/yourusername/ansible-gnmi.git
   cd ansible-gnmi
   ```
3. **Set up development environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r tests/requirements.txt
   ```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive branch names:
- `feature/add-xyz` for new features
- `fix/issue-123` for bug fixes
- `docs/update-readme` for documentation updates

### 2. Make Your Changes

- Follow the existing code style
- Add tests for new functionality
- Update documentation as needed
- Follow Cisco IOS XE gNMI requirements (see CISCO_GNMI_CAVEATS.md)

### 3. Run Tests

```bash
# Run unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=plugins --cov-report=term-missing

# Run linters
make lint
```

### 4. Format Code

```bash
# Format with black
black plugins/ tests/

# Or use make
make format
```

### 5. Commit Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "Add feature: description of what you added"
```

Good commit message format:
```
[Type] Short description (50 chars or less)

Longer description if needed. Explain what and why,
not how. Wrap at 72 characters.

- Bullet points are okay
- Reference issues: Fixes #123
```

Types: `Feature`, `Fix`, `Docs`, `Test`, `Refactor`, `Style`, `Chore`

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear title and description
- Reference to related issues
- Test results
- Screenshots (if applicable)

## Code Style Guidelines

### Python Code

- Follow [PEP 8](https://pep8.org/) style guide
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Keep functions focused and small
- Maximum line length: 100 characters

Example:
```python
def example_function(param1: str, param2: int) -> bool:
    """
    Brief description of function.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param2 is negative
    """
    # Implementation
    pass
```

### Ansible Playbooks

- Use YAML best practices
- Indent with 2 spaces
- Use descriptive task names
- Include comments for complex logic
- Follow Ansible naming conventions

Example:
```yaml
- name: Descriptive task name
  cisco.iosxe_gnmi.cisco_iosxe_gnmi:
    host: "{{ inventory_hostname }}"
    username: "{{ gnmi_username }}"
    password: "{{ gnmi_password }}"
    operation: get
    paths:
      - /interfaces/interface
  register: result
```

## Testing Guidelines

### Unit Tests

- Write tests for all new functionality
- Use pytest framework
- Mock external dependencies
- Aim for >80% code coverage

Test structure:
```python
class TestFeatureName:
    """Test suite for FeatureName"""

    def test_specific_behavior(self):
        """Test that specific behavior works correctly"""
        # Arrange
        client = GnmiClient(host='test', username='admin', password='pass')

        # Act
        result = client.some_method()

        # Assert
        assert result.success is True
```

### Integration Tests

- Test against real or simulated Cisco IOS XE devices
- Include in `tests/integration/`
- Document required setup
- Make tests idempotent

## Documentation Guidelines

### Code Documentation

- Add docstrings to all public functions/classes
- Use Google-style docstrings
- Include examples in docstrings when helpful

### User Documentation

- Update README.md for user-facing changes
- Add examples to `examples/` directory
- Update CISCO_GNMI_CAVEATS.md for Cisco-specific info
- Keep documentation in sync with code

### Module Documentation

Update DOCUMENTATION, EXAMPLES, and RETURN sections in the module:

```python
DOCUMENTATION = r'''
module: cisco_iosxe_gnmi
short_description: Brief description
description:
  - Detailed description
  - More details
options:
  parameter_name:
    description: What this parameter does
    type: str
    required: true
'''
```

## Pull Request Process

1. **Ensure all tests pass** before submitting PR
2. **Update documentation** for any changed functionality
3. **Add entry to CHANGELOG** (if exists)
4. **Request review** from maintainers
5. **Address review comments** promptly
6. **Squash commits** if requested

### PR Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] Commit messages are clear
- [ ] No merge conflicts
- [ ] PR description is complete

## Reporting Issues

### Bug Reports

Include:
- Ansible version
- Python version
- Cisco IOS XE version
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs/error messages
- Minimal reproducing example

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternative solutions considered
- Impact on existing functionality

## Community Guidelines

- Be respectful and constructive
- Follow [Code of Conduct](CODE_OF_CONDUCT.md)
- Help others in discussions
- Credit others' contributions

## License

By contributing, you agree that your contributions will be licensed under the GNU General Public License v3.0.

## Questions?

- Open an issue for questions
- Check existing issues and PRs
- Review documentation

Thank you for contributing! 🎉
