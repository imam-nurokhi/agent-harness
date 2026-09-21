# Plan: AI Provider Switch (Claude ↔ OpenAgentic) di @AskNexAIBot

- **Tanggal:** 2026-09-22
- **Host:** `31.97.67.241` (VPS bersama)
- **Status:** EXECUTED 2026-09-22 ~18:00–18:20 WIB (disetujui owner via OK).
  Laporan detail: `agents/reports/2026-09-22-ai-provider-switch-exec.md`
- **Scope disetujui:** switch dipasang di `@AskNexAIBot` saja, **satu setting global**

## 1. Tujuan & batasan scope

1. Menambah opsi jawab via **OpenAgentic** (`openagentic/muse-spark-1.3-free`,
   OpenAI-compatible `POST {BASE}/chat/completions`) untuk tanya-jawab produk
   NexAccred & DeAcademy di `@AskNexAIBot`.
2. **Default = perilaku persis seperti sekarang** (Claude Team via sesi Channels).
   Jalur OpenAgentic **hanya aktif** bila switch global dipindah ke `opencode`
   lewat perintah switch. Tidak ada perubahan perilaku default.
3. `@AgentNexoraBot` (`bin/lib/tgbot.py`, 39 command) **tidak disentuh sama sekali**:
   tidak ada file-nya yang diubah, prosesnya tidak di-restart.
4. Setiap perubahan yang dikerjakan **bisa di-restore** ke kondisi persis
   sebelum eksekusi (§5). Backup dibuat SEBELUM eksekusi (§6 langkah 0).

## 2. Kondisi sekarang (terverifikasi langsung di host, 2026-09-22)

| Item | Fakta |
|---|---|
| `@AgentNexoraBot` | proses `python3 .../bin/lib/tgbot.py` jalan (ahagent). Tidak via systemd di host ini |
| `@AskNexAIBot` | tmux `tgchannel` (ahagent), cwd `/home/ahagent/ask-nexai`, `claude --channels ... --permission-mode auto --settings .../ops/channels/asknexai-settings.json --add-dir accreditation --add-dir academy` |
| Permission sesi | `allow`: Read, Grep, Glob, TodoWrite. `deny`: Bash, Write, Edit, WebFetch/WebSearch, Task, Read `**/.env`, Read workspace/.claude/.ssh/root/etc/var, semua MCP (kecuali plugin telegram). Artinya sesi **tidak bisa panggil API apa pun hari ini** |
| `.env` workspace | `OPENCODE_BASE_URL` (29 char) + `OPENCODE_API_KEY` (67 char) **ada tapi tidak dipakai kode mana pun** (grep kosong) |
| OpenAgentic API | **Live**, OpenAI-compatible (probe `/models` tanpa key valid → 401 JSON `authentication_error` yang proper). Model `muse-spark-1.3-free` ada di daftar model live (konteks 1M, output 64K) |
| opencode.json root | provider `openagentic` sudah ter-inject (38 model). ahagent belum punya config opencode — tidak relevan untuk plan ini |
| Catatan | Contoh curl user ada typo kutip: `"model": "openagentic/muse-spark-1.3-free”` (kutip tutup tipografis) — diperbaiki di helper, bukan di-copy mentah |

## 3. Desain

```
Telegram (@AskNexAIBot)
  │ pesan bebas / perintah switch
  ▼
Sesi Claude Channels (tetap: Read docs + reply)
  │ tiap pesan: baca state file (Read, sudah diizinkan)
  ▼
.ai-provider.json = {"provider": "claude"}  ──► jawab seperti SEKARANG (tidak ada yg berubah)
.ai-provider.json = {"provider": "openagentic"} ──► panggil helper (satu-satunya akses network)
                                                       ▼
                                              bin/ask-opencode (stdlib py, kunci dari .opencode-env 0600)
                                                       ▼
                                              https://openagentic.id/api/v1/chat/completions
```

**Perintah switch** (trigger phrase di chat, didokumentasikan di `ask-nexai/CLAUDE.md`):

| Perintah | Efek |
|---|---|
| `/pakai claude` | state → `claude`. Jawaban kembali persis seperti sekarang |
| `/pakai opencode` | state → `openagentic` (+ model default `openagentic/muse-spark-1.3-free`) |
| `/provider` | lapor posisi switch + model aktif (read-only) |

- Toggle `/pakai` **hanya owner** (chat `6687943152`); chat lain ditolak halus.
- State global: satu file untuk semua chat (sesuai keputusan).
- Helper gagal (timeout/non-200) → sesi fallback ke pengetahuan Claude + bilang jujur sedang fallback. Tidak pernah diam, tidak pernah ngarang status.

**Kenapa workspace `.env` tidak di-source ke sesi** (aturan lama, tetap berlaku):
`TELEGRAM_BOT_TOKEN` ikut terbawa → consumer `getUpdates` ganda → **HTTP 409, dua bot mati**.
`CLAUDE_CODE_OAUTH_TOKEN` → menimpa login Team. Maka kunci OpenAgentic tinggal di file
khusus `.opencode-env` (0600) yang hanya dibaca helper, **tidak pernah bisa di-Read sesi**.

## 4. File yang disentuh (final)

| # | File | Aksi |
|---|---|---|
| 1 | `/home/ahagent/ask-nexai/.ai-provider.json` | BARU — state global, default `claude` |
| 2 | `/home/ahagent/ask-nexai/.opencode-env` | BARU, 0600 — hanya 2 var OpenAgentic (disalin dari `.env` existing via SSH) |
| 3 | `/home/ahagent/ask-nexai/bin/ask-opencode` | BARU, 0755 — helper stdlib, model di-hardcode, hanya pertanyaan yang dinamis |
| 4 | `/home/ahagent/AI-Workspace/ops/channels/asknexai-settings.json` | EDIT — tambah 2 allow path-scoped (lihat §6 langkah 3), deny lain tetap |
| 5 | `/home/ahagent/ask-nexai/CLAUDE.md` | EDIT — tambah blok instruksi switch (§3) |
| 6 | `/home/ahagent/AI-Workspace/ops/harness/tests/test_ask_opencode.py` | BARU — test helper + test settings (wajib per komentar di settings) |
| 7 | Dokumen ini | BARU — plan + jejak audit |

**Tidak disentuh:** `tgbot.py`, `tgcmd.py`, `tgcore.py`, workspace `.env`,
`~/.claude/channels/telegram/.env`, `access.json`, proses/tmux yang jalan
(tidak ada restart service selama eksekusi).

## 5. Jaminan default & rollback

- **Default tidak berubah secara konstruksi:** state awal `claude` → code path sesi
  identik dengan hari ini (Read docs → jawab → reply). Helper tidak pernah dipanggil.
  Test §6 langkah 5 membuktikan jawaban default sama sebelum vs sesudah.
- **Backup pra-eksekusi** (dibuat dulu, file `.bak.YYYYMMDDHHMMSS`, tidak mengubah perilaku):
  `ask-nexai/CLAUDE.md`, `ops/channels/asknexai-settings.json`.
- **Restore** = salin kembali 2 file backup + hapus file #1–#3, #6 (opsional, karena
  tidak dirujuk siapa pun setelah restore) + verifikasi `/provider`-setara via
  SSH (state file hilang → sesi kembali murni Claude). Perintah restore persis
  dicantumkan di laporan eksekusi.
- **Kegagalan helper tidak merusak default:** fallback ke Claude selalu ada;
  OpenAgentic down ≠ bot down.

## 6. Langkah eksekusi (berurutan, setelah plan ini disetujui)

0. [SUDAH, pra-eksekusi] Backup 2 file §4 + catat `md5sum` sebelum/sesudah.
1. Buat `.ai-provider.json` (`{"provider":"claude",...}`) — perilaku nol-berubah.
2. Buat `.opencode-env` 0600 dari nilai `.env` existing (tidak tampil di log/transkrip).
3. Tulis `bin/ask-opencode`, `chmod 755`, `py_compile`, unit test mock-HTTP hijau.
4. Edit settings: tambah `Bash(/home/ahagent/ask-nexai/bin/ask-opencode *)` dan
   `Write(/home/ahagent/ask-nexai/.ai-provider.json)` ke `allow`; validasi JSON;
   tambah test settings. (Alternatif tanpa Write: toggle hanya via SSH — diputuskan saat eksekusi bila owner keberatan.)
5. Edit `ask-nexai/CLAUDE.md`: blok switch + owner-only + fallback. **Tanpa restart tmux** (instruksi dibaca sesi per pesan).
6. Live test 1 pertanyaan pendek via helper (SSH): assert HTTP 200 + isi jawaban masuk akal.
7. Uji Telegram berurutan: `/provider` → `/pakai opencode` → 1 tanya produk →
   `/pakai claude` → 1 tanya produk → bandingkan dengan baseline. Cek `@AgentNexoraBot`
   tetap responsif (tanpa 409).
8. Tulis laporan eksekusi ke `agents/reports/` + cantumkan perintah restore.

## 7. Acceptance criteria

- [ ] `/provider` → `claude` (default), jawaban identik dengan sebelum perubahan
- [ ] `/pakai opencode` → jawaban produk datang dari model OpenAgentic (terbukti di log helper, bukan klaim)
- [ ] `/pakai claude` → kembali ke perilaku sekarang, tanpa restart apa pun
- [ ] Helper gagal (simulasi) → fallback Claude + pemberitahuan jujur
- [ ] Chat non-owner kirim `/pakai ...` → ditolak, state tidak berubah
- [ ] `@AgentNexoraBot` normal sepanjang uji (0 error 409)
- [ ] API key tidak muncul di transkrip/chat/log mana pun
- [ ] Perintah restore §5 teruji (dry-run di file backup)

## 9. Hasil eksekusi (2026-09-22, dicatat pasca-eksekusi)

| Langkah §6 | Hasil |
|---|---|
| 0. Backup | 2 file `.bak.20260921181107`, md5 cocok dengan aslinya |
| 1–3. State, key file, helper | terpasang; `.opencode-env` 0600, state default `claude` |
| 4–5. Settings + CLAUDE.md | 2 allow path-scoped ditambah, deny utuh, JSON valid; blok switch masuk CLAUDE.md |
| 6a. Unit test | **7/7 OK**; 1 bug riil (exception non-HTTP lolos) ditemukan test dan diperbaiki |
| 6b. Live probe | request lolos auth, tapi upstream **HTTP 502 `proxy_error`** (2x). `/models` → 200, 39 model, `muse-spark-1.3-free` ada. Plumbing + key benar; gangguan di sisi completion OpenAgentic |
| Restart sesi | tmux `tgchannel` restart dengan perintah identik; sesi baru hidup, config baru aktif |
| Bot lama | `tgbot.py` tidak di-restart; `getMe` → `AgentNexoraBot` OK, 0 error 409 |

Dampak saat ini: default `claude` = perilaku persis seperti sebelum perubahan.
`/pakai opencode` memanggil helper; selama upstream 502, sesi fallback ke Claude
dengan pemberitahuan jujur, lalu otomatis memakai `muse-spark` saat upstream pulih
tanpa perubahan lanjutan. Perintah restore: lihat laporan eksekusi §Restore.

## 8. Risiko & mitigasi

| Risiko | Mitigasi |
|---|---|
| Switch global berdampak ke semua chat | hanya owner boleh toggle; default `claude` |
| 1 allow Bash melebarkan izin sesi `auto` | prefix dikunci 1 script; URL+model hardcode; argumen hanya teks pertanyaan; tidak ada Write/Exec lain |
| OpenAgentic lambat/down | timeout 30s + fallback Claude; default path tidak pernah menyentuh network |
| Flapping auto-switch | maksimal 3 flip per 30 menit (state `auto_flip_times`); lebih → tahan + info owner sekali |

## 10. Update: shortcut + auto-failover (2026-09-22 ~18:50 WIB)

Tujuan: pemakaian maksimal — Claude limit → otomatis ke OpenAgentic saat
auto-retry, begitu juga sebaliknya saat OpenAgentic gagal.

- **Shortcut (menu BotFather @AskNexAIBot, sudah diset):**
  `/provider`, `/pakai`, `/o` (pakai OpenAgentic), `/c` (kembali Claude),
  `/auto` (mode otomatis). Berlaku juga bentuk panjang `/p`, `/pakai claude`,
  `/pakai opencode`.
- **Mode `auto` (default):** preferensi Claude → OpenAgentic. Aturan: Claude
  error limit → flip ke opencode + notice; >15 mnt → coba Claude lagi, sukses →
  flip balik; helper ERROR → balik ke Claude + notice; anti-flap 3x/30 mnt;
  dua-duanya gagal → jujur tidak bisa jawab.
- **Mode `manual` (via `/pakai`/`/o`/`/c`):** provider dikunci; error → fallback
  sekali tanpa mengubah state.
- **Helper:** retry 1x (jeda 5 dtk) saat HTTP 5xx — terbukti bekerja di probe
  (`retry 1x...` lalu `ERROR:` rapi → jalur fallback sesi).
- **State:** tambah `mode`, `switch_reason`, `last_auto_switch_at`,
  `auto_flip_times`. Nilai saat ini: `claude/auto`.
- **Test 8/8 OK**, sesi `tgchannel` restart 18:54, `@AgentNexoraBot` untouched.
- Upstream completion **masih 502** saat probe terakhir → fallback aktif sampai
  OpenAgentic pulih (tanpa perubahan lanjutan di sisi kita).
| Drift README (auto vs manual, cwd) | didokumentasikan di laporan eksekusi agar runbook sinkron |
