# Quality Assurance Policies

## Development Language Policy

All development activities within this project must be conducted in **English**:

- **Code**: All variable names, function names, class names, comments, and documentation
- **Commit messages**: All git commit messages must be in English
- **Pull request descriptions**: Titles and descriptions must be in English
- **Test names and descriptions**: All test cases and their descriptions must be in English
- **Documentation**: All README files, technical documentation, and API docs must be in English
- **Issue tracking**: Bug reports, feature requests, and discussion must be in English

## Code Quality Standards

### Testing Requirements

- Follow Test-Driven Development (TDD) practices
- Implement Behavior-Driven Development (BDD) using Gherkin scenarios
- All tests must pass before merging
- Maintain minimum 80% code coverage
- Write unit tests for all business logic
- **Unit Tests for Generated Code**: When generating or modifying code, create corresponding unit tests if necessary depending on:
  - Code complexity (functions with business logic)
  - Public API methods and classes
  - Critical functionality that could break
  - Code that handles edge cases or error conditions
  - Integration points between modules

### Code Style

- Follow language-specific style guides
- Use meaningful, descriptive names in English
- Keep functions small and focused
- Implement proper error handling
- No hardcoded values; use configuration where appropriate

#### Python Code Standards

- **PEP8 Compliance**: All Python code must comply with PEP8 style guidelines
- **Pylint**: Code must pass pylint checks with minimal warnings
- **Line Length**: Maximum 88 characters per line (Black formatter standard)
- **Import Organization**: Follow PEP8 import ordering (standard library, third-party, local)
- **No Emojis**: Code must not contain emojis in comments, strings, or documentation
- **Naming Conventions**:
  - Functions and variables: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private methods/attributes: prefix with underscore `_method_name`

### Architecture Constraints

- Maintain existing architecture patterns
- Follow established ADRs (Architecture Decision Records)
- Implement dependency injection for testability
- Ensure deterministic behavior (no direct datetime.now() usage)
- Maintain idempotency for batch operations

### Security

- Never commit secrets, keys, or sensitive information
- Follow security best practices
- Validate all inputs
- Use secure defaults

### Documentation

- Document all public APIs
- Maintain up-to-date README
- Document architectural decisions
- Include setup and running instructions

#### Documentation Organization

- **Root Level**: Only `README.md` and `QA.md` files are allowed in project root
- **doc/ Directory**: All other markdown documentation files must be placed in the `doc/` directory
- **File Naming**: Use descriptive, lowercase names with hyphens (e.g., `api-reference.md`, `deployment-guide.md`)

#### README Maintenance Policy

- **Update Requirement**: When making significant changes to the codebase, update `README.md` if necessary for better understanding
- **Content to Update**:
  - New features or functionality added
  - Changes to installation or setup procedures
  - Modified usage examples or API changes
  - New dependencies or requirements
  - Updated project structure or architecture
- **Guidelines**: Only update README when changes would genuinely help users understand or use the project better

#### Code Documentation Format

All code documentation must follow **Sphinx format** with this structure:

```python
"""Brief description of the function.

Detailed description if needed (optional).

:param param_name: Description of parameter
:type param_name: type
:param param_name2: Description of second parameter
:type param_name2: type
:return: Description of return value
:rtype: return_type
:raises ExceptionType: Description of when this exception is raised
"""
```

**Example:**

```python
def normalize_token(token):
    """Normalize a raw token.

    - Lowercases
    - Strips leading/trailing non-alphanumeric characters

    :param token: Raw token to normalize
    :type token: str
    :return: Normalized token (empty if no alphanumeric chars found)
    :rtype: str
    """
```

## Delivery Standards

Every implementation must include:

1. List of created/modified files
2. Brief implementation explanation
3. Instructions for running tests
4. Verification that all tests pass

### Code Verification Requirements

**Before completing any code request, ensure:**

1. **Functionality Verification**: Run and test the new code to confirm it works as expected
2. **Regression Testing**: Execute existing tests to ensure no previously working code was broken
3. **Integration Testing**: Verify that new code integrates properly with existing codebase
4. **Error Handling**: Test edge cases and error conditions
5. **Code Quality Checks**: Run linting tools (pylint, PEP8) to ensure code quality
6. **Documentation Verification**: Ensure all new code is properly documented with Sphinx format

### Verification Checklist

- [ ] New functionality works correctly
- [ ] All existing tests still pass
- [ ] New tests (if created) pass
- [ ] Code follows PEP8/pylint standards
- [ ] No breaking changes introduced
- [ ] Proper error handling implemented
- [ ] Documentation is complete and accurate

## Review Process

- All code must be reviewed before merging
- Tests must pass in CI/CD pipeline
- Code must follow established conventions
- No breaking changes without proper migration strategy