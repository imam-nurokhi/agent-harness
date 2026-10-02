"""Print the projects an agent may currently act on. Used to expand {PROJECTS}.

Paths come from the project row itself, not from class+name: a repository that
sits directly at projects/<name> has class == name, so composing the path would
emit projects/sandbox/sandbox, which does not exist.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import state  # noqa: E402

lines = []
for p in state.workable_projects():
    try:
        rel = Path(p["path"]).relative_to(state.WORKSPACE)
    except ValueError:
        rel = Path(p["path"])
    lines.append(f"- {rel}  (branch {p['branch'] or '?'})")

print("\n".join(lines) or "- (tidak ada project yang boleh dikerjakan)")
