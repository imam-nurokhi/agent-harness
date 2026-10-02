"""Which engine to launch, and which one has stopped being allowed to run.

Phase 1a made `claude` the only engine the harness would choose. That is right
for the VPS, but it assumed being *installed* and being *authorised* are the
same thing. They are not: on a machine whose default credentials belong to an
org that has disabled Claude Code, every run dies in under a second with

    Your organization has disabled Claude subscription access for Claude Code

and the harness cheerfully picks the same engine again for the next job.

So an engine here has three states, not two: installed, authorised, and chosen.
A refusal is remembered in `agents/.engine.json`, the next engine in the order
is chosen instead, and a later success clears the note — so when the admin
re-enables access the harness recovers on its own, without anyone editing a
file. `AH_ENGINE` always wins: the operator is never overruled by a cache.
"""
import json
import os
import re
import shutil
import sys
import time
from contextlib import contextmanager
from pathlib import Path

import state

STATE = state.AGENTS / ".engine.json"

DEFAULT_ORDER = ("claude", "codex")

# How many times one piece of work may be handed to an engine before the
# harness stops trying. Rotating costs a real quota every attempt, so this is
# deliberately small.
MAX_ATTEMPTS = 3

# An engine can be out of action for two very different reasons, and treating
# them the same is what made this harness stall.
#
#   refused — the account may not use this engine at all ("your organization
#             has disabled Claude Code"). Nothing changes until a human acts,
#             so it stays until a later run succeeds or someone clears it.
#   limited — the account has spent its quota ("try again at 3:56 AM"). It ends
#             by itself, at a time the engine usually tells us. Treating this
#             as permanent would have retired an engine that was coming back in
#             twenty minutes.
KIND_REFUSED = "refused"
KIND_LIMITED = "limited"

# When an engine says it is out of quota but not when it returns.
DEFAULT_COOLDOWN = 30 * 60

# These are deliberately whole vendor sentences rather than keywords. An agent
# in this harness reviews auth code for a living, and "invalid api key" or
# "authentication_error" appear in its transcripts as subject matter. Matching
# on those would migrate every later run to another vendor for a reason nobody
# could trace, so only phrasings an engine actually emits are listed here.
_LIMITS = re.compile(
    r"hit your (?:usage|rate) limit"
    r"|usage limit (?:reached|exceeded)"
    r"|rate limit (?:reached|exceeded)"
    r"|quota (?:exceeded|exhausted)"
    r"|too many requests"
    r"|purchase more credits"
    r"|credit balance is too low"
    r"|out of credits",
    re.IGNORECASE,
)

# Refusals mean "this account may not use this engine here". They are not
# crashes: a crash should never get an engine banned, or one bad prompt would
# silently move every future run to another vendor.
_REFUSALS = re.compile(
    r"organization has disabled"
    r"|disabled Claude subscription access"
    r"|please run /login"
    r"|not logged in"
    r"|oauth token (?:has )?expired"
    r"|ask your admin to enable access",
    re.IGNORECASE,
)


# An engine speaks at the edges of a run and the agent fills the middle. claude
# refuses on byte zero and stops; codex echoes the whole prompt first and puts
# its error last. So both ends are searched and the body is not — the body is
# where an agent's own prose about authentication lives.
HEAD = 2000


def is_auth_refusal(text: str) -> bool:
    """True when the *opening* of an engine's output says: not for this account."""
    return classify(text) == KIND_REFUSED


def classify(text: str) -> str | None:
    """Why an engine could not work, or None when it merely failed.

    A limit is checked first. Some engines phrase a quota message in terms that
    also mention credentials, and calling a temporary limit permanent is the
    more expensive mistake of the two.
    """
    if not text:
        return None
    edges = text[:HEAD] + "\n" + text[-HEAD:]
    if _LIMITS.search(edges):
        return KIND_LIMITED
    if _REFUSALS.search(edges):
        return KIND_REFUSED
    return None


# "or try again at 3:56 AM." — the engine usually says when it comes back, and
# honouring that beats a blind cooldown that either wastes an hour or retries
# into the same wall.
_RETRY_AT = re.compile(
    r"try again (?:at|after)\s+(\d{1,2})[:.](\d{2})\s*(am|pm)?", re.IGNORECASE)


def retry_at(text: str, now: float | None = None) -> float | None:
    """The unix time an engine said it would be usable again, if it said one."""
    m = _RETRY_AT.search(text or "")
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2)), (m.group(3) or "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None

    now = now if now is not None else time.time()
    lt = time.localtime(now)
    target = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hour, minute, 0,
                          0, 0, -1))
    # A time that has already gone past today means tomorrow: "try again at
    # 3:56 AM" said at 4am is not an invitation to retry immediately.
    if target <= now:
        target += 24 * 3600
    return target


def blocked() -> dict:
    """Engines known to refuse this account, by name. Never raises."""
    try:
        data = json.loads(STATE.read_text())
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write(data: dict) -> None:
    try:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
        tmp.replace(STATE)
    except Exception as exc:
        # Engine choice must never be the reason a run cannot start, so this
        # does not raise. It does complain: an unwritable state file means
        # every refusal is detected and then forgotten, and the harness would
        # retry a refused engine forever with `ah engine` showing nothing.
        print(f"ah: cannot record engine health in {STATE}: {exc}",
              file=sys.stderr)


@contextmanager
def _locked():
    """Serialise read-modify-write across processes.

    Jobs finish concurrently. Without this, a `clear()` based on a stale read
    can erase a `mark_blocked()` written a millisecond earlier, and the harness
    spends another doomed run rediscovering the refusal.
    """
    lock = None
    try:
        import fcntl
        STATE.parent.mkdir(parents=True, exist_ok=True)
        lock = open(STATE.with_suffix(".lock"), "w")
        fcntl.flock(lock, fcntl.LOCK_EX)
    except Exception:
        lock = None
    try:
        yield
    finally:
        if lock is not None:
            try:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_UN)
            finally:
                lock.close()


def mark(name: str, kind: str, reason: str = "",
         until: float | None = None) -> None:
    """Record that an engine is out of action, and on what terms."""
    with _locked():
        data = blocked()
        data[name] = {
            "kind": kind,
            "reason": (reason or "").strip()[:300],
            "at": time.time(),
            "until": until,
        }
        _write(data)


def mark_blocked(name: str, reason: str = "") -> None:
    """Back-compat: a refusal, which is the kind that does not expire."""
    mark(name, KIND_REFUSED, reason)


def unavailable() -> dict:
    """Engines out of action *right now*.

    A limit whose time has passed is simply gone from this view. Nobody should
    have to run a command to undo a limit that expired while they slept.
    """
    now = time.time()
    live = {}
    for name, entry in blocked().items():
        if not isinstance(entry, dict):
            continue
        until = entry.get("until")
        if until is not None and until <= now:
            continue
        # Entries written before limits existed carry no kind. They were all
        # refusals, and a missing kind must not read as a third, unhandled
        # state in the surfaces that match on it.
        live[name] = {"kind": KIND_REFUSED, "until": None, **entry}
    return live


def available(is_installed=None) -> list:
    here = is_installed or installed
    out = unavailable()
    return [n for n in order() if n not in out and here(n)]


def paused(is_installed=None) -> bool:
    """True when no engine can run. Starting a job now only wastes a quota."""
    return not available(is_installed)


def next_free_at() -> float | None:
    """The earliest moment an engine returns on its own, or None if unknowable.

    Refusals have no such moment — they end when a human acts, not when a clock
    ticks — so a board of nothing but refusals reports None rather than a
    reassuring guess.
    """
    times = [e["until"] for e in unavailable().values()
             if e.get("until") is not None]
    return min(times) if times else None


def clear(name: str) -> None:
    with _locked():
        data = blocked()
        if data.pop(name, None) is not None:
            _write(data)


def order() -> list:
    raw = os.environ.get("AH_ENGINE_ORDER", "").strip()
    names = [n.strip() for n in raw.replace(",", " ").split() if n.strip()]
    return names or list(DEFAULT_ORDER)


def installed(name: str) -> bool:
    if shutil.which(name):
        return True
    for base in (Path.home() / ".local/bin", Path("/opt/homebrew/bin"),
                 Path("/usr/local/bin")):
        cand = base / name
        if cand.is_file() and os.access(cand, os.X_OK):
            return True
    return False


def pick(role: str = "", is_installed=None) -> str:
    """The engine to launch: operator override, else the first usable one.

    `is_installed` is injected so callers with their own PATH rebuild (jobs.py
    runs under launchd, which hands it a bare PATH) resolve engines the same
    way they will later execute them.
    """
    override = os.environ.get("AH_ENGINE", "").strip()
    if override:
        return override

    here = is_installed or installed
    names = order()

    usable = available(here)
    if usable:
        return usable[0]
    # Everything preferred is blocked or missing. Rather than refuse to run,
    # hand back something real and let the engine speak for itself.
    for name in names:
        if here(name):
            return name
    return names[0]


def note_result(name: str, ok: bool, output: str = "") -> None:
    """Record what a finished run proved about the engine.

    The output is believed over the exit code. codex 0.154.0 prints "You've hit
    your usage limit" and then exits 0; trusting the code there meant reading a
    run that did nothing as a success, clearing the engine's record, and handing
    it the next job — which failed the same way.
    """
    kind = classify(output)
    if kind is None:
        if ok:
            clear(name)
        return
    if kind == KIND_REFUSED:
        mark(name, KIND_REFUSED, output)
    elif kind == KIND_LIMITED:
        # Prefer the time the engine named; fall back to a cooldown rather than
        # retiring it, because a limit always ends.
        mark(name, KIND_LIMITED, output,
             until=retry_at(output) or time.time() + DEFAULT_COOLDOWN)


def _cli() -> int:
    args = sys.argv[1:]
    cmd = args[0] if args else "pick"
    if cmd == "pick":
        print(pick(args[1] if len(args) > 1 else ""))
    elif cmd == "block":
        mark_blocked(args[1], " ".join(args[2:]))
    elif cmd == "clear":
        clear(args[1])
    elif cmd == "refusal":
        return 0 if is_auth_refusal(sys.stdin.read()) else 1
    elif cmd == "note":
        # note <engine> <rc>, output on stdin. Prints the kind when the ENGINE
        # was at fault, nothing when the run's failure was its own.
        name, rc = args[1], int(args[2])
        text = sys.stdin.read()
        note_result(name, rc == 0, text)
        kind = classify(text) if rc != 0 else None
        if kind:
            print(kind)
        return 0
    elif cmd == "next":
        off, cur = unavailable(), args[1]
        for name in order():
            if name != cur and name not in off and installed(name):
                print(name)
                return 0
        return 1
    elif cmd == "status":
        print(json.dumps(unavailable(), indent=2, sort_keys=True))
    elif cmd == "paused":
        return 0 if paused() else 1
    else:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
