# Email Labeler Test Suite

This directory contains a comprehensive pytest test suite for the email_labeler package. The tests cover all major components and use dependency injection for clean, isolated testing.

## Structure

```
tests/
├── conftest.py                    # Shared fixtures and test configuration
├── test_database.py              # EmailDatabase class tests
├── test_email_processor.py       # EmailProcessor class tests  
├── test_llm_service.py           # LLMService class tests
├── test_labeler.py               # EmailAutoLabeler class tests
├── test_pipeline_stages.py       # Pipeline stage tests
├── test_pipeline_orchestrator.py # Pipeline orchestrator tests
├── test_factory.py               # Factory function tests
├── test_cli.py                   # CLI argument parsing and execution tests
└── README.md                     # This file
```

## Running Tests

### Prerequisites

Install required packages:
```bash
pip install pytest pytest-cov pytest-mock
```

### Basic Usage

Run all tests:
```bash
pytest
# or
python run_tests.py
```

Run tests with coverage:
```bash
pytest --cov=email_labeler --cov-report=term-missing --cov-report=html
```

Run specific test files:
```bash
pytest tests/test_database.py
pytest tests/test_llm_service.py -v
```

Run tests matching a pattern:
```bash
pytest -k "test_categorize"
pytest -k "database"
```

### Using Test Runner Script

The project includes a convenient test runner script:

```bash
# Run all tests
python run_tests.py

# Run tests matching a pattern
python run_tests.py --pattern database

# Run tests with specific markers
python run_tests.py --marker unit

# Show help
python run_tests.py --help
```

### Test Markers

Tests are organized using pytest markers:

- `unit`: Fast unit tests with mocked dependencies
- `integration`: Integration tests with real components
- `slow`: Tests that take longer to run
- `external`: Tests requiring external services (Gmail API, LLM services)
- `database`: Tests requiring database operations
- `gmail`: Tests requiring Gmail API access
- `llm`: Tests requiring LLM services

Run specific marker groups:
```bash
pytest -m "unit"
pytest -m "not external"
pytest -m "database or gmail"
```

## Test Coverage

The test suite aims for comprehensive coverage of:

### Core Components
- **EmailDatabase**: Database operations, connection management, data persistence
- **EmailProcessor**: Gmail API operations, email retrieval, label management
- **LLMService**: Email categorization, both OpenAI and Ollama backends
- **EmailAutoLabeler**: Main orchestration logic, email processing workflows

### Pipeline Components
- **ExtractStage**: Email extraction from Gmail API
- **TransformStage**: Email categorization using LLM
- **LoadStage**: Saving results to database
- **SyncStage**: Label synchronization with Gmail
- **EmailPipeline**: Orchestration, error handling, metrics collection

### Factory and CLI
- **Factory Functions**: Dependency injection, component creation
- **CLI**: Argument parsing, execution modes, error handling

## Test Patterns and Best Practices

### Fixture Usage

Tests use pytest fixtures for common setup:

```python
def test_example(email_database, mock_gmail_client):
    # email_database and mock_gmail_client are injected fixtures
    pass
```

### Mocking External Dependencies

External services are mocked to ensure tests are fast and reliable:

```python
def test_llm_categorization(llm_service, mock_openai_client):
    # LLM client is mocked, responses are controlled
    mock_openai_client.chat.completions.create.return_value = mock_response
```

### Parametrized Tests

Tests use parametrization for testing multiple scenarios:

```python
@pytest.mark.parametrize("category,expected_label", [
    ("Work", "Work"),
    ("Personal", "Personal"),
    ("Newsletter", "Newsletter"),
])
def test_category_mapping(category, expected_label):
    # Test runs for each parameter combination
    pass
```

### Error Handling Tests

Tests verify proper error handling:

```python
def test_api_error_handling(email_processor, mock_gmail_client):
    mock_gmail_client.side_effect = HttpError(...)
    
    with pytest.raises(HttpError):
        email_processor.get_emails()
```

## Shared Fixtures

The `conftest.py` file provides shared fixtures:

- **Database fixtures**: `temp_database`, `mock_sqlite_connection`, `email_database`
- **API client fixtures**: `mock_gmail_client`, `mock_openai_client`
- **Data fixtures**: `sample_email_records`, `sample_enriched_email_records`
- **Configuration fixtures**: `pipeline_config`, `pipeline_context`
- **Component fixtures**: `llm_service`, `email_processor`, `email_auto_labeler`

## Test Data

Tests use realistic but controlled test data:

```python
sample_email = EmailRecord(
    id="msg123",
    subject="Weekly Team Meeting",
    sender="boss@company.com",
    content="Please join the weekly team meeting tomorrow at 2 PM.",
    received_date="2024-01-01T10:00:00Z"
)
```

## Configuration

Test configuration is in `pytest.ini`:

- Test discovery patterns
- Coverage settings
- Marker definitions
- Warning filters

## Continuous Integration

Tests are designed to run reliably in CI environments:

- No external dependencies required
- Deterministic test data
- Proper resource cleanup
- Fast execution with mocked services

## Debugging Tests

For debugging test failures:

```bash
# Run with detailed output
pytest -vv --tb=long

# Run and drop into debugger on failure
pytest --pdb

# Run specific test with maximum verbosity
pytest tests/test_database.py::TestEmailDatabase::test_init_with_connection -vv
```

## Test Development Guidelines

When adding new tests:

1. Use existing fixtures when possible
2. Mock external dependencies
3. Test both success and failure paths
4. Include edge cases
5. Use descriptive test names
6. Add appropriate markers
7. Ensure tests are independent and can run in any order

## Performance

The test suite is designed for speed:

- All external services are mocked
- Database operations use in-memory SQLite
- Minimal test data
- Efficient fixture reuse

Typical run time for full suite: ~30 seconds

## Maintenance

To maintain test quality:

- Run tests before committing changes
- Keep test coverage above 80%
- Update tests when modifying code
- Remove obsolete tests
- Regularly review and refactor test code