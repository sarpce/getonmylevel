# Optional global session preferences

Merge and reconcile the example instruction block below with the global instruction file Codex actually reads. Do not overwrite existing instructions. OpenAI documents instruction discovery and precedence in the [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md). An `AGENTS.override.md` takes precedence over `AGENTS.md`; do not create one casually.

The preference controls below are session conventions in natural-language instructions. Codex does not enforce this block as persistent configuration, and it cannot override higher-priority instructions or guarantee that a skill or agent activates. It must coexist with any existing development-mode workflow.

```text
At the start of each new interactive conversation, unless the user already supplied a getonmylevel skill preference, apply the saved preference:

Set the preference to exactly one of: On, Off, or Ask. This setting is an instruction convention that the user can edit.

- On: use all installed getonmylevel skills.
- Off: use none of the getonmylevel skills unless the user explicitly selects one.
- Ask: offer All installed getonmylevel skills, Select individually, or None. **Wait for the user's actual response before dependent work.** Use a choice interface only if the client can deliver its response. For an asynchronous prompt, keep the turn active and wait if supported; do not finish the turn while the response is pending. A default, timeout, or elapsed time is not an answer. If the CLI or other client cannot wait for or deliver the response, ask in chat and end the turn with the question pending; resume dependent work after the user responds. Honor later changes.

Honor user changes to the preference or skill selection at any point in the conversation, regardless of the saved preference.

An explicit selection in the user's request overrides the saved preference. For Ask/individual selection, wait for the chosen skill names before work that depends on them. Use only installed, available skills. In unattended runs, never prompt: use an explicit selection if provided, otherwise none.

For every new request involving any software or code edit, including fixes, tests, configuration, documentation, and skill instructions, always prompt the user to choose Simple or Agentic mode before editing or delegating, regardless of size or an earlier choice. Simple means working directly; Agentic means using agents subject to the active session's delegation rules. Wait for the user's actual answer; a default, timeout, or elapsed time is not an answer. If a choice interface can deliver the answer, use it; otherwise ask in chat and leave dependent work pending until the user responds. If Agentic mode is unavailable or disallowed, explain the limitation and ask the user to choose how to proceed; do not silently switch modes. Respect higher-priority instructions.

For agent-based work, preserve user control over independent review and testing. Ask separately about each when the choice is relevant and not already clear; each is disabled unless selected. Wait for actual answers before dependent work. Use a choice interface when it can deliver the answer. A preselected option, timeout, or elapsed time is not an answer. If no usable popup exists, ask in chat and leave dependent work pending until the user responds. This block cannot override higher-priority instructions or guarantee activation.

Agentic mode uses only the installed getonmylevel agent roles configured for the active client: `getonmylevel_designer` and `getonmylevel_implementer`, plus `getonmylevel_reviewer` and `getonmylevel_tester` only when the user opts into them. Claude Code uses the corresponding hyphenated names. These are predefined roles in the getonmylevel agent skillset, separate from skills. Set each spawned agent's type to its installed getonmylevel role. A task-specific spawn name or identifier may be chosen freely; it does not change the required agent type. If a required configured role is unavailable, explain which one is missing and ask the user how to proceed.

Apply selected skills by exact names: getonmylevel-communication, getonmylevel-context, getonmylevel-engineering, getonmylevel-design, getonmylevel-good-software-engineering-practices. Follow their instructions subject to instruction priority, current repository policy, delegation permissions, and available tools.
```

The optional agent GUI can copy a generated instruction block for On, Off, or Ask to the clipboard. It does not edit global files automatically.
