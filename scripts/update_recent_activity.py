import json
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


START_MARKER = "<!-- recent-activity:start -->"
END_MARKER = "<!-- recent-activity:end -->"
MAX_ITEMS = 5


def fetch_public_events(username, token=None):
    url = f"https://api.github.com/users/{quote(username, safe='')}/events/public?per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "profile-readme-recent-activity",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers)
    with urlopen(request, timeout=15) as response:
        events = json.load(response)
    if not isinstance(events, list):
        raise ValueError("GitHub's public events endpoint returned an unexpected response.")
    return events


def _repository_link(repository_name):
    parts = repository_name.split("/", 1)
    if len(parts) != 2 or not all(parts):
        return None
    path = "/".join(quote(part, safe="") for part in parts)
    label = repository_name.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
    return f"[{label}](https://github.com/{path})"


def _event_description(event, repository_link):
    event_type = event.get("type")
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        return None

    if event_type == "PushEvent":
        return f"Pushed to {repository_link}"
    if event_type == "PullRequestEvent":
        action = payload.get("action")
        number = payload.get("number")
        if action in {"opened", "closed", "reopened"} and type(number) is int:
            link = repository_link[:-1] + f"/pull/{number})"
            return f"{action.capitalize()} pull request in {link}"
    if event_type == "IssuesEvent":
        action = payload.get("action")
        issue = payload.get("issue")
        if not isinstance(issue, dict):
            return None
        number = issue.get("number")
        if action in {"opened", "closed", "reopened"} and type(number) is int:
            link = repository_link[:-1] + f"/issues/{number})"
            return f"{action.capitalize()} issue in {link}"
    if event_type == "ReleaseEvent":
        release = payload.get("release")
        if not isinstance(release, dict):
            return None
        tag = release.get("tag_name")
        if isinstance(tag, str) and tag:
            return f"Released {quote(tag, safe='')} in {repository_link}"
    if event_type == "CreateEvent":
        ref_type = payload.get("ref_type")
        if ref_type in {"repository", "branch", "tag"}:
            return f"Created {ref_type} in {repository_link}"
    return None


def format_activity(events):
    items = []
    for event in events:
        if not isinstance(event, dict):
            continue
        repository = event.get("repo", {})
        repository_name = repository.get("name") if isinstance(repository, dict) else None
        if not isinstance(repository_name, str):
            continue
        repository_link = _repository_link(repository_name)
        if not repository_link:
            continue
        description = _event_description(event, repository_link)
        if not description:
            continue

        created_at = event.get("created_at")
        if not isinstance(created_at, str):
            continue
        date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        items.append(f"- **{date}** — {description}")
        if len(items) == MAX_ITEMS:
            break

    return "\n".join(items) if items else "_No recent public activity found._"


def replace_activity(readme, activity):
    if readme.count(START_MARKER) != 1 or readme.count(END_MARKER) != 1:
        raise ValueError("README.md must contain exactly one recent-activity marker pair.")
    start = readme.index(START_MARKER) + len(START_MARKER)
    end = readme.index(END_MARKER)
    if start > end:
        raise ValueError("README.md recent-activity markers are out of order.")
    return f"{readme[:start]}\n{activity}\n{readme[end:]}"


def main():
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    username = repository.split("/", 1)[0]
    if not username:
        print("GITHUB_REPOSITORY must identify the profile repository owner.", file=sys.stderr)
        return 1

    readme_path = Path("README.md")
    try:
        readme = readme_path.read_text(encoding="utf-8")
        events = fetch_public_events(username, os.environ.get("GITHUB_TOKEN"))
        updated = replace_activity(readme, format_activity(events))
    except (HTTPError, URLError, OSError, ValueError) as error:
        print(f"Unable to update recent activity: {error}", file=sys.stderr)
        return 1

    if updated != readme:
        readme_path.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
