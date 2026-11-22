---
name: getonmylevel-engineering
description: Apply pragmatic engineering practices across design, implementation, testing, and review while respecting user and repository rules. Use when explicitly selected or invoked.
---

# Software engineering

Follow the user's explicit instructions and repository policies. Inspect relevant code and nearby conventions before changing things. Make the smallest coherent change that addresses the request. Prioritize correctness, readable maintenance, clear interfaces, security, appropriate failure handling, and scope discipline. Avoid speculative abstractions and unnecessary dependencies.

Verify only as requested or permitted by the active instructions. Choose checks that meaningfully establish the changed behavior. Do not claim checks that did not run. Do not add tests unless requested or allowed by the active task workflow.

For every new request involving any software or code edit, including fixes, tests, configuration, documentation, and skill instructions, prompt the user to choose Simple or Agentic mode before editing or delegating, regardless of size or a choice made for an earlier request. Read-only investigation may continue while the answer is pending. Record the actual answer for this request; do not edit or delegate until it arrives. Simple means working directly; Agentic means using agents subject to the active session's delegation rules. Wait for the actual answer; a preselected option, default, timeout, or elapsed time is not an answer. Use a choice interface only when it can deliver the response; otherwise ask in chat and leave dependent work pending. If Agentic mode is unavailable or disallowed, explain why and ask how to proceed instead of silently switching modes. Respect higher-priority instructions.

When Agentic mode is selected, use the installed getonmylevel agent roles configured for the active client: `getonmylevel_designer` and `getonmylevel_implementer`, with `getonmylevel_reviewer` and `getonmylevel_tester` only when the user opts into those roles. Claude Code uses the corresponding hyphenated names. These predefined agents are in the getonmylevel agent skillset, separate from the skills. Set each spawned agent's type to its installed getonmylevel role. A task-specific spawn name or identifier may be chosen freely; it does not change the required agent type. If a required configured role is unavailable, explain which one is missing and ask the user how to proceed. Ask separately whether the user wants an independent reviewer and tester; each is disabled unless selected. Wait for actual answers before assigning those optional roles. Then follow the agent workflow, subject to higher-priority instructions and tool availability.

For agent-based work, preserve user control over independent review and testing: ask separately whether the user wants an independent reviewer and an independent tester, with each disabled unless selected. Ask only when the choice is relevant and not already answered. Use available choice interfaces when useful, and wait for actual answers before dependent work. Do not prompt inside a delegated role.

Read [agent-workflow.md](references/agent-workflow.md) when using the agent-based workflow.
