# Prototype review surfaces on agents.nexoratech.co

**Date:** 2026-09-17 · **Host:** `31.97.67.241` (`dev-kemenkes`) · **Requested by:** owner

Three prototype apps published behind Basic Auth so management can review them
at a live URL:

| URL | Repo (`dev`) | HEAD at publish |
|---|---|---|
| `/academy/` | `NexoraTechTeam/academy` | `b890da7` |
| `/accreditation/` | `NexoraTechTeam/accreditation` | `afbc668` |
| `/servicedesk/` | `NexoraTechTeam/service-desk` | `512c4ed` |

Artefacts: `ops/prototypes/{README.md,refresh.sh,verify.sh}`; vhost block in
`ops/nginx/agents.nexoratech.co.conf`.

## Why paths, not the `dev-*` hostnames that were asked for

The owner first asked where `dev-academy` / `dev-accreditation` /
`dev-servicedesk.nexoratech.co` should live. Searching Notion and Slack settled
that question: the only record anywhere is the owner's own unanswered Slack
message to Rafli Putra (`#daily-updates`, 2026-09-17 16:02, thread
`1789619609.679089`), and all three names resolve `NXDOMAIN`. The
ENVIRONMENT-REGISTER (v2.4) does not contain them and only knows the older
`*-dev.nexoratech.co` pattern.

Rather than block on DNS and an unanswered question, the three apps were
published as paths under `agents.nexoratech.co`, which already has a
certificate, Basic Auth and a proven vhost. No DNS record, no new certificate,
nothing else on the shared host touched.

Cost of moving to real hostnames later: three A records to `31.97.67.241`,
three certbot runs, three small vhosts, and a `service-desk` rebuild with
`--base=/`. The other two artefacts are base-path independent.

## Access path — three dead ends before a live one

1. **Anonymous clone** — repos were private; `git ls-remote` failed.
2. **Deploy keys** — generated three, then GitHub showed *"Deploy keys —
   Disabled by NexoraTechTeam"* at org level, with a recommendation to use
   GitHub Apps. Keys removed again (`/root/.ssh/nexora-deploy`,
   `config.d-nexora`), nothing left behind.
3. **OAuth connector** — authorised on claude.ai but never registered in the
   CLI session; only `authenticate` / `complete_authentication` were ever
   exposed, never the real tools.
4. **What worked** — the owner made all three repos public. No credential is
   involved in the build at all.

Two credentials were pasted into chat during this (a GitHub account password
with a TOTP code, then a PAT). Neither was used and neither was stored; both
were flagged for revocation. `CLAUDE.md` §9 already lists three credentials
awaiting rotation for the same reason.

The Basic Auth credential created here was therefore generated on the server
and written only to `/root/prototypes-basic-auth.txt` (`0600`); the bcrypt hash
is in `/etc/nginx/.prototypes.htpasswd` (`root:www-data`, `0640`). It never
entered a transcript.

## Build

- **academy** — `lsp-unified-app.html`, 620 088 bytes, self-contained. Copied,
  no build. (The live `academy-test.nexoratech.co` serves an *older* copy,
  573 420 bytes, different md5 — left untouched.)
- **accreditation** — `npm run build:standalone` in `nexaccred-react`, which
  uses `vite-plugin-singlefile` to inline everything → 318 254 bytes. Chosen
  over the ordinary build because that one expects `nexaccred-api` on
  `localhost:3001`; the standalone entry point carries sample data and needs no
  backend.
- **service-desk** — `npx vite build --base=/servicedesk/`, 1 581 modules,
  295 967-byte bundle. Tailwind's CDN script vendored to `public/tailwind.js`
  (407 279 bytes) first.

## nginx

Three `location ^~` blocks plus three exact-match redirects, inserted before
the `/` catch-all in the `:443` server. `root /var/www/prototypes` rather than
`alias`, since directory names match the URL prefixes.

Procedure each time: edit `ops/nginx/agents.nexoratech.co.conf` →
`validate_vhost.py` → `ops/nginx/tests` → copy to
`/etc/nginx/sites-available/` → `nginx -t` → `systemctl reload nginx`. Never
restarted. Pre-change copy at `/root/agents.nexoratech.co.bak.20260917-181733`;
artefact and live file verified identical before and after.

## Five defects caught before or during publish

**Two `location /` blocks, not one.** The first insertion attempt asserted a
single catch-all and aborted: there is one in the `:80` redirect server and one
in `:443`. Blind insertion would have replaced the HTTP→HTTPS redirect.

**`'unsafe-eval'` rejected by an existing test.** The first CSP draft included
it; `test_inline_svg_favicon_is_allowed_but_nothing_wider` asserts the string
appears nowhere in the file. Rather than weaken the test, the need was removed
— grepping all three bundles found no `eval(` or `new Function(`, and a browser
load confirmed all three run without it. The vendored Tailwind JIT does not
need it either.

**SPA fallback answered `200 text/html` for a missing `.js`.** Caught by a
deliberate request for a non-existent asset — the same shape as the
`/automation/assets/*.js` failure in
`2026-09-17-cloud-ops-nginx-ratelimit-fix.md`. Fixed with a nested regex
location doing `try_files $uri =404`. The probe is now permanent in
`verify.sh`.

**CSP blocked academy's fonts — and this time CSP really was the cause.**
`ops/nginx/README.md` warns it was falsely blamed three times. Here a static
grep of `lsp-unified-app.html` found no external references, yet headless
chromium reported a CSP-blocked request to `fonts.googleapis.com`: the bundle
injects the stylesheet at *runtime*. Only the browser step could have found it.
`/academy/` and `/accreditation/` now permit `fonts.googleapis.com` and
`fonts.gstatic.com`; nothing else is relaxed.

**`add_header` replaces rather than accumulates.** Any `add_header` in a
location discards the entire inherited set, so all six headers are restated in
each block. The nested asset locations declare none on purpose and inherit —
confirmed 6 of 6 present on `/servicedesk/tailwind.js`.

## Verification

`ops/prototypes/verify.sh` — all checks pass. Per app: `401` unauthenticated,
`200 text/html` authenticated, every referenced asset returns its own content
type (`application/javascript`, not `text/html`), absent assets `404`. Plus:
the prototype credential is refused at `/` (401), and the Command Center, n8n
and `academy-test.nexoratech.co` answer exactly as before.

Headless chromium, 1440×900, per app — academy: 52 nodes, heading *"Explore
training and verified talent on DeAcademy"*; accreditation: 83 nodes, heading
*"NEXACCRED"*; servicedesk: 75 nodes, heading *"NexServe"*. Zero console
errors, zero failed requests, screenshots reviewed and all three fully styled.

Test suites after the change: `tests` 291, `ops/harness` 11, `ops/nginx` 14,
`ops/n8n` 10 — all green.

## Open items

- **Revoke the PAT and rotate the GitHub account password** pasted into chat.
- The three repos are **public**. That was the owner's change and it is what
  makes the build credential-free; it is worth a conscious decision whether
  they stay that way.
- `dev-*` hostnames and their VPS assignment are still unanswered by Rafli.
- `/var/www/deacademy` (`academy-test.nexoratech.co`) still serves an older
  build of the same app. Two copies of academy now exist on this host; decide
  whether `academy-test` is retired or re-pointed.
- These are prototypes with no security review. Basic Auth is the floor.

## Rollback

Delete the delimited block from `ops/nginx/agents.nexoratech.co.conf`, copy to
`/etc/nginx/sites-available/agents.nexoratech.co`, `nginx -t`, then
`systemctl reload nginx`. `/var/www/prototypes/` may stay; nothing routes to it
once the block is gone.
