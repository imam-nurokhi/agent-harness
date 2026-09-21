"""Task mutation from Telegram: create, assign, worktree, tick, note, close."""
from __future__ import annotations

import re
import subprocess

import state
from tgcore import code, esc

AH = str(state.WORKSPACE / "bin" / "ah")


def _run(args: list[str], timeout: int = 60) -> tuple[bool, str]:
    try:
        r = subprocess.run([AH, *args], capture_output=True, text=True, timeout=timeout)
    except Exception as e:
        return False, str(e)
    out = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", (r.stdout or "") + (r.stderr or ""))
    return r.returncode == 0, out.strip()


def _task_path(tid: str):
    return state.TASKS / f"{tid}.md"


def _require(tid: str):
    if not re.fullmatch(r"task-\d+", tid):
        raise ValueError(f"Task tidak ditemukan: {tid or '(kosong)'}")
    p = _task_path(tid)
    if not p.exists():
        raise ValueError(f"Task tidak ditemukan: {tid or '(kosong)'}")
    return p


def cmd_new(args: str) -> str:
    title = args.strip()
    if not title:
        return ("Format: " + code("/new <judul task>") +
                "\nContoh: " + code("/new Perbaiki total invoice"))
    ok, out = _run(["task", "new", title])
    if not ok:
        return f"Gagal membuat task: {esc(out)}"
    m = re.search(r"(task-\d+)", out)
    tid = m.group(1) if m else "?"
    return (f"📝 Task dibuat: {code(tid)}\n<b>{esc(title)}</b>\n\n"
            f"Berikutnya:\n"
            f"{code('/assign ' + tid + ' backend')} — tetapkan role\n"
            f"{code('/ac ' + tid + ' <kriteria>')} — tambah acceptance criteria\n"
            f"{code('/run <role> ' + tid)} — jalankan")


def cmd_assign(args: str) -> str:
    parts = args.split()
    if len(parts) < 2:
        return "Format: " + code("/assign <task-id> <role>")
    tid, role = parts[0], parts[1].lower()
    if role not in state.ROLE_LIST:
        return f"Role tidak dikenal: {code(role)}\nPilihan: {', '.join(state.ROLE_LIST)}"
    try:
        p = _require(tid)
    except ValueError as e:
        return esc(e)

    text = p.read_text()
    new, n = re.subn(r"^- \*\*Role:\*\* .*$", f"- **Role:** {role}", text, count=1, flags=re.M)
    if not n:
        return "Baris Role tidak ditemukan di file task."
    p.write_text(new)
    persona = next((a for a in state.agents() if a["role"] == role), None)
    who = f"{persona['glyph']} {persona['name']}" if persona else role
    return f"✅ {code(tid)} ditetapkan ke {who} ({code(role)})"


def cmd_ac(args: str) -> str:
    parts = args.split(None, 1)
    if len(parts) < 2:
        return "Format: " + code("/ac <task-id> <kriteria yang bisa diuji>")
    tid, crit = parts[0], parts[1].strip()
    try:
        p = _require(tid)
    except ValueError as e:
        return esc(e)

    text = p.read_text()
    m = re.search(r"(## Acceptance criteria\n)(.*?)(\n## )", text, re.S)
    if not m:
        return "Bagian Acceptance criteria tidak ditemukan."
    body = m.group(2).rstrip("\n")
    # Drop the template placeholders the first time a real criterion is added.
    lines = [l for l in body.split("\n")
             if l.strip() and "<testable statement>" not in l]
    lines.append(f"- [ ] {crit}")
    text = text[:m.start(2)] + "\n".join(lines) + "\n" + text[m.end(2):]
    p.write_text(text)
    return f"➕ Kriteria ditambahkan ke {code(tid)} (total {len(lines)})\n{esc(crit)}"


def cmd_tick(args: str) -> str:
    parts = args.split()
    if len(parts) < 2 or not parts[1].isdigit():
        return ("Format: " + code("/tick <task-id> <nomor>") +
                "\nNomor dilihat dari " + code("/task <task-id>"))
    tid, idx = parts[0], int(parts[1])
    try:
        p = _require(tid)
    except ValueError as e:
        return esc(e)

    text = p.read_text()
    m = re.search(r"(## Acceptance criteria\n)(.*?)(\n## )", text, re.S)
    if not m:
        return "Bagian Acceptance criteria tidak ditemukan."
    lines = m.group(2).rstrip("\n").split("\n")
    items = [i for i, l in enumerate(lines) if re.match(r"^- \[( |x|X)\]", l)]
    if idx < 1 or idx > len(items):
        return f"Nomor di luar jangkauan. Task ini punya {len(items)} kriteria."
    i = items[idx - 1]
    lines[i] = re.sub(r"^- \[( |x|X)\]", "- [x]", lines[i])
    text = text[:m.start(2)] + "\n".join(lines) + "\n" + text[m.end(2):]
    p.write_text(text)

    t = next((x for x in state.tasks() if x["id"] == tid), None)
    prog = f"{t['criteria_done']}/{t['criteria_total']}" if t else "?"
    done = t and t["criteria_total"] and t["criteria_done"] == t["criteria_total"]
    return (f"✅ {code(tid)} kriteria {idx} dicentang — sekarang {prog}"
            + ("\n\n🎉 Semua kriteria terpenuhi. Tulis laporan lalu tutup dengan "
               + code(f"/close {tid}") if done else ""))


def cmd_note(args: str) -> str:
    parts = args.split(None, 1)
    if len(parts) < 2:
        return "Format: " + code("/note <task-id> <catatan>")
    tid, note = parts[0], parts[1].strip()
    try:
        p = _require(tid)
    except ValueError as e:
        return esc(e)
    text = p.read_text().rstrip("\n")
    if "## Catatan" not in text:
        text += "\n\n## Catatan\n"
    text += f"\n- {note}\n"
    p.write_text(text)
    return f"📌 Catatan ditambahkan ke {code(tid)}"


def cmd_wt(args: str) -> str:
    parts = args.split()
    if len(parts) < 2:
        return ("Format: " + code("/wt <task-id> <path-project>") +
                "\nContoh: " + code("/wt task-005 projects/sandbox"))
    tid, project = parts[0], parts[1]
    try:
        _require(tid)
    except ValueError as e:
        return esc(e)
    ok, out = _run(["wt", "add", tid, project], timeout=90)
    return (f"🌿 Worktree dibuat untuk {code(tid)}\n<pre>{esc(out[-600:])}</pre>"
            if ok else f"Gagal: <pre>{esc(out[-600:])}</pre>")


def cmd_close(args: str) -> str:
    tid = args.strip().split()[0] if args.strip() else ""
    t = next((x for x in state.tasks() if x["id"] == tid), None)
    if not t:
        return f"Task tidak ditemukan: {code(tid or '(kosong)')}"
    if t["criteria_total"] and t["criteria_done"] < t["criteria_total"]:
        missing = [c["text"] for c in t["criteria"] if not c["done"]]
        return (f"❌ Belum bisa ditutup: {t['criteria_done']}/{t['criteria_total']} kriteria.\n\n"
                "Belum terpenuhi:\n" + "\n".join(f"⬜ {esc(m)}" for m in missing))
    report = state.REPORTS / f"{tid}.md"
    if not report.exists():
        return (f"❌ Belum ada laporan di {code(f'agents/reports/{tid}.md')}.\n"
                f"Jalankan agent untuk menulis laporan, atau tulis manual di Mac.")
    return f"🟢 {code(tid)} sudah tertutup: semua kriteria terpenuhi dan laporan ada."


HANDLERS = {
    "new": cmd_new, "assign": cmd_assign, "ac": cmd_ac,
    "tick": cmd_tick, "note": cmd_note, "wt": cmd_wt, "close": cmd_close,
}
