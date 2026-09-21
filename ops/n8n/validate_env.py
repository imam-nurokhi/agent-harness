#!/usr/bin/env python3
"""Fail closed before a n8n deployment accepts its environment file."""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse


REQUIRED = {
    "N8N_IMAGE",
    "POSTGRES_IMAGE",
    "POSTGRES_PASSWORD",
    "N8N_ENCRYPTION_KEY",
    "N8N_HOST",
    "N8N_WEBHOOK_URL",
    "N8N_PATH",
    "N8N_EDITOR_BASE_URL",
}
PLACEHOLDER = ("replace_with", "example.invalid", "changeme", "change-me")


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"line {number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        if not key or key.strip() != key:
            raise ValueError(f"line {number}: invalid key")
        values[key] = value
    return values


def validate(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    missing = sorted(key for key in REQUIRED if not values.get(key))
    if missing:
        errors.append("missing required values: " + ", ".join(missing))

    for key in ("N8N_IMAGE", "POSTGRES_IMAGE"):
        value = values.get(key, "")
        if value and ("@sha256:" not in value or ":latest" in value):
            errors.append(f"{key} must use an immutable @sha256 digest, not a tag")

    for key in ("POSTGRES_PASSWORD", "N8N_ENCRYPTION_KEY"):
        value = values.get(key, "")
        if value and (len(value) < 32 or any(marker in value.lower() for marker in PLACEHOLDER)):
            errors.append(f"{key} must be a unique random value of at least 32 characters")

    host = values.get("N8N_HOST", "")
    if host and any(marker in host.lower() for marker in PLACEHOLDER):
        errors.append("N8N_HOST must be the approved shared-VPS hostname")

    webhook = values.get("N8N_WEBHOOK_URL", "")
    parsed = urlparse(webhook)
    if webhook and (parsed.scheme != "https" or not parsed.hostname):
        errors.append("N8N_WEBHOOK_URL must be an absolute HTTPS URL")
    elif host and parsed.hostname and parsed.hostname != host:
        errors.append("N8N_WEBHOOK_URL hostname must match N8N_HOST")

    path = values.get("N8N_PATH", "")
    if path and (not path.startswith("/") or not path.endswith("/")):
        errors.append("N8N_PATH must start and end with a slash")
    editor_base = values.get("N8N_EDITOR_BASE_URL", "")
    if editor_base and editor_base != webhook:
        errors.append("N8N_EDITOR_BASE_URL must equal N8N_WEBHOOK_URL")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_env.py PATH_TO_ENV", file=sys.stderr)
        return 2
    try:
        errors = validate(load_env(Path(argv[1])))
    except (OSError, ValueError) as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2
    if errors:
        print("n8n deployment configuration rejected:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print("n8n deployment configuration is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
