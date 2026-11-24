"""Stop hook for Claude Code, Codex, GitHub Copilot CLI, and OpenCode: run the targeted checks before the agent finishes.

Reads the hook event from stdin. When the working tree changed since the last
run in this session, it runs the targeted checks from find_checks.py. If any
fail, it hands the failures back so the agent continues: exit 2 with the
report on stderr (Claude Code, Codex), or a JSON block decision on stdout
(``--format json``: Copilot CLI and the OpenCode plugin). It never blocks
twice in a row (``stop_hook_active``), skips repositories without changes,
and exits 0 on any internal error so a broken hook cannot trap a session.

Turn it off for one repository with an empty ``.getonmylevel-checks`` file, or
everywhere with GETONMYLEVEL_VERIFY_HOOK=off.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import find_checks  # noqa: E402

BUDGET = float(os.environ.get("GETONMYLEVEL_VERIFY_BUDGET", "240"))


def _state_file(session: str, root: Path) -> Path:
    key = hashlib.sha256(f"{session}\0{root}".encode("utf-8", "replace")).hexdigest()[:32]
    return Path(tempfile.gettempdir()) / "getonmylevel-verify" / key


FORMATS = ("exit2", "json")
# exit2: Claude Code Stop and Codex Stop hooks. Exit 2; stderr becomes the agent's next prompt.
# json:  GitHub Copilot CLI agentStop hooks and the OpenCode plugin. Exit 0 with
#        {"decision": "block", "reason": ...} on stdout; Copilot treats exit 2 as a warning only.


def failure_message(event: dict) -> str | None:
    """Run the checks for this stop event; return the message for the agent, or None to let it stop."""
    if os.environ.get("GETONMYLEVEL_VERIFY_HOOK", "").lower() in ("0", "off", "false", "no"):
        return None
    if event.get("stop_hook_active") or event.get("stopHookActive"):
        return None
    cwd = Path(event.get("cwd") or os.getcwd())
    root = find_checks.repo_root(cwd)
    if not (root / ".git").exists():
        return None
    files = find_checks.changed_files(root)
    if not files:
        return None
    session = str(event.get("session_id") or event.get("sessionId") or "")
    state = _state_file(session, root)
    current = find_checks.fingerprint(root)
    try:
        if state.read_text(encoding="utf-8") == current:
            return None
    except OSError:
        pass
    checks = find_checks.find_checks(root, files)
    passed, failed, skipped = find_checks.run_checks(root, checks, BUDGET)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(current, encoding="utf-8")
    if not failed:
        return None
    return ("getonmylevel verify: the project's checks for the changed files fail. Fix the cause and rerun the "
            "failing command. If a failure is unrelated to this change, tell the user instead.\n\n"
            + find_checks.report(root, passed, failed, skipped))


def run(event: dict, output: str = "exit2") -> int:
    message = failure_message(event)
    if message is None:
        return 0
    if output == "json":
        print(json.dumps({"decision": "block", "reason": message}))
        return 0
    print(message, file=sys.stderr)
    return 2


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    output = argv[argv.index("--format") + 1] if "--format" in argv[:-1] else "exit2"
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
        return run(event if isinstance(event, dict) else {}, output if output in FORMATS else "exit2")
    except Exception:  # a hook must never trap the session
        return 0


if __name__ == "__main__":
    sys.exit(main())
