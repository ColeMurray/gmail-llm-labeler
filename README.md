# Gmail LLM Labeler

An intelligent Gmail email labeling system that uses Large Language Models (LLMs) to automatically categorize and label emails.

## Prerequisites

Before you begin, you'll need:

1. **Python 3.8+** installed
2. **Gmail account** with access to Gmail API
3. **LLM provider** - choose one:
   - OpenAI API key (requires paid account)
   - Ollama installed locally (free, runs on your machine)
4. **Google Cloud Project** with Gmail API enabled (see setup below)

## Installation

### For Development

```bash
# Clone the repository
git clone https://github.com/ColeMurray/gmail-llm-labeler.git
cd gmail-llm-labeler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e ".[dev]"
```

### For Production

```bash
# Install package
pip install .

# Or with optional Ollama support
pip install ".[ollama]"
```

## Gmail API Setup

To access your Gmail account, you need to create OAuth 2.0 credentials in Google Cloud Platform.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **Select a project** → **New Project**
3. Enter a project name (e.g., "Gmail LLM Labeler")
4. Click **Create**

### Step 2: Enable Gmail API

1. In your project, go to **APIs & Services** → **Library**
2. Search for "Gmail API"
3. Click on **Gmail API**
4. Click **Enable**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (unless you have a Google Workspace)
3. Click **Create**
4. Fill in the required fields:
   - **App name**: Gmail LLM Labeler
   - **User support email**: Your email
   - **Developer contact email**: Your email
5. Click **Save and Continue**
6. **Scopes**: Click **Add or Remove Scopes**
   - Search and add: `https://www.googleapis.com/auth/gmail.modify`
   - This allows reading and modifying labels
7. Click **Save and Continue**
8. **Test users**: Add your Gmail address
9. Click **Save and Continue**

### Step 4: Create OAuth Client ID

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Choose **Application type**: Desktop app
4. **Name**: Gmail LLM Labeler
5. Click **Create**
6. Click **Download JSON** - save this as `credentials.json` in your project root
7. Click **OK**

### Step 5: First Run Authentication

The first time you run the application, it will:

1. Open your browser for authentication
2. Ask you to sign in to Google
3. Show a warning "Google hasn't verified this app" - click **Continue** (safe, it's your app)
4. Grant permissions to modify Gmail
5. Generate a `token.json` file for future runs

**Note**: Both `credentials.json` and `token.json` are already in `.gitignore` and will never be committed.

## Configuration

Create a `.env` file in the project root with your LLM provider settings:

### Option A: Using OpenAI

```env
OPENAI_API_KEY=your_openai_api_key_here
```

### Option B: Using Ollama (Local)

```env
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gpt-oss:20b
```

> **Note**: The `credentials.json` file handles Gmail authentication. You don't need to set `GOOGLE_CLIENT_ID` or `GOOGLE_CLIENT_SECRET` in `.env`.

### Advanced Configuration

For detailed configuration options including file paths, YAML configuration, and platform-specific defaults, see [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Usage

### Command Line Interface

After installation, use the `gmail-pipeline` command:

```bash
# Show available commands
gmail-pipeline --help

# Run the complete pipeline
gmail-pipeline run

# Run with a custom config file
gmail-pipeline run --config examples/pipeline_config_local.yaml

# Run in dry-run mode (no changes)
gmail-pipeline run --dry-run

# Run in preview mode
gmail-pipeline run --preview

# Show metrics from last run
gmail-pipeline show-metrics

# Validate configuration file
gmail-pipeline validate-config examples/pipeline_config_local.yaml

# Generate a sample configuration
gmail-pipeline generate-config --output my_config.yaml
```

## Testing

Run the test suite:

```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_database.py

# Run with verbose output
pytest -v

# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration
```

## Project Structure

```
gmail-llm-labeler/
├── email_labeler/               # Main package
│   ├── __init__.py
│   ├── database.py              # Database operations
│   ├── email_processor.py       # Gmail API operations
│   ├── factory.py               # Factory functions
│   ├── gmail_utils.py           # Gmail utility functions
│   ├── labeler.py               # Main labeling logic
│   ├── llm_service.py           # LLM service interface
│   ├── metrics.py               # Metrics tracking
│   └── pipeline/                # ETL pipeline module
│       ├── __init__.py
│       ├── base.py              # Base classes
│       ├── cli.py               # Command-line interface
│       ├── config.py            # Configuration
│       ├── extract_stage.py     # Extract stage
│       ├── load_stage.py        # Load stage
│       ├── orchestrator.py      # Pipeline orchestrator
│       ├── sync_stage.py        # Sync stage
│       └── transform_stage.py   # Transform stage
├── tests/                       # Test suite
│   ├── conftest.py              # Shared fixtures
│   ├── test_cli.py
│   ├── test_database.py
│   ├── test_email_processor.py
│   ├── test_factory.py
│   ├── test_labeler.py
│   ├── test_llm_service.py
│   ├── test_pipeline_orchestrator.py
│   └── test_pipeline_stages.py
├── docs/                        # Documentation
│   └── CONFIGURATION.md         # Configuration guide
├── examples/                    # Example configurations
│   ├── example_config.yaml      # Example pipeline config
│   └── pipeline_config_local.yaml  # Local development config
├── pyproject.toml               # Project configuration
├── setup.py                     # Setup script
├── pytest.ini                   # Pytest configuration
└── README.md                    # This file
```

## Features

- **Gmail Integration**: Fetches emails directly from Gmail using the Gmail API
- **LLM Categorization**: Uses OpenAI GPT or Ollama for intelligent email categorization
- **Automatic Labeling**: Applies Gmail labels based on categories
- **ETL Pipeline**: Robust Extract-Transform-Load pipeline for batch processing
- **Database Tracking**: SQLite database for tracking processed emails
- **Metrics & Monitoring**: Built-in metrics tracking and reporting
- **Dry Run Mode**: Test categorization without applying labels
- **Comprehensive Testing**: Full test suite with pytest

## License

MIT
