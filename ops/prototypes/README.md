# Prototype review surfaces — academy / accreditation / service-desk

Three prototype apps published behind Basic Auth so management can review them
at a live URL. Requested and decided by the owner on 2026-09-17; published the
same day.

| URL | Repo (branch `dev`) | Shape |
|---|---|---|
| `https://agents.nexoratech.co/academy/` | `NexoraTechTeam/academy` | single self-contained HTML, no build |
| `https://agents.nexoratech.co/accreditation/` | `NexoraTechTeam/accreditation` | Vite `build:standalone` → one inlined HTML |
| `https://agents.nexoratech.co/servicedesk/` | `NexoraTechTeam/service-desk` | Vite build, `--base=/servicedesk/` |

Credential: user `nexora-mgmt`, hash in `/etc/nginx/.prototypes.htpasswd`
(bcrypt, `root:www-data` `0640`). The password lives **only** in
`/root/prototypes-basic-auth.txt` (`0600`) and was deliberately never written
into a chat transcript — `CLAUDE.md` §9 lists three credentials awaiting
rotation for exactly that reason.

This credential is **not** the Command Center's. `auth_basic` is overridden per
location, so a reviewer holding it gets the three prototypes and is still
challenged at `/` and `/automation/`. That separation is asserted in
`verify.sh`.

## Why paths on an existing host, not `dev-*` hostnames

`dev-academy` / `dev-accreditation` / `dev-servicedesk.nexoratech.co` were
`NXDOMAIN` and the Slack thread asking Rafli which VPS should own them
(2026-09-17, `#daily-updates`) was never answered. Paths under an already
working, already certificated vhost needed no DNS record and no new
certificate, so the review could start immediately.

Moving to real hostnames later means three A records to `31.97.67.241`, three
certbot runs, and three small vhosts — the built artefacts under
`/var/www/prototypes/` do not change, except that `service-desk` must be
rebuilt with `--base=/` since it would then be served from a root.

## Layout

```
/opt/nexora-prototypes/src/{academy,accreditation,service-desk}   clones + node_modules
/var/www/prototypes/{academy,accreditation,servicedesk}/          what nginx serves
ops/prototypes/refresh.sh                                         rebuild + republish
ops/prototypes/verify.sh                                          prove it works
```

nginx config lives in `ops/nginx/agents.nexoratech.co.conf` (the source of
truth for the whole vhost), in a clearly delimited block before the `/`
catch-all.

## Refresh

```sh
ops/prototypes/refresh.sh                 # all three, then verify
ops/prototypes/refresh.sh service-desk    # one
```

The repos are **public**, so no credential is involved. Note that
NexoraTechTeam policy disables deploy keys org-wide (GitHub steers to GitHub
Apps instead), so if these repos are ever made private again, the fix is a
fine-grained read-only token in `.env` — not a deploy key.

## Four things that would have broken this, and did not

**The subpath asset trap.** A default Vite build references `/assets/index-*.js`
at the *server root*, where the Command Center answers — the browser gets
`200 text/html` for a JS URL, `nosniff` refuses to execute it, and the page is
blank. This is the same failure that took `/automation/` down. `service-desk`
is therefore built with `--base=/servicedesk/`; `verify.sh` re-checks the
content type of every referenced asset on every run.

**The SPA fallback hiding 404s.** `try_files ... /index.html` cheerfully
answered `200 text/html` for a missing `.js`. A nested regex location now makes
static assets `404` instead. The negative probe that caught this is kept in
`verify.sh`.

**`add_header` does not accumulate.** A location that declares any
`add_header` silently discards every inherited one. All six headers are
restated in each of the three blocks. The nested asset locations deliberately
declare none, so they inherit the full set — verified, 6 of 6 present.

**CSP, which this time really was the culprit.** `ops/nginx/README.md` warns
that CSP was falsely blamed three times. Here it genuinely bit twice:
`service-desk` loads `cdn.tailwindcss.com` (now vendored into the bundle, so
`script-src 'self'` still holds), and `academy` injects a Google Fonts
stylesheet *at runtime* — invisible to a static grep, and only a real browser
load revealed it. `/academy/` and `/accreditation/` allow
`fonts.googleapis.com` and `fonts.gstatic.com`; nothing else is relaxed, and
`'unsafe-eval'` appears nowhere (`ops/nginx/tests/` asserts this file-wide).

## Verification standard

`verify.sh` is the gate and must stay green:

```sh
ops/prototypes/verify.sh
```

It checks auth, content types of real assets, `404` for absent ones, that the
prototype credential cannot reach `/`, and that the Command Center, n8n and
`academy-test.nexoratech.co` still answer as before.

Status-only checks are not sufficient and never were. Each app was also loaded
in headless chromium with console errors and failed requests captured: all
three render, zero console errors, zero failed requests.

## Rollback

Remove the delimited block from `ops/nginx/agents.nexoratech.co.conf`, then:

```sh
cp ops/nginx/agents.nexoratech.co.conf /etc/nginx/sites-available/agents.nexoratech.co
nginx -t && systemctl reload nginx        # never restart; the host is shared
```

A pre-change copy of the vhost is at `/root/agents.nexoratech.co.bak.*`.
`/var/www/prototypes/` can be left in place; nothing routes to it afterwards.
