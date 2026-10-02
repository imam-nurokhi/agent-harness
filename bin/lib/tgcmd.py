"""Command handlers for the Telegram control surface."""
from __future__ import annotations

import re
import subprocess
import time

import ghflow
import jobs
import state
import tggh
from tgcore import code, esc

MAX_TAIL = 2800
DASHBOARD_URL = "https://agents.nexoratech.co"
AUTOMATION_URL = f"{DASHBOARD_URL}/automation/"


def _personas() -> dict:
    return {a["role"]: a for a in state.agents()}


def _who(role: str) -> str:
    a = _personas().get(role)
    return f"{a['glyph']} {a['name']}" if a else role


def cmd_help(_args: str) -> str:
    """Every command the bot will accept, grouped by the role it needs.

    Grouped by role on purpose: a viewer can see why /run is refused instead of
    finding out by being denied. The grouping mirrors tgbot.COMMAND_LEVELS, and
    tests/test_telegram_help_coverage.py fails if this text and the dispatch
    table ever disagree.
    """
    return (
        "<b>Agent Harness — Kara</b>\n"
        "Perintah dikelompokkan menurut role yang dibutuhkan chat ini.\n"
        "Cek role-mu dengan /status.\n\n"

        "<b>Viewer</b> — baca ringkasan\n"
        "/help — daftar perintah ini\n"
        "/status — ringkasan harness + role kamu\n"
        "/agents — roster bidak catur\n"
        "/jobs — run terakhir\n"
        "/ops — status n8n, backup, kapasitas server\n"
        "/monitor — uptime situs, SSL, disk, target Prometheus\n"
        "/brief — daily brief dari data yang tersedia\n"
        "/reporting director|management|dev — ringkasan per audiens\n"
        "/sources — status sumber data dan integrasi\n"
        "/reminders — cakupan reminder aktif\n"
        "/support — status intake customer/developer\n"
        "/deploy — guardrail deploy production\n\n"

        "<b>Operator</b> — data task dan eksekusi rinci\n"
        "/kanban — papan task\n"
        "/tasks — semua task + acceptance criteria\n"
        "/task task-001 — detail satu task\n"
        "/triggers — jadwal otomatis\n"
        "/engine — engine yang dipakai, dan yang kena limit\n"
        "/tail &lt;job-id&gt; — potongan output sebuah run\n"
        "/log &lt;job-id&gt; — kirim log penuh sebagai berkas\n"
        "/diff task-005 — kirim diff worktree sebagai berkas\n"
        "/report task-005 — kirim report/transkrip sebagai berkas\n"
        "/digest — ringkasan sesuai permintaan\n"
        "/weekly — laporan mingguan untuk meeting manajemen\n"
        "/daily — update tim dari Slack #daily-updates minggu ini\n\n"

        "<b>Owner</b> — mengubah, menjalankan, memberi akses\n"
        "/new &lt;judul&gt; — buat task baru\n"
        "/assign task-005 backend — tetapkan role\n"
        "/ac task-005 &lt;kriteria&gt; — tambah acceptance criteria\n"
        "/tick task-005 2 — centang kriteria ke-2\n"
        "/wt task-005 projects/sandbox — buat worktree\n"
        "/note task-005 &lt;catatan&gt; — tempel catatan\n"
        "/close task-005 — cek apakah sudah bisa ditutup\n"
        "/run backend task-001 — jalankan agent pada task\n"
        "/ask lead ringkas status hari ini — instruksi bebas\n"
        "/trigger standup — jalankan trigger sekarang\n"
        "/stop &lt;job-id&gt; — hentikan run\n"
        "/resume — lanjutkan task yang mandek sekarang\n"
        "/push task-005 NexoraTechTeam/academy — push ke branch baru + buka PR ke dev\n"
        "/pr NexoraTechTeam/academy ah/task-005-… — buka PR untuk branch yang sudah ada\n"
        "/prs NexoraTechTeam/academy — daftar PR terbuka ke dev\n"
        "/merge NexoraTechTeam/academy 12 — minta approval merge (tombol Approve)\n"
        "/doctor — cek engine, auth, disk\n"
        "/quiet on|off — matikan/nyalakan notifikasi\n"
        "/grant &lt;chat-id&gt; viewer|operator|owner — ubah role chat\n\n"

        "<b>Tanpa slash</b> — ketik biasa untuk tanya-jawab bebas atau minta "
        "pekerjaan development (owner saja). Agent tidak pernah push sendiri: "
        f"merge ke {ghflow.PR_BASE} selalu lewat tombol Approve.\n\n"

        "Role agent: lead, frontend, backend, qa, review, devops, docs\n"
        "Notifikasi hanya dikirim untuk run yang selesai dan task yang "
        "kriterianya lengkap — bukan untuk setiap perubahan."
    )


def cmd_status(_args: str) -> str:
    d = state.snapshot()
    h, s = d["health"], d["summary"]
    running = [j for j in jobs.listing() if j["status"] == "running"]
    working = [a for a in d["agents"] if a["status"] == "working"]

    lines = ["<b>Status harness</b>", ""]
    lines.append(f"Task: {s['tasks_total']} "
                 f"({s['by_status']['planned']} planned, {s['by_status']['active']} active, "
                 f"{s['by_status']['review']} review, {s['by_status']['reported']} reported)")
    lines.append(f"Worktree: {len(d['worktrees'])} "
                 f"({sum(1 for w in d['worktrees'] if w['dirty'])} ada perubahan)")
    lines.append(f"Project: {len(d['projects'])}")
    lines.append(f"Disk: {h['disk_free_gb']} GB bebas ({h['disk_pct']}% terpakai)")
    lines.append(f"Guard ~/Documents: {'aktif' if h['documents_guard'] else 'TIDAK AKTIF'}")
    lines.append("")
    if running:
        lines.append(f"<b>Sedang berjalan ({len(running)})</b>")
        for j in running:
            lines.append(f"• {_who(j['role'])} — {code(j['id'])} — {j['elapsed']}s")
    elif working:
        lines.append(f"<b>Bekerja:</b> {', '.join(a['name'] for a in working)}")
    else:
        lines.append("Tidak ada run yang berjalan.")
    return "\n".join(lines)


def _operations_lines(snapshot: dict) -> list[str]:
    services = snapshot.get("operations", {}).get("services", [])
    if not services:
        return ["Status operasi belum tersedia."]
    return [
        f"• {esc(item.get('label', 'service'))}: <b>{esc(item.get('status', 'unknown'))}</b>"
        f" — {esc(item.get('detail', '-'))}"
        for item in services
    ]


def cmd_ops(_args: str) -> str:
    """Expose the isolated operations surface without credentials or actions."""
    lines = ["<b>Operasional cloud</b>", ""]
    lines.extend(_operations_lines(state.snapshot()))
    lines += ["", f"Dashboard: {code(DASHBOARD_URL)}",
              f"n8n: {code(AUTOMATION_URL)}"]
    return "\n".join(lines)


def cmd_monitor(_args: str) -> str:
    """Uptime, SSL, disk and scrape health, read from the monitoring stack.

    Deterministic and free: Prometheus answers this, so it costs no engine
    quota and cannot invent a number — the same reasoning that made /weekly
    and /daily harness code instead of agent runs (AGENTS.md).
    """
    import metrics
    return metrics.render(metrics.collect())


def cmd_brief(_args: str) -> str:
    """Return the existing digest on demand; it only uses connected local data."""
    import tgwatch
    return tgwatch.digest()


def cmd_reporting(args: str) -> str:
    """Role-tailored but aggregate-only reporting until owner RBAC exists."""
    audience = args.strip().lower()
    if audience not in {"director", "management", "dev"}:
        return "Format: " + code("/reporting director|management|dev")

    snapshot = state.snapshot()
    summary = snapshot.get("summary", {})
    counts = summary.get("by_status", {})
    operational = snapshot.get("operations", {}).get("services", [])
    attention = [item.get("label", "service") for item in operational
                 if item.get("status") not in {"ok", "ready"}]
    role_copy = {
        "director": "Ringkasan eksekutif: delivery dan risiko operasi.",
        "management": "Ringkasan manajemen: kapasitas kerja dan hambatan operasi.",
        "dev": "Ringkasan engineering: antrian kerja dan kesehatan platform.",
    }
    lines = [f"<b>Report {esc(audience)}</b>", role_copy[audience], ""]
    lines.append(
        f"Task: {summary.get('tasks_total', 0)} total · "
        f"{counts.get('planned', 0)} planned · {counts.get('active', 0)} active · "
        f"{counts.get('review', 0)} review · {counts.get('reported', 0)} reported"
    )
    lines.append("Perlu perhatian: " + (", ".join(esc(item) for item in attention)
                                           if attention else "tidak ada dari status yang tersedia"))
    lines.append("Detail task dan data personal belum dibuka sampai owner RBAC dikonfigurasi.")
    return "\n".join(lines)


def cmd_weekly(_args: str) -> str:
    """Friday management report, derived from harness state, not from an agent.

    /reporting gives counts; this gives the week: what shipped, what is moving,
    what has stopped moving, and what is at risk. Deterministic on purpose --
    it costs no engine spend and cannot claim progress that did not happen.
    """
    import time

    import weekly
    return weekly.report(state.snapshot(), jobs.listing(200), now=time.time())


def cmd_daily(_args: str) -> str:
    """This week's #daily-updates, grouped and attributed, not paraphrased.

    Runs in the bot process, so it needs no engine and meets no permission gate
    -- the thing that stopped a lead agent from doing this. Configuration lives
    in the workspace .env and the command says so plainly when it is absent,
    rather than raising at whoever typed it.
    """
    import os

    import slackread
    try:
        messages, names = slackread.fetch_week(
            token=os.environ.get("SLACK_BOT_TOKEN", ""),
            channel=os.environ.get("SLACK_DAILY_CHANNEL_ID", ""),
            now=time.time())
    except slackread.NotConfigured as exc:
        return ("⚙️ <b>Slack belum tersambung</b>\n\n" + esc(str(exc))
                + "\n\nSetelah itu restart " + code("ah-telegram") + ".")
    except Exception as exc:
        return "❌ Gagal membaca Slack: " + esc(str(exc)[:200])
    return slackread.report(messages, names, now=time.time())


def cmd_sources(_args: str) -> str:
    """Declare only the sources actually connected to the cloud control plane."""
    snapshot = state.snapshot()
    automation = next(
        (item for item in snapshot.get("operations", {}).get("services", [])
         if item.get("id") == "automation"),
        {},
    )
    lines = ["<b>Sumber data & integrasi</b>", ""]
    lines.append(f"• n8n platform: <b>{esc(automation.get('status', 'unknown'))}</b>")
    lines.append("• GitHub: belum dihubungkan dengan credential read-only")
    lines.append("• Slack: belum dikonfigurasi")
    lines.append("• Notion: belum dikonfigurasi")
    lines.append("• NEXONE: belum dihubungkan; menunggu review keamanan autentikasi")
    lines.append("• Domain, billing, dan support: belum dikonfigurasi")
    lines += ["", f"Kelola workflow: {code(AUTOMATION_URL)}"]
    return "\n".join(lines)


def cmd_reminders(_args: str) -> str:
    return (
        "<b>Reminder aktif</b>\n\n"
        "• Run agent selesai atau gagal\n"
        "• Trigger terjadwal gagal atau terlambat\n"
        "• Task dengan acceptance criteria lengkap\n\n"
        "Reminder DevOps, domain, billing, sales, certificate, dan client belum aktif "
        "karena sumber datanya belum dihubungkan."
    )


def cmd_support(_args: str) -> str:
    return (
        "<b>Support intake</b>\n\n"
        "Intake customer dan developer belum diaktifkan. Jangan kirim data pelanggan, "
        "credential, atau detail insiden sensitif lewat command ini. Routing akan "
        "diaktifkan setelah kanal helpdesk dan aturan akses disetujui."
    )


def cmd_deploy(_args: str) -> str:
    """A hard stop: Telegram cannot deploy production."""
    return (
        "⛔ Deploy production tidak tersedia dari Telegram.\n\n"
        "Production hanya dapat dipromosikan melalui GitHub Environment dengan required "
        "approval owner. Bot ini tidak menjalankan deploy, shell, atau SSH ke production."
    )


def cmd_agents(_args: str) -> str:
    lines = ["<b>Roster</b>", ""]
    for a in state.agents():
        mark = {"working": "🟢", "assigned": "🟡", "idle": "⚪"}.get(a["status"], "⚪")
        lines.append(f"{mark} {a['glyph']} <b>{esc(a['name'])}</b> — {esc(a['title'])} "
                     f"({code(a['role'])})")
        lines.append(f"    {esc(a['status'])} · {esc(a['detail'])}")
    lines.append("")
    lines.append("Pakai <b>role</b> di perintah, bukan nama persona.")
    return "\n".join(lines)


def cmd_tasks(_args: str) -> str:
    tasks = state.tasks()
    if not tasks:
        return "Belum ada task."
    mark = {"planned": "⚪", "active": "🟡", "review": "🟠", "reported": "🟢"}
    lines = ["<b>Task</b>", ""]
    for t in tasks:
        lines.append(f"{mark.get(t['status'], '⚪')} {code(t['id'])} — {esc(t['title'])}")
        lines.append(f"    {esc(t['role'] or '-')} · {esc(t['status'])} · "
                     f"AC {t['criteria_done']}/{t['criteria_total']}"
                     + (" · worktree" if t["has_worktree"] else ""))
    return "\n".join(lines)


def cmd_task(args: str) -> str:
    tid = args.strip().split()[0] if args.strip() else ""
    t = next((x for x in state.tasks() if x["id"] == tid), None)
    if not t:
        return f"Task tidak ditemukan: {code(tid or '(kosong)')}\nCoba /tasks"
    lines = [f"<b>{esc(t['title'])}</b>",
             f"{code(t['id'])} · {esc(t['role'] or '-')} · {esc(t['status'])}",
             f"Project: {esc(t['project'] or '-')}", ""]
    lines.append(f"<b>Acceptance criteria {t['criteria_done']}/{t['criteria_total']}</b>")
    for c in t["criteria"]:
        lines.append(f"{'✅' if c['done'] else '⬜'} {esc(c['text'])}")
    if t["logs"]:
        lines += ["", "<b>Transkrip</b>"] + [code(l) for l in t["logs"]]
    if t["role"]:
        lines += ["", f"Jalankan: {code('/run ' + t['role'] + ' ' + t['id'])}"]
    return "\n".join(lines)


def cmd_jobs(_args: str) -> str:
    js = jobs.listing(12)
    if not js:
        return "Belum ada run. Mulai dengan /run atau /ask."
    mark = {"running": "🟢", "done": "✅", "stopped": "🛑"}
    lines = ["<b>Run terakhir</b>", ""]
    for j in js:
        lines.append(f"{mark.get(j['status'], '•')} {code(j['id'])} — {_who(j['role'])}")
        lines.append(f"    {esc(j['status'])} · {j['elapsed']}s · {esc(j['title'][:60])}")
    lines.append("")
    lines.append(f"Output: {code('/tail <job-id>')}")
    return "\n".join(lines)


def _clean(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def cmd_tail(args: str) -> str:
    jid = args.strip().split()[0] if args.strip() else ""
    if not jid:
        js = jobs.listing(1)
        if not js:
            return "Belum ada run."
        jid = js[0]["id"]
    r = jobs.tail(jid, 0)
    if r.get("error"):
        return f"Run tidak ditemukan: {code(jid)}\nCoba /jobs"
    body = _clean(r["chunk"])
    i = body.rfind("## Report")
    shown = body[i:] if i > 0 else body[-MAX_TAIL:]
    return (f"<b>{code(jid)}</b> — {_who(r['role'])} · {esc(r['status'])} · {r['elapsed']}s\n\n"
            f"<pre>{esc(shown[-MAX_TAIL:])}</pre>")


def cmd_run(args: str) -> str:
    parts = args.split()
    if len(parts) < 2:
        return ("Format: " + code("/run <role> <task-id>") +
                "\nContoh: " + code("/run backend task-001"))
    role, tid = parts[0], parts[1]
    extra = " ".join(parts[2:])
    try:
        meta = jobs.spawn(role=role, task_id=tid, prompt=extra)
    except ValueError as e:
        return f"Gagal: {esc(e)}"
    return (f"▶️ {_who(role)} mulai mengerjakan {code(tid)}\n"
            f"Job {code(meta['id'])}\n\nNotifikasi dikirim saat selesai.")


def cmd_ask(args: str) -> str:
    parts = args.split(None, 1)
    if len(parts) < 2:
        return ("Format: " + code("/ask <role> <instruksi>") +
                "\nContoh: " + code("/ask lead ringkas status hari ini"))
    role, prompt = parts[0], parts[1]
    try:
        meta = jobs.spawn(role=role, prompt=prompt)
    except ValueError as e:
        return f"Gagal: {esc(e)}"
    return f"▶️ {_who(role)} menerima instruksi\nJob {code(meta['id'])}"


def cmd_stop(args: str) -> str:
    jid = args.strip().split()[0] if args.strip() else ""
    if not jid:
        return "Format: " + code("/stop <job-id>")
    r = jobs.stop(jid)
    return f"Run tidak ditemukan: {code(jid)}" if r.get("error") else f"🛑 Dihentikan: {code(jid)}"


def cmd_triggers(_args: str) -> str:
    trs = state.triggers()
    if not trs:
        return "Belum ada trigger."
    lines = ["<b>Trigger terjadwal</b>", ""]
    for t in trs:
        lines.append(f"{'⏰' if t['installed'] else '⏸'} {code(t['id'])} — {esc(t['label'])}")
        lines.append(f"    {esc(t['schedule'])} · {esc(t['role'])} · "
                     f"{'terpasang' if t['installed'] else 'belum terpasang'}")
    lines.append("")
    lines.append(f"Jalankan sekarang: {code('/trigger <id>')}")
    return "\n".join(lines)


def cmd_trigger(args: str) -> str:
    tid = args.strip().split()[0] if args.strip() else ""
    tr = next((t for t in state.triggers() if t["id"] == tid), None)
    if not tr:
        return f"Trigger tidak ditemukan: {code(tid or '(kosong)')}\nCoba /triggers"
    try:
        meta = jobs.spawn(role=tr.get("role") or "lead", prompt=tr["prompt"])
    except ValueError as e:
        return f"Gagal: {esc(e)}"
    return f"▶️ Trigger {code(tid)} dijalankan oleh {_who(tr.get('role') or 'lead')}\nJob {code(meta['id'])}"


def cmd_doctor(_args: str) -> str:
    try:
        out = subprocess.run([str(state.WORKSPACE / "bin" / "ah"), "doctor"],
                             capture_output=True, text=True, timeout=60)
        body = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", out.stdout)
    except Exception as e:
        return f"Gagal menjalankan doctor: {esc(e)}"
    return f"<pre>{esc(body[-MAX_TAIL:])}</pre>"


def cmd_diff(args: str) -> str:
    """Send the worktree diff for a task as a file, so it is readable on a phone."""
    import tgfiles
    tid = args.strip().split()[0] if args.strip() else ""
    if not tid:
        return "Format: " + code("/diff <task-id>")
    dest, reason = tgfiles.diff_path(tid)
    if not dest:
        return esc(reason)
    return ("__DOC__", str(dest), f"diff {tid}")


def cmd_report(args: str) -> str:
    """Send a task's report or its newest transcript."""
    import tgfiles
    tid = args.strip().split()[0] if args.strip() else ""
    if not tid:
        return "Format: " + code("/report <task-id>")
    dest = tgfiles.report_path(tid)
    if not dest:
        return f"Belum ada report atau transkrip untuk {code(tid)}."
    return ("__DOC__", str(dest), f"report {tid}")


def cmd_log(args: str) -> str:
    """Send a job's full log when /tail truncated it."""
    import tgfiles
    jid = args.strip().split()[0] if args.strip() else ""
    if not jid:
        return "Format: " + code("/log <job-id>")
    dest = tgfiles.job_log_path(jid)
    if not dest:
        return f"Tidak ada log untuk job {code(jid)}."
    return ("__DOC__", str(dest), f"log {jid}")


def cmd_push(args: str) -> str:
    """Owner approval to publish an agent's work — as a branch plus a PR to dev.

    It used to push straight onto dev/staging. The owner replaced that rule on
    2026-09-19: work goes to a fresh ah/ branch and reaches dev only through a
    pull request they approve in Telegram. The implementation lives in tggh so
    the GitHub rules stay in one place; this stays the /push entry point.
    """
    import tggh
    return tggh.cmd_push(args)


def cmd_engine(_args: str) -> str:
    """Which engine will run, and which are refused or out of quota.

    Reads the same engine health the dashboard and the scheduler use. Wrapped
    so a malformed state file returns a line, never an exception into the loop.
    """
    try:
        import engine
        chosen = engine.pick()
        out = engine.unavailable()
        paused = engine.paused()
    except Exception as exc:
        return f"Engine: tidak bisa dibaca ({esc(str(exc))})"

    lines = [f"<b>Engine</b>: {code(chosen)} akan dipakai"]
    if paused:
        free = None
        try:
            free = engine.next_free_at()
        except Exception:
            free = None
        import time
        when = (time.strftime("%H:%M", time.localtime(free)) if free
                else "belum diketahui")
        lines.append(f"⏸️ <b>PAUSED</b> — tidak ada engine tersedia; "
                     f"pulih otomatis, perkiraan {when}")
    if not out:
        lines.append("Semua engine sehat.")
    for name, info in out.items():
        kind = info.get("kind")
        if kind == "limited":
            import time
            until = info.get("until")
            back = (time.strftime("%H:%M", time.localtime(until)) if until
                    else "belum diketahui")
            lines.append(f"{code(name)} — limit pemakaian, pulih {back}")
        else:
            lines.append(f"{code(name)} — ditolak (butuh admin)")
            lines.append(f"    {code('ah engine clear ' + name)}")
    return "\n".join(lines)


def cmd_resume(_args: str) -> str:
    """Trigger one auto-resume sweep by hand and report what it did."""
    try:
        import resumerun
        result = resumerun.sweep()
    except Exception as exc:
        return f"Resume gagal: {esc(str(exc))}"

    action = result.get("action")
    if action == "started":
        return (f"▶️ Melanjutkan {code(result.get('task', '?'))} "
                f"(job {code(result.get('job', '?'))})")
    if action == "paused":
        return (f"⏸️ Ditunda — semua engine tidak tersedia; "
                f"lanjut otomatis saat pulih (perkiraan {result.get('when', '?')})")
    if action == "busy":
        return "Sudah ada run yang berjalan — satu agent dulu."
    return "Tidak ada task mandek untuk dilanjutkan."


HANDLERS = {
    "help": cmd_help, "start": cmd_help,
    "status": cmd_status, "agents": cmd_agents,
    "tasks": cmd_tasks, "task": cmd_task,
    "jobs": cmd_jobs, "tail": cmd_tail,
    "run": cmd_run, "ask": cmd_ask, "stop": cmd_stop,
    "triggers": cmd_triggers, "trigger": cmd_trigger,
    "doctor": cmd_doctor,
    "engine": cmd_engine, "resume": cmd_resume,
    "diff": cmd_diff, "report": cmd_report, "log": cmd_log,
    "push": cmd_push, "pr": tggh.cmd_pr, "prs": tggh.cmd_prs,
    "merge": tggh.cmd_merge,
    "ops": cmd_ops, "monitor": cmd_monitor, "brief": cmd_brief, "reporting": cmd_reporting,
    "weekly": cmd_weekly, "daily": cmd_daily,
    "sources": cmd_sources, "reminders": cmd_reminders, "support": cmd_support,
    "deploy": cmd_deploy,
}


def cmd_kanban(_args: str) -> str:
    """The Command Center board, rendered for a phone screen."""
    d = state.snapshot()
    cols = [
        ("📋 TO DO", "planned"),
        ("🔨 DOING", "active"),
        ("👀 NEEDS REVIEW", "review"),
        ("✅ DONE", "reported"),
    ]
    personas = _personas()
    lines = ["<b>Papan Kanban</b>"]
    for label, key in cols:
        items = [t for t in d["tasks"] if t["status"] == key]
        lines.append("")
        lines.append(f"<b>{label} ({len(items)})</b>")
        if not items:
            lines.append("  <i>kosong</i>")
            continue
        for t in items:
            who = personas.get(t["role"] or "", {})
            tag = f"{who.get('glyph','')} {who.get('name', t['role'] or '-')}"
            bar = ""
            if t["criteria_total"]:
                filled = round(t["criteria_done"] / t["criteria_total"] * 5)
                bar = f" {'▰' * filled}{'▱' * (5 - filled)} {t['criteria_done']}/{t['criteria_total']}"
            lines.append(f"  {code(t['id'])} {esc(t['title'][:38])}")
            lines.append(f"     {esc(tag)}{bar}"
                         + ("  🌿" if t["has_worktree"] else ""))

    running = [j for j in jobs.listing(10) if j["status"] == "running"]
    if running:
        lines += ["", f"<b>▶️ Berjalan ({len(running)})</b>"]
        for j in running:
            lines.append(f"  {_who(j['role'])} {code(j['id'])} {j['elapsed']}s")

    lines += ["", f"Detail: {code('/task <id>')} · Buat: {code('/new <judul>')}"]
    return "\n".join(lines)


HANDLERS["kanban"] = cmd_kanban
HANDLERS["board"] = cmd_kanban
