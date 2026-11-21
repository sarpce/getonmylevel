# getonmylevel

Six independently installable skills for Codex or Claude Code, plus optional role-agent templates and local setup tools.

## Prerequisites

- Git to clone this repository.
- Python 3.11 or newer for the setup tools. They use the standard library; the graphical tools also require a Python build with Tkinter.
- Codex or Claude Code for client-native discovery. See the [Codex skills documentation](https://developers.openai.com/codex/skills) and the [Claude Code skills](https://code.claude.com/docs/en/skills), [subagents](https://code.claude.com/docs/en/sub-agents), and [memory](https://code.claude.com/docs/en/memory) documentation.

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
```

Choose Codex or Claude Code in the installer. It integrates selected skills into the selected client's instruction file with a managed block that asks the client to read them by default when relevant. This natural-language preference remains subject to instruction precedence, client behavior, file-size limits, and skill availability. Skill installation itself does not change client settings. CodeGraph is independently selectable for either client; the context skill does not require it or Node.js and npm.

## Install skills

Run the graphical installer from any working directory:

```sh
python tools/install_gui.py
```

Select one or more skills and a scope: **User-wide**, **Target repository**, or **Both**. For repository scope, choose an existing target repository. The preview shows skill and instruction actions. The installer uses the skill files in this checkout; it does not download a release. After confirmation, an existing skill directory is replaced with the checked-out version, and its previous contents (including local edits) are kept under `getonmylevel-backups` beside the skills directory. Existing files, symlinks, junctions, and other detected reparse points are refused as skill destinations, as are linked or invalid managed paths. An I/O error during a multi-skill operation can leave earlier completed copies in place; the tool reports completed changes and backup paths.

Codex user-wide skills go to `$HOME/.agents/skills`; their instructions go in `$CODEX_HOME/AGENTS.md` when `CODEX_HOME` is set, otherwise `~/.codex/AGENTS.md`. Repository skills go to `<repo>/.agents/skills` and their instructions to `AGENTS.md` (a nonempty `AGENTS.override.md` takes precedence). Claude Code user skills go to `~/.claude/skills`, or `$CLAUDE_CONFIG_DIR/skills` when set; instructions go in the matching `CLAUDE.md`. Repository Claude skills go to `<repo>/.claude/skills`, with instructions in `<repo>/CLAUDE.md`. Installing in both scopes may cause duplicate skill discovery; usually choose one. Restart or start a new conversation if the client does not discover the new skills or instructions.

In **Agents**, Codex roles use the existing TOML format and local Codex model discovery. Claude Code roles use native Markdown subagent files. Model and effort fields are editable for each role; Claude offers common aliases as suggestions and also accepts full model IDs. A selected ID does not guarantee account access or model availability. The suggested RTK, Last 30 Days, and CLI-Anything installers are Codex-only and are disabled when Claude Code is selected. CodeGraph can be configured for either client.

The managed block preserves surrounding instruction text. Later installs add newly selected skill names to the existing block; deselecting a skill does not remove it. Malformed or manually edited managed blocks are refused for manual repair. To turn off the default preference, remove the exact region beginning `<!-- getonmylevel-skills:begin -->` and ending `<!-- getonmylevel-skills:end -->`; this leaves installed skill directories in place. Instructions are subject to higher-priority guidance and Codex's `project_doc_max_bytes` limit, so a large instruction file may prevent the block from being read.

Selecting **getonmylevel-skill-discovery** also adds an instruction to review available skills and relevant skill locations for each task, and use skills when they can materially help. The GUI labels the bundled choices **Core skills**. CodeGraph is an independent recommendation for Codex and Claude Code, whether or not the context skill is selected. If explicitly selected and missing, Node.js and npm are required to install it. Global setup may download packages and changes the selected client's MCP configuration and managed instructions. The GUI does not initialize or index a project; indexing is a separate choice. Restart the selected client if its MCP server is not available.

### Suggested skillsets and tools

The GUI includes an unchecked-by-default **Suggested skillsets and tools** section for [RTK](https://github.com/rtk-ai/rtk), [Last 30 Days](https://github.com/mvanhorn/last30days-skill), and [CLI-Anything](https://github.com/HKUDS/CLI-Anything). It detects Last 30 Days and CLI-Anything in `~/.agents/skills` and `$CODEX_HOME/skills` (or `~/.codex/skills` when `CODEX_HOME` is unset), shows every detected location, and lets you install absent skills or remove detected skill directories. Use **Refresh status** to rescan. Removals list the exact directories and require confirmation; linked paths or trees without `SKILL.md` are refused. Installations refuse to create a duplicate when either supported location already contains the skill. Each operation reports its result independently.

Last 30 Days requires Git and installs the complete upstream `skills/last30days` directory to `~/.agents/skills/last30days` from selected commit `bb2f1ed2b9f6d07b90557c5eebd736b566533fec`. CLI-Anything requires Git plus PowerShell on Windows or Bash on macOS/Linux. It runs the upstream Codex skill installer from selected commit `34f519533bc175d2fe287ab8316b0dd99bb9cc43`, which installs the generator skill and its supporting resources to `$CODEX_HOME/skills/cli-anything` or `~/.codex/skills/cli-anything`; it does not install all application harnesses. The installer fetches each commit, checks out detached, and verifies `HEAD` before copying or executing. These selected revisions have not been represented as integration-tested. Last 30 Days files are copied without executing their code. CLI-Anything executes upstream code with your user privileges.

RTK is a standalone command-output optimizer. Automatic installation is disabled because Winget and Homebrew select moving package versions. Install a reviewed version manually from the [RTK installation guide](https://www.rtk-ai.app/docs/getting-started/installation/), checking the edition, source and license (Winget full edition includes Apache-2.0 and BUSL-1.1 components; Homebrew `rtk-oss` is Apache-2.0 and omits the pipeline engine). The GUI detects an `rtk` executable on PATH but cannot establish its identity or version; removal is manual. RTK installation does not activate it or configure Codex. Review [RTK setup instructions](https://github.com/rtk-ai/rtk) separately before running `rtk init -g --codex`, which changes global Codex configuration.

CodeGraph installs the exact npm spec `@colbymchenry/codegraph@1.6.4` when no executable exists. This is a selected package version and is not claimed as tested by this installer. If a `codegraph` command already exists, it is preserved without an upgrade; its version and provenance are reported as unknown and unverified. To update one, manually review the existing configuration and perform a deliberate remove/reinstall or package-manager update after checking the desired release.

The confirmation shows selected versions/commits, planned commands/actions, destinations, prerequisites, network activity, and execution effects. Canceling makes no changes. Git commands use argument arrays without shell interpretation. Existing suggested skills are detected and not updated; remove the detected skill in the GUI, then reinstall the selected pin. This replaces the prior copy after explicit removal confirmation. Restart Codex after installing skills if they are not discovered.

Maintainers update pins in `tools/codegraph_installer.py` (`PACKAGE_VERSION`) and `tools/suggested_installers.py` (`LAST30_COMMIT`, `CLI_ANYTHING_COMMIT`). Review upstream release notes and diffs, select immutable versions/commit IDs, validate the expected files and installer behavior, run the mocked/local-repository test suite, then update this document and README. Record actual integration-test evidence before describing a pin as tested. Pins do not make registries or Git hosting immutable, validate publisher identity, pin npm transitive dependencies or downloads performed by upstream scripts, or guarantee platform-specific installer behavior. Existing installations may have unknown provenance.

### Terminal fallback

The terminal fallback supports **Codex only** and new installations only. Existing skill destinations are refused to prevent overwriting them. To install for Claude Code or update an existing installation with a backup of its current contents, use the graphical installer above. Run the Codex terminal commands from this repository root and edit the exact allowlisted names, scopes, and repository root. The script preflights selected source files and every destination, including symlinks, before it creates directories or copies files. The terminal fallback only copies skills; add equivalent default-use instructions to the applicable `AGENTS.md` yourself, or use the GUI installer for integrated instructions.

PowerShell:

```powershell
$ErrorActionPreference = 'Stop'
$allowedNames = @('getonmylevel-communication', 'getonmylevel-context', 'getonmylevel-engineering', 'getonmylevel-design', 'getonmylevel-good-software-engineering-practices', 'getonmylevel-skill-discovery')
$names = @('getonmylevel-communication', 'getonmylevel-context', 'getonmylevel-engineering', 'getonmylevel-design', 'getonmylevel-good-software-engineering-practices', 'getonmylevel-skill-discovery')
$scopes = @('user') # 'repo' or @('user', 'repo') are also supported
$targetRepo = 'C:\path\to\target-repository'
if ($names.Count -eq 0) { throw 'Select at least one skill.' }
$seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
foreach ($name in $names) {
  if ($name -cnotin $allowedNames) { throw "Unknown skill: $name" }
  if (-not $seen.Add($name)) { throw "Duplicate skill: $name" }
}
if ($scopes.Count -eq 0) { throw 'Select at least one scope.' }
$validScopes = @('user', 'repo')
$seenScopes = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
foreach ($scope in $scopes) {
  if ($scope -cnotin $validScopes) { throw "Unknown scope: $scope" }
  if (-not $seenScopes.Add($scope)) { throw "Duplicate scope: $scope" }
}
$sourceRoot = Join-Path (Get-Location) 'skills'
$sourceRepo = [System.IO.Path]::GetFullPath((Get-Location).Path).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
if ($scopes -contains 'repo') {
  if (-not (Test-Path -LiteralPath $targetRepo -PathType Container)) { throw "Target repository does not exist: $targetRepo" }
  $targetFull = [System.IO.Path]::GetFullPath($targetRepo).TrimEnd([System.IO.Path]::DirectorySeparatorChar)
  if ($targetFull -eq $sourceRepo) { throw 'Target repository must differ from this source checkout.' }
}
$roots = @(foreach ($scope in $scopes) {
  if ($scope -ceq 'user') { Join-Path $HOME '.agents/skills' }
  else { Join-Path $targetRepo '.agents/skills' }
})
$rootSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
for ($i = 0; $i -lt $roots.Count; $i++) {
  $roots[$i] = [System.IO.Path]::GetFullPath($roots[$i])
  if (-not $rootSet.Add($roots[$i])) { throw "Scopes resolve to the same destination: $($roots[$i])" }
  if ((Test-Path -LiteralPath $roots[$i]) -and -not (Test-Path -LiteralPath $roots[$i] -PathType Container)) { throw "Destination root is not a directory: $($roots[$i])" }
}
$sources = foreach ($name in $names) { Join-Path $sourceRoot $name }
foreach ($source in $sources) {
  if (-not (Test-Path -LiteralPath (Join-Path $source 'SKILL.md') -PathType Leaf)) { throw "Missing SKILL.md: $source" }
}
$destinations = foreach ($root in $roots) { foreach ($name in $names) { Join-Path $root $name } }
$occupied = @($destinations | Where-Object { $null -ne (Get-Item -LiteralPath $_ -Force -ErrorAction SilentlyContinue) })
if ($occupied.Count) { throw "Refusing to overwrite: $($occupied -join ', ')" }
foreach ($root in $roots) {
  New-Item -ItemType Directory -Force -Path $root | Out-Null
  foreach ($name in $names) { Copy-Item -Recurse -LiteralPath (Join-Path $sourceRoot $name) -Destination $root }
}
```

POSIX shell:

```sh
set -e
names='getonmylevel-communication getonmylevel-context getonmylevel-engineering getonmylevel-design getonmylevel-good-software-engineering-practices getonmylevel-skill-discovery'
scopes='user' # 'repo' or 'user repo' are also supported
target_repo='/path/to/target-repository'
allowed_names=' getonmylevel-communication getonmylevel-context getonmylevel-engineering getonmylevel-design getonmylevel-good-software-engineering-practices getonmylevel-skill-discovery '
allowed_scopes=' user repo '
[ -n "$names" ] || { printf 'Select at least one skill.\n' >&2; exit 1; }
seen=' '
for name in $names; do
  case "$allowed_names" in *" $name "*) ;; *) printf 'Unknown skill: %s\n' "$name" >&2; exit 1 ;; esac
  case "$seen" in *" $name "*) printf 'Duplicate skill: %s\n' "$name" >&2; exit 1 ;; esac
  seen="$seen$name "
done
[ -n "$scopes" ] || { printf 'Select at least one scope.\n' >&2; exit 1; }
seen_scopes=' '
for scope in $scopes; do
  case "$allowed_scopes" in *" $scope "*) ;; *) printf 'Unknown scope: %s\n' "$scope" >&2; exit 1 ;; esac
  case "$seen_scopes" in *" $scope "*) printf 'Duplicate scope: %s\n' "$scope" >&2; exit 1 ;; esac
  seen_scopes="$seen_scopes$scope "
done
source_repo=$(pwd -P)
user_home=$(cd -P "$HOME" && pwd)
case " $scopes " in
  *' repo '*)
    [ -d "$target_repo" ] || { printf 'Target repository does not exist: %s\n' "$target_repo" >&2; exit 1; }
    target_real=$(cd -P "$target_repo" && pwd)
    [ "$target_real" != "$source_repo" ] || { printf 'Target must differ from this source checkout.\n' >&2; exit 1; }
    ;;
esac
set --
for scope in $scopes; do
  case "$scope" in
    user) set -- "$@" "$user_home/.agents/skills" ;;
    repo) set -- "$@" "$target_real/.agents/skills" ;;
  esac
done
seen_roots=' '
for root do
  case "$seen_roots" in
    *" $root "*) printf 'Selected scopes resolve to the same destination: %s\n' "$root" >&2; exit 1 ;;
  esac
  seen_roots="$seen_roots$root "
done
for name in $names; do
  [ -f "skills/$name/SKILL.md" ] || { printf 'Missing SKILL.md: %s\n' "skills/$name" >&2; exit 1; }
done
for root do
  if [ -L "$root" ] && [ ! -e "$root" ]; then
    printf 'Destination root is a dangling symlink: %s\n' "$root" >&2
    exit 1
  fi
  if [ -e "$root" ] && [ ! -d "$root" ]; then
    printf 'Destination root is not a directory: %s\n' "$root" >&2
    exit 1
  fi
  for name in $names; do
    if [ -e "$root/$name" ] || [ -L "$root/$name" ]; then
      printf 'Refusing to overwrite: %s\n' "$root/$name" >&2
      exit 1
    fi
  done
done
for root do
  mkdir -p "$root"
  for name in $names; do cp -R "skills/$name" "$root/"; done
done
```

To update a manual install, review the repository changes and replace only the selected skill directories in the relevant scope, preserving local edits. To remove a skill, delete only its `getonmylevel-*` directory. The optional `[[skills.config]]` setting can disable skills in the relevant Codex configuration; consult current documentation. Do not remove a shared parent directory containing other skills.

## Session selection

The optional selector instruction in [`optional/global-session-selector.md`](optional/global-session-selector.md) supports **On**, **Off**, and **Ask** preferences for the original five skills. It also states that Simple/Agent-based development choice is independent of skill selection. Merge it manually with your effective global instructions; it does not edit or override them. These are conversation conventions, not enforced Codex settings. The GUI can copy a generated instruction block without changing any file.

Explicit skill invocation uses `$getonmylevel-communication`, `$getonmylevel-context`, `$getonmylevel-engineering`, `$getonmylevel-design`, `$getonmylevel-good-software-engineering-practices`, or `$getonmylevel-skill-discovery`. Higher-priority instructions and available tools always constrain activation; the installed client determines whether a skill is discovered and invoked.

## Optional agent roles

The optional TOML templates in [`optional/agents`](optional/agents) configure designer, implementer, reviewer, and tester roles separately from the skills. Run the GUI with:

```sh
python tools/agents_gui.py
```

Choose roles and global user, repository, or both scopes. Global files go to `$CODEX_HOME/agents` when set, otherwise `~/.codex/agents`. Repository files go to `<target-repository>/.codex/agents`. The tool shows a preview and requires confirmation. It updates only files bearing its management marker and exact template instructions, preserving existing model and reasoning-effort values in editable controls. Unknown or hand-edited templates and symlinks are refused. Each file replacement is atomic; a set of files is not transactional. It never edits `AGENTS.md` or Codex configuration.

Model and effort fields are editable. Blank values inherit Codex defaults. **Refresh available models** is an explicit request to the local `codex app-server`; it requires Codex on `PATH` or, on Windows, the Codex VS Code extension installed in its standard location. It uses the documented [`model/list` API](https://developers.openai.com/codex/app-server) and [`agents` configuration](https://developers.openai.com/codex/multi-agent). Model discovery may be unavailable; in that case enter values manually. A listed model does not guarantee account access or entitlement. The tool does not log credentials or make network calls itself.

Before any software edit, including small fixes, tests, configuration, documentation, or skills, the generated main instructions ask the user to choose Simple or Agent-based for that request. Agent-based mode asks separately about reviewer and tester. When an answer-capable multiple-choice popup is available, instructions require using it and waiting for the actual answer; otherwise the question stays pending in chat. These are natural-language instructions and cannot override higher-priority session rules or guarantee client behavior. Agent-based work uses the configured designer then implementer, followed by fresh reviewer and tester agents when selected and available.

## Context tools

CodeGraph is an independently selectable user-wide recommendation. After confirmation, the GUI installs it if needed and configures the selected client globally; it may download packages and edit that client's MCP configuration and managed instructions. It does not initialize or index a project. The terminal fallback copies skill files only and does not install CodeGraph.

The GUI shows the planned global setup command and distinguishes an existing CodeGraph command from a planned package installation. If using CodeGraph manually, review its [repository and setup instructions](https://github.com/colbymchenry/codegraph); project indexing is separate from global client configuration.

## Platform notes

The GUIs use Python's standard-library Tkinter and work on Windows, macOS, and Linux when Tk support is available. Run scripts directly with Python; they locate repository content relative to their own files. If no graphical display or Tk is available, the skill installer has terminal instructions above and agent templates can be edited manually. No credentials are needed for local installation. Codex is needed only for the optional model refresh.

## License and attribution

This repository is source-available under a custom license: personal, noncommercial use and private modifications are permitted; commercial use and public distribution of modified or derivative work require prior written permission. This is not an open-source license. See [`LICENSE`](LICENSE) and [`ATTRIBUTION.md`](ATTRIBUTION.md). The license wording is a starting point and should receive legal review before publication.
