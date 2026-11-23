---
name: getonmylevel-simplicity
description: Choose the simplest maintainable approach that fully solves a software task. Use when implementing, fixing, refactoring, reviewing, or selecting dependencies, especially when scope or complexity needs careful control.
---

# Focused solutions

Solve the whole problem with only the complexity the task needs. Simplicity is a way to reduce unnecessary work, not a reason to leave requirements unfinished.

## Work from the complete scope

Understand the requested outcome and inspect the code and conventions the change touches. Identify affected callers, interfaces, tests, fixtures, configuration, and user-visible behavior. Consider compatibility, data loss or exposure, and failure cases relevant to the change. Keep the implementation focused while completing every necessary part.

## Choose an approach

Consider, in order, whether the work is needed as requested, whether an existing project utility or pattern fits, and whether a suitable platform capability or already-installed dependency solves it. Add code, abstraction, configuration, or a dependency when it makes the complete solution clearer, safer, or easier to maintain. Do not optimize for line count: prefer code that is straightforward to understand and handles the task's real cases.

Keep existing validation and error handling when moving or combining code. Preserve security boundaries, accessibility, compatibility, and behavior the user asked to retain. Do not trade these away for a smaller diff.

## Finish and communicate

Use checks appropriate to the risk and scope, following the user's preferences and repository instructions. Trivial changes may need no extra tests; consequential logic and security-sensitive behavior need meaningful verification. Report what changed and checks actually run. State important limitations or risks plainly, without implying that unverified behavior was checked.

Respect higher-priority instructions and explicit user choices. Resolve routine implementation details with judgment; ask only when missing information materially changes correctness, safety, or the result the user wants.
