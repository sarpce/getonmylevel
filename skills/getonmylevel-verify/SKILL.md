---
name: getonmylevel-verify
description: Finds and runs a repository's own tests, typecheck, and build for the files a change touched, and reproduces a reported bug through the project's entry point before fixing it. Use before reporting a code change as done, and when fixing a bug. Not for documentation-only or prose edits.
---

# Verify with the project's own checks

A check is worth running when it can tell a working change from a plausible one. Use checks the project already has.

## Find the checks

Run `python scripts/find_checks.py` from this skill's folder, with the repository as the working directory. It lists the targeted checks for the changed files (nearby tests plus a syntax, type, or compile check) and the full-suite commands. Pass file paths to check specific files. If it finds nothing, look in the README, CI workflow, `package.json`, `Makefile`, or `pyproject.toml`.

If the repository has a `.getonmylevel-checks` file, its commands are the checks to run.

## Code change

1. Run the targeted checks for the files you changed.
2. If the change alters shared behavior (a public function, a schema, a config format, a CLI flag), find its callers and run their tests too. Run the full suite when the change crosses a module boundary and the suite is not marked as slow.
3. Report each command you ran and its result. If you could not run a check, say which one and why.

## Bug fix

1. Reproduce the failure through the way the project is actually used: the failing test, the CLI command, the request, or the script from the report. Record the exact command and the wrong output.
2. Make the fix.
3. Rerun the same command and confirm the output is now correct. Then run the targeted checks for the files you changed.
4. If you could not reproduce the failure, say so before changing code, and describe what you tried.

## Don't

- Don't report a check as passing unless you ran it in this session and it passed.
- Don't run a slow full suite when targeted tests cover the change. If the repository says its suite is slow, it is.
- Don't write new test files just to have tests. Add one only when the request asks for it or no existing check can show the fix works.
- Don't re-read your own diff in a loop instead of running a check. Running a check is what catches the bug.
- Don't change or skip a failing test to make it pass unless the test is wrong, and say so if it is.
- Don't install tools or dependencies to run a check without asking.

If the project has no runnable checks, say so and describe the manual steps that would verify the change.
