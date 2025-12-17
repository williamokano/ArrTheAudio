# Contributing to ArrTheAudio

Thank you for considering contributing to ArrTheAudio! This document provides guidelines and instructions for contributing.

## Code of Conduct

Be respectful, inclusive, and constructive. We aim to maintain a welcoming community for everyone.

## How to Contribute

### Reporting Bugs

Before creating a bug report:
1. Check existing issues to avoid duplicates
2. Collect information about the bug (logs, config, environment)
3. Include steps to reproduce

Create an issue with:
- Clear, descriptive title
- Detailed description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Docker version, etc.)
- Relevant logs (sanitize sensitive data!)

### Suggesting Features

Feature requests are welcome! Please:
1. Check if the feature has already been suggested
2. Explain the use case and problem it solves
3. Describe the proposed solution
4. Consider alternative solutions

### Pull Requests

#### Before Starting

1. **Fork the repository** and create a branch from `main`
2. **Check existing PRs** to avoid duplicate work
3. **Open an issue first** for significant changes to discuss the approach

#### Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/arrtheaudio.git
cd arrtheaudio

# Create a branch
git checkout -b feature/your-feature-name

# Install dependencies (for local development)
pip install -r requirements.txt

# Or use Docker for testing
make build-test
make test
```

#### Development Workflow

1. **Write Tests First** (TDD)
   ```bash
   make test-unit        # Run unit tests
   make test-integration # Run integration tests
   make test             # Run all tests
   ```

2. **Follow Code Style**
   - Use ruff for linting and formatting
   - Follow existing code patterns
   - Add docstrings to public functions
   - Keep functions focused and small

3. **Commit Messages**
   Follow [Conventional Commits](https://www.conventionalcommits.org/):
   ```
   <type>(<scope>): <description>

   [optional body]

   [optional footer]
   ```

   Types:
   - `feat`: New feature
   - `fix`: Bug fix
   - `docs`: Documentation changes
   - `chore`: Maintenance tasks
   - `test`: Test changes
   - `refactor`: Code refactoring
   - `perf`: Performance improvements

   Examples:
   ```
   feat(selector): add support for multiple audio codec priorities
   fix(executor): handle mkvpropedit error when track doesn't exist
   docs(readme): update installation instructions
   ```

4. **Create Pull Request**
   - Push to your fork
   - Open PR against `main` branch
   - Fill out the PR template
   - Link related issues
   - Ensure CI passes

#### PR Requirements

- [ ] Tests pass (all 21+ tests)
- [ ] Code follows existing style (ruff passes)
- [ ] New features have tests
- [ ] Documentation updated (if applicable)
- [ ] Commit messages follow conventions
- [ ] No merge conflicts with main

#### PR Review Process

1. Maintainers will review your PR
2. Address feedback and comments
3. Once approved, maintainers will merge

## Development Guidelines

### Project Structure

```
arrtheaudio/
├── src/arrtheaudio/       # Application code
│   ├── api/               # FastAPI webhook endpoints
│   ├── core/              # Core processing logic
│   ├── metadata/          # Metadata resolution
│   ├── models/            # Data models
│   └── utils/             # Utilities
├── tests/                 # Test suite
│   ├── unit/              # Unit tests
│   └── integration/       # Integration tests
└── config/                # Configuration examples
```

### Adding New Features

#### Phase-Based Development

ArrTheAudio follows a phased development approach:
- **Phase 1**: MKV processing with priority lists ✅
- **Phase 2**: Daemon mode with webhooks ✅
- **Phase 3**: TMDB integration (planned)
- **Phase 4**: MP4 support (planned)
- **Phase 5**: Batch processing API (planned)
- **Phase 6**: Production hardening (planned)

New features should align with the project roadmap.

#### Adding a New Endpoint

1. Add Pydantic models in `api/models.py`
2. Add route in `api/routes.py`
3. Update `api/app.py` if needed
4. Write integration tests in `tests/integration/`
5. Update `WEBHOOK_SETUP.md` if user-facing

#### Adding Core Functionality

1. Create module in `src/arrtheaudio/core/`
2. Add data models in `src/arrtheaudio/models/`
3. Write unit tests in `tests/unit/`
4. Integrate into `core/pipeline.py`
5. Update configuration schema if needed

### Testing Guidelines

#### Unit Tests

- Test individual functions/methods
- Mock external dependencies
- Fast execution (<1s per test)
- Example: `tests/unit/test_selector.py`

#### Integration Tests

- Test complete workflows
- Use TestClient for API tests
- Mock external services (TMDB, etc.)
- Example: `tests/integration/test_webhook.py`

#### Test Structure

```python
def test_feature_description():
    """Clear docstring explaining what's being tested."""
    # Arrange - setup test data
    config = create_test_config()

    # Act - execute the feature
    result = function_under_test(config)

    # Assert - verify expected behavior
    assert result.status == "success"
```

### Code Style

```bash
# Format code
ruff format src/ tests/

# Lint code
ruff check src/ tests/

# Fix auto-fixable issues
ruff check --fix src/ tests/
```

### Documentation

- Update README.md for user-facing changes
- Update WEBHOOK_SETUP.md for setup/configuration changes
- Add docstrings to all public functions
- Include type hints
- Comment complex logic

## Release Process

Maintainers handle releases:

1. Update version in `src/arrtheaudio/__init__.py`
2. Update CHANGELOG.md
3. Create git tag: `git tag -a v1.2.3 -m "Release v1.2.3"`
4. Push tag: `git push origin v1.2.3`
5. GitHub Actions automatically:
   - Runs tests
   - Builds Docker images (multi-arch)
   - Pushes to Docker Hub
   - Creates GitHub release with changelog
   - Comments on related issues

## Getting Help

- 💬 **Discussions**: Use GitHub Discussions for questions
- 🐛 **Issues**: Use GitHub Issues for bugs/features
- 📖 **Documentation**: Check README.md and WEBHOOK_SETUP.md

## Recognition

Contributors will be:
- Listed in release notes
- Credited in git commits
- Acknowledged in the project README (for significant contributions)

Thank you for contributing to ArrTheAudio! 🎉
