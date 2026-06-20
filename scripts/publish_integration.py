#!/usr/bin/env python3
"""Publish a Mise en Place Assistant release for HACS."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")
SECRET_PATTERN = re.compile(
    r"(password: [\"'][^!]|token|api[_-]?key: [^!]|authorization|bearer|"
    r"ghp_|github_pat|192\.168)",
    re.IGNORECASE,
)


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a command from the repository root."""
    print("+ " + " ".join(command))
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )


def validate_version(version: str) -> None:
    """Validate semantic version text."""
    if not SEMVER.match(version):
        raise SystemExit(f"Invalid semantic version: {version}")


def ensure_clean_start() -> None:
    """Avoid publishing from a dirty working tree."""
    status = run(["git", "status", "--porcelain"], capture=True).stdout.strip()
    if status:
        raise SystemExit("Working tree is not clean. Commit or stash changes first.")


def ensure_tag_available(version: str) -> None:
    """Fail if the tag already exists."""
    tag = f"v{version}"
    result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        raise SystemExit(f"Tag already exists: {tag}")


def scan_staged_content() -> None:
    """Scan staged content for obvious secrets."""
    staged = run(["git", "diff", "--cached"], capture=True).stdout
    if SECRET_PATTERN.search(staged):
        raise SystemExit("Potential sensitive content found in staged diff.")


def validate_files() -> None:
    """Run lightweight local validation."""
    run(
        [
            "python3",
            "-m",
            "compileall",
            "custom_components/mise_en_place_assistant",
            "scripts",
        ]
    )
    for filename in ("hacs.json", "custom_components/mise_en_place_assistant/manifest.json"):
        json.loads((ROOT / filename).read_text(encoding="utf-8"))


def main() -> int:
    """Publish the integration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="Semantic version, for example 0.1.1")
    parser.add_argument("release_note", help="Short release note")
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Create the commit and tag locally without pushing.",
    )
    args = parser.parse_args()

    validate_version(args.version)
    ensure_clean_start()
    ensure_tag_available(args.version)

    run(["git", "config", "user.email", "leseulsteve@users.noreply.github.com"])
    run(["python3", "scripts/publish_release.py", args.version, args.release_note])
    validate_files()
    run(["git", "add", "custom_components/mise_en_place_assistant/manifest.json"])
    # CHANGELOG.md is intentionally ignored during ordinary development, but a
    # generated release entry must be part of the tagged release commit.
    run(["git", "add", "-f", "CHANGELOG.md"])
    scan_staged_content()
    run(["git", "commit", "-m", f"Release {args.version}"])
    run(["git", "tag", "-a", f"v{args.version}", "-m", f"Mise en Place Assistant {args.version}"])

    if not args.no_push:
        run(["git", "push", "origin", "main", "--tags"])

    print(f"Published Mise en Place Assistant {args.version}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as err:
        sys.exit(err.returncode)
