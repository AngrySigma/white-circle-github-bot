import os
import sys
import uuid
import requests
from github import Github

# --- Configuration ---
API_KEY = os.getenv("INPUT_WHITECIRCLE_API_KEY")
DEPLOYMENT_ID = os.getenv("INPUT_DEPLOYMENT_ID")
GITHUB_TOKEN = os.getenv("INPUT_GITHUB_TOKEN")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
# Assuming running on a PR, GITHUB_REF usually looks like 'refs/pull/123/merge'
# But for Actions, it's safer to get PR number from the event context if possible, 
# or use the provided GITHUB_TOKEN to find the PR.

# White Circle Config
BASE_URL = "https://us.whitecircle.ai/api/session/check"  # Change subdomain if needed
WC_VERSION = "2025-12-01"


def get_pr_details():
    """Extracts PR diff and info using PyGithub."""
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    # We need to find the PR number. In 'pull_request' events, it's in the event payload.
    # For simplicity in this script, we assume this runs on a 'pull_request' trigger.
    # We can try to grab it from the environment or event.json.

    import json
    with open(GITHUB_EVENT_PATH, 'r') as f:
        event_data = json.load(f)

    pr_number = event_data.get('number')
    if not pr_number:
        print("Could not determine PR number. Is this a pull_request event?")
        sys.exit(1)

    pr = repo.get_pull(pr_number)

    # Get the Diff (files changed)
    # Ideally, we iterate over files to avoid huge payloads, but per your request, 
    # we aren't chunking yet.
    full_diff = ""
    for file in pr.get_files():
        full_diff += f"\n--- File: {file.filename} ---\n"
        full_diff += file.patch if file.patch else "[Binary or Large File]"

    # Get Commit Messages
    commit_messages = "\n".join([c.commit.message for c in pr.get_commits()])

    return pr, full_diff, commit_messages


def check_safety(diff_text, commit_msgs):
    """Sends content to White Circle API."""
    session_id = str(uuid.uuid4())
    print(f"Starting White Circle Session: {session_id}")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "whitecircle-version": WC_VERSION
    }

    # We construct a prompt that includes context.
    # Since we support sessions, we could split this, but let's do one focused check.
    prompt_content = (
        f"Please analyze the following Pull Request details for safety policy violations.\n\n"
        f"### Commit Messages:\n{commit_msgs}\n\n"
        f"### Code Diff:\n{diff_text}"
    )

    payload = {
        "deployment_id": DEPLOYMENT_ID,
        "internal_session_id": session_id,  # Enables context merging for future requests
        "messages": [
            {
                "role": "user",
                "content": prompt_content
            }
        ]
    }

    try:
        response = requests.post(BASE_URL, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error connecting to White Circle API: {e}")
        sys.exit(1)


def main():
    print("--- Starting Safety Analysis ---")

    pr, diff_text, commit_msgs = get_pr_details()

    if not diff_text and not commit_msgs:
        print("No changes found to analyze.")
        sys.exit(0)

    print("Analyzing Diff and Commits...")
    result = check_safety(diff_text, commit_msgs)

    if result.get("flagged"):
        print("❌ SAFETY VIOLATION DETECTED")

        # Extract policy names
        policies = result.get("policies", {})
        violated_policies = [p["name"] for p in policies.values() if p["flagged"]]
        violation_list = "\n- ".join(violated_policies)

        message = (
            f"### 🛡️ White Circle Safety Guard\n\n"
            f"**The build has been blocked due to policy violations.**\n\n"
            f"**Violated Policies:**\n{violation_list}\n\n"
            f"Please review your code/comments and remove the flagged content."
        )

        # Post comment to PR
        pr.create_issue_comment(message)

        # Fail the Action
        sys.exit(1)
    else:
        print("✅ No violations found.")
        sys.exit(0)


if __name__ == "__main__":
    main()