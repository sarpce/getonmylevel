# getonmylevel

**Practical skills and optional agent roles for Codex and Claude Code. Install from one desktop app.**

Six skills for communication, context, engineering, design, software practices, and skill discovery. Choose what you need.

## Skills

| Skill | Purpose |
| --- | --- |
| [Communication](skills/getonmylevel-communication/SKILL.md) | Clear, concise answers. |
| [Context](skills/getonmylevel-context/SKILL.md) | Find relevant project context efficiently. |
| [Engineering](skills/getonmylevel-engineering/SKILL.md) | Guide software work; choose Simple or Agent-based workflow. |
| [Design](skills/getonmylevel-design/SKILL.md) | Design deliberate, usable interfaces. |
| [Good software engineering practices](skills/getonmylevel-good-software-engineering-practices/SKILL.md) | Keep software changes correct, secure, and maintainable. |
| [Skill discovery](skills/getonmylevel-skill-discovery/SKILL.md) | Find useful available skills for each task. |

Optional **designer, implementer, reviewer, and tester** agent templates give Codex separate roles. Skills are instructions, not magic switches: actual behavior depends on client support, available tools, and higher-priority instructions.

## Install

Requires Git, Python 3.11+ with Tkinter, and a Codex client supporting local skills and custom agents. GUI works on Windows, macOS, and Linux when Tk and a display are available.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
python tools/install_gui.py
```

1. In **Skills & installation**, choose skills and **User-wide**, **Target repository**, or **Both**. For repository scope, choose an existing repository.
2. Read preview. Confirm to install the versions in this checkout and add managed default-use instructions to the applicable `AGENTS.md` (or existing nonempty `AGENTS.override.md`). Existing surrounding instructions stay.
3. Choose **Codex** or **Claude Code** in either installer. In **Agents**, optionally choose roles, scope, and per-role model settings. Review and confirm those changes separately.
4. Start a new Codex conversation to load changed instructions. Restart Codex if new skills or the CodeGraph MCP server are not discovered.

Already have a skill installed? GUI updates it and keeps the old directory in a `getonmylevel-backups` folder beside the skills directory. A failed multi-skill operation can leave earlier changes in place; read the result. To open the same app through the agent entry point, run `python tools/agents_gui.py`.

## Use skills and agents

The installer asks Codex to read selected skills by default when relevant. You can also name a skill explicitly, for example `$getonmylevel-engineering` or `$getonmylevel-design`. Your instructions and higher-priority rules still apply.

For an interactive software change, the engineering skill offers **Simple** or **Agent-based** and waits for your choice. Simple means the main agent works directly. Agent-based uses a designer and then an implementer; independent review and testing are separate choices. Delegation and checks still need to be allowed by the active session. Configure the optional roles in the Agents tab before using them.

The Agents tab can also copy an optional On/Off/Ask session preference block. It does not write that block to a file; merge it into your instructions yourself if wanted. See [session selector](optional/global-session-selector.md) for its scope.

## Where things go

- User-wide skills: `~/.agents/skills`. Instructions: `$CODEX_HOME/AGENTS.md`, or `~/.codex/AGENTS.md` when `CODEX_HOME` is unset.
- Repository skills: `<target-repository>/.agents/skills`. Instructions: the target repository's `AGENTS.md`.
- Agent roles: `$CODEX_HOME/agents` (or `~/.codex/agents`) for user scope; `<target-repository>/.codex/agents` for repository scope.

A nonempty `AGENTS.override.md` takes precedence over `AGENTS.md` in Codex locations. Installing skills in both scopes can cause duplicate discovery; usually choose one. The Agents tab writes native Codex TOML roles or Claude Code Markdown subagents, not client configuration.

Claude Code uses `~/.claude/skills` and `<repo>/.claude/skills`, with managed default-use instructions in `~/.claude/CLAUDE.md` or `<repo>/CLAUDE.md`. User-wide locations follow `CLAUDE_CONFIG_DIR` when set. Claude subagents go to `~/.claude/agents` or `<repo>/.claude/agents`. Codex keeps its existing `.agents`, `.codex`, and `AGENTS.md` locations. Claude model aliases are suggestions; editable model IDs are accepted, but availability depends on the account. Optional suggested tools remain Codex-specific; CodeGraph can target either client. Switching clients refreshes destinations and changes only the selected client's files.

To remove the managed default-use instructions, choose the scope and use **Remove getonmylevel instructions** in the GUI. This leaves skill files in place. To remove a skill itself, delete only its own `getonmylevel-*` directory. Deselecting a skill during a later install does not remove it or its managed instruction.

## Extra tools

**CodeGraph** is an independently selectable recommendation for Codex and Claude Code. Selecting the context skill does not install it or require Node.js or npm. When explicitly selected, CodeGraph is installed if missing (requiring Node.js and npm) and configured globally for the chosen client. Setup may download packages and change that client's MCP configuration and managed instructions. It does not initialize or index any project; that is a separate choice.

The GUI offers optional [RTK](https://github.com/rtk-ai/rtk), [Last 30 Days](https://github.com/mvanhorn/last30days-skill), and [CLI-Anything](https://github.com/HKUDS/CLI-Anything). They are unchecked by default. Review each confirmation: external installs may download files or run upstream code, and upstream branches are not pinned. RTK is installed separately from its Codex activation. The GUI can remove detected Last 30 Days and CLI-Anything skill directories; remove RTK with its package manager.

## More details

[INSTALL.md](INSTALL.md) has detailed destinations, update and removal behavior, optional tool prerequisites, troubleshooting, and a terminal fallback when Tkinter is unavailable. The terminal fallback installs new skill copies only; it does not add instructions or install CodeGraph.

## License

Source-available under a custom license. Personal, noncommercial use and private modifications are permitted. Commercial use and public distribution of modified or derivative work require prior written permission. See [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md).
