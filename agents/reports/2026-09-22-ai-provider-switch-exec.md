# Laporan Eksekusi: AI Provider Switch (Claude ↔ OpenAgentic)

- **Tanggal:** 2026-09-22 ~18:00–18:20 WIB (server UTC 11:xx)
- **Plan:** `docs/2026-09-22-ai-provider-switch-opencode-plan.md` (disetujui owner via OK)
- **Prinsip:** default = Claude persis seperti sekarang; OpenAgentic hanya aktif
  saat `/pakai opencode`. `@AgentNexoraBot` tidak disentuh.

## Yang dikerjakan (§6 langkah 0–6)

| Langkah | Hasil |
|---|---|
| 0. Backup + md5 baseline | `ask-nexai/CLAUDE.md.bak.20260921181107`, `asknexai-settings.json.bak.20260921181107` — md5 cocok dengan aslinya (tanpa drift) |
| 1. State global | `/home/ahagent/ask-nexai/.ai-provider.json` → `{"provider":"claude",...}` (default, nol-perubahan perilaku) |
| 2. Key file khusus | `/home/ahagent/ask-nexai/.opencode-env` 0600 ahagent, hanya 2 var (disalin dari `.env`; workspace `.env` tetap tidak di-source ke sesi) |
| 3. Helper + test | `ask-nexai/bin/ask-opencode` (0755, stdlib only, model hardcode, key tak pernah ke stdout) + `ops/harness/tests/test_ask_opencode.py` |
| 4. Settings | tambah 2 allow path-scoped (`Bash(.../bin/ask-opencode *)`, `Write(.../.ai-provider.json)`); deny lain utuh; JSON valid |
| 5. CLAUDE.md | tambah blok "Pilihan AI" (perintah `/pakai claude`, `/pakai opencode`, `/provider`, owner-only `6687943152`, fallback jujur) |
| 6a. Unit test | **7/7 OK** (request shape, auth header, fallback model, error code 2, settings sempit, default claude). Satu bug riil ditemukan test (exception non-HTTP lolos) dan diperbaiki |
| 6b. Live probe helper | request lolos auth (**bukan 401**) tapi upstream jawab **HTTP 502 `proxy_error`: "AI service temporarily unavailable"** (2x, selang 20 dtk). `/models` dengan key yang sama → **200, 39 model, `muse-spark-1.3-free` ada**. Kesimpulan: plumbing + key benar, sisi completion OpenAgentic sedang gangguan |
| Restart sesi | tmux `tgchannel` di-restart (kill + new, perintah identik, `auto`, settings baru). Sesi baru hidup (`claude --channels`, auto mode on). Instruksi + settings baru aktif mulai sesi ini |
| Bot lama | `tgbot.py` PID 555643 (sejak 09:53) **tidak di-restart**; `getMe` → `AgentNexoraBot` OK. 0 gangguan |

## Perilaku saat ini

- `/provider` (atau chat biasa) → `provider=claude` → jawaban persis seperti sebelum perubahan.
- `/pakai opencode` → helper dipanggil; **selama upstream 502, sesi fallback ke Claude + bilang jujur** (sesuai desain). Saat upstream pulih, jawaban datang dari `muse-spark` tanpa perubahan apa pun di sisi kita.
- Chat non-owner kirim `/pakai ...` → ditolak, state tidak berubah.

## Menunggu owner dari HP (Telegram e2e)

1. `/provider` → harus jawab `claude`
2. `/pakai opencode` → konfirmasi pindah
3. Tanya 1 soal produk → (saat ini: jawaban Claude + kalimat fallback jujur)
4. `/pakai claude` → konfirmasi kembali
5. Cek `@AgentNexoraBot` (`/status`) tetap normal

## Restore (bila tidak sesuai — kembalikan persis ke sebelum eksekusi)

```sh
cp -p /home/ahagent/ask-nexai/CLAUDE.md.bak.20260921181107 /home/ahagent/ask-nexai/CLAUDE.md
cp -p /home/ahagent/AI-Workspace/ops/channels/asknexai-settings.json.bak.20260921181107 /home/ahagent/AI-Workspace/ops/channels/asknexai-settings.json
rm -rf /home/ahagent/ask-nexai/bin /home/ahagent/ask-nexai/.ai-provider.json /home/ahagent/ask-nexai/.opencode-env /home/ahagent/AI-Workspace/ops/harness/tests/test_ask_opencode.py /home/ahagent/AI-Workspace/ops/harness/tests/__pycache__
sudo -u ahagent -H tmux kill-session -t tgchannel
sudo -u ahagent -H tmux new-session -d -s tgchannel -x 200 -y 50 -c /home/ahagent/ask-nexai claude --channels plugin:telegram@claude-plugins-official --permission-mode auto --settings /home/ahagent/AI-Workspace/ops/channels/asknexai-settings.json --add-dir /opt/nexora-prototypes/src/accreditation /opt/nexora-prototypes/src/academy
```

Setelah restore: tidak ada referensi ke file baru dari file mana pun, sesi
kembali murni Claude, `tgbot.py` tidak pernah tersentuh sejak awal.

## Catatan

- Drift runbook: sesi aktual `auto` + cwd `ask-nexai` (README menyebut `manual`).
  Tidak diubah dalam task ini; layak disinkronkan terpisah.
- Contoh curl user ada typo kutip (`free”`) — diperbaiki di helper.
