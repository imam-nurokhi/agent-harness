# OneAlpha Rebuild Plan Using Ever Gauzy as Reference

**Document type:** Master implementation plan for Agent Harness  
**Target platform:** OneAlpha CRM + Audit Platform + supporting business modules  
**Reference platform:** Ever Gauzy  
**Status:** Proposed baseline for discovery and execution  
**Primary timezone:** Asia/Jakarta  

---

## 1. Executive decision

Ever Gauzy can be used as a **reference architecture and product-pattern library** for rebuilding OneAlpha. It should not be copied wholesale and should not become the source of truth for CBQA-specific business rules.

Use Gauzy for:

- Multi-tenant organization and access patterns.
- Generic CRM, contacts, proposals, clients, projects, tasks, calendar, HR, time tracking, documents, reports, and dashboards.
- REST/GraphQL API patterns.
- Plugin and integration architecture.
- TypeScript monorepo conventions.
- Docker/Kubernetes, observability, search, cache, object storage, and analytics patterns.
- AI/MCP integration concepts.

Keep OneAlpha as the source of truth for:

- CBQA Global CRM and sales rules.
- Audit methodology and audit lifecycle.
- Application Review, Audit Scheduling, Auditor assignment, Technical Review, Decision, and Certificate Issuance.
- ISO, ISCC, LVV, and LATIK rules.
- Personnel qualification, competency, sectors, rates, and impartiality.
- Transfer Audit precedence.
- Audit evidence, forms, certificate numbering, accreditation requirements, and controlled outputs.

### Recommended target

Build a **OneAlpha modular monolith first**, with strong domain boundaries and event-driven interfaces. Extract services only when there is a proven operational reason.

```text
OneAlpha Platform
├── Identity & Access
├── Tenant / Organization / Master Tenant
├── CRM & Commercial
├── Proposal & Project
├── Audit Platform
│   ├── Application Review
│   ├── Audit Methodology
│   ├── Audit Scheduling
│   ├── Personnel & Competency
│   ├── Audit Execution
│   ├── Technical Review
│   ├── Decision
│   └── Certificate Issuance
├── Documents & Evidence
├── Calendar & Notifications
├── Reporting & Dashboard
├── Integration Layer
└── Platform Administration
```

The Go Audit service may remain a separate bounded service if it is already operationally justified. The agent must not merge or replace it without an explicit architecture decision.

---

## 2. Reference analysis: what to learn from Gauzy

Ever Gauzy is a broad open-source ERP/CRM/HRM/ATS/project/time-tracking platform built with TypeScript, Node.js/NestJS, Angular, Nx/Lerna, multiple ORM options, REST/GraphQL APIs, and multi-tenant support. It also provides desktop applications, plugins, cloud-native deployment options, search, caching, object storage, analytics, and an MCP server.

Reference links:

- Repository: <https://github.com/ever-co/ever-gauzy>
- Documentation: <https://docs.gauzy.co/>
- Architecture documentation: <https://docs.gauzy.co/>
- Releases: <https://github.com/ever-co/ever-gauzy/releases>

### Adopt as patterns

| Gauzy area | OneAlpha use | Adoption rule |
|---|---|---|
| Organizations / tenants | Master Tenant and tenant-scoped access | Reimplement after comparing with current OneAlpha/OneDatahub identity model |
| Roles and permissions | Tenant roles, module permissions, action permissions | Preserve least privilege and approval boundaries |
| CRM contacts, leads, proposals | OneAlpha CRM | Reuse concepts, not schemas or labels blindly |
| Projects and tasks | Project and audit task generation | Make audit task creation backend-driven and idempotent |
| Time tracking | Optional operational reporting | Do not introduce employee surveillance without business approval |
| Documents / knowledge hub | Audit evidence and controlled documents | Add versioning, access control, retention, and audit trail |
| Dashboard / reports | Executive and staff dashboards | Build role-specific metrics from approved definitions |
| Plugin model | Integrations and future modules | Define stable extension points before extracting plugins |
| REST / GraphQL | Headless integrations | REST remains the primary contract unless GraphQL is explicitly required |
| Search / OpenSearch | Client, certificate, document, and audit search | Start with PostgreSQL search; add OpenSearch when scale requires it |
| Redis | Cache, queue, distributed locks | Use only for defined workloads; avoid hidden business state |
| MinIO/S3 | Evidence and generated files | Use private buckets, signed URLs, retention, and malware scanning |
| MCP | Read-only analysis and controlled actions | Never allow unrestricted production mutation from an agent |
| Docker/Kubernetes | Deployment reference | Start with staging Docker Compose or VM; use Kubernetes when operationally justified |

### Do not adopt directly

- Gauzy's generic accounting, payroll, inventory, or HR rules as CBQA rules.
- Gauzy's entity names or database tables without domain mapping.
- Default demo credentials or secrets.
- Its license assumptions for proprietary OneAlpha deployment.
- Its entire infrastructure stack before measuring actual OneAlpha needs.
- Any UI flow that conflicts with the approved OneAlpha E2E workflow.

### License gate

The public documentation describes AGPL-3.0/community usage and separate commercial licensing. Before copying source code, packages, schemas, or substantial implementation patterns into a proprietary OneAlpha product, Legal/management must approve the license position. The harness may perform read-only analysis of Gauzy, but must not copy code into OneAlpha until this gate is recorded.

---

## 3. Existing OneAlpha constraints to preserve

These are non-negotiable domain constraints for the rebuild.

### Identity and authentication

- Keycloak 25 is the identity broker.
- Internal staff authentication uses Microsoft Entra SSO.
- External customer authentication uses OneDatahub POST signin.
- Application-specific OIDC clients include AuditQ, OneAlpha, CRM, and related CBQA modules.
- Staging must never use the production OneDatahub URL.
- Refresh tokens, cookies, issuer, redirect URI, and audience configuration must be environment-specific.

### Audit lifecycle

```text
CRM / Sales
  → Audit Date
  → Application Review
  → Audit Scheduling
  → Auditor / Audit Execution
  → Technical Review
  → Certification Decision
  → Certificate Issuance
```

Rules:

- The stepper is backend-driven.
- Only the active stage is editable.
- Completed stages become read-only except through controlled revision.
- Integrated/Combined Audit is one auditable flow with one Application Review.
- Assignment is competency-based.
- Stage transitions are permission-controlled and auditable.
- Need Revision must return to the correct stage with reason, actor, timestamp, and changed data.
- Audit tasks must be idempotent and must not duplicate when project dates or methodology are edited.

### Roles

At minimum, model these roles and actions separately:

- Sales.
- Application Reviewer.
- Scheduler / Operation.
- Auditor.
- Technical Reviewer.
- Certification Authority.
- Certification Reviewer / Issuer.
- Accreditation / administration.
- Master Tenant Admin.
- Tenant Admin.

### Domain-specific requirements

- ISO and ISCC scheduler roles differ.
- ISCC may require GHG Expert and MB Verifier.
- Technical Review and MBV must be independent from the Auditor where required.
- Competency includes standard, sector, qualification, rate, and external-personnel support.
- Audit impartiality must be captured and auditable.
- Transfer Audit must be completed before Surveillance or Recertification when present.
- Certificate drafting may proceed in parallel before surveillance, but certificate data must remain editable at issuance under controlled permissions.
- LVV, LATIK, ISO, and ISCC have different forms, stage rules, numbering rules, and evidence requirements.
- PDF/XLSX/PPTX outputs must be generated from controlled templates and tested against approved samples.

---

## 4. Target architecture

### 4.1 Architecture principles

1. Domain-first: model business capabilities before copying framework structure.
2. Modular monolith first: separate modules in one deployable backend unless extraction is justified.
3. Contract-first: API, events, permissions, and state transitions are explicit.
4. Backend-driven workflow: frontend renders allowed actions returned by backend.
5. Immutable history: stage changes, approvals, revisions, certificate changes, and assignments are auditable.
6. Tenant isolation by default: every tenant-sensitive query must be scoped.
7. Idempotency: retries must not duplicate tasks, documents, notifications, or certificates.
8. Controlled extensibility: plugins and integrations may extend a domain but may not bypass its invariants.
9. Secure-by-default: secrets, PII, evidence, and certificate files are protected.
10. Testable boundaries: every module has unit, integration, contract, and E2E coverage appropriate to risk.

### 4.2 Logical components

```text
Web Frontend
    │
    ▼
API / BFF Layer
    │
    ├── Identity & Access Module
    ├── Tenant Module
    ├── CRM Module
    ├── Proposal / Project Module
    ├── Audit Workflow Module
    ├── Personnel / Competency Module
    ├── Document / Evidence Module
    ├── Certificate Module
    ├── Reporting Module
    ├── Notification Module
    └── Integration Adapters
    │
    ├── PostgreSQL
    ├── Redis / Queue
    ├── Object Storage
    ├── Search Index (optional)
    └── External: Keycloak, OneDatahub, Audit-Q, email, payment/integration services
```

### 4.3 Technology decision

The agent must first inspect the current OneAlpha repositories and produce a recommendation rather than force Gauzy's stack.

Default decision criteria:

- Preserve the current production-supported stack where migration cost is high.
- Use Gauzy's TypeScript/NestJS/Angular approach as a reference when it improves consistency and the current stack is not a firm constraint.
- Preserve the Go Audit service as a bounded service if it already owns audit execution APIs.
- Do not perform a language rewrite during the first rebuild increment.

Output required from discovery: `architecture-decision-records/ADR-001-stack-and-boundaries.md`.

---

## 5. Module rebuild scope and sequence

### Phase 0 — Harness and repository onboarding

**Goal:** Make the agent-harness safe and capable of working across the real repositories.

Tasks:

- Confirm available disk space before cloning or materializing repositories.
- Register OneAlpha frontend, OneAlpha backend, OneDatahub, and Go Audit repositories in the harness.
- Keep the harness local-first under `~/AI-Workspace`.
- Create an isolated worktree per task and per agent branch.
- Add or validate `AGENTS.md` in each repository.
- Define repository ownership, build commands, test commands, environment templates, and protected paths.
- Configure GitHub CLI access without exposing tokens to agent prompts.
- Configure read-only analysis of Ever Gauzy in a separate reference directory.
- Do not clone into `~/Documents`.
- Do not connect agents directly to production databases or production servers.

Exit criteria:

- `doctor` passes.
- Every repository has a valid health report.
- A no-op task can be planned, executed, reviewed, and discarded without touching protected branches.
- Harness dashboard is available locally at the configured loopback address.

### Phase 1 — Current-state discovery and domain inventory

**Goal:** Establish a baseline before changing code.

Tasks:

- Inventory frontend routes, modules, components, guards, services, and state management.
- Inventory backend controllers, services, entities, repositories, migrations, queues, and integrations.
- Inventory OneDatahub contracts and authentication dependencies.
- Inventory Go Audit APIs and ownership boundaries.
- Map current database tables and relationships.
- Map current CRM-to-Audit E2E workflow.
- Identify duplicated or conflicting business logic in FE and BE.
- Record current known gaps: multi-standard certificate drafting, ISCC formatting retest, and UAT readiness by case.
- Create a capability matrix: existing, incomplete, duplicated, missing, obsolete.

Required outputs:

- `discovery/current-state-report.md`
- `discovery/module-inventory.csv`
- `discovery/api-inventory.md`
- `discovery/database-inventory.md`
- `discovery/workflow-state-inventory.md`
- `discovery/legacy-to-target-mapping.md`
- `architecture-decision-records/ADR-000-current-state-baseline.md`

Gate: human approval before target schema or destructive migration work.

### Phase 2 — Reference mining from Gauzy

**Goal:** Extract patterns without copying implementation blindly.

Tasks:

- Inspect Gauzy repository structure, apps, packages, modules, entities, API conventions, plugins, and deployment files.
- Record relevant patterns for tenancy, permissions, organizations, projects, tasks, documents, dashboards, integrations, and MCP.
- Record differences between Gauzy assumptions and CBQA requirements.
- Check the exact license files and dependency licenses before any code reuse.
- Build a decision table: adopt, adapt, reject, or defer.

Required outputs:

- `reference/gauzy-architecture-notes.md`
- `reference/gauzy-module-pattern-matrix.csv`
- `reference/gauzy-license-and-dependency-review.md`
- `architecture-decision-records/ADR-002-gauzy-adoption-boundary.md`

Gate: no direct source-code copy until Legal/management approval is recorded.

### Phase 3 — Platform foundation

**Goal:** Establish stable cross-cutting capabilities.

Build or stabilize:

- Keycloak integration.
- Internal and external login flows.
- Tenant and Master Tenant model.
- User, role, permission, and action authorization.
- Audit log and correlation IDs.
- Standard error contract.
- Request validation.
- Pagination, filtering, sorting, and export controls.
- File storage abstraction.
- Notification abstraction.
- Feature flags.
- Configuration validation.
- Health/readiness probes.
- OpenAPI contract generation.
- Background job and idempotency framework.

Exit criteria:

- Cross-tenant access tests pass.
- No endpoint returns data without an authorization decision.
- Auth behavior is covered for staff, external customer, expired token, invalid audience, and staging configuration.
- All mutations produce traceable audit events.

### Phase 4 — CRM and commercial foundation

**Goal:** Rebuild CRM as the upstream source for audit work.

Scope:

- Leads.
- Contacts and companies.
- Proposal.
- Proposal items/services.
- Standards and schemes.
- Scope and sectors.
- Sites and multi-site information.
- Audit methodology.
- Commercial status and pipeline.
- Sales/invoice relation.
- Client and certificate references.
- Proposal revision and approval.
- Project creation from approved proposal.
- Audit date and project details.

Important invariants:

- Proposal revisions preserve history.
- Approved proposal data cannot be silently changed.
- Audit date changes trigger controlled recalculation of downstream task dates.
- Methodology and multi-site data move from project editing into the approved proposal/audit methodology source of truth.
- Free-text and project-linked invoice flows remain distinguishable.

### Phase 5 — Audit workflow foundation

**Goal:** Implement the common lifecycle before standard-specific branching.

Scope:

- Application Review.
- Audit Scheduling.
- Auditor assignment.
- Audit execution/task tracking.
- Technical Review.
- Certification Decision.
- Certificate Issuance.
- Stage locking.
- Need Revision.
- Approval routing.
- Audit trail.
- Calendar and notifications.

Recommended state model:

```text
DRAFT
  → READY_FOR_APPLICATION_REVIEW
  → APPLICATION_REVIEW_IN_PROGRESS
  → READY_FOR_SCHEDULING
  → SCHEDULED
  → AUDIT_IN_PROGRESS
  → READY_FOR_TECHNICAL_REVIEW
  → TECHNICAL_REVIEW_IN_PROGRESS
  → READY_FOR_DECISION
  → DECISION_IN_PROGRESS
  → READY_FOR_ISSUANCE
  → CERTIFICATE_ISSUANCE_IN_PROGRESS
  → COMPLETED
```

Revision paths must be explicit, for example:

```text
TECHNICAL_REVIEW_IN_PROGRESS
  → NEED_REVISION
  → AUDIT_IN_PROGRESS or APPLICATION_REVIEW_IN_PROGRESS
```

The backend must return:

- Current stage.
- Completed stages.
- Allowed actions.
- Required fields.
- Required documents.
- Assigned role/person.
- Lock state.
- Revision history.
- Transition reasons.

### Phase 6 — Personnel, competency, and impartiality

**Goal:** Make assignment and independence rules reliable.

Scope:

- Internal/external personnel.
- Personnel qualifications.
- Competencies.
- Standard and sector mapping.
- Qualification validity and expiry.
- External rates.
- Auditor availability/calendar.
- Impartiality statement and conflict checks.
- Competency-based plotting and assignment.
- Assignment override with authorized reason.

Acceptance tests:

- Ineligible personnel cannot be assigned.
- Expired qualification blocks assignment.
- Sector mismatch blocks or flags assignment according to approved rule.
- Auditor/TR/MBV independence rules are enforced.
- Every manual override is auditable.

### Phase 7 — Standard-specific workflows

Implement common workflow first, then standard-specific policy modules.

#### ISO

- Auditor, TR, certification authority, reviewer/issuer roles.
- Standard and sector competency.
- Transfer, surveillance, recertification, upgrade, and extension scope.
- Three-year audit program.
- Certificate and scope rules.

#### ISCC

- GHG Expert.
- MB Verifier.
- Material mapping.
- Address/site mapping.
- GHG, ISCC EU waste, SAI FSA, and other custom fields.
- Finding severity and TR approval.
- Custom certificate numbering and formatting.

#### LVV

- Doc Review and Package Review merged where specified.
- Independent Validation and Verification.
- Opinion numbering.

#### LATIK

- Stage 1 and Stage 2.
- Audit Aplikasi/Infra/Keamanan naming.
- Stage 1 CAP optional.
- Stage 2 final TR.
- Accept/Reject decision.
- Numbering at Stage 2 Final Report.
- CAP 14-day rule.

#### Transfer Audit

- Detect Transfer Audit at proposal/project level.
- Enforce Transfer first.
- Prevent Surveillance/Recertification from bypassing Transfer.
- Allow certificate preparation in parallel where approved.
- Keep certificate data editable until issuance under controlled permission.

### Phase 8 — Documents, evidence, certificates, and exports

**Goal:** Make output generation controlled and reproducible.

Scope:

- Document metadata and versioning.
- Evidence upload/download permissions.
- Required-document rules by workflow and standard.
- PDF templates.
- XLSX exports.
- PPTX or management outputs where required.
- Certificate draft, review, approval, and issuance.
- Certificate numbering.
- Signature and signer metadata.
- Additional locations and SOA data.
- Audit report and audit summary.
- FAPP-01 through FAPP-08.

Controls:

- Store template version with each generated output.
- Store input snapshot or hash for reproducibility.
- Never overwrite an issued certificate file.
- Use private object storage and expiring signed URLs.
- Log who generated, reviewed, approved, downloaded, or replaced an output.
- Add visual regression tests for representative documents.

### Phase 9 — Dashboards, reports, and client view

**Goal:** Provide role-specific operational and executive visibility.

Dashboard modes:

- Executive/Management.
- Staff Operational.

Required concepts:

- Today Scheduled: My Schedule / All Schedule.
- Application Review throughput.
- Scheduler throughput.
- Auditor capacity.
- Technical Review capacity.
- Certification issuance capacity.
- SLA/throughput without misleading labels.
- Sales funnel: Leads, Proposal, Negotiation, Contract, Won, Project.
- Sales Achievement naming instead of ambiguous Total Revenue where approved.
- Client view showing certificate, sites, cycle, and related documents.

All metrics require a definition document before implementation.

### Phase 10 — Migration, coexistence, and rollout

**Goal:** Move from Audit-Q/current OneAlpha safely.

Strategy:

1. Freeze and document source mappings.
2. Build staging migration scripts with dry-run mode.
3. Validate row counts, relationships, status mappings, and files.
4. Run parallel-read comparison.
5. Migrate a pilot tenant or controlled client set.
6. Execute UAT cases C1–C9 and standard-specific cases.
7. Obtain sign-off from business owners.
8. Roll out by module/tenant/standard.
9. Keep rollback and reconciliation procedures available.

Migration rules:

- Never run migration against production without explicit approval.
- Every migration is versioned, repeatable, observable, and reversible where practical.
- Preserve source IDs in a mapping table.
- Preserve historical dates, actors, approvals, documents, and certificate references.
- Do not use fake seed data in production.
- Production URL and credentials must never appear in staging configuration.

---

## 6. Agent-harness operating model

The harness is an orchestrator, not an AI model runtime. It coordinates isolated agents and requires reviewable output for every task.

### 6.1 Required agent roles

| Role | Responsibility | Must not do alone |
|---|---|---|
| Architect | Boundaries, ADRs, data/workflow design | Approve its own production migration |
| Frontend | Angular/UI/routes/forms/stepper/guards | Invent backend workflow rules |
| Backend | APIs, services, entities, policies, events | Bypass authorization or migration gates |
| QA | Test strategy, automation, regression, UAT evidence | Mark a failed risk as passed |
| Reviewer | Clean code, security, correctness, scope review | Merge without required approvals |
| DevOps | CI/CD, environments, Docker, observability | Touch production without approval |
| Documentation | PRD, API, runbook, release notes, traceability | Alter requirements silently |

### 6.2 Agent execution sequence

```text
Task intake
  → Architect analysis
  → Backend/Frontend implementation
  → QA test execution
  → Reviewer inspection
  → Documentation update
  → Human approval gate
  → Merge/deploy action
```

### 6.3 Mandatory task packet

Every task given to an agent must include:

- Task ID.
- Business objective.
- In-scope modules.
- Out-of-scope modules.
- Source of truth/requirement references.
- Repository and branch/worktree.
- Dependencies.
- Acceptance criteria.
- Required tests.
- Protected paths.
- Approval level.
- Expected artifacts.

### 6.4 Mandatory agent output

Each completed task must produce:

- Summary of implementation.
- Files changed.
- Database/API changes.
- Tests executed and results.
- Screenshots or evidence for UI changes.
- Risks and unresolved issues.
- Migration/deployment impact.
- Follow-up tasks.

### 6.5 Approval levels

| Level | Examples | Approval |
|---|---|---|
| A0 | Read-only analysis, documentation, local tests | Agent may complete |
| A1 | Non-breaking code, unit tests, UI polish | Reviewer approval |
| A2 | API/schema changes, permissions, workflow transitions | Architect + Reviewer + QA |
| A3 | Migration, staging deployment, external integration | Human approval required |
| A4 | Production deployment, merge to protected branch, destructive action | Explicit human approval required |

No agent may:

- Push directly to protected branches.
- Merge its own PR.
- Apply an irreversible migration without approval.
- Use production credentials in a local or staging task.
- Change requirements without an ADR or approved task update.

---

## 7. Recommended harness directory and artifacts

```text
~/AI-Workspace/
├── harness/
├── projects/
│   ├── onealpha-frontend/
│   ├── onealpha-backend/
│   ├── onedatahub/
│   └── go-audit/
├── references/
│   └── ever-gauzy/
├── plans/
│   └── onealpha-gauzy-reference-agent-harness-plan.md
├── discovery/
├── architecture-decision-records/
├── contracts/
├── test-evidence/
├── migration/
├── runbooks/
└── reports/
```

Repository onboarding must be completed before implementation tasks are dispatched. The current harness context indicates that only the sandbox project is registered; real repositories therefore require explicit cloning/copying, health checks, and `AGENTS.md` setup.

---

## 8. Initial backlog for the harness

### Epic A — Harness readiness

- A-001 Verify disk, Git, Node, package managers, Docker, and GitHub CLI.
- A-002 Register each OneAlpha-related repository.
- A-003 Generate repository-specific `AGENTS.md`.
- A-004 Define protected branches and approval rules.
- A-005 Create task packet and result schema.
- A-006 Create local dashboard and monitoring checks.

### Epic B — Discovery

- B-001 FE module and route inventory.
- B-002 BE controller/service/entity inventory.
- B-003 Database and migration inventory.
- B-004 Keycloak/OneDatahub auth inventory.
- B-005 Go Audit boundary inventory.
- B-006 CRM-to-certificate workflow inventory.
- B-007 UAT case inventory C1–C9.

### Epic C — Gauzy reference

- C-001 Repository structure review.
- C-002 Tenant and permission pattern review.
- C-003 CRM/project/task pattern review.
- C-004 Document/report pattern review.
- C-005 Plugin/integration/MCP review.
- C-006 Deployment and observability review.
- C-007 License/dependency review.

### Epic D — Platform foundation

- D-001 Tenant context and query scoping.
- D-002 Permission/action policy layer.
- D-003 Audit log and correlation IDs.
- D-004 API error/validation/pagination standards.
- D-005 File storage abstraction.
- D-006 Idempotent job framework.
- D-007 Contract and integration test foundation.

### Epic E — CRM

- E-001 Lead/contact/company model.
- E-002 Proposal and proposal item model.
- E-003 Standard/scheme/sector/scope model.
- E-004 Audit methodology and multi-site model.
- E-005 Proposal revision and approval.
- E-006 Project creation from approved proposal.
- E-007 Audit date and downstream task generation.

### Epic F — Audit Platform

- F-001 Common audit case and stage model.
- F-002 Application Review.
- F-003 Scheduling and competency plotting.
- F-004 Auditor/task execution.
- F-005 Technical Review.
- F-006 Decision.
- F-007 Certificate issuance.
- F-008 Need Revision and stage lock.
- F-009 Transfer Audit precedence.

### Epic G — Standard policy modules

- G-001 ISO.
- G-002 ISCC.
- G-003 LVV.
- G-004 LATIK.
- G-005 Multi-standard certificate drafting.

### Epic H — Documents and reporting

- H-001 FAPP-01–08.
- H-002 Certificate templates and numbering.
- H-003 Evidence storage and versioning.
- H-004 Audit report and summary.
- H-005 Executive dashboard.
- H-006 Operational dashboard.
- H-007 Client view.

### Epic I — Migration and rollout

- I-001 Source-to-target mapping.
- I-002 Dry-run migration.
- I-003 Reconciliation reports.
- I-004 Parallel-read comparison.
- I-005 Pilot rollout.
- I-006 C1–C9 UAT.
- I-007 Production rollout and rollback runbook.

---

## 9. Quality strategy

### Test pyramid

- Unit tests for policies, state transitions, calculations, mappings, and validators.
- Integration tests for database, authorization, Keycloak, OneDatahub, storage, and queues.
- API contract tests for FE/BE and external integrations.
- E2E tests for CRM-to-certificate workflows.
- Permission matrix tests for every role and transition.
- Migration tests with fixtures and rollback/dry-run behavior.
- Visual regression tests for critical screens and generated documents.
- Performance tests for dashboards, client search, certificate search, and bulk operations.
- Security tests for tenant isolation, IDOR, file access, token validation, CSRF/CORS, SSRF, and secret exposure.

### Mandatory E2E scenarios

- Standard ISO initial certification.
- Standard ISCC with GHG/MBV roles.
- LVV flow.
- LATIK Stage 1 and Stage 2.
- Integrated/Combined Audit.
- Multi-site proposal and audit.
- Transfer Audit before Surveillance/Recertification.
- Need Revision from TR back to the responsible stage.
- External auditor with competency and rate.
- Unauthorized cross-tenant access attempt.
- Certificate draft, review, correction, approval, and issuance.
- Audit date revision without duplicate task creation.

### UAT baseline

Use the existing C1–C9 cases as the initial regression baseline. Current context indicates C1 and C5 are closest to UAT readiness, C9 requires ISCC formatting retest, and C2–C4/C6–C8 require multi-standard certificate-drafting enhancement. The harness must preserve these statuses and update them only with evidence.

---

## 10. Security and compliance gates

- Secrets must come from environment/secret management, never committed files.
- Production and staging identity providers must be separated by configuration and validation.
- Every tenant-scoped query must have automated isolation tests.
- Certificate and evidence files must be private by default.
- File downloads use authorization checks and expiring URLs.
- Sensitive audit data must not be sent to third-party models without explicit policy approval.
- MCP tools must default to read-only and use allowlisted actions.
- Agent prompts must not contain credentials, tokens, or raw production data.
- Dependency licenses must be scanned before reuse of Gauzy code or packages.
- Security vulnerabilities must be triaged separately from ordinary feature issues.
- All production changes require a rollback plan and release record.

---

## 11. Delivery milestones

### Milestone 1 — Baseline ready

Deliverables: harness onboarding, repository map, discovery reports, Gauzy reference matrix, ADRs.

### Milestone 2 — Foundation ready

Deliverables: tenant context, authorization, audit log, API standards, storage abstraction, test foundation.

### Milestone 3 — CRM-to-project ready

Deliverables: leads through approved proposal and project/audit-date task generation.

### Milestone 4 — Common audit flow ready

Deliverables: AR → Scheduling → Audit → TR → Decision → Issuance with locks, revisions, permissions, and audit trail.

### Milestone 5 — Standard workflows ready

Deliverables: ISO, ISCC, LVV, LATIK, Transfer Audit, and multi-standard rules.

### Milestone 6 — Output and dashboard ready

Deliverables: evidence, certificates, reports, dashboards, client view, export tests.

### Milestone 7 — Migration and UAT ready

Deliverables: dry-run migration, reconciliation, C1–C9 evidence, pilot sign-off, rollout runbook.

### Milestone 8 — Production rollout

Deliverables: approved release, backup/restore verification, monitoring, rollback readiness, operational handover.

---

## 12. Definition of Done

A feature is done only when:

- Requirement and scope are traceable.
- Backend invariants are implemented.
- Frontend uses backend-provided permissions and workflow state.
- Database changes have migration and rollback consideration.
- Tenant isolation is tested.
- Unit/integration/API/E2E tests appropriate to risk pass.
- Reviewer has inspected changed files and security impact.
- Documentation and runbooks are updated.
- Staging deployment is repeatable.
- UAT evidence is attached.
- No unresolved critical/high-risk item is hidden in the summary.
- Human approval is obtained for the applicable level.

---

## 13. First execution command for the harness

The first harness task should be discovery only:

```text
Task: ONEALPHA-DISCOVERY-001
Objective: Build a read-only current-state inventory for OneAlpha CRM, Audit Platform, OneDatahub, and Go Audit, then compare it with Ever Gauzy patterns.
Mode: Read-only; no code changes; no migrations; no deployment.
Agents: Architect lead, Backend, Frontend, QA, Reviewer, Documentation.
Required outputs:
  - current-state-report.md
  - module-inventory.csv
  - api-inventory.md
  - database-inventory.md
  - workflow-state-inventory.md
  - gauzy-module-pattern-matrix.csv
  - ADR-002-gauzy-adoption-boundary.md
Approval: Human review before implementation planning.
```

The second task should implement only the platform foundation after the first task is approved. Do not begin a full rebuild by generating all modules in parallel; first stabilize the domain model, workflow state machine, permissions, and migration strategy.

---

## Final recommendation

Use Gauzy as a **design and engineering reference**, not as a drop-in replacement. The safest rebuild path is:

```text
Discover current OneAlpha
  → Extract Gauzy patterns
  → Approve architecture boundaries
  → Stabilize foundation
  → Rebuild CRM upstream
  → Rebuild common Audit lifecycle
  → Add ISO/ISCC/LVV/LATIK policies
  → Add documents/certificates/reports
  → Migrate and validate C1–C9
  → Roll out incrementally
```

This preserves the business value already encoded in OneAlpha while using Gauzy to improve platform architecture, extensibility, multi-tenancy, generic modules, reporting, and future agent/MCP integration.
