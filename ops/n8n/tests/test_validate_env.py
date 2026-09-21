from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import validate_env  # noqa: E402


def valid_values() -> dict[str, str]:
    return {
        "N8N_IMAGE": "docker.n8n.io/n8nio/n8n@sha256:" + "a" * 64,
        "POSTGRES_IMAGE": "postgres@sha256:" + "b" * 64,
        "POSTGRES_PASSWORD": "p" * 32,
        "N8N_ENCRYPTION_KEY": "k" * 32,
        "N8N_HOST": "agents.nexoratech.co",
        "N8N_WEBHOOK_URL": "https://agents.nexoratech.co/automation/",
        "N8N_PATH": "/automation/",
        "N8N_EDITOR_BASE_URL": "https://agents.nexoratech.co/automation/",
    }


class ValidateEnvTests(unittest.TestCase):
    def test_valid_shared_vps_configuration_is_accepted(self):
        self.assertEqual([], validate_env.validate(valid_values()))

    def test_image_tag_is_rejected(self):
        values = valid_values()
        values["N8N_IMAGE"] = "docker.n8n.io/n8nio/n8n:latest"
        self.assertIn("N8N_IMAGE must use an immutable @sha256 digest, not a tag",
                      validate_env.validate(values))

    def test_placeholder_and_short_secret_are_rejected(self):
        values = valid_values()
        values["POSTGRES_PASSWORD"] = "replace_with_password"
        self.assertIn("POSTGRES_PASSWORD must be a unique random value of at least 32 characters",
                      validate_env.validate(values))

    def test_mismatched_webhook_host_is_rejected(self):
        values = valid_values()
        values["N8N_WEBHOOK_URL"] = "https://elsewhere.nexoratech.co/"
        self.assertIn("N8N_WEBHOOK_URL hostname must match N8N_HOST", validate_env.validate(values))

    def test_invalid_path_and_editor_base_are_rejected(self):
        values = valid_values()
        values["N8N_PATH"] = "automation"
        values["N8N_EDITOR_BASE_URL"] = "https://automation.nexoratech.co/"
        errors = validate_env.validate(values)
        self.assertIn("N8N_PATH must start and end with a slash", errors)
        self.assertIn("N8N_EDITOR_BASE_URL must equal N8N_WEBHOOK_URL", errors)


if __name__ == "__main__":
    unittest.main()
