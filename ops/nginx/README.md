# ops/nginx — agents.nexoratech.co

Reviewed nginx artefacts for the shared VPS **31.97.67.241**. Before this pass
the vhost and its rate-limit zone existed **only on the host**: no artefact to
review, no test, no change record. These files close that gap.

> This host is shared with `dev-kemenkes`, `dev-support`, `monitoring` and other
> vhosts. Nothing here touches them. The only production files this directory
> owns are the two named below.

## Files

| File | Deploys to |
|---|---|
| `agents-rate-limit.conf` | `/etc/nginx/conf.d/agents-rate-limit.conf` |
| `agents.nexoratech.co.conf` | `/etc/nginx/sites-available/agents.nexoratech.co` |
| `validate_vhost.py` | not deployed — gate run before deploying |
| `verify_rate_limit.sh` | not deployed — external probe, no credentials needed |
| `tests/test_validate_vhost.py` | not deployed |

## Why these values

**Every number below is measured, not estimated.** One cold load of the n8n
editor through this vhost logs **797 requests** (2026-09-17, chromium headless,
empty cache; 794 of them `200`). Two earlier passes on this same outage sized
the limits from a guess of "40+ chunks" and the editor stayed blank both times.

| | before | after | why |
|---|---|---|---|
| zone `rate` | `60r/m` | `50r/s` | `60r/m` refills 1 r/s; one cold load needs 797. `50r/s` carries a full load every 16s. |
| `burst` | `200` | `1200` | the reservoir must absorb one whole cold load or a hard refresh is cut off part-way |
| `limit_conn` | `10` | `256` | under HTTP/2 nginx counts each **stream** as a connection |
| `http2_max_concurrent_streams` | (default) | `128` pinned | `limit_conn` is meaningless unless this is stated |

Measured, one editor load each: `limit_conn 10` → 629 × `503`; `limit_conn 64`
→ 407 × `503`; `limit_conn 256` → 0, editor renders.

The dashboard chip froze on `connecting…` because `dash.js` itself was refused
(`bin/lib/dash.html:20` ships that literal text; only `dash.js` ever replaces
it). `/automation/` blanked for two further reasons — see below.

The vhost also now forwards `Upgrade`/`Connection` to n8n, which it never did;
without them the editor's push channel cannot establish. `$agents_connection_upgrade`
is mapped from `$http_upgrade` so plain HTTP requests are unaffected.

`proxy_pass http://127.0.0.1:5678/` **must keep the trailing slash**, so the
`/automation/` prefix is stripped before the upstream. Verified against the
running container (n8n 2.39.6) on 2026-09-17:

```
GET 127.0.0.1:5678/assets/index-DbGpghR9.js             200 text/javascript  890935 B
GET 127.0.0.1:5678/automation/assets/index-DbGpghR9.js  200 text/html         56733 B  <- SPA catch-all
```

n8n 2.x serves its bundles from the **server root** and no longer mounts them
under `N8N_PATH`; `N8N_PATH` only still sets the prefix the HTML *references*.
Keep the prefix and every asset resolves to `index.html`, which `nosniff` then
stops the browser executing — a blank white editor. An earlier handoff in this
repo asserted the exact opposite; `tests/test_validate_vhost.py` now pins the
verified behaviour so that claim cannot come back.

`location = /automation` must redirect to `/automation/`: `^~ /automation/`
does not match the bare URL, which would otherwise hit the dashboard upstream.

## Gate

```sh
python3 -m unittest discover -s ops/nginx/tests
python3 ops/nginx/validate_vhost.py \
    ops/nginx/agents-rate-limit.conf ops/nginx/agents.nexoratech.co.conf
```

Run the validator against the **live** files too, before and after deploying —
it is what caught both defects here.

## Deploy

```sh
TS=$(date -u +%Y%m%dT%H%M%SZ)
cp -p /etc/nginx/conf.d/agents-rate-limit.conf      "/etc/nginx/conf.d/agents-rate-limit.conf.bak-${TS}-rate"
cp -p /etc/nginx/sites-available/agents.nexoratech.co "/etc/nginx/sites-available/agents.nexoratech.co.bak-${TS}-ws"

install -m 0644 -o root -g root ops/nginx/agents-rate-limit.conf      /etc/nginx/conf.d/agents-rate-limit.conf
install -m 0600 -o root -g root ops/nginx/agents.nexoratech.co.conf   /etc/nginx/sites-available/agents.nexoratech.co

nginx -t && systemctl reload nginx     # reload, never restart
./ops/nginx/verify_rate_limit.sh       # must print PASS: 0/240 rate-limited

# with credentials, also checks the assets are not served as index.html:
AUTH=user:pass ./ops/nginx/verify_rate_limit.sh
```

## Rollback

```sh
cp -p /etc/nginx/conf.d/agents-rate-limit.conf.bak-<TS>-rate       /etc/nginx/conf.d/agents-rate-limit.conf
cp -p /etc/nginx/sites-available/agents.nexoratech.co.bak-<TS>-ws  /etc/nginx/sites-available/agents.nexoratech.co
nginx -t && systemctl reload nginx
```

Backups from this pass, oldest first: `…bak-20260917T113952Z-rate` (zone),
`…bak-20260917T113952Z-ws` (vhost before the Upgrade headers),
`…bak-20260917T124046Z-prefix` (vhost before the prefix fix).
Earlier rungs (`…bak-20260917-ratelimit`, `…bak-20260917-n8n`) stay in place.

## Known, not changed here

- `client_max_body_size 256k` applies to `/automation/` too. Large n8n workflow
  imports or saves will fail with `413`. Raise it deliberately, with a test,
  when that becomes real — it was not part of the reported outage.
- The `Content-Security-Policy` is strict and that is **fine**. Both pages were
  loaded in a headless browser against production under exactly this policy:
  the dashboard reports **0** violations and **0** JS errors, the editor
  renders with exactly one violation — Vite's
  `import 'data:text/javascript,…'` modern-browser probe, which Vite catches
  itself. The only widening ever applied is `img-src 'self' data:`, for the
  dashboard's inline-SVG favicon. **Do not loosen the CSP because a page looks
  blank** — that was the rate limit, the `/automation/` prefix and `limit_conn`,
  never the CSP.
