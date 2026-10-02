# Shared-VPS n8n Automation

This is the deployment baseline for the isolated Nexora/CBQA automation stack on
`31.97.67.241`. It does not include production, NEXONE, GitHub, Slack, Notion,
Telegram, or AI credentials.

## Guardrails

- Keep n8n on `127.0.0.1:5678`; the existing Nginx reverse proxy provides TLS,
  rate limiting, and owner authentication at
  `https://agents.nexoratech.co/automation/`. Do not expose port `5678`
  publicly.
- Pin both images to reviewed SHA-256 digests. `validate_env.py` rejects tags.
- Use one service credential per integration, with read-only scope by default.
- Do not install community nodes or use shell, SSH, filesystem, or Code nodes
  in phase one. They are excluded by configuration. Run `n8n audit` before
  enabling any workflow.
- Production deployment remains in GitHub Environments. n8n may notify or link
  to an approval; it must never hold a production deployment credential.

## Provisioning sequence

1. On `31.97.67.241`, copy `.env.example` to `.env`, generate unique secrets, and
   replace the image digests with reviewed values. PostgreSQL 17 or newer is
   required by the installed n8n version.
2. Run `python3 validate_env.py .env` and fix every error before starting Docker.
3. Run `docker compose --env-file .env -f compose.yaml config` to render the
   exact deployment without starting it.
4. Configure the reverse proxy and TLS separately, then run `docker compose
   --env-file .env -f compose.yaml up -d`.
5. Verify n8n is only listening on loopback, create the owner account, and run
   `docker compose --env-file .env -f compose.yaml exec n8n n8n audit` before
   adding a workflow.

## Backup

`nexora-operations-backup` and its systemd timer create a root-only local backup
at `/var/backups/nexora-operations/` each day, retaining 14 days. The archive
contains the PostgreSQL dump, n8n data volume, and stack environment file. It is
a fast local-recovery layer only; add an encrypted off-host destination and test
restore before treating it as disaster recovery.

## Phase-one workflow order

1. GitHub read-only CI/PR event to an audit table and owner notification.
2. Daily brief that aggregates the approved read model only.
3. Domain/SSL/backup reminder using read-only probes or APIs.
4. Documentation-draft reminder and customer-support intake with human handoff.

Each workflow needs a failure path, redacted log payload, deduplication key,
owner-only notification target, and an explicit approval step for any write.

## Review templates

`workflow-templates/github-read-only-daily-status.json` is an importable,
inactive review template. It has a manual trigger and three `GET` requests to
the GitHub API for open pull requests, failed Actions runs, and open issues.
It contains no token and cannot post, dispatch a workflow, alter a repository,
or deploy. Before importing it, the owner must review and replace the repository
placeholders, create a dedicated read-only GitHub credential in n8n, and approve
the eventual notification destination. Do not activate it until its output,
redaction, retry, and failure path have been tested with non-sensitive data.

The template is validated by `tests/test_workflow_templates.py`, which rejects
an active template, a missing manual trigger, a non-GET GitHub request, a
non-GitHub endpoint, or an enabled shell/SSH/filesystem/Code node.

`validate_workflow_templates.py` checks every JSON workflow template against
`workflow-templates/manifest.json`. The manifest is required to declare an
owner, data classification, credential scope, outputs, activation prerequisites,
and rollback. Run `python3 validate_workflow_templates.py` before a template is
reviewed, imported, or changed.
