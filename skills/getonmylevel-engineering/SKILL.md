---
name: getonmylevel-engineering
description: Apply pragmatic engineering practices across design, implementation, testing, and review while respecting user and repository rules. Use when explicitly selected or invoked.
---

# Software engineering

Follow the user's explicit instructions and repository policies. Inspect relevant code and nearby conventions before changing things. Make the smallest coherent change that addresses the request. Prioritize correctness, readable maintenance, clear interfaces, security, appropriate failure handling, and scope discipline. Avoid speculative abstractions and unnecessary dependencies.

Verify only as requested or permitted by the active instructions. Choose checks that meaningfully establish the changed behavior. Do not claim checks that did not run. Do not add tests unless requested or allowed by the active task workflow.

For every new request involving any software or code edit, including fixes, tests, configuration, documentation, and skill instructions, always prompt the user to choose Simple or Agentic mode before editing or delegating, regardless of size or an earlier choice. Simple means working directly; Agentic means using agents subject to the active session's delegation rules. Wait for the user's actual answer; a default, timeout, or elapsed time is not an answer. If a choice interface can deliver the answer, use it; otherwise ask in chat and leave dependent work pending until the user responds. If Agentic mode is unavailable or disallowed, explain the limitation and ask the user to choose how to proceed; do not silently switch modes. Respect higher-priority instructions.

When Agentic mode is selected, delegate work to available sub-agents as described in the workflow, subject to higher-priority instructions and tool availability.

For agent-based work, preserve user control over independent review and testing: ask separately whether the user wants an independent reviewer and an independent tester, with each disabled unless selected. Ask only when the choice is relevant and not already answered. Use available choice interfaces when useful, and wait for actual answers before dependent work. Do not prompt inside a delegated role.

Read [agent-workflow.md](references/agent-workflow.md) when using the agent-based workflow.
