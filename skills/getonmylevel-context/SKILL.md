---
name: getonmylevel-context
description: Find relevant project context efficiently and maintain a small, local architecture summary when it has recurring value. Use when explicitly selected or invoked.
---

# Context and navigation

Start with a focused query using available project indexes and ignore-aware search. For small or one-off tasks, targeted file reads and `rg` are often enough. Reuse an existing index when useful; do not create a duplicate graph without a demonstrated benefit. CodeGraph is an independently selectable recommendation in the GUI installer for Codex and Claude Code; if it is absent or the project is not indexed, use the available search and read tools.

Indexes and summaries are navigation aids. They can be stale, incomplete, or wrong. Inspect authoritative source for implementation, correctness, and consequential decisions. Do not invent undocumented behavior. Respect repository instructions, permissions, and ignore rules. Exclude secrets, generated files, and irrelevant content.

For choosing tools, read [context-tools.md](references/context-tools.md). For initializing or maintaining a local summary, read [local-summary.md](references/local-summary.md). Keep summaries local and maintenance proportional to their value. After a material change to architecture, responsibilities, key symbols, or relationships, update affected records incrementally when a summary exists. Handle additions, renames, and deletions. If freshness cannot be established, mark affected information stale and report the limitation. Routine edits do not justify a broad refresh.

Suggest practical ways to reduce repeated context work, such as scoped queries, batching independent searches, reusing returned source, and progressive disclosure. Do not promise token savings. Measure representative tasks only when authorized and feasible, and describe the workload, observed costs, and limitations.
