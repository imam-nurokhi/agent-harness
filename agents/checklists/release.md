# Release / Staging Checklist

Run before any deploy. A "no" anywhere stops the release.

## Pre-flight
- [ ] All acceptance criteria for every included task are ticked
- [ ] CI green on the exact commit being deployed
- [ ] Branch up to date with the target branch; conflicts resolved
- [ ] Code review completed; no CRITICAL or HIGH findings open

## Verification
- [ ] Test suite run locally and passing — paste the summary line
- [ ] Build succeeds from a clean checkout
- [ ] Migrations tested against a copy of staging data, and rollback verified

## Safety
- [ ] Database backed up, with the restore command written down
- [ ] Secrets present in the target environment; none added to the repo
- [ ] Feature flag or rollback path exists for the risky part
- [ ] Someone is available to watch logs after deploy

## After
- [ ] Smoke-test the critical user flow by hand
- [ ] Error rate and latency checked for 15 minutes
- [ ] Changelog updated
- [ ] Task closed with a link to the deployed commit
