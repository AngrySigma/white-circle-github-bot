# White Circle Safety Guard

A GitHub Action that enforces safety policies by analyzing Pull Request changes and commit messages. It checks your code against the **White Circle API** to detect policy violations before they are merged.

If a violation is detected, the bot will:
1. **Block the build** (fail the workflow).
2. **Post a comment** on the Pull Request detailing the specific policies violated.

## Features

- **Automated Safety Analysis**: Scans PR diffs, full file contents (contextually), and commit messages.
- **Smart Batching**: Automatically handles token limits (using `tiktoken`) by batching large PRs into multiple API requests.
- **Policy Enforcement**: Blocks PRs that trigger safety flags defined in your White Circle deployment.
- **Feedback**: Posts immediate feedback directly to the PR timeline.

## Usage

To use this action in your workflow, add the following to a YAML file in `.github/workflows/` (e.g., `.github/workflows/safety.yml`).

### Standard Configuration

```yaml
name: Safety Check

on: [pull_request]

jobs:
  white-circle-scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write # Required to post comments on the PR
    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Run White Circle Bot
        uses: AngrySigma/white-circle-github-bot@master
        with:
          whitecircle_api_key: ${{ secrets.WHITECIRCLE_API_KEY }}
          deployment_id: ${{ secrets.WHITECIRCLE_DEPLOYMENT_ID }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          # debug: 'true' # Optional: Enable for verbose logs
```

## Setup & Configuration

### 1. Get Credentials
You need a valid **API Key** and **Deployment ID** from the White Circle platform.

### 2. Configure Repository Secrets
To keep your API keys secure, **never** hardcode them in your workflow files. You must add them as GitHub Secrets.

1. Navigate to your GitHub repository.
2. Click on the **Settings** tab.
3. In the left sidebar, expand **Secrets and variables** and click **Actions**.
4. Click the **New repository secret** button.
5. Add the following two secrets:
    * **Name:** `WHITECIRCLE_API_KEY`
        * **Value:** *(Paste your actual White Circle API Key)*
    * **Name:** `WHITECIRCLE_DEPLOYMENT_ID`
        * **Value:** *(Paste your Deployment ID)*

### 3. Permissions
This action posts comments to your Pull Requests when violations are found. Therefore, your workflow must include the `permissions` block with `pull-requests: write`, as shown in the usage example above.

## Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `whitecircle_api_key` | Your White Circle API Key. | **Yes** | - |
| `deployment_id` | The specific Deployment ID for your policy configuration. | **Yes** | - |
| `github_token` | The standard GitHub token (usually `${{ secrets.GITHUB_TOKEN }}`). Used to fetch PR diffs and post comments. | **Yes** | - |
| `debug` | Set to `'true'` to print verbose logs about batching and payloads. | No | `'false'` |

## Development

### Files Structure

- `action.yml` - GitHub Actions metadata file
- `Dockerfile` - Container definition for the action
- `requirements.txt` - Python dependencies (requires `requests`, `tiktoken`, `PyGithub`)
- `main.py` - Main bot logic

### Local Testing

To test the Docker container locally, you can build and run it with the necessary environment variables. Note that `INPUT_` prefixes are how GitHub Actions passes arguments to the container.

```bash
# 1. Build the image
docker build -t white-circle-bot .

# 2. Run the image
# Replace the placeholder values with real data for testing
docker run --rm \
  -e INPUT_WHITECIRCLE_API_KEY="your-real-api-key" \
  -e INPUT_DEPLOYMENT_ID="your-deployment-id" \
  -e INPUT_GITHUB_TOKEN="your-personal-access-token" \
  -e INPUT_DEBUG="true" \
  -e GITHUB_REPOSITORY="owner/repo" \
  -e GITHUB_EVENT_PATH="/path/to/local/event.json" \
  white-circle-bot
```

*Note: For local testing, you will need to mount a dummy `event.json` that mimics the GitHub Pull Request event payload to the path specified in `GITHUB_EVENT_PATH`.*

## License

See [LICENSE](LICENSE) file for details.