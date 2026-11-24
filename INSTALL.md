# getonmylevel

Three narrow, independently installable skills for Codex, Claude Code, GitHub Copilot CLI and VS Code, or OpenCode, an optional stop hook for each client that runs the project's checks, an optional reviewer role, and local setup tools.

Each part is kept only because a controlled evaluation showed that kind of change improves coding agents; parts without such evidence were removed. The README's [What changed from earlier versions](README.md#what-changed-from-earlier-versions) table gives the evidence for each.

## Contents

- [Prerequisites](#prerequisites)
- [Install skills](#install-skills)
- [Client capabilities and paths](#client-capabilities-and-paths)
- [Suggested skillsets and tools](#suggested-skillsets-and-tools)
- [Scriptable installation](#scriptable-installation)
- [Headless setup operations](#headless-setup-operations)
- [Upgrading from the seven-skill release](#upgrading-from-the-seven-skill-release)
- [Verify hook](#verify-hook)
- [Optional agent roles](#optional-agent-roles)
- [Platform notes](#platform-notes)
- [Troubleshooting](#troubleshooting)
- [License and attribution](#license-and-attribution)

## Prerequisites

- Git to clone this repository.
- Python 3.11 or newer for the setup tools. They use the standard library; the graphical tools also require a Python build with Tkinter and a graphical display.
- Codex, Claude Code, or GitHub Copilot CLI/VS Code for client-native discovery. See OpenAI's current [Codex skills documentation](https://learn.chatgpt.com/docs/build-skills.md) and the [Claude Code skills](https://code.claude.com/docs/en/skills), [subagents](https://code.claude.com/docs/en/sub-agents), and [memory](https://code.claude.com/docs/en/memory) documentation. For OpenCode, see its [config](https://opencode.ai/docs/config), [rules](https://opencode.ai/docs/rules), [skills](https://opencode.ai/docs/skills), [agents](https://opencode.ai/docs/agents), [models](https://opencode.ai/docs/models), and [MCP servers](https://opencode.ai/docs/mcp-servers) documentation.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
```

Choose Codex, Claude Code, GitHub Copilot, or OpenCode in the installer. Clients discover installed skills on their own. The Active by default checklist also writes a short managed block to the client's instruction file: one line per selected skill naming the step where it applies, so the client reads the skill when it reaches that step. Nothing is read at the start of a conversation. The block remains subject to instruction precedence, client behavior, and file-size limits. Skill installation itself does not change client settings.

## Install skills

From the checkout, run the graphical installer (from another working directory, use the path to the script):

```sh
python tools/install_gui.py
```

Choose a client and select one or more skills. Choose **User-wide**, **Target repository**, or **Both**; repository scope requires an existing target directory. The preview shows skill and instruction actions. The installer uses the skill files in this checkout; it does not download a release. After confirmation, an existing skill directory is replaced with the checked-out version, and its previous contents (including local edits) are kept under `getonmylevel-backups` beside the skills directory. Existing files, symlinks, junctions, and other detected reparse points are refused as skill destinations, as are linked or invalid managed paths. An I/O error during a multi-skill operation can leave earlier completed copies in place; the tool reports completed changes and backup paths.

### Client capabilities and paths

| Capability | Codex | Claude Code | GitHub Copilot CLI and VS Code | OpenCode |
| --- | --- | --- | --- | --- |
| User-wide skills | `~/.agents/skills` | `$CLAUDE_CONFIG_DIR/skills` or `~/.claude/skills` | `~/.copilot/skills` | `~/.config/opencode/skills` |
| User-wide instructions | `$CODEX_HOME/AGENTS.md` or `~/.codex/AGENTS.md` | `$CLAUDE_CONFIG_DIR/CLAUDE.md` or `~/.claude/CLAUDE.md` | `~/.copilot/copilot-instructions.md` | `~/.config/opencode/AGENTS.md` |
| Repository skills and instructions | `<repo>/.agents/skills`, `<repo>/AGENTS.md` | `<repo>/.claude/skills`, `<repo>/CLAUDE.md` | `<repo>/.github/skills`, `<repo>/.github/copilot-instructions.md` | `<repo>/.opencode/skills`, `<repo>/AGENTS.md` (shared block with Codex) |
| Agent files, user-wide | `$CODEX_HOME/agents` or `~/.codex/agents` (TOML) | `$CLAUDE_CONFIG_DIR/agents` or `~/.claude/agents` (Markdown) | `~/.copilot/agents` (Markdown) | `~/.config/opencode/agents` (Markdown) |
| Agent files, repository | `<repo>/.codex/agents` (TOML) | `<repo>/.claude/agents` (Markdown) | `<repo>/.github/agents` (Markdown) | `<repo>/.opencode/agents` (Markdown) |
| Optional integrations | Go viper and testify skills | Same as Codex | Same as Codex | Same as Codex |
| Verify stop hook | `Stop` in `$CODEX_HOME/hooks.json` or `~/.codex/hooks.json` | `Stop` in `settings.json` | `agentStop` in `~/.copilot/hooks/getonmylevel-verify.json` | V2 plugin `~/.config/opencode/plugins/getonmylevel-verify.js` |

Environment-variable paths apply when the variable is set; otherwise the home-directory path is used. OpenCode paths are fixed (see [OpenCode notes](#opencode-notes)). For Codex instructions, the installer selects a nonempty `AGENTS.override.md` in preference to `AGENTS.md` at either scope. **Both** writes to both selected scope locations and may cause duplicate skill discovery; usually choose one. Skills and agents have separate client and scope controls and separate confirmations. Start a new conversation if changed instructions are not picked up; restart the selected client if new skills are not discovered. Client behavior depends on its version and configuration.

In **Agents**, Codex roles use TOML files, Claude Code roles use Markdown subagent files, GitHub Copilot roles use `.agent.md` profiles shared by CLI and VS Code, and OpenCode roles use Markdown subagent files with `mode: subagent`. Model and effort fields are editable independently per role where supported; Copilot profiles accept a model but do not set reasoning effort. OpenCode takes a model as `provider/model-id`, optionally with a `#variant` suffix, and has no separate effort field; model suggestions come only from managed OpenCode agent files already present. Claude offers common aliases and a snapshot of current Claude API model IDs as suggestions; other IDs can be entered manually. The suggestions are not fetched or checked for availability, and provider-specific IDs may differ. See Anthropic's [model overview](https://platform.claude.com/docs/en/models/overview). A selected ID does not guarantee account access or model availability. Integration availability is summarized in the table above and detailed below.

The **Active by default** checklist is independent of the core skill install/update selection. It starts with the existing managed selections; applying it replaces the active set for each displayed scope. When Both is selected, user-wide and repository checklists remain separate. Unchecking a skill leaves its files installed for explicit use. Clearing a checklist removes its managed block. The preview shows any missing skill files that must be installed before activation and the proposed instruction changes. The managed block preserves surrounding instruction bytes. Malformed or manually edited managed blocks are refused for manual repair. To turn off the default preference, select the client and scope and use **Remove getonmylevel instructions** in the GUI, or remove the exact region beginning `<!-- getonmylevel-skills:begin -->` and ending `<!-- getonmylevel-skills:end -->`. Either leaves installed skill directories in place. Instructions are subject to higher-priority guidance and Codex's `project_doc_max_bytes` limit, so a large instruction file may prevent the block from being read.

### OpenCode notes

- Paths are always `~/.config/opencode` (on Windows too) and `<repo>/.opencode`. This tool does not read `XDG_CONFIG_HOME` or `OPENCODE_CONFIG_DIR`; how OpenCode itself handles those variables is not documented or verified here.
- OpenCode reads `AGENTS.md`, not `AGENTS.override.md`. When Codex uses `AGENTS.override.md`, the two clients use separate files.
- A repository `AGENTS.md` holds one managed block shared by Codex and OpenCode. Each client changes only its own list, and a Codex list already in the block is preserved. Older versions of this tool refuse the shared block rather than changing it.
- According to the [OpenCode rules documentation](https://opencode.ai/docs/rules), OpenCode also reads `CLAUDE.md` where no `AGENTS.md` exists, and `~/.claude/CLAUDE.md` where no `~/.config/opencode/AGENTS.md` exists. Activating OpenCode instructions creates `AGENTS.md`, which ends that fallback. `OPENCODE_DISABLE_CLAUDE_CODE_PROMPT=1` or `OPENCODE_DISABLE_CLAUDE_CODE=1` disables the fallback.
- According to the [OpenCode skills documentation](https://opencode.ai/docs/skills), OpenCode also discovers skills in `~/.claude/skills`, `~/.agents/skills`, `.claude/skills`, and `.agents/skills`, and for duplicate skill IDs the source registered later wins. Suggested installs refuse a second OpenCode copy, and a Codex or Claude install into a location OpenCode also scans reports this in its details.
- Reasoning is set through a `#variant` suffix on the model, and there is no model discovery. The behaviour above comes from OpenCode's documentation and has not been checked in a running client.

### Suggested skillsets and tools

The GUI's unchecked-by-default **Suggested skillsets and tools** section, and `tools/setup.py suggested`, offer only items with a controlled evaluation showing a benefit. **Details** shows the evidence for each. All four clients are supported.

| Item | How it installs | Evidence |
| --- | --- | --- |
| Go: spf13/viper skill | Pinned copy of `skills/golang-spf13-viper` from [samber/cc-skills-golang](https://github.com/samber/cc-skills-golang) at commit `d68d80aec298e1b74b37c2a472c002b5217248b3` (MIT) | One of 4 of 98 public skills with a significant gain in [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401): pass ratio 59.6% to 77.3% |
| Go: stretchr/testify skill | Pinned copy of `skills/golang-stretchr-testify` from the same commit | Also significant in SWE-Skills-Bench, +4.9 points |

The Go skills help only in Go projects that use those libraries; their descriptions keep them dormant elsewhere. They are copied into the selected client's user-wide skill directory with the upstream license as `LICENSE.upstream`. Nothing upstream is executed. The installer fetches the pinned commit, verifies `HEAD`, and rejects symlinks and submodules. It refuses a second copy where the client would discover two; OpenCode also scans the Claude Code and Codex skill folders. Removal moves the directory to `getonmylevel-backups`. No general docs-lookup tool is suggested: the bundled context skill already reads the installed version's own docs and types, and the general tool with published numbers, Context7, has a positive result only from its vendor and a negative one from an independent test. A browser such as Playwright is not suggested either; ui-check uses whatever browser tool the session has.

**Removed suggestions.** Earlier releases offered six more items. None had a controlled evaluation showing a benefit on coding tasks:

- **RTK** (command-output compression). In [Quesma's 1,740-run Terminal-Bench 2.1 study](https://quesma.com/blog/does-rtk-make-ai-coding-cheaper/), its token savings did not lower cost: runs were about 1% more expensive on one model and 17% on another. Tool output was 11–40% of input tokens, and much of that was cached. Its own savings figure counts bytes, not billed tokens.
- **Impeccable, UI UX Pro Max, and Anti UI Slop** (broad design guidance). The only published numbers are registry evals with a few scenarios, scored on criteria the skill itself prescribes. In [WebDev-Skills-Bench](https://arxiv.org/abs/2608.23067), forcing relevant-looking web skills into the prompt cost 72–394% more tokens and lowered success. The ui-check skill covers the rendered check.
- **Last 30 Days** (web research) and **CLI-Anything** (harness generator for desktop applications). Neither is a coding procedure, and neither has a published evaluation beyond the maintainers' own tests.

`tools/setup.py suggested status` lists retired copies that are still installed, and `suggested remove --items last30days impeccable ui_ux_pro_max anti_ui_slop cli_anything --yes` moves them to backups. Claude marketplace plugins and RTK are removed with their own tools.

Maintainers update the pin in `tools/suggested_installers.py` (`SAMBER_COMMIT`). Review the upstream diff, run the tests, and update this document. Add a suggestion only with a controlled evaluation showing a benefit, and record that evidence in its `evidence` field.

### Scriptable installation

The command works without Tkinter or a display, for Codex, Claude Code, GitHub Copilot, and OpenCode. It requires Python 3.11 or newer and uses only the standard library. Run it from the checkout (or use the full path to `tools/install.py`):

```sh
python tools/install.py install --client codex --scope user
python tools/install.py update --client claude --scope repo --repo /path/to/repository
python tools/install.py install --client opencode --scope repo --repo /path/to/repository --dry-run
python tools/install.py remove --client codex --scope user --skills getonmylevel-context
python tools/install.py activate --client claude --scope repo --repo /path/to/repository --skills getonmylevel-ui-check --dry-run
python tools/install.py install --client copilot --scope repo --repo /path/to/repository --dry-run
python tools/install.py activate --client codex --scope user --skills none
```

All three skills are selected by default; `--skills` accepts one or more exact skill names. `install` and `update` both install missing skills and update existing ones without changing the active selection. They also upgrade a managed block written by an earlier release and retire the old skill directories; see [upgrading](#upgrading-from-the-seven-skill-release). `activate` replaces the active set and installs missing selected skills; `--skills none` clears it. With `--scope both`, activate applies the same explicit selection to both scopes; run it separately for differing selections. Updates and removals preserve previous directories in `getonmylevel-backups`. Removal also removes the selected skills from managed default-use instructions, retaining other skill references and surrounding text. `--dry-run` previews actions without writing; normal commands apply immediately and return a nonzero exit status on failure. Operations across multiple paths are not transactional. This command handles bundled skills and their instructions. Agent roles, the verify hook, and suggested skills use the separate setup command below.

### Headless setup operations

`tools/setup.py` uses the standard library and does not import Tkinter. `--dry-run` previews file destinations, third-party commands, network activity, global configuration targets, and removals. `--yes` is required before global role changes, the verify hook, suggested skill installation, and suggested skill removal. Without it the command exits without prompting.

```sh
# The stop hook that runs targeted checks (requires the verify skill at user scope for that client).
python tools/setup.py hooks install --client claude --dry-run
python tools/setup.py hooks install --client codex --yes
python tools/setup.py hooks install --client copilot --yes
python tools/setup.py hooks install --client opencode --yes
python tools/setup.py hooks status --client codex
python tools/setup.py hooks remove --client copilot --yes

# Inspect role destinations, then write the reviewer role for a repository.
python tools/setup.py roles install --client claude --scope repo --repo /path/to/repository --roles reviewer --dry-run
python tools/setup.py roles install --client claude --scope repo --repo /path/to/repository --roles reviewer --model reviewer=sonnet --effort reviewer=high

# Omitted model/effort values preserve each existing file's settings.
python tools/setup.py roles update --client codex --scope both --repo /path/to/repository --roles reviewer --dry-run
python tools/setup.py roles install --client codex --scope global --roles reviewer --yes

# Retired roles from earlier releases can only be removed.
python tools/setup.py roles remove --client codex --scope global --roles designer implementer tester --yes

# Suggested items: status, pinned install plan, and removal (including retired suggestions).
python tools/setup.py suggested status --client copilot
python tools/setup.py suggested install --client codex --items go_viper go_testify --dry-run
python tools/setup.py suggested install --client opencode --items go_testify --yes
python tools/setup.py suggested remove --client claude --items impeccable last30days --yes
```

Role scope is `global`, `repo`, or `both`; repository scope requires an existing target distinct from this checkout. The supported role is `reviewer`. The retired `designer`, `implementer`, and `tester` roles are accepted only by `remove`. Use repeated `--model ROLE=VALUE` and `--effort ROLE=VALUE`; `ROLE=` clears a field. New files inherit client defaults, and Copilot and OpenCode do not support a separate reasoning effort; OpenCode uses a `#variant` suffix on the model instead. Existing settings are preserved when omitted. Role files are written or removed only if their management marker and template content match; linked and hand-edited files are refused. Writes are atomic per file, but a multi-file failure can leave earlier actions completed; those paths are reported.

Suggested items are supported for all four clients. Each is a pinned skill copy; retired suggestions can only be removed. The CLI reports each result and any partial changes.

## Upgrading from the seven-skill release

Earlier releases shipped seven skills (communication, context, engineering, design, good software engineering practices, skill discovery, and focused solutions). Their managed block told the client to read every selected skill at the start of each conversation, to ask for a Simple or Agentic choice before every edit, and to offer CodeGraph indexing. Those rules added tokens and questions to every task.

This release also removes the CodeGraph setup. CodeGraph itself stays installed if an earlier release set it up: getonmylevel ran CodeGraph's own installer, which changed the client's MCP configuration. To remove it, follow the [CodeGraph instructions](https://github.com/colbymchenry/codegraph) and uninstall the npm package `@colbymchenry/codegraph`.

This release keeps only what controlled evaluations support and removes the rest:

| Removed | Why | Replaced by |
| --- | --- | --- |
| Communication, engineering, good practices, focused solutions, and skill discovery skills | Broad guidance: no measured benefit on average, and extra tokens on every task | verify (where the procedure applies) |
| Design skill | Broad guidance; it also told the agent not to render unless asked | ui-check, which renders and uses the screen |
| Reading every skill at conversation start | Forced context raised tokens by 72–394% and lowered success | A one-line-per-skill index; skills load when needed |
| The Simple-or-Agentic question | No evidence of benefit; it stops headless runs | Nothing: the agent works directly |
| Designer, implementer, and tester roles | Multiple agents cost more without reliable gains on code; the roles were also told not to run checks | One optional reviewer that runs checks |
| CodeGraph indexing offer on every task, and the CodeGraph setup | No evidence for the prompt; the setup's results were mixed (55% fewer tool calls but 6.8% higher cost in one test) | The context skill uses whatever code index the session already has |
| Session selector | Added a question at the start of every conversation | Nothing |
| Six suggested add-ons | No controlled evaluation showed a benefit; RTK's showed no cost saving | Two Go skills with a significant measured gain |

The evidence is for each kind of change, from other people's benchmarks; this bundle has not yet been measured head to head against the previous one.

`install`, `update`, and `activate` upgrade an unedited earlier block in place and keep the text around it and its line endings. Old names map to new skills: engineering, good software engineering practices, and focused solutions become **verify**; design becomes **ui-check**; context stays **context**; communication and skill discovery have no replacement. A block that maps to no skill is removed. The upgraded block lists only skills that are installed. A block that was edited by hand is refused for manual repair.

The same commands move installed copies of the six retired skills to `getonmylevel-backups`. Their bodies still contain the old workflow rules, and clients discover installed skills on their own, so they would stay active if left in place. `remove --skills all` also retires them. Remove the retired roles with `tools/setup.py roles remove --roles designer implementer tester`. The session selector in `optional/` is gone; its block is not migrated automatically, so delete it from your instructions if you merged it.

## Verify hook

`tools/setup.py hooks install --client <client>` installs a user-wide stop hook. All four clients run the same script, the installed `getonmylevel-verify/scripts/stop_check.py`, when the agent finishes a turn in a git repository with uncommitted changes. That script runs the targeted checks for the changed files: a Python syntax check, the tests next to each changed file (unittest, pytest, Vitest, or Jest), and a TypeScript, Go, or Rust compile check where those toolchains are present. It does not run full suites. If a check fails, the agent gets the output and continues the turn. The hook does not block twice in a row, does not re-run on an unchanged working tree, has a 240-second budget, and lets the agent stop if the hook itself fails.

| Client | Where it is written | How failures reach the agent |
| --- | --- | --- |
| Claude Code | `Stop` hook merged into `$CLAUDE_CONFIG_DIR/settings.json` or `~/.claude/settings.json` | Exit 2; stderr becomes the next prompt |
| Codex | `Stop` hook merged into `$CODEX_HOME/hooks.json` or `~/.codex/hooks.json` | Exit 2; stderr becomes the next prompt. Codex skips new or changed hooks until you trust them with `/hooks` |
| GitHub Copilot CLI | `agentStop` hook in its own file, `~/.copilot/hooks/getonmylevel-verify.json` (`$COPILOT_HOME/hooks` when set), with bash and PowerShell commands | `{"decision": "block", "reason": ...}` on stdout. Copilot treats exit 2 as a warning, so the script uses `--format json`. Copilot ends the turn after 8 blocks in a row |
| OpenCode | A V2 plugin in its own file, `~/.config/opencode/plugins/getonmylevel-verify.js` | On `session.idle` the plugin runs the script and sends the failures back with `ctx.session.prompt` |

Merged files keep every other setting. Removal deletes only this hook's entry from merged files, and deletes an owned file only if getonmylevel wrote it. The Copilot hook was run with both its bash and PowerShell commands. The OpenCode plugin follows the documented V2 plugin API (`Plugin.define`, `ctx.event.subscribe`, `ctx.session.prompt`) and passes `node --check`, but it has not been run inside OpenCode. OpenCode's event payload is not documented, so the plugin looks for the session ID in several places.

To declare a repository's checks, add `.getonmylevel-checks` at its root with one shell command per line. An empty file turns the hook off for that repository. `GETONMYLEVEL_VERIFY_HOOK=off` turns it off everywhere.

Explicit invocation uses `$getonmylevel-verify`, `$getonmylevel-ui-check`, or `$getonmylevel-context` (Claude Code: `/getonmylevel-verify` and so on).

## Optional agent roles

The optional template in [`optional/agents`](optional/agents) configures one opt-in **reviewer** role for Codex, Claude Code, GitHub Copilot, and OpenCode. It reviews a diff in a fresh context and runs the project's existing checks for the changed code; it does not edit files. Use it for risky changes, not routine edits. Templates from earlier releases are kept in `optional/agents/retired` so unedited old files can still be updated or removed. Run the GUI with:

```sh
python tools/agents_gui.py
```

Choose the client, roles, and global user, repository, or both scopes. Destinations and file formats are listed in the [client table](#client-capabilities-and-paths). The tool shows a preview and requires confirmation. It updates only files bearing its management marker and exact template instructions, preserving existing model and reasoning-effort values in editable controls. Unknown or hand-edited templates and symlinks are refused. Each file replacement is atomic; a set of files is not transactional. It does not edit client instruction or configuration files.

Model and effort fields are editable independently per role where supported; Copilot profiles support an optional model and do not set reasoning effort. OpenCode subagents take a model as `provider/model-id`, optionally followed by `#variant`; a blank model omits the field. Reasoning is chosen through the variant, and the GUI offers no model discovery for OpenCode. For Claude Code, a blank model omits `model` from the agent frontmatter; Claude then resolves the model using invocation settings, `CLAUDE_CODE_SUBAGENT_MODEL`, and the spawning conversation in its documented precedence order. The explicit value `inherit` selects the spawning conversation's model (or the parent's model for a nested subagent). Blank effort omits `effort` and lets Claude resolve it at runtime. The documented frontmatter effort values are `low`, `medium`, `high`, `xhigh`, and `max`; support depends on the selected model, and Claude Code may lower an unsupported value or apply an account or policy cap. Environment settings can override frontmatter. `ultracode` is not a frontmatter effort value. The GUI offers model aliases as suggestions while allowing full IDs, so it does not need a fixed list of future models. See Anthropic's [subagent model and effort resolution](https://code.claude.com/docs/en/sub-agents) and [model effort documentation](https://code.claude.com/docs/en/model-config). The current docs do not specify a general minimum Claude Code version for these two frontmatter fields; invocation-level effort override requires v2.1.292 or later, and agent effort handling fixes are listed in the [changelog](https://code.claude.com/docs/en/changelog). For Codex, **Refresh available models** explicitly queries the local `codex app-server`; it requires Codex on `PATH` or, on Windows, the Codex VS Code extension installed in its standard location. It uses the documented [`model/list` API](https://developers.openai.com/codex/app-server) and [`agents` configuration](https://developers.openai.com/codex/multi-agent). For Copilot, refresh uses the [Copilot Python SDK](https://github.com/github/copilot-sdk/tree/main/python). Install the optional SDK in the Python environment running the GUI with `python -m pip install microsoft-copilot-sdk`. The SDK uses its compatible runtime and may download it on first use; listing models contacts GitHub and requires Copilot authentication. Discovery may be unavailable; in that case enter values manually. A listed model does not guarantee availability in every Copilot client or account.

## Platform notes

The GUIs use Python's standard-library Tkinter and work on Windows, macOS, and Linux when Tk support is available. Run scripts directly with Python; they locate repository content relative to their own files. If no graphical display or Tk is available, the skill installer has terminal instructions above and agent templates can be edited manually. No credentials are needed for local installation. Model refresh has the optional client-specific requirements described above.

## Troubleshooting

- **The client does not use an installed skill:** confirm that the skill is installed for the selected client and scope. Restart the client if it does not discover new skill files. To ask for a skill directly, use its exact name, such as `$getonmylevel-context`.
- **An installed skill is not read when it should be:** clients load skills by matching their descriptions, and they sometimes miss. Apply the skill in **Active by default** or run `activate` to add its line to the managed block, or name the skill in the request.
- **The agent still asks Simple or Agentic:** a retired skill or an old block is still installed. Run `install` or `update` for that client and scope, then check other instruction files for a merged session selector.
- **The verify hook blocks on a failure unrelated to the change:** the agent is told to report unrelated failures instead of fixing them. To change which checks run, add `.getonmylevel-checks` to the repository.
- **The GUI will not start:** use Python 3.11 or newer with Tkinter installed and a graphical display, or use `tools/install.py` and `tools/setup.py` from a terminal.
- **An operation reports partial changes:** read the paths in its result. Multi-file operations are not transactional, so earlier completed actions may remain after a later failure. Skill updates keep replaced directories in `getonmylevel-backups` beside the skills directory.
- **A managed file is refused:** linked paths and manually edited or unrecognized managed content require manual inspection. Do not remove or overwrite the file until its contents and destination are understood.

## License and attribution

This repository is source-available under a custom license: personal, noncommercial use and private modifications are permitted; commercial use and public distribution of modified or derivative work require prior written permission. This is not an open-source license. See [`LICENSE`](LICENSE) and [`ATTRIBUTION.md`](ATTRIBUTION.md). The license wording is a starting point and should receive legal review before publication.
