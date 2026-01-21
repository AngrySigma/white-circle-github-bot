import os
import sys
import uuid
import json
import requests
import tiktoken
from github import Github

# --- Configuration ---
API_KEY = os.getenv("INPUT_WHITECIRCLE_API_KEY")
DEPLOYMENT_ID = os.getenv("INPUT_DEPLOYMENT_ID")
GITHUB_TOKEN = os.getenv("INPUT_GITHUB_TOKEN")
GITHUB_EVENT_PATH = os.getenv("GITHUB_EVENT_PATH")
REPO_NAME = os.getenv("GITHUB_REPOSITORY")
DEBUG = os.getenv("INPUT_DEBUG", "false").lower() == "true"

# White Circle Config
BASE_URL = "https://tmp.whitecircle.dev/api/session/check"
WC_VERSION = "2025-12-01"

# Token limits
MAX_TOKENS_PER_REQUEST = 8000
TARGET_TOKENS_PER_BATCH = 6000  # Leave headroom for safety

# Initialize tiktoken encoder (cl100k_base is used by GPT-4/Claude-like models)
ENCODER = tiktoken.get_encoding("cl100k_base")


def count_tokens(text):
    """Count tokens in text using tiktoken."""
    if not text:
        return 0
    return len(ENCODER.encode(text))


def truncate_to_tokens(text, max_tokens):
    """Truncate text to fit within max_tokens."""
    if not text:
        return text
    tokens = ENCODER.encode(text)
    if len(tokens) <= max_tokens:
        return text
    truncated_tokens = tokens[:max_tokens]
    return ENCODER.decode(truncated_tokens) + "\n... [truncated]"


def get_pr_details():
    """Extracts PR diff and info using PyGithub. Returns structured file data."""
    g = Github(GITHUB_TOKEN)
    repo = g.get_repo(REPO_NAME)

    with open(GITHUB_EVENT_PATH, 'r') as f:
        event_data = json.load(f)

    pr_number = event_data.get('number')
    if not pr_number:
        print("Could not determine PR number. Is this a pull_request event?")
        sys.exit(1)

    pr = repo.get_pull(pr_number)

    # Collect structured file data
    files_data = []
    for file in pr.get_files():
        file_info = {
            "filename": file.filename,
            "patch": file.patch if file.patch else None,
            "status": file.status,  # added, modified, removed, renamed
            "additions": file.additions,
            "deletions": file.deletions,
        }

        # Try to get file content for context (only for non-deleted files)
        file_content = None
        if file.status != "removed":
            try:
                content_file = repo.get_contents(file.filename, ref=pr.head.sha)
                if content_file.size < 100000:  # Skip very large files
                    file_content = content_file.decoded_content.decode('utf-8', errors='replace')
            except Exception:
                pass  # File might be binary or inaccessible

        file_info["content"] = file_content
        files_data.append(file_info)

    # Get Commit Messages
    commit_messages = "\n".join([c.commit.message for c in pr.get_commits()])

    return pr, files_data, commit_messages


def format_file_content(file_info, max_tokens=None):
    """
    Format a single file's content for the API request.
    Prioritizes diff (patch) over full file content.
    Returns formatted string and token count.
    """
    filename = file_info["filename"]
    patch = file_info["patch"]
    content = file_info["content"]
    status = file_info["status"]

    parts = [f"### File: {filename} ({status})"]

    # Always include the diff first (it's the priority)
    if patch:
        diff_section = f"\n#### Diff:\n```diff\n{patch}\n```"
        parts.append(diff_section)
    else:
        parts.append("\n#### Diff: [Binary or Large File - no diff available]")

    result = "\n".join(parts)
    current_tokens = count_tokens(result)

    # Add file content if we have room
    if content and max_tokens:
        remaining_tokens = max_tokens - current_tokens - 50  # buffer for formatting
        if remaining_tokens > 100:  # Only add if meaningful space left
            content_header = f"\n#### Full File Content:\n```\n"
            content_footer = "\n```"
            header_tokens = count_tokens(content_header + content_footer)
            available_for_content = remaining_tokens - header_tokens

            if available_for_content > 100:
                truncated_content = truncate_to_tokens(content, available_for_content)
                result += content_header + truncated_content + content_footer

    return result, count_tokens(result)


def create_batches(files_data, commit_msgs):
    """
    Create batches of files that fit within TOKEN_TARGET.
    Each batch will be sent as a separate API request.
    """
    batches = []
    current_batch = []
    current_tokens = 0

    # Reserve tokens for commit messages and formatting overhead
    commit_section = f"### Commit Messages:\n{commit_msgs}\n\n"
    base_prompt = "Please analyze the following Pull Request details for safety policy violations.\n\n"
    overhead_tokens = count_tokens(base_prompt + commit_section) + 100  # extra buffer

    available_per_batch = TARGET_TOKENS_PER_BATCH - overhead_tokens

    for file_info in files_data:
        # Calculate tokens needed for this file (with truncation if needed)
        file_text, file_tokens = format_file_content(file_info, max_tokens=available_per_batch)

        # If single file exceeds limit, it gets its own batch (already truncated)
        if file_tokens > available_per_batch:
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            batches.append([{"file_info": file_info, "formatted": file_text, "tokens": file_tokens}])
            continue

        # Check if file fits in current batch
        if current_tokens + file_tokens <= available_per_batch:
            current_batch.append({"file_info": file_info, "formatted": file_text, "tokens": file_tokens})
            current_tokens += file_tokens
        else:
            # Start new batch
            if current_batch:
                batches.append(current_batch)
            current_batch = [{"file_info": file_info, "formatted": file_text, "tokens": file_tokens}]
            current_tokens = file_tokens

    if current_batch:
        batches.append(current_batch)

    return batches


def check_safety(files_data, commit_msgs):
    """Sends content to White Circle API in batches."""
    session_id = str(uuid.uuid4())
    print(f"Starting White Circle Session: {session_id}")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "whitecircle-version": WC_VERSION
    }

    batches = create_batches(files_data, commit_msgs)
    print(f"Created {len(batches)} batch(es) for analysis")

    all_results = []
    any_flagged = False
    all_policies = {}

    for i, batch in enumerate(batches):
        batch_files = "\n\n".join([item["formatted"] for item in batch])
        file_names = [item["file_info"]["filename"] for item in batch]

        prompt_content = (
            f"Please analyze the following Pull Request details for safety policy violations.\n\n"
            f"### Commit Messages:\n{commit_msgs}\n\n"
            f"{batch_files}"
        )

        payload = {
            "deployment_id": DEPLOYMENT_ID,
            "internal_session_id": session_id,
            "messages": [
                {
                    "role": "user",
                    "content": prompt_content
                }
            ]
        }

        # Debug logging
        if DEBUG:
            print(f"\n{'='*60}")
            print(f"DEBUG: Batch {i+1}/{len(batches)}")
            print(f"DEBUG: Files in batch: {file_names}")
            print(f"DEBUG: Total tokens: {sum(item['tokens'] for item in batch)}")
            print(f"DEBUG: Message content preview:")
            print("-" * 40)
            # Show first 2000 chars of the message
            preview = prompt_content[:2000]
            if len(prompt_content) > 2000:
                preview += f"\n... [truncated, total length: {len(prompt_content)} chars]"
            print(preview)
            print("-" * 40)

        try:
            print(f"Sending batch {i+1}/{len(batches)} ({len(batch)} file(s): {', '.join(file_names)})")
            response = requests.post(BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            all_results.append(result)

            if result.get("flagged"):
                any_flagged = True
                # Merge policies
                for policy_id, policy_data in result.get("policies", {}).items():
                    if policy_id not in all_policies or policy_data.get("flagged"):
                        all_policies[policy_id] = policy_data

            if DEBUG:
                print(f"DEBUG: Response: {json.dumps(result, indent=2)}")

        except Exception as e:
            print(f"Error connecting to White Circle API: {e}")
            sys.exit(1)

    # Combine results
    combined_result = {
        "flagged": any_flagged,
        "policies": all_policies,
        "batch_count": len(batches),
        "batch_results": all_results
    }

    return combined_result


def main():
    print("--- Starting Safety Analysis ---")
    if DEBUG:
        print("DEBUG mode enabled")

    pr, files_data, commit_msgs = get_pr_details()

    if not files_data and not commit_msgs:
        print("No changes found to analyze.")
        sys.exit(0)

    print(f"Found {len(files_data)} file(s) to analyze")
    if DEBUG:
        for f in files_data:
            patch_tokens = count_tokens(f["patch"]) if f["patch"] else 0
            content_tokens = count_tokens(f["content"]) if f["content"] else 0
            print(f"  - {f['filename']}: patch={patch_tokens} tokens, content={content_tokens} tokens")

    print("Analyzing Diff and Commits...")
    result = check_safety(files_data, commit_msgs)

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