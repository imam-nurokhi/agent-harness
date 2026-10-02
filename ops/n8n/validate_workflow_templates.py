#!/usr/bin/env python3
"""Fail closed when a n8n review template lacks operational governance."""
from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED_METADATA = {
    "id", "file", "status", "owner", "data_classification",
    "credential_scope", "trigger", "outputs", "activation_prerequisites", "rollback",
}
DISALLOWED_NODE_PARTS = ("executeCommand", ".ssh", "readWriteFile", ".code")


def _read_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name} is not valid JSON: {exc}")
        return None


def validate(templates: Path) -> list[str]:
    errors: list[str] = []
    manifest_data = _read_json(templates / "manifest.json", errors)
    if not isinstance(manifest_data, dict) or not isinstance(manifest_data.get("templates"), list):
        return errors + ["manifest.json must contain a templates list"]

    manifest_by_file: dict[str, dict] = {}
    for item in manifest_data["templates"]:
        if not isinstance(item, dict):
            errors.append("manifest entry must be an object")
            continue
        missing = sorted(REQUIRED_METADATA - set(item))
        if missing:
            errors.append("manifest entry missing: " + ", ".join(missing))
            continue
        filename = item["file"]
        if not isinstance(filename, str) or not filename.endswith(".json") or filename == "manifest.json":
            errors.append("manifest file must name one workflow JSON file")
            continue
        if filename in manifest_by_file:
            errors.append(f"manifest has duplicate entry for {filename}")
            continue
        manifest_by_file[filename] = item

    workflow_files = sorted(path for path in templates.glob("*.json") if path.name != "manifest.json")
    for path in workflow_files:
        item = manifest_by_file.get(path.name)
        if not item:
            errors.append(f"{path.name} is missing from manifest")
            continue
        expected_id = path.stem
        if item["id"] != expected_id:
            errors.append(f"{path.name} manifest id must be {expected_id}")
        if item["status"] != "review":
            errors.append(f"{expected_id} must remain in review status until owner approval")
        if item["trigger"] != "manual":
            errors.append(f"{expected_id} must use a manual trigger before activation")
        for required_list in ("outputs", "activation_prerequisites"):
            if not isinstance(item[required_list], list) or not item[required_list]:
                errors.append(f"{expected_id} must declare {required_list}")
        if not isinstance(item["owner"], str) or not item["owner"].strip():
            errors.append(f"{expected_id} must declare an owner")
        if not isinstance(item["rollback"], str) or not item["rollback"].strip():
            errors.append(f"{expected_id} must declare rollback")

        workflow = _read_json(path, errors)
        if not isinstance(workflow, dict):
            continue
        if workflow.get("active") is not False:
            errors.append(f"{expected_id} must remain inactive until owner approval")
        nodes = workflow.get("nodes")
        if not isinstance(nodes, list):
            errors.append(f"{expected_id} must define nodes")
            continue
        if not any(node.get("type") == "n8n-nodes-base.manualTrigger"
                   for node in nodes if isinstance(node, dict)):
            errors.append(f"{expected_id} must include a manual trigger")
        for node in nodes:
            if not isinstance(node, dict):
                errors.append(f"{expected_id} has an invalid node")
                continue
            node_type = str(node.get("type", ""))
            if any(part in node_type for part in DISALLOWED_NODE_PARTS):
                errors.append(f"{expected_id} contains disallowed node {node_type}")
            if node_type != "n8n-nodes-base.httpRequest":
                continue
            params = node.get("parameters", {})
            if not isinstance(params, dict):
                errors.append(f"{expected_id} has invalid HTTP parameters")
                continue
            if params.get("method") != "GET":
                errors.append(f"{expected_id} HTTP requests must use GET")
            url = params.get("url", "")
            if not isinstance(url, str) or not url.startswith("https://api.github.com/"):
                errors.append(f"{expected_id} HTTP requests must target GitHub API")

    for filename in manifest_by_file:
        if not (templates / filename).is_file():
            errors.append(f"manifest references missing workflow {filename}")
    return errors


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) == 2 else Path(__file__).with_name("workflow-templates")
    errors = validate(path)
    if errors:
        print("workflow templates rejected:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print("workflow templates are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
