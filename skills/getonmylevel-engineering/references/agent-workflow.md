# Agent-based workflow

Scale the process to the task and respect the active session's delegation and verification rules.

1. **Designer:** automatically spawn the configured designer and wait for a concrete handoff with decisions, scope, affected interfaces, edge cases, acceptance criteria, and exact verification procedures.
2. **Implementer:** after design is complete, automatically spawn the configured implementer, who owns edits. If a consequential design question or missing specification arises, return it to the designer before continuing the affected work. Escalate preference-dependent choices to the user.
3. **Coordinator:** wait for implementation, inspect the actual diff, and reconcile it with the handoff.
4. **Reviewer and tester:** after implementation, spawn fresh agents independently only when each is enabled and authorized. Report findings and evidence. Recheck affected findings after edits.

Use available named roles when the platform permits, and automatically start them in this order rather than asking the user to manually trigger each role. The roles are configured separately from the three skills. If only generic delegation is available and allowed, give each agent explicit role instructions and scope. Do not claim independence or verification that the platform did not provide. Do not delegate further from a delegated role unless authorized.

Use this workflow when the user selects Agentic mode and the active session permits delegation. If delegation is unavailable or disallowed, explain the limitation and ask the user how to proceed; do not silently switch modes. Never imply that a single-agent review is independent or claim a spawn without a returned agent identity. Follow stricter project and session rules, including requirements for design, ownership, verification, or release. Keep the process proportional to the task. Ask separately whether the user wants an independent reviewer and tester unless each choice is already clear; both are disabled unless selected. Do not prompt inside a delegated role.
