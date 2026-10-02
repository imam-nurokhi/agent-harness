# Session log: clone AI-Workspace VPS → lokal (2026-09-22)

- Sumber: `/home/ahagent/AI-Workspace/` (210MB/3655 file) + `/home/ahagent/ask-nexai/`
  di `31.97.67.241` → `/Users/user/AI-Workspace/` (+ subdir baru `ask-nexai/`).
- Metode: `rsync -avz --update` (newer-wins), exclude `__pycache__/`, `*.pyc`,
  `.DS_Store`. Tanpa `--delete` (tidak ada file lokal yang dihapus).
- Hasil: ±2347 file baru, 29 file lama tertimpa. Spot-check md5 6 file kunci
  (plan md, exec report, ask-nexai CLAUDE.md, helper, test, settings) cocok VPS↔lokal.
- `.gitignore`: tambah `ask-nexai/.opencode-env`, `ask-nexai/.ai-provider.json`
  (kredensial ikut terclone tapi tidak masuk git; `.env` memang sudah ter-ignore).
- PERHATIAN: `.env` lokal (minimal, 1 key) tertimpa versi VPS (penuh);
  `agents/triggers.json` (modifikasi lokal) tertimpa versi VPS yang lebih baru;
  `agents/.telegram/config.json` + `watch.json` (runtime state lokal) tertimpa
  versi VPS. Backup pra-sync: `/tmp/aiws-clone-backup-20260922020059/` (29 file).
- Rollback: `git checkout -- <file>` untuk tracked;
  `cp -p /tmp/aiws-clone-backup-20260922020059/<path> /Users/user/AI-Workspace/<path>`
  untuk untracked (termasuk `.env`).
- Test harness tidak dijalankan di lokal (path absolut `/home/ahagent/...`).
