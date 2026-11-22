---
name: getonmylevel-context
description: Find relevant project context efficiently and maintain a small, local architecture summary when it has recurring value. Use when explicitly selected or invoked.
---

# Context and navigation

Whenever a task requires repository context, check whether the repository has a CodeGraph index. If indexed, use CodeGraph for relevant code exploration when available; fall back to targeted search and reads if it is unavailable or insufficient. If the project is not indexed, always tell the user and ask whether they want CodeGraph indexing to improve context navigation. Do not install CodeGraph or initialize an index without the user?s authorization. Continue independent work using available search and read tools while the choice is pending, and respect the user?s answer and higher-priority instructions. CodeGraph is independently selectable in the GUI installer for Codex and Claude Code.

Indexes and summaries are navigation aids. They can be stale, incomplete, or wrong. Inspect authoritative source for implementation, correctness, and consequential decisions. Do not invent undocumented behavior. Respect repository instructions, permissions, and ignore rules. Exclude secrets, generated files, and irrelevant content.

For choosing tools, read [context-tools.md](references/context-tools.md). For initializing or maintaining a local summary, read [local-summary.md](references/local-summary.md). Keep summaries local and maintenance proportional to their value. After a material change to architecture, responsibilities, key symbols, or relationships, update affected records incrementally when a summary exists. Handle additions, renames, and deletions. If freshness cannot be established, mark affected information stale and report the limitation. Routine edits do not justify a broad refresh.

Suggest practical ways to reduce repeated context work, such as scoped queries, batching independent searches, reusing returned source, and progressive disclosure. Do not promise token savings. Measure representative tasks only when authorized and feasible, and describe the workload, observed costs, and limitations.
