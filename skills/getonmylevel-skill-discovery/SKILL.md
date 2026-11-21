---
name: getonmylevel-skill-discovery
description: Discover and apply available skills when they can materially improve the current task.
---

# Skill discovery

For each task, review the available skills and consider which could materially improve the outcome. Use the session's skill catalog first; where relevant, check applicable user and repository skill locations, including `.agents/skills`, `.codex/skills`, and `.skills` where present. Avoid broad searches when the catalog already provides the needed information.

Read a selected skill's `SKILL.md` before applying it, and follow its relevant instructions. Use judgment: do not invoke a skill solely because a keyword matches, and do not load unrelated skills. Honor explicit user preferences, instruction precedence, available tools, and filesystem permissions. A skill's presence does not itself authorize actions outside the user's request.
