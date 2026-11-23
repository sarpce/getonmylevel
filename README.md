# getonmylevel

**A set of practical instructions and optional agent roles for Codex, Claude Code, and GitHub Copilot CLI and VS Code.** Install only the skills you want, choose whether the client should read them by default, and add role templates when your client supports them.

The seven skills cover communication, project context, software engineering, interface design, skill discovery, and focused solutions. The optional designer, implementer, reviewer, and tester roles provide separate agent profiles for supported clients. These are instructions and templates: client behavior, available tools, and higher-priority instructions determine what can run.

## Get started

### GUI

Requirements: Git, Python 3.11 or newer, Tkinter, and a graphical display. The setup tools use only Python's standard library.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
python tools/install_gui.py
```

Choose a client, select skills and a scope, then review and confirm. Choose an existing repository for repository scope. Skill files come from the checkout you cloned. To control default use, open **Active by default**, select the skills, and review and confirm that change separately. The optional **Agents** tab configures role profiles in a separate operation.

### Headless

Requirements: Git and Python 3.11 or newer. No Tkinter or graphical display is needed.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
python tools/install.py install --client codex --scope user
```

This installs the seven bundled skills for Codex. Use `--client claude` or `--client copilot` for the other supported clients. Installation does not activate skills. See [scriptable installation](INSTALL.md#scriptable-installation) for selection, scope, updates, removal, and activation.

## Install, then activate

Installing copies skill files to the selected client and scope. **Active by default** is a separate choice: it updates a managed section of the client's instructions to ask the client to read selected installed skills when relevant. The GUI provides a separate checklist; the CLI uses `activate`. Unchecking a skill from that list leaves its files available for explicit invocation. Activation is a natural-language preference and remains subject to client behavior and instruction precedence.

For example, to activate one skill for Codex:

```sh
python tools/install.py activate --client codex --scope user --skills getonmylevel-context
```

`activate` replaces the active selection for the chosen scope, so include every skill you want active in that command.

To clear the default-use selection while keeping installed files:

```sh
python tools/install.py activate --client codex --scope user --skills none
```

You can also ask for a skill explicitly, such as `$getonmylevel-engineering` or `$getonmylevel-simplicity`.

## Simple and Agentic choices

When the communication, engineering, or good software engineering practices skill is active, each new request involving a software edit calls for a fresh choice between **Simple** (work directly) and **Agentic** (use agents when delegation is permitted) before editing or delegating, including documentation changes. In Agentic mode, independent reviewer and tester choices are separate; each is off unless selected. Read-only investigation can continue while the mode choice is pending. If Agentic mode is unavailable, explain why and ask how to proceed.

These skills express instructions in natural language. They cannot intercept client tools or guarantee a choice was presented, and they do not override higher-priority session rules. Applying or updating the active skills refreshes the managed instruction block. The engineering skill also asks for delegation in Agentic mode; actual delegation depends on client and session support.

## Skills and roles

| Skill | What it helps with |
| --- | --- |
| [Communication](skills/getonmylevel-communication/SKILL.md) | Clear, concise answers with necessary context. |
| [Context](skills/getonmylevel-context/SKILL.md) | Find relevant project information and navigate code. |
| [Engineering](skills/getonmylevel-engineering/SKILL.md) | Choose Simple or Agentic mode for each software edit. |
| [Design](skills/getonmylevel-design/SKILL.md) | Design and review usable interfaces. |
| [Good software engineering practices](skills/getonmylevel-good-software-engineering-practices/SKILL.md) | Make software changes carefully and maintainably. |
| [Skill discovery](skills/getonmylevel-skill-discovery/SKILL.md) | Find relevant available skills for a task. |
| [Focused solutions](skills/getonmylevel-simplicity/SKILL.md) | Complete the requested work with a simple maintainable approach. |

Optional **designer**, **implementer**, **reviewer**, and **tester** templates configure roles independently of the skills. See [agent roles](INSTALL.md#optional-agent-roles) for client formats, model settings, and setup.

## Supported clients

| Capability | Codex | Claude Code | GitHub Copilot CLI and VS Code |
| --- | --- | --- | --- |
| Bundled skills and managed instructions | Yes | Yes | Yes |
| Optional role profiles | TOML | Markdown subagents | `.agent.md` profiles |
| Role model settings | Model and effort | Model and effort | Model only; no reasoning effort |
| CodeGraph setup | Global Codex configuration | Global Claude Code configuration | Configures CLI and VS Code together |
| Suggested integrations | Skills and tools; RTK manual | Four skill copies; CLI-Anything plugin and RTK manual | Not available |

See [client capabilities and paths](INSTALL.md#client-capabilities-and-paths) for destinations and scope behavior. All three support bundled skills and optional roles; integrations differ by client as shown above.

## Optional integrations

CodeGraph is an independent, optional global setup for all supported clients. It can provide code navigation through an MCP server; it does not initialize or index a project. Selecting the context skill does not install CodeGraph. Setup may download npm packages and change the selected client's MCP configuration and managed instructions; Node.js and npm are needed if CodeGraph must be installed.

Suggested integrations include Last 30 Days, CLI-Anything, Impeccable, UI UX Pro Max, Anti UI Slop, and RTK. Four skills can be copied for Codex and Claude Code. CLI-Anything's Codex skill uses an upstream installer; Claude uses its marketplace plugin. RTK installation is manual, and suggested integration actions are unavailable for Copilot. Review the [integration details](INSTALL.md#suggested-skillsets-and-tools) for prerequisites, pinned revisions, licenses, and installation effects.

## More information

[INSTALL.md](INSTALL.md) covers prerequisites, destinations, activation, update and removal, troubleshooting, headless setup, and integrations. [ATTRIBUTION.md](ATTRIBUTION.md) describes the focused-solutions adaptation and third-party attribution.

The optional [session selector](optional/global-session-selector.md) provides an On/Off/Ask preference block for five skills. The GUI can copy the block; it does not write it to a file. Merge it into your instructions manually if you want to use it.

## License

Source-available under a custom license. Personal, noncommercial use and private modifications are permitted. Commercial use and public distribution of modified or derivative work require prior written permission. This is not an open-source license. See [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md).
