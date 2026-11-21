---
name: getonmylevel-engineering
description: Apply pragmatic engineering practices across design, implementation, testing, and review while respecting user and repository rules. Use when explicitly selected or invoked.
---

# Software engineering

Follow the user's explicit instructions and repository policies. Inspect relevant code and nearby conventions before changing things. Make the smallest coherent change that addresses the request. Prioritize correctness, readable maintenance, clear interfaces, security, appropriate failure handling, and scope discipline. Avoid speculative abstractions and unnecessary dependencies.

Verify only as requested or permitted by the active instructions. Choose checks that meaningfully establish the changed behavior. Do not claim checks that did not run. Do not add tests unless requested or allowed by the active task workflow.

On the first anticipated interactive software-change request in a session, unless already chosen, offer **Simple** or **Agent-based** and wait for a real answer. This choice is independent of whether getonmylevel skills are On or Off. In Agent-based mode, separately offer Yes/No choices for an independent reviewer and tester; wait for missing answers. Use a supported choice interface where available. If asynchronous, keep the turn active and wait when the client supports it; a default choice or elapsed time is not an answer. Otherwise ask in chat and wait for the next user turn. Honor prior choices and changes. In unattended sessions, use an explicit selection or default to Simple; reviewer and tester remain off unless session policy says otherwise. Do not prompt inside a delegated role.

Simple mode means the main agent works directly. In Agent-based mode, read [agent-workflow.md](references/agent-workflow.md) and automatically spawn the configured designer and implementer sequentially, then fresh reviewer and tester agents when each is enabled. Do not leave spawning as a manual suggestion. Follow stricter project or session instructions where they apply.
