---
name: getonmylevel-engineering
description: Apply pragmatic engineering practices across design, implementation, testing, and review while respecting user and repository rules. Use when explicitly selected or invoked.
---

# Software engineering

Follow the user's explicit instructions and repository policies. Inspect relevant code and nearby conventions before changing things. Make the smallest coherent change that addresses the request. Prioritize correctness, readable maintenance, clear interfaces, security, appropriate failure handling, and scope discipline. Avoid speculative abstractions and unnecessary dependencies.

Verify only as requested or permitted by the active instructions. Choose checks that meaningfully establish the changed behavior. Do not claim checks that did not run. Do not add tests unless requested or allowed by the active task workflow.

Handle straightforward software changes directly without asking the user to choose a mode. Use agent-based work when the user explicitly requests it or when it would materially help, and only when the active session permits delegation. Honor explicit requests to work directly and any stricter session or repository rules. If the user requests agents but delegation is unavailable or disallowed, explain the limitation and proceed directly when that fits the user's request.

For agent-based work, preserve user control over independent review and testing: ask separately whether the user wants an independent reviewer and an independent tester, with each disabled unless selected. Ask only when the choice is relevant and not already answered. Use available choice interfaces when useful, and wait for actual answers before dependent work. Do not prompt inside a delegated role.

Read [agent-workflow.md](references/agent-workflow.md) when using the agent-based workflow.
