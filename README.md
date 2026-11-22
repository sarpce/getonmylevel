# getonmylevel

**Practical skills and optional agent roles for Codex and Claude Code.**

Six skills for communication, context, engineering, design, software practices, and skill discovery. Choose what you need.

## Skills

| Skill | Purpose |
| --- | --- |
| [Communication](skills/getonmylevel-communication/SKILL.md) | Clear, concise answers. |
| [Context](skills/getonmylevel-context/SKILL.md) | Find relevant project context efficiently. |
| [Engineering](skills/getonmylevel-engineering/SKILL.md) | Require a Simple or Agentic mode choice for software edits. |
| [Design](skills/getonmylevel-design/SKILL.md) | Design deliberate, usable interfaces. |
| [Good software engineering practices](skills/getonmylevel-good-software-engineering-practices/SKILL.md) | Keep software changes correct, secure, and maintainable. |
| [Skill discovery](skills/getonmylevel-skill-discovery/SKILL.md) | Find useful available skills for each task. |

Optional **designer, implementer, reviewer, and tester** templates provide roles for Codex and subagents for Claude Code. Skills are instructions, not magic switches: actual behavior depends on client support, available tools, and higher-priority instructions.

## Install

To clone and run the GUI, use Git and Python 3.11+ with Tkinter and a graphical display. Choose Codex or Claude Code for client-native discovery; see [installation prerequisites](INSTALL.md#prerequisites) for optional tools.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
python tools/install_gui.py
```

1. In **Skills & installation**, choose **Codex** or **Claude Code**, then select skills and a scope. For repository scope, choose an existing repository. CodeGraph is an independent optional selection and can be installed on its own.
2. Review the preview and confirm. Selected skills are copied from this checkout. Use **Active by default** separately to select and apply the skills the client should read when relevant; the preview shows any missing files required for activation.
3. In **Agents**, optionally choose the client, roles, scope, and per-role model settings. Review and confirm those changes separately.
4. Start a new conversation if changed instructions are not picked up. Restart the selected client if new skills or the CodeGraph MCP server are not discovered.

Already have a skill installed? GUI updates it and keeps the old directory in a `getonmylevel-backups` folder beside the skills directory. A failed multi-skill operation can leave earlier changes in place; read the result. To open the same app through the agent entry point, run `python tools/agents_gui.py`.

For headless or automated setup, install all bundled skills with:

```sh
python tools/install.py install --client codex --scope user
```

Use `--client claude` for Claude Code, `--dry-run` to preview, and `update` or `remove` for subsequent changes. See [scriptable installation](INSTALL.md#scriptable-installation) for scope and skill selection. Python 3.11+ is required.

## Use skills and agents

The Active by default checklist controls which installed skills the selected client is asked to read when relevant. You can also name a skill explicitly, for example `$getonmylevel-engineering` or `$getonmylevel-design`. Your instructions and higher-priority rules still apply.

When the engineering skill is active, every new request involving a software edit requires a choice between Simple and Agentic modes before editing or delegating, including small fixes and documentation changes. Simple means working directly; Agentic uses agents when delegation is permitted. Independent review and testing are separate choices, each disabled unless selected. Activating the engineering skill adds a standing request for delegation in Agentic mode to the installer-managed instructions. If Agentic mode is unavailable, the user chooses how to proceed. Higher-priority session instructions still apply.

The Agents tab can also copy an optional On/Off/Ask session preference block. It does not write that block to a file; merge it into your instructions yourself if wanted. See [session selector](optional/global-session-selector.md) for its scope.

## Client support and paths

The GUI writes client-specific skills, instructions, and optional agent files. The [client capabilities and paths table](INSTALL.md#client-capabilities-and-paths) lists destinations, environment overrides, and scope behavior. Suggested tools are offered in the Codex view; CodeGraph can target either client.

## Extra tools

**CodeGraph** is an independently selectable recommendation for Codex and Claude Code. Selecting the context skill does not install it or require Node.js or npm. When explicitly selected, CodeGraph is installed if missing (requiring Node.js and npm) and configured globally for the chosen client regardless of skill scope. Setup may download packages and change that client's MCP configuration and managed instructions. It does not initialize or index any project; that is a separate choice.

The Codex GUI offers optional [RTK](https://github.com/rtk-ai/rtk), [Last 30 Days](https://github.com/mvanhorn/last30days-skill), [CLI-Anything](https://github.com/HKUDS/CLI-Anything), [Impeccable](https://github.com/pbakaus/impeccable), [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill), and [Anti UI Slop](https://github.com/uizze/uizze). They are unchecked by default. Git-based skills install from selected commits. CLI-Anything runs upstream code with your privileges. Impeccable, UI UX Pro Max, and Anti UI Slop are copied without running installer code or setting up optional hooks. Existing suggested skills are not silently updated. CodeGraph uses selected npm version `1.6.4` when installing fresh. RTK automatic installation is disabled because available package-manager commands float; install a reviewed version manually. Maintainers update pins in the installer modules; see [INSTALL.md](INSTALL.md) for pinning and installation details.

## More details

[INSTALL.md](INSTALL.md) has detailed destinations, update and removal behavior, optional tool prerequisites, and scriptable installation, updates, and removal for both clients without Tkinter or a display. The command also manages default-use instructions; CodeGraph remains a separate GUI operation.

## License

Source-available under a custom license. Personal, noncommercial use and private modifications are permitted. Commercial use and public distribution of modified or derivative work require prior written permission. See [LICENSE](LICENSE) and [ATTRIBUTION.md](ATTRIBUTION.md).
