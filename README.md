# White Circle GitHub Bot

A GitHub Actions bot that analyzes pull request code lines and messages using the GitHub API.

## Features

- Analyzes pull request file changes
- Counts lines added and deleted
- Retrieves and counts PR comments
- Uses the GitHub API with the `requests` library
- Provides detailed summary of PR analysis

## Usage

To use this action in your workflow, add the following to your `.github/workflows/` YAML file:

```yaml
name: PR Analysis
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - name: Analyze PR
        uses: AngrySigma/white-circle-github-bot@main
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          api-endpoint: 'https://api.github.com'  # Optional, defaults to GitHub API
```

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `github-token` | GitHub token for API authentication | Yes | - |
| `api-endpoint` | API endpoint to check code and messages | No | `https://api.github.com` |

## Outputs

| Output | Description |
|--------|-------------|
| `status` | Status of the bot execution (success, failed, skipped) |
| `message` | Result message from the bot |

## Development

### Files Structure

- `action.yml` - GitHub Actions metadata file
- `Dockerfile` - Container definition for the action
- `requirements.txt` - Python dependencies
- `main.py` - Main bot logic

### Local Testing

Build and run the Docker container locally:

```bash
docker build -t white-circle-bot .
docker run --rm \
  -e INPUT_GITHUB-TOKEN="your-token" \
  -e INPUT_API-ENDPOINT="https://api.github.com" \
  -e GITHUB_REPOSITORY="owner/repo" \
  -e GITHUB_EVENT_PATH="/path/to/event.json" \
  white-circle-bot
```

## License

See [LICENSE](LICENSE) file for details.