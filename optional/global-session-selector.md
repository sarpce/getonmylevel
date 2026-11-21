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

Independently, on the first anticipated software-change request in an interactive session, offer Simple or Agent-based unless already chosen, even when getonmylevel skills are Off. In Agent-based mode, offer separate Yes/No choices for reviewer and tester unless existing session policy already supplies them. Apply the same response-waiting rules above to these choices, regardless of the saved preference. Honor established session choices and changes. The selector setting does not replace or weaken existing session-development instructions.

Apply selected skills by exact names: getonmylevel-communication, getonmylevel-context, getonmylevel-engineering, getonmylevel-design, getonmylevel-good-software-engineering-practices. Follow their instructions subject to instruction priority, current repository policy, delegation permissions, and available tools.
```

The optional agent GUI can copy a generated instruction block for On, Off, or Ask to the clipboard. It does not edit global files automatically.
