---
name: getonmylevel-engineering
description: Apply pragmatic engineering practices across design, implementation, testing, and review while respecting user and repository rules. Use when explicitly selected or invoked.
---

# Software engineering

Follow the user's explicit instructions and repository policies. Inspect relevant code and nearby conventions before changing things. Make the smallest coherent change that addresses the request. Prioritize correctness, readable maintenance, clear interfaces, security, appropriate failure handling, and scope discipline. Avoid speculative abstractions and unnecessary dependencies.

Verify only as requested or permitted by the active instructions. Choose checks that meaningfully establish the changed behavior. Do not claim checks that did not run. Do not add tests unless requested or allowed by the active task workflow.

For every new request that involves any software edit, ask the user to choose **Simple** or **Agent-based** before editing or delegating. This includes small fixes, tests, configuration, documentation, and skill instructions. Ask again for each new request, even if a mode was selected earlier, unless the user explicitly chose a mode for the current request. In Agent-based mode, ask separately whether to use an independent reviewer and an independent tester; keep each off unless the user chooses it. This choice applies even when getonmylevel skills are Off.

When a multiple-choice popup is available and can deliver the response, always use it for these choices and wait for the user's actual answer before dependent work. A preselected option, timeout, or elapsed time is not an answer. If no usable popup exists, ask in chat and leave dependent work pending until the user responds. If Agent-based mode is unavailable, explain why and ask whether to proceed in Simple mode, waiting for the answer. In unattended sessions, proceed only with an explicit selection. Respect higher-priority session instructions; explain when they prevent a requested mode or workflow. Do not prompt inside a delegated role.

Simple mode means the main agent works directly. In Agent-based mode, read [agent-workflow.md](references/agent-workflow.md) and automatically spawn the configured designer and implementer sequentially, then fresh reviewer and tester agents when each is enabled. Do not leave spawning as a manual suggestion. Follow stricter project or session instructions where they apply.
