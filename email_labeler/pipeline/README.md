# Email Auto-Labeler ETL Pipeline

A production-grade ETL pipeline for automatically categorizing and labeling Gmail emails using LLM.

## Architecture

The pipeline follows a 4-stage ETL pattern:

```
Extract → Transform → Load → Sync
```

- **Extract**: Fetch emails from Gmail API or database
- **Transform**: Categorize emails using LLM (OpenAI/Ollama)
- **Load**: Apply labels and actions to emails in Gmail
- **Sync**: Persist state to database and save metrics

## Quick Start

### 1. Install Dependencies

```bash
pip install -r email_labeler/requirements.txt
```

### 2. Configure Environment

Create a `.env` file:

```env
# LLM Configuration
LLM_SERVICE=OpenAI
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=gpt-4o-mini

# Database
DATABASE_PATH=email_pipeline.db

# Logging
LOG_LEVEL=INFO
```

### 3. Run the Pipeline

```bash
# Run with default configuration
python run_pipeline.py run

# Run in dry-run mode (no changes)
python run_pipeline.py run --dry-run

# Run in preview mode (show what would be done)
python run_pipeline.py run --preview

# Run with custom configuration
python run_pipeline.py run --config pipeline_config.yaml

# Limit number of emails
python run_pipeline.py run --limit 10
```

## Configuration

### Generate Configuration File

```bash
python run_pipeline.py generate-config --output my_config.yaml
```

### Configuration Structure

```yaml
pipeline:
  # General settings
  dry_run: false
  continue_on_error: true
  
  # Extract stage
  extract:
    source: "gmail"  # or "database"
    gmail_query: "is:unread"
    batch_size: 100
    
  # Transform stage
  transform:
    llm_service: "openai"  # or "ollama"
    model: "gpt-4o-mini"
    categories:
      - "Marketing"
      - "Bills"
      - "Personal"
      # ... more categories
    
  # Load stage
  load:
    apply_labels: true
    category_actions:
      "Marketing":
        - "apply_label"
        - "archive"
      "Bills":
        - "apply_label"
        - "star"
    
  # Sync stage
  sync:
    database_path: "email_pipeline.db"
    save_metrics: true
```

## CLI Commands

### Run Pipeline

```bash
# Full pipeline
python run_pipeline.py run [options]

Options:
  --config FILE      Configuration file
  --dry-run         No changes made
  --preview         Show what would be done
  --test            Use mock data
  --source TYPE     Override source (gmail/database)
  --query QUERY     Override Gmail query
  --limit N         Limit emails processed
  -v, -vv           Increase verbosity
```

### Run Individual Stage

```bash
# Run a specific stage
python run_pipeline.py run-stage STAGE [options]

Stages: extract, transform, load, sync

Options:
  --config FILE     Configuration file
  --input FILE      Input data (JSON)
  --output FILE     Save output (JSON)
  --dry-run        No changes made
```

### Validate Configuration

```bash
python run_pipeline.py validate-config CONFIG_FILE
```

### Show Metrics

```bash
python run_pipeline.py show-metrics [--file METRICS_FILE]
```

## Pipeline Modes

### Dry Run Mode
- No changes made to Gmail or database
- Logs what would be done
- Useful for testing configuration

### Preview Mode
- Shows detailed preview of actions
- Processes emails but doesn't modify them
- Good for reviewing categorization

### Test Mode
- Uses mock LLM responses
- Doesn't call external APIs
- For testing pipeline logic

## Extending the Pipeline

### Custom Stage Example

```python
from email_labeler.pipeline import PipelineStage, EmailRecord

class CustomValidationStage(PipelineStage):
    def execute(self, input_data, context):
        validated = []
        for email in input_data:
            if self.is_valid(email):
                validated.append(email)
        return validated
    
    def validate_input(self, input_data):
        return isinstance(input_data, list)
    
    def is_valid(self, email):
        return len(email.content) > 0

# Add to pipeline
pipeline = EmailPipeline(config)
pipeline.add_stage("validate", CustomValidationStage(), after="extract")
```

## Monitoring

### Metrics Export

The pipeline exports metrics in JSON or CSV format:

```json
{
  "run_id": "uuid",
  "start_time": "2024-01-01T00:00:00",
  "summary": {
    "total_processed": 100,
    "successful": 95,
    "failed": 5,
    "categories": {
      "Marketing": 30,
      "Bills": 10,
      ...
    }
  }
}
```

### Logging

Configure logging level via environment or config:

```bash
export LOG_LEVEL=DEBUG
```

Or in config:

```yaml
pipeline:
  monitoring:
    log_level: "DEBUG"
```

## Features

- **Modular Architecture**: Clean separation between stages
- **Configuration-Driven**: YAML-based configuration
- **Error Handling**: Graceful error recovery
- **Batch Processing**: Efficient batch operations
- **Metrics & Monitoring**: Detailed metrics and logging
- **Multiple Modes**: Dry-run, preview, and test modes
- **Extensible**: Easy to add custom stages
- **Production Ready**: Transaction support, retries, and error recovery

## Troubleshooting

### Gmail API Authentication

1. Ensure `credentials.json` exists in the project root
2. First run will open browser for OAuth authentication
3. Token saved to `token.json` for future runs

### Database Issues

```bash
# Reset database
rm email_pipeline.db
```

### LLM Service Issues

```bash
# Test OpenAI connection
export OPENAI_API_KEY=your-key
python -c "import openai; print('OK')"

# Test Ollama connection
curl http://localhost:11434/api/tags
```

## Architecture Benefits

1. **Separation of Concerns**: Each stage has single responsibility
2. **Testability**: Stages can be tested independently
3. **Flexibility**: Run individual stages or full pipeline
4. **Resilience**: Resume from any stage after failure
5. **Observability**: Clear metrics per stage
6. **Configuration-Driven**: No code changes for common modifications
7. **Scalability**: Ready for parallel processing

## Migration from Legacy Code

The pipeline maintains compatibility with the existing database and Gmail integration while providing:

- Better error handling
- More flexible configuration
- Cleaner separation of concerns
- Enhanced monitoring capabilities

To migrate:
1. Update configuration file with your settings
2. Test with dry-run mode
3. Run in preview mode to verify categorization
4. Deploy to production

## License

See project LICENSE file.