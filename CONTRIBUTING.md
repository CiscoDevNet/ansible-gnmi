# Contributing to the Cisco gNMI Ansible Collection

Thank you for your interest in contributing! This document provides guidelines for contributing to the `cisco.gnmi` collection.

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
- Review platform-specific notes in `CISCO_GNMI_CAVEATS.md`

### 3. Run Tests

```bash
# Run unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=plugins --cov-report=term-missing

# Run linters
make lint
```

### 4. Run Sanity Tests

```bash
# Build and install the collection
ansible-galaxy collection build --force
ansible-galaxy collection install cisco-gnmi-*.tar.gz --force

# Run ansible-test sanity (from collection install path)
cd ~/.ansible/collections/ansible_collections/cisco/gnmi
ansible-test sanity --docker default -v
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

## Code Style Guidelines

### Python Code

- Follow [PEP 8](https://pep8.org/) style guide
- **No f-strings** — use `.format()` or `%` formatting (required by `ansible-test sanity`)
- Include `from __future__ import absolute_import, division, print_function` and `__metaclass__ = type` boilerplate
- Add docstrings to all functions and classes
- Keep functions focused and small
- Maximum line length: 100 characters

### Ansible Playbooks

- Use YAML best practices
- Indent with 2 spaces
- Use descriptive task names
- Use FQCNs for all modules (e.g. `cisco.gnmi.gnmi`)
- Include comments for complex logic

Example:
```yaml
- name: Descriptive task name
  cisco.gnmi.gnmi:
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
- Mock external dependencies (gRPC, device connections)
- Aim for >80% code coverage

Test structure:
```python
class TestFeatureName:
    """Test suite for FeatureName."""

    def test_specific_behavior(self):
        """Test that specific behavior works correctly."""
        # Arrange
        client = GnmiClient(host='test', username='admin', password='pass')

        # Act
        result = client.some_method()

        # Assert
        assert result.success is True
```

### Platform Support

This collection is vendor-neutral by design. When adding features:
- Default behaviour should work on **any** gNMI-capable device
- Platform-specific restrictions belong in `PLATFORM_PROFILES` (in `gnmi_client.py`)
- Use the `platform` parameter to gate vendor-specific logic
- Test with at least one platform profile and the `auto` (default) profile

## Documentation Guidelines

### Module Documentation

Update DOCUMENTATION, EXAMPLES, and RETURN sections in the module. Ensure:
- Every option in `argument_spec` has a matching entry in DOCUMENTATION
- Types, defaults, and choices match exactly
- Use `type: path` for file path parameters containing `cert`, `key`, or `_path`

### User Documentation

- Update `README.md` for user-facing changes
- Add examples to `examples/` directory
- Update `CISCO_GNMI_CAVEATS.md` for platform-specific information
- Keep documentation in sync with code

## Pull Request Process

1. **Ensure all tests pass** before submitting PR
2. **Update documentation** for any changed functionality
3. **Add entry to CHANGELOG.md**
4. **Request review** from maintainers
5. **Address review comments** promptly

### PR Checklist

- [ ] Tests pass locally (`pytest tests/unit/ -v`)
- [ ] Sanity tests pass (`ansible-test sanity`)
- [ ] Code follows style guidelines (no f-strings, boilerplate present)
- [ ] Documentation updated (DOCUMENTATION block, README, examples)
- [ ] CHANGELOG.md updated
- [ ] Commit messages are clear
- [ ] No real device IPs, hostnames, or passwords in committed files

## Reporting Issues

### Bug Reports

Include:
- `ansible-core` version
- Python version
- Target device platform and software version
- Clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs/error messages

### Feature Requests

Include:
- Use case description
- Proposed solution
- Alternative solutions considered
- Impact on existing functionality

## Community Guidelines

- Be respectful and constructive
- Help others in discussions
- Credit others' contributions

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0 (see [LICENSE](LICENSE)).

## Questions?

- Open an issue for questions
- Check existing issues and PRs
- Review documentation

Thank you for contributing!
