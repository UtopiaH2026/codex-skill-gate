from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=check,
    )


def credential_from_git() -> str | None:
    request = "protocol=https\nhost=github.com\n\n"
    result = subprocess.run(
        ["git", "credential", "fill"],
        input=request,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values.get("password")


def request_json(method: str, url: str, token: str, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        method=method,
        data=data,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "codex-skill-gate-publisher",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and push the public GitHub repository.")
    parser.add_argument("--repo", default="codex-skill-gate")
    parser.add_argument("--private", action="store_true")
    parser.add_argument("--description", default="Binary coding/non-coding gate for Codex skill metadata")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args()

    token = os.environ.get(args.token_env) or os.environ.get("GH_TOKEN")
    token_source = "environment"
    if not token:
        token = credential_from_git()
        token_source = "git-credential-manager"
    if not token:
        print(
            f"Missing GitHub credentials. Set {args.token_env} or run `git credential-manager github login`.",
            file=sys.stderr,
        )
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    status = run_git("-C", str(repo_root), "status", "--porcelain").stdout.strip()
    if status:
        print("Working tree must be clean before publishing.", file=sys.stderr)
        return 2

    try:
        user = request_json("GET", f"{API}/user", token)
        login = str(user["login"])
    except urllib.error.HTTPError as exc:
        print(f"GitHub authentication failed: HTTP {exc.code}", file=sys.stderr)
        return 2

    create_payload = {
        "name": args.repo,
        "description": args.description,
        "private": bool(args.private),
        "auto_init": False,
        "has_issues": True,
        "has_discussions": True,
    }
    try:
        repository = request_json("POST", f"{API}/user/repos", token, create_payload)
        html_url = str(repository["html_url"])
        print(f"Created {html_url}")
    except urllib.error.HTTPError as exc:
        if exc.code != 422:
            body = exc.read().decode("utf-8", "ignore")
            print(f"Repository creation failed: HTTP {exc.code} {body}", file=sys.stderr)
            return 2
        html_url = f"https://github.com/{login}/{args.repo}"
        print(f"Repository already exists; using {html_url}")

    remote = f"https://github.com/{login}/{args.repo}.git"
    existing = run_git("-C", str(repo_root), "remote", "get-url", "origin", check=False)
    if existing.returncode == 0:
        run_git("-C", str(repo_root), "remote", "set-url", "origin", remote)
    else:
        run_git("-C", str(repo_root), "remote", "add", "origin", remote)

    push_command = ["git", "-C", str(repo_root)]
    if token_source == "environment":
        basic = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
        push_command.extend(["-c", f"http.extraHeader=Authorization: Basic {basic}"])
    push_command.extend(["push", "-u", "origin", "HEAD:main"])
    push = subprocess.run(push_command, text=True, encoding="utf-8")
    if push.returncode != 0:
        return push.returncode
    print(f"Published {remote}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
