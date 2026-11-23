# getonmylevel

Six independently installable skills for Codex, Claude Code, or GitHub Copilot CLI and VS Code, plus optional role-agent templates and local setup tools.

## Prerequisites

- Git to clone this repository.
- Python 3.11 or newer for the setup tools. They use the standard library; the graphical tools also require a Python build with Tkinter and a graphical display.
- Codex, Claude Code, or GitHub Copilot CLI/VS Code for client-native discovery. See the [Codex skills documentation](https://developers.openai.com/codex/skills) and the [Claude Code skills](https://code.claude.com/docs/en/skills), [subagents](https://code.claude.com/docs/en/sub-agents), and [memory](https://code.claude.com/docs/en/memory) documentation.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
```

Choose Codex, Claude Code, or GitHub Copilot in the installer. The Active by default checklist integrates selected skills into the selected client's instruction file with a managed block that asks the client to read them by default when relevant. This natural-language preference remains subject to instruction precedence, client behavior, file-size limits, and skill availability. Skill installation itself does not change client settings. CodeGraph is independently selectable for Codex and Claude Code and can target Copilot CLI and VS Code together; the context skill does not require it or Node.js and npm.

## Install skills

From the checkout, run the graphical installer (from another working directory, use the path to the script):

```sh
python tools/install_gui.py
```

Choose a client and select one or more skills, CodeGraph, or both. For skills, choose **User-wide**, **Target repository**, or **Both**; repository scope requires an existing target directory. The preview shows skill and instruction actions. CodeGraph is always configured globally for the selected client, regardless of skill scope, and can be selected without a skill or target repository. The installer uses the skill files in this checkout; it does not download a release. After confirmation, an existing skill directory is replaced with the checked-out version, and its previous contents (including local edits) are kept under `getonmylevel-backups` beside the skills directory. Existing files, symlinks, junctions, and other detected reparse points are refused as skill destinations, as are linked or invalid managed paths. An I/O error during a multi-skill operation can leave earlier completed copies in place; the tool reports completed changes and backup paths.

### Client capabilities and paths

| | Codex | Claude Code | GitHub Copilot CLI and VS Code |
| --- | --- | --- |
| User-wide skills | `~/.agents/skills` | `$CLAUDE_CONFIG_DIR/skills` or `~/.claude/skills` | `~/.copilot/skills` |
| User-wide instructions | `$CODEX_HOME/AGENTS.md` or `~/.codex/AGENTS.md` | `$CLAUDE_CONFIG_DIR/CLAUDE.md` or `~/.claude/CLAUDE.md` | `~/.copilot/copilot-instructions.md` |
| Repository skills and instructions | `<repo>/.agents/skills`, `<repo>/AGENTS.md` | `<repo>/.claude/skills`, `<repo>/CLAUDE.md` | `<repo>/.github/skills`, `<repo>/.github/copilot-instructions.md` |
| Agent files, user-wide | `$CODEX_HOME/agents` or `~/.codex/agents` (TOML) | `$CLAUDE_CONFIG_DIR/agents` or `~/.claude/agents` (Markdown) | `~/.copilot/agents` (Markdown) |
| Agent files, repository | `<repo>/.codex/agents` (TOML) | `<repo>/.claude/agents` (Markdown) | `<repo>/.github/agents` (Markdown) |
| Optional integrations | CodeGraph; Last 30 Days, CLI-Anything, Impeccable, UI UX Pro Max, and Anti UI Slop; RTK is manual | CodeGraph; Last 30 Days, Impeccable, UI UX Pro Max, and Anti UI Slop skills; CLI-Anything marketplace plugin and RTK are manual | CodeGraph; suggested integrations are unavailable |

Environment-variable paths apply when the variable is set; otherwise the home-directory path is used. For Codex instructions, the installer selects a nonempty `AGENTS.override.md` in preference to `AGENTS.md` at either scope. **Both** writes to both selected scope locations and may cause duplicate skill discovery; usually choose one. Skills and agents have separate client and scope controls and separate confirmations. Start a new conversation if changed instructions are not picked up; restart the selected client if new skills are not discovered or the CodeGraph MCP server is unavailable. Client behavior depends on its version and configuration.

In **Agents**, Codex roles use the existing TOML format. Claude Code roles use native Markdown subagent files. GitHub Copilot roles use `.agent.md` profiles shared by Copilot CLI and VS Code. Model and effort fields are editable for each role; Claude offers common aliases as suggestions and also accepts full model IDs. A selected ID does not guarantee account access or model availability. Suggested skill copies are available for Codex and Claude Code. Claude Code uses `$CLAUDE_CONFIG_DIR/skills` when configured, otherwise `~/.claude/skills`; Codex paths remain independent. CLI-Anything's Codex skill is automatic; for Claude it is a marketplace plugin managed through Claude Code's `/plugin` interface. RTK remains manual. GitHub Copilot suggested actions remain unavailable. CodeGraph can be configured for Codex, Claude Code, and GitHub Copilot CLI and VS Code together.

The **Active by default** checklist is independent of the core skill install/update selection. It starts with the existing managed selections; applying it replaces the active set for each displayed scope. When Both is selected, user-wide and repository checklists remain separate. Unchecking a skill leaves its files installed for explicit use. Clearing a checklist removes its managed block. The preview shows any missing skill files that must be installed before activation and the proposed instruction changes. The managed block preserves surrounding instruction bytes. Malformed or manually edited managed blocks are refused for manual repair. To turn off the default preference, select the client and scope and use **Remove getonmylevel instructions** in the GUI, or remove the exact region beginning `<!-- getonmylevel-skills:begin -->` and ending `<!-- getonmylevel-skills:end -->`. Either leaves installed skill directories in place. Instructions are subject to higher-priority guidance and Codex's `project_doc_max_bytes` limit, so a large instruction file may prevent the block from being read.

Activating **getonmylevel-skill-discovery** asks the client to read that skill when relevant; its discovery guidance remains in the skill file. The GUI labels the bundled choices **Core skills**. CodeGraph is an independent recommendation for Codex, Claude Code, and Copilot CLI plus VS Code, whether or not the context skill is selected. If explicitly selected and missing, Node.js and npm are required to install it. Global setup may download packages and changes the selected client's MCP configuration and managed instructions. The GUI does not initialize or index a project; indexing is a separate choice. When managed instructions are active, the client is instructed to use an existing index for repository context and offer indexing when a project has none. Client behavior remains subject to instruction precedence and tool availability. Restart the selected client if its MCP server is not available.

### Suggested skillsets and tools

The Codex view includes an unchecked-by-default **Suggested skillsets and tools** section. Claude Code supports automatic copies for Last 30 Days, Impeccable, UI UX Pro Max, and Anti UI Slop. Claude CLI-Anything is a marketplace plugin and RTK is manual. Suggested actions are unavailable for GitHub Copilot. See the [headless setup commands](#headless-setup-operations) for status, installation, and safe removal. Presence in a supported directory does not establish that a copy was installed by this project. Removals target exact directories; linked paths or trees without `SKILL.md` are refused. Each operation reports its result independently.

Last 30 Days requires Git and installs the complete upstream `skills/last30days` directory to `~/.agents/skills/last30days` from selected commit `bb2f1ed2b9f6d07b90557c5eebd736b566533fec`. CLI-Anything requires Git plus PowerShell on Windows or Bash on macOS/Linux. It runs the upstream Codex skill installer from selected commit `34f519533bc175d2fe287ab8316b0dd99bb9cc43`, which installs the generator skill and its supporting resources to `$CODEX_HOME/skills/cli-anything` or `~/.codex/skills/cli-anything`; it does not install all application harnesses. The installer fetches each commit, checks out detached, and verifies `HEAD` before copying or executing. These selected revisions have not been represented as integration-tested. Last 30 Days files are copied without executing their code. CLI-Anything executes upstream code with your user privileges.

Impeccable, UI UX Pro Max, and Anti UI Slop install as complete Codex skill directories in `~/.agents/skills`. Installation requires Git and network access and uses pinned commits `b49177d32788f2dc585c42831d845dacf1ebed2c`, `a38d04c3d5c298c851dbe5e6ee1965ee3de42cb5`, and `4a0224f578f65a87f328e9c533b3d8bf1023c1f7`, respectively. The installer verifies the pinned commit, rejects symlinks and submodules within the selected skill tree, and copies the upstream license notices with the skill files. UI UX Pro Max uses bundled Python 3 scripts and local data. Its Codex instructions use `{SKILL_DIR}` to refer to the installed skill directory. Impeccable's engine may download a platform binary on first use. The installer copies the skill files for manual invocation in Codex.

RTK is a standalone command-output optimizer. Automatic installation is disabled because Winget and Homebrew select moving package versions. Install a reviewed version manually from the [RTK installation guide](https://www.rtk-ai.app/docs/getting-started/installation/), checking the edition, source and license (Winget full edition includes Apache-2.0 and BUSL-1.1 components; Homebrew `rtk-oss` is Apache-2.0 and omits the pipeline engine). The GUI detects an `rtk` executable on PATH but cannot establish its identity or version; removal is manual. RTK installation does not activate it or configure Codex. Review [RTK setup instructions](https://github.com/rtk-ai/rtk) separately before running `rtk init -g --codex`, which changes global Codex configuration.

CodeGraph installs the exact npm spec `@colbymchenry/codegraph@1.6.4` when no executable exists. This is a selected package version and is not claimed as tested by this installer. If a `codegraph` command already exists, it is preserved without an upgrade; its version and provenance are reported as unknown and unverified. To update one, manually review the existing configuration and perform a deliberate remove/reinstall or package-manager update after checking the desired release.

The confirmation shows selected commits, planned commands/actions, destinations, prerequisites, network activity, client adaptations, and execution effects. Canceling makes no changes. Git commands use argument arrays without shell interpretation. Existing skill copies are detected separately per client and are not silently updated; remove the selected client's detected skill in the GUI or CLI, then reinstall the selected pin. Claude marketplace plugins are detected where their registration is present and must be removed through Claude's `/plugin` interface; the setup tools never delete plugin caches. Restart the selected client after installing skills if they are not discovered. Detected installations do not establish version or provenance.

Maintainers update pins in `tools/codegraph_installer.py` (`PACKAGE_VERSION`) and `tools/suggested_installers.py` (`LAST30_COMMIT`, `CLI_ANYTHING_COMMIT`, `IMPECCABLE_COMMIT`, `UI_UX_PRO_MAX_COMMIT`, `ANTI_UI_SLOP_COMMIT`). Review upstream release notes and diffs, select immutable versions/commit IDs, validate the expected files and installer behavior, run the mocked/local-repository test suite, then update this document and README. Record actual integration-test evidence before describing a pin as tested. Pins do not make registries or Git hosting immutable, validate publisher identity, pin npm transitive dependencies or downloads performed by upstream scripts, or guarantee platform-specific installer behavior. Existing installations may have unknown provenance.

### Scriptable installation

The command works without Tkinter or a display, for Codex, Claude Code, and GitHub Copilot. It requires Python 3.11 or newer and uses only the standard library. Run it from the checkout (or use the full path to `tools/install.py`):

```sh
python tools/install.py install --client codex --scope user
python tools/install.py update --client claude --scope repo --repo /path/to/repository
python tools/install.py remove --client codex --scope user --skills getonmylevel-context
python tools/install.py activate --client claude --scope repo --repo /path/to/repository --skills getonmylevel-design --dry-run
python tools/install.py install --client copilot --scope repo --repo /path/to/repository --dry-run
python tools/install.py activate --client codex --scope user --skills none
```

All six skills are selected by default; `--skills` accepts one or more exact skill names. `install` and `update` both install missing skills and update existing ones without changing activation. `activate` replaces the active set and installs missing selected skills; `--skills none` clears it. With `--scope both`, activate applies the same explicit selection to both scopes; run it separately for differing selections. Updates and removals preserve previous directories in `getonmylevel-backups`. Removal also removes the selected skills from managed default-use instructions, retaining other skill references and surrounding text. `--dry-run` previews actions without writing; normal commands apply immediately and return a nonzero exit status on failure. Operations across multiple paths are not transactional. This command handles bundled skills and their instructions. Agent roles, CodeGraph, and suggested integrations use the separate setup command below.

### Headless setup operations

`tools/setup.py` uses the standard library and does not import Tkinter. `--dry-run` previews file destinations, third-party commands, network activity, global configuration targets, and removals. CodeGraph dry runs defer npm's global-prefix command because running npm may execute code; the exact executable path remains unresolved until confirmed setup. No setup command initializes or indexes a project. `--yes` is required before global role changes, CodeGraph package installation/global configuration, suggested integration installation, and suggested integration removal. Without it the command exits without prompting.

```sh
# Inspect role destinations, then write selected roles for a repository.
python tools/setup.py roles install --client claude --scope repo --repo /path/to/repository --roles designer implementer --dry-run
python tools/setup.py roles install --client claude --scope repo --repo /path/to/repository --roles designer implementer --model designer=sonnet --effort designer=high

# Omitted model/effort values preserve each existing file's settings.
python tools/setup.py roles update --client codex --scope both --repo /path/to/repository --roles reviewer tester --dry-run
python tools/setup.py roles install --client codex --scope global --roles designer --yes
python tools/setup.py roles remove --client copilot --scope global --roles reviewer --dry-run

# Inspect CodeGraph, preview global setup, then confirm its network/global effects.
python tools/setup.py codegraph status --client codex
python tools/setup.py codegraph setup --client claude --dry-run
python tools/setup.py codegraph setup --client claude --yes

# Suggested integrations: status, pinned install plan, and guarded removal.
python tools/setup.py suggested status --client claude
python tools/setup.py suggested install --client codex --items last30days impeccable --dry-run
python tools/setup.py suggested install --client codex --items last30days --yes
python tools/setup.py suggested remove --client claude --items last30days --dry-run
python tools/setup.py suggested remove --client claude --items last30days --yes
```

Role scope is `global`, `repo`, or `both`; repository scope requires an existing target distinct from this checkout. Supported roles are `designer`, `implementer`, `reviewer`, and `tester`. Use repeated `--model ROLE=VALUE` and `--effort ROLE=VALUE`; `ROLE=` clears a field. New files inherit client defaults, and Copilot does not support reasoning effort. Existing settings are preserved when omitted. Role files are written or removed only if their management marker and template content match; linked and hand-edited files are refused. Writes are atomic per file, but a multi-file failure can leave earlier actions completed; those paths are reported.

CodeGraph status reports command presence without inferring version or provenance. Setup selects `@colbymchenry/codegraph@1.6.4`, may download npm packages and run lifecycle code, and configures the selected client's global MCP settings and managed instructions. Copilot targets CLI and VS Code together. A detected command is preserved without upgrading. Project indexing remains a separate explicit operation.

Suggested integrations are supported for Codex and Claude Code. Claude supports four copied skills; CLI-Anything is managed through Claude's marketplace interface, and RTK is manual for every client. GitHub Copilot has no suggested integration actions. Codex CLI-Anything runs its selected upstream installer with the user account. The CLI reports each install/removal result and possible partial changes. Detection does not establish version or provenance.

## Session selection

The optional selector instruction in [`optional/global-session-selector.md`](optional/global-session-selector.md) supports **On**, **Off**, and **Ask** preferences for the original five skills. It requests a Simple or Agentic mode choice for each software edit independently of skill selection, subject to the active session's rules. Merge it manually with your effective global instructions; it does not edit or override them. These are conversation conventions, not enforced Codex settings. The GUI can copy a generated instruction block without changing any file.

Explicit skill invocation uses `$getonmylevel-communication`, `$getonmylevel-context`, `$getonmylevel-engineering`, `$getonmylevel-design`, `$getonmylevel-good-software-engineering-practices`, or `$getonmylevel-skill-discovery`. Higher-priority instructions and available tools always constrain activation; the installed client determines whether a skill is discovered and invoked.

## Optional agent roles

The optional templates in [`optional/agents`](optional/agents) configure designer, implementer, reviewer, and tester roles separately from the skills for Codex, Claude Code, and GitHub Copilot. Run the GUI with:

```sh
python tools/agents_gui.py
```

Choose the client, roles, and global user, repository, or both scopes. Destinations and file formats are listed in the [client table](#client-capabilities-and-paths). The tool shows a preview and requires confirmation. It updates only files bearing its management marker and exact template instructions, preserving existing model and reasoning-effort values in editable controls. Unknown or hand-edited templates and symlinks are refused. Each file replacement is atomic; a set of files is not transactional. It does not edit client instruction or configuration files.

Model and effort fields are editable where supported; Copilot profiles support an optional model and do not set reasoning effort. Blank model values inherit client defaults. For Codex, **Refresh available models** explicitly queries the local `codex app-server`; it requires Codex on `PATH` or, on Windows, the Codex VS Code extension installed in its standard location. It uses the documented [`model/list` API](https://developers.openai.com/codex/app-server) and [`agents` configuration](https://developers.openai.com/codex/multi-agent). For Copilot, refresh uses the [Copilot Python SDK](https://github.com/github/copilot-sdk/tree/main/python). Install the optional SDK in the Python environment running the GUI with `python -m pip install microsoft-copilot-sdk`. The SDK uses its compatible runtime and may download it on first use; listing models contacts GitHub and requires Copilot authentication. Discovery may be unavailable; in that case enter values manually. Claude Code offers model aliases as suggestions and accepts full IDs. A listed model does not guarantee availability in every Copilot client or account.

Activating the engineering skill adds a standing request for delegation in Agentic mode to the installer-managed instructions. Update the active selection to refresh an existing managed block. The engineering skill requests a Simple or Agentic mode choice for every new software edit before editing or delegating. Simple means direct work; Agentic uses configured roles when delegation is permitted. Independent review and testing remain separate choices, each disabled unless selected. These are natural-language instructions and cannot override higher-priority session rules or guarantee client behavior.

## Context tools

CodeGraph is an independently selectable user-wide recommendation. After confirmation, the GUI or `tools/setup.py` installs it if needed and configures the selected client globally; it may download packages and edit that client's MCP configuration and managed instructions. It does not initialize or index a project.

The GUI shows local CodeGraph command detection and has a **Refresh status** control and **Details** view with the official project page, selected version for a new installation, unknown existing version/provenance, and installation effects. Detection does not execute a command or establish its identity. If using CodeGraph manually, review its [repository and setup instructions](https://github.com/colbymchenry/codegraph); project indexing is separate from global client configuration.

## Platform notes

The GUIs use Python's standard-library Tkinter and work on Windows, macOS, and Linux when Tk support is available. Run scripts directly with Python; they locate repository content relative to their own files. If no graphical display or Tk is available, the skill installer has terminal instructions above and agent templates can be edited manually. No credentials are needed for local installation. Model refresh has the optional client-specific requirements described above.

## License and attribution

This repository is source-available under a custom license: personal, noncommercial use and private modifications are permitted; commercial use and public distribution of modified or derivative work require prior written permission. This is not an open-source license. See [`LICENSE`](LICENSE) and [`ATTRIBUTION.md`](ATTRIBUTION.md). The license wording is a starting point and should receive legal review before publication.
