# Configuration Guide

## Quick Start

The simplest way to use Gmail LLM Labeler is to just run it - files are automatically stored in the right place for your operating system:

```bash
gmail-pipeline run
```

**Default data locations:**
- Linux/Mac: `~/.local/share/gmail-llm-labeler/`
- Windows: `%LOCALAPPDATA%/gmail-llm-labeler/`

## Customizing File Locations

If you want to store files in a specific location, you have two options:

### Option 1: Environment Variables (Simple)

Create a `.env` file:

```bash
# Store everything in project directory
DATABASE_FILE=./email_pipeline.db
LLM_LOG_FILE=./llm_interactions.jsonl
ERROR_LOG_FILE=./categorization_errors.log
```

### Option 2: YAML Config File (Recommended)

Use a config file for all your settings:

```bash
# Run with config
gmail-pipeline run --config examples/pipeline_config_local.yaml
```

Example `config.yaml`:

```yaml
# File locations (optional - uses defaults if not specified)
paths:
  database_file: ./email_pipeline.db
  llm_log_file: ./llm_interactions.jsonl
  error_log_file: ./categorization_errors.log

# Pipeline settings
pipeline:
  extract:
    source: gmail
    gmail_query: "is:unread"
    max_results: 100

  transform:
    llm_service: ollama
    model: gpt-oss:20b
    categories:
      - "Marketing"
      - "Response Needed / High Priority"
      - "Bills"
      - "Personal"
      - "Other"

  load:
    apply_labels: true
    create_missing_labels: true
```

See [`examples/pipeline_config_local.yaml`](../examples/pipeline_config_local.yaml) for a complete example.

## Configuration Priority

When you set the same value in multiple places:

1. **Environment Variables** (highest priority)
2. **YAML Config File**
3. **Default Values** (lowest priority)

Example: If `DATABASE_FILE` is set in both `.env` and `config.yaml`, the `.env` value wins.

## Available Environment Variables

### File Paths
- `DATABASE_FILE` - SQLite database for email tracking
- `LLM_LOG_FILE` - Log of LLM API interactions
- `ERROR_LOG_FILE` - Error logs
- `TEST_OUTPUT_FILE` - Test results output
- `TEST_SUMMARY_FILE` - Test summary JSON

### API Configuration
- `OPENAI_API_KEY` - OpenAI API key (if using OpenAI)
- `OLLAMA_HOST` - Ollama server URL (default: `http://localhost:11434`)
- `OLLAMA_MODEL` - Ollama model name (e.g., `gpt-oss:20b`)
- `GOOGLE_CLIENT_ID` - Gmail API client ID
- `GOOGLE_CLIENT_SECRET` - Gmail API client secret

## Security Notes

- Never commit `.env`, `credentials.json`, or `token.json` to version control
- The `.gitignore` file already excludes these files
- Database and log files may contain your email content - keep them secure

## Checking Your Configuration

To see what paths are being used:

```bash
python -c "from email_labeler.config import _path_config; import json; print(json.dumps(_path_config.to_dict(), indent=2))"
```

Or validate your YAML config:

```bash
gmail-pipeline validate-config my_config.yaml
```
