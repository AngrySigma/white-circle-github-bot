#!/usr/bin/env python3
"""
White Circle GitHub Bot
A GitHub Actions bot that analyzes pull request code lines and messages.
"""

import os
import sys
import requests
import json


def get_env_variable(name, required=True):
    """Get environment variable with optional requirement check."""
    value = os.environ.get(name)
    if required and not value:
        print(f"Error: Required environment variable {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


def get_pr_info():
    """Extract pull request information from GitHub context."""
    github_token = get_env_variable('INPUT_GITHUB_TOKEN')
    api_endpoint = get_env_variable('INPUT_API_ENDPOINT', required=False) or 'https://api.github.com'
    
    # Get GitHub context from environment
    github_repository = get_env_variable('GITHUB_REPOSITORY')
    github_event_path = get_env_variable('GITHUB_EVENT_PATH')
    
    # Read event data
    try:
        with open(github_event_path, 'r') as f:
            event_data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Event file not found at {github_event_path}", file=sys.stderr)
        sys.exit(1)
    
    return {
        'token': github_token,
        'api_endpoint': api_endpoint,
        'repository': github_repository,
        'event_data': event_data
    }


def get_pr_files(token, repository, pr_number, api_endpoint):
    """Get the list of files changed in a pull request."""
    url = f"{api_endpoint}/repos/{repository}/pulls/{pr_number}/files"
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PR files: {e}", file=sys.stderr)
        return []


def get_pr_comments(token, repository, pr_number, api_endpoint):
    """Get the comments from a pull request."""
    url = f"{api_endpoint}/repos/{repository}/pulls/{pr_number}/comments"
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PR comments: {e}", file=sys.stderr)
        return []


def analyze_pr():
    """Main function to analyze pull request."""
    print("Starting White Circle GitHub Bot...")
    
    # Get PR information
    pr_info = get_pr_info()
    token = pr_info['token']
    api_endpoint = pr_info['api_endpoint']
    repository = pr_info['repository']
    event_data = pr_info['event_data']
    
    # Check if this is a pull request event
    if 'pull_request' not in event_data:
        print("This action only works on pull request events")
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write('status=skipped\n')
                f.write('message=Not a pull request event\n')
        return
    
    pr_number = event_data['pull_request']['number']
    pr_title = event_data['pull_request']['title']
    
    print(f"Analyzing PR #{pr_number}: {pr_title}")
    
    # Get files changed in the PR
    files = get_pr_files(token, repository, pr_number, api_endpoint)
    print(f"Found {len(files)} changed file(s)")
    
    # Analyze files
    total_additions = 0
    total_deletions = 0
    for file in files:
        filename = file.get('filename', 'unknown')
        additions = file.get('additions', 0)
        deletions = file.get('deletions', 0)
        changes = file.get('changes', 0)
        
        total_additions += additions
        total_deletions += deletions
        
        print(f"  - {filename}: +{additions} -{deletions} ({changes} changes)")
    
    # Get comments
    comments = get_pr_comments(token, repository, pr_number, api_endpoint)
    print(f"Found {len(comments)} comment(s)")
    
    # Summary
    print("\n=== Analysis Summary ===")
    print(f"PR Number: {pr_number}")
    print(f"PR Title: {pr_title}")
    print(f"Files Changed: {len(files)}")
    print(f"Lines Added: {total_additions}")
    print(f"Lines Deleted: {total_deletions}")
    print(f"Comments: {len(comments)}")
    
    # Set outputs
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        # Sanitize output to prevent injection
        message = f'Analyzed PR #{pr_number} with {len(files)} files and {total_additions + total_deletions} line changes'
        message = message.replace('\n', ' ').replace('\r', '')
        with open(github_output, 'a') as f:
            f.write('status=success\n')
            f.write(f'message={message}\n')


if __name__ == '__main__':
    try:
        analyze_pr()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            # Sanitize error message to prevent injection
            error_msg = str(e).replace('\n', ' ').replace('\r', '')
            with open(github_output, 'a') as f:
                f.write('status=failed\n')
                f.write(f'message=Bot execution failed: {error_msg}\n')
        sys.exit(1)
