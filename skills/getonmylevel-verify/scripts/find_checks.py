"""List or run a project's own checks for the files that changed.

    python find_checks.py [--root DIR] [FILE ...]          list checks
    python find_checks.py --run [--budget SECONDS] [FILE ...]  run the targeted checks

Without FILE arguments, the changed files come from git (staged, unstaged, and
untracked). A ``.getonmylevel-checks`` file at the repository root overrides
detection: each non-comment line is a shell command run from the root. An
empty override file turns automatic checks off for that repository.

Targeted checks are the tests that sit next to the changed files plus a
syntax, type, or compile check. Full-suite commands are only listed, because
they can take a long time; run one when the change crosses a module boundary.
Standard library only; Python 3.8 or newer.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Callable, Optional, Union

OVERRIDE = ".getonmylevel-checks"
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", ".tox", ".nox",
             ".mypy_cache", ".pytest_cache", "target", "vendor", ".next", ".turbo", "coverage", "site-packages"}
JS_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte")
TS_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".vue")
MAX_INDEXED_FILES = 50000
TAIL_LINES = 40
TAIL_CHARS = 3000


@dataclass
class Check:
    label: str
    command: Union[list, str, None]
    cwd: Path
    scope: str = "targeted"  # "targeted" runs automatically; "full" is listed only
    func: Optional[Callable[[], Optional[str]]] = field(default=None, repr=False)

    def display(self, root: Path) -> str:
        where = "" if self.cwd == root else f"(in {self.cwd.relative_to(root).as_posix()}) "
        if self.command is None:
            return f"{self.label} [built in]"
        text = self.command if isinstance(self.command, str) else " ".join(_quote(part) for part in self.command)
        return where + text


def _quote(part: str) -> str:
    return f'"{part}"' if (" " in part or not part) else part


def _git(root: Path, *args: str) -> Optional[bytes]:
    try:
        done = subprocess.run(["git", *args], cwd=root, capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def repo_root(start: Path) -> Path:
    out = _git(start, "rev-parse", "--show-toplevel")
    return Path(out.decode("utf-8", "replace").strip()) if out else start


def changed_files(root: Path) -> list:
    """Existing files that differ from HEAD, plus untracked files git does not ignore."""
    out = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if not out:
        return []
    entries = out.decode("utf-8", "replace").split("\0")
    files, skip = [], False
    for entry in entries:
        if skip:
            skip = False
            continue
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        if "R" in status or "C" in status:
            skip = True  # the next field is the source path of a rename or copy
        candidate = root / path
        # Running checks creates caches such as __pycache__; they are not changes.
        if candidate.is_file() and not SKIP_DIRS.intersection(Path(path).parts[:-1]) and candidate.suffix != ".pyc":
            files.append(candidate)
    return files


def fingerprint(root: Path) -> str:
    """A cheap identity for the working-tree state, used to skip re-running unchanged checks."""
    import hashlib
    digest = hashlib.sha256()
    digest.update(_git(root, "diff", "HEAD", "--binary") or b"")
    for path in changed_files(root)[:500]:
        try:
            info = path.stat()
        except OSError:
            continue
        digest.update(f"{path}\0{info.st_size}\0{info.st_mtime_ns}\n".encode("utf-8", "replace"))
    return digest.hexdigest()


class _Index:
    """File names under the root, built once on demand, skipping dependency and build folders."""

    def __init__(self, root: Path):
        self.root = root
        self._by_name: Optional[dict] = None

    def find(self, name: str) -> list:
        if self._by_name is None:
            self._by_name = {}
            count = 0
            for current, dirs, files in os.walk(self.root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
                for file in files:
                    self._by_name.setdefault(file, []).append(Path(current) / file)
                    count += 1
                if count > MAX_INDEXED_FILES:
                    break
        return self._by_name.get(name, [])


def _nearest(path: Path, root: Path, marker: str) -> Optional[Path]:
    for parent in (path.parent, *path.parent.parents):
        if (parent / marker).is_file():
            return parent
        if parent == root:
            break
    return None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _python(root: Path) -> str:
    for candidate in (".venv/Scripts/python.exe", ".venv/bin/python", "venv/Scripts/python.exe", "venv/bin/python"):
        if (root / candidate).is_file():
            return str(root / candidate)
    return sys.executable or "python"


def _uses_pytest(root: Path) -> bool:
    if (root / "pytest.ini").is_file() or (root / "conftest.py").is_file():
        return True
    return ("[tool.pytest" in _read(root / "pyproject.toml") or "[tool:pytest]" in _read(root / "setup.cfg")
            or "[pytest]" in _read(root / "tox.ini"))


def _syntax_check(files: list) -> Callable[[], Optional[str]]:
    def run() -> Optional[str]:
        errors = []
        for path in files:
            try:
                compile(path.read_bytes(), str(path), "exec")
            except SyntaxError as exc:
                errors.append(f"{path}:{exc.lineno}: {exc.msg}")
            except (OSError, ValueError):
                continue
        return "\n".join(errors) or None
    return run


def _python_checks(root: Path, files: list, index: _Index) -> list:
    py = [f for f in files if f.suffix == ".py"]
    if not py:
        return []
    checks = [Check("python syntax", None, root, func=_syntax_check(py))]
    tests = []
    for path in py:
        stem = path.stem
        if stem.startswith("test_") or stem.endswith("_test"):
            tests.append(path)
            continue
        for name in (f"test_{stem}.py", f"{stem}_test.py"):
            tests.extend(index.find(name))
    tests = sorted(set(tests))
    if not tests:
        return checks
    interpreter = _python(root)
    if _uses_pytest(root):
        checks.append(Check("python tests", [interpreter, "-m", "pytest", "-q", *[t.relative_to(root).as_posix() for t in tests]], root))
        return checks
    for test in tests:
        command = [interpreter, "-m", "unittest", "discover", "-s", test.parent.relative_to(root).as_posix() or ".", "-p", test.name]
        if (test.parent / "__init__.py").is_file():
            command += ["-t", "."]
        checks.append(Check(f"python tests: {test.name}", command, root))
    return checks


def _bin(package_dir: Path, root: Path, name: str) -> Optional[str]:
    for base in (package_dir, root):
        for candidate in (base / "node_modules" / ".bin" / (name + ".cmd"), base / "node_modules" / ".bin" / name):
            if candidate.is_file() and (os.name == "nt") == candidate.name.endswith(".cmd"):
                return str(candidate)
    return None


def _package_manager(package_dir: Path, root: Path) -> str:
    for base in (package_dir, root):
        for lock, manager in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lockb", "bun"), ("bun.lock", "bun")):
            if (base / lock).is_file():
                return manager
    return "npm"


def _js_checks(root: Path, files: list, index: _Index) -> list:
    groups: dict = {}
    for path in files:
        if path.suffix in JS_SUFFIXES:
            package_dir = _nearest(path, root, "package.json")
            if package_dir is not None:
                groups.setdefault(package_dir, []).append(path)
    checks = []
    for package_dir, members in groups.items():
        try:
            package = json.loads(_read(package_dir / "package.json") or "{}")
        except ValueError:
            continue
        scripts = package.get("scripts") or {}
        deps = {**(package.get("dependencies") or {}), **(package.get("devDependencies") or {})}
        manager = _package_manager(package_dir, root)
        if any(p.suffix in TS_SUFFIXES for p in members):
            if "typecheck" in scripts:
                checks.append(Check("typecheck", [manager, "run", "typecheck"], package_dir))
            elif (package_dir / "tsconfig.json").is_file() and _bin(package_dir, root, "tsc"):
                checks.append(Check("typecheck", [_bin(package_dir, root, "tsc"), "--noEmit"], package_dir))
        tests = []
        for path in members:
            base = path.name.split(".")[0]
            if any(tag in path.name for tag in (".test.", ".spec.")) or path.parent.name == "__tests__":
                tests.append(path)
                continue
            for tag in ("test", "spec"):
                for suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs"):
                    tests.extend(p for p in index.find(f"{base}.{tag}{suffix}") if package_dir in p.parents)
            tests.extend(p for p in index.find(path.name) if p.parent.name == "__tests__" and package_dir in p.parents)
        tests = sorted(set(tests))
        runner = next((name for name in ("vitest", "jest") if name in deps), None)
        binary = _bin(package_dir, root, runner) if runner else None
        if tests and binary:
            relative = [t.relative_to(package_dir).as_posix() for t in tests]
            checks.append(Check(f"{runner} tests", [binary, "run", *relative] if runner == "vitest" else [binary, *relative], package_dir))
        for name in ("test", "lint", "build"):
            if name in scripts:
                checks.append(Check(f"package {name}", [manager, "run", name], package_dir, scope="full"))
    return checks


def _go_checks(root: Path, files: list) -> list:
    if not shutil.which("go"):
        return []
    modules: dict = {}
    for path in files:
        if path.suffix == ".go":
            module = _nearest(path, root, "go.mod")
            if module is not None:
                modules.setdefault(module, set()).add(path.parent)
    checks = []
    for module, packages in modules.items():
        targets = ["./" + p.relative_to(module).as_posix() if p != module else "." for p in sorted(packages)]
        checks.append(Check("go vet", ["go", "vet", *targets], module))
        checks.append(Check("go test", ["go", "test", *targets], module))
        checks.append(Check("go test (all)", ["go", "test", "./..."], module, scope="full"))
    return checks


def _rust_checks(root: Path, files: list) -> list:
    if not shutil.which("cargo"):
        return []
    crates = {_nearest(p, root, "Cargo.toml") for p in files if p.suffix == ".rs"} - {None}
    checks = []
    for crate in sorted(crates):
        checks.append(Check("cargo check", ["cargo", "check", "--quiet"], crate))
        checks.append(Check("cargo test", ["cargo", "test", "--quiet"], crate, scope="full"))
    return checks


def _full_suite(root: Path) -> list:
    checks = []
    if (root / "pyproject.toml").is_file() or (root / "setup.py").is_file() or (root / "tests").is_dir():
        if _uses_pytest(root):
            checks.append(Check("python tests (all)", [_python(root), "-m", "pytest", "-q"], root, scope="full"))
        elif (root / "tests").is_dir():
            checks.append(Check("python tests (all)", [_python(root), "-m", "unittest", "discover", "-s", "tests"], root, scope="full"))
    makefile = _read(root / "Makefile")
    for target in ("test", "check", "lint"):
        if f"\n{target}:" in "\n" + makefile:
            checks.append(Check(f"make {target}", ["make", target], root, scope="full"))
    return checks


def read_override(root: Path) -> Optional[list]:
    path = root / OVERRIDE
    if not path.is_file():
        return None
    lines = [line.strip() for line in _read(path).splitlines()]
    return [Check(line, line, root) for line in lines if line and not line.startswith("#")]


def find_checks(root: Path, files: list) -> list:
    override = read_override(root)
    if override is not None:
        return override
    index = _Index(root)
    checks = [*_python_checks(root, files, index), *_js_checks(root, files, index),
              *_go_checks(root, files), *_rust_checks(root, files)]
    seen = {c.display(root) for c in checks}
    checks += [c for c in _full_suite(root) if c.display(root) not in seen]
    return checks


def _tail(text: str) -> str:
    lines = text.strip().splitlines()[-TAIL_LINES:]
    return "\n".join(lines)[-TAIL_CHARS:]


def run_checks(root: Path, checks: list, budget: float = 300.0) -> tuple:
    """Run targeted checks in order. Returns (passed, failed, skipped) lists of (check, detail)."""
    passed, failed, skipped = [], [], []
    deadline = time.monotonic() + budget
    for check in (c for c in checks if c.scope == "targeted"):
        remaining = deadline - time.monotonic()
        if remaining <= 1:
            skipped.append((check, "time budget used up"))
            continue
        if check.func is not None:
            problem = check.func()
            (failed if problem else passed).append((check, problem or ""))
            continue
        try:
            done = subprocess.run(check.command, cwd=check.cwd, shell=isinstance(check.command, str),
                                  capture_output=True, timeout=remaining, stdin=subprocess.DEVNULL)
        except FileNotFoundError:
            skipped.append((check, "command not found"))
            continue
        except subprocess.TimeoutExpired:
            skipped.append((check, f"timed out after {int(remaining)}s"))
            continue
        except OSError as exc:
            skipped.append((check, str(exc)))
            continue
        output = (done.stdout or b"").decode("utf-8", "replace") + (done.stderr or b"").decode("utf-8", "replace")
        (passed if done.returncode == 0 else failed).append((check, _tail(output)))
    return passed, failed, skipped


def report(root: Path, passed: list, failed: list, skipped: list) -> str:
    lines = []
    for check, detail in failed:
        lines += [f"FAILED: {check.display(root)}", detail, ""]
    for check, detail in skipped:
        lines.append(f"Not run: {check.display(root)} ({detail})")
    lines.append(f"{len(passed)} passed, {len(failed)} failed, {len(skipped)} not run.")
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="*", help="files to check (default: changed files in git)")
    parser.add_argument("--root", help="repository root (default: git top level of the current directory)")
    parser.add_argument("--run", action="store_true", help="run the targeted checks and report failures")
    parser.add_argument("--budget", type=float, default=300.0, help="total seconds for --run (default 300)")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else repo_root(Path.cwd()).resolve()
    files = [Path(f).resolve() for f in args.files] if args.files else changed_files(root)
    checks = find_checks(root, files)
    if not args.run:
        if not checks:
            print("No checks detected. Look for test, lint, or build commands in the README, CI config, or task runner.")
        for scope, title in (("targeted", "Targeted checks for the changed files:"),
                             ("full", "Full-suite commands (run when the change crosses a module boundary):")):
            group = [c for c in checks if c.scope == scope]
            if group:
                print(title)
                print("\n".join(f"  {c.display(root)}" for c in group))
        return 0
    passed, failed, skipped = run_checks(root, checks, args.budget)
    print(report(root, passed, failed, skipped))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
