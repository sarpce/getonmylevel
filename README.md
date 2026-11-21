# getonmylevel

Four independently installable Codex skills for communication, project context, software engineering, and interface design, plus optional role-agent templates and local setup tools.

## Prerequisites

- Git to clone this repository.
- Python 3.11 or newer for the setup tools. They use the standard library; the graphical tools also require a Python build with Tkinter.
- A Codex client supporting local skills and custom agents. See the official [skills documentation](https://developers.openai.com/codex/skills), [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md), and [multi-agent documentation](https://developers.openai.com/codex/multi-agent).

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
```

Each skill is independent. The installer integrates selected skills into the applicable Codex instruction file by adding a managed block that tells Codex to read them by default when relevant. This is a natural-language preference: instruction precedence, client behavior, file-size limits, and skill availability still govern activation. No Codex settings file is changed.

## Install skills

Run the graphical installer from any working directory:

```sh
python tools/install_gui.py
```

Select one or more skills and a scope: **User-wide**, **Target repository**, or **Both**. For repository scope, choose an existing target repository. The preview shows skill and instruction actions. The installer uses the skill files in this checkout; it does not download a release. After confirmation, an existing skill directory is replaced with the checked-out version, and its previous contents (including local edits) are kept under `getonmylevel-backups` beside the skills directory. Existing files, symlinks, junctions, and other detected reparse points are refused as skill destinations, as are linked or invalid managed paths. An I/O error during a multi-skill operation can leave earlier completed copies in place; the tool reports completed changes and backup paths.

User-wide skills go to `$HOME/.agents/skills`; their managed instructions go in `$CODEX_HOME/AGENTS.md` when `CODEX_HOME` is set, otherwise `~/.codex/AGENTS.md`. Repository skills go to `<target-repository>/.agents/skills`; their instructions go in that repository's `AGENTS.md`. An existing nonempty `AGENTS.override.md` is used in preference to `AGENTS.md`; an empty override is left untouched and `AGENTS.md` is used. If the override later becomes nonempty, it takes precedence. Installing in both places may cause duplicate skill discovery; usually choose one. The built-in `$skill-installer` uses `$CODEX_HOME/skills`; locations may differ by client. Follow current [Codex skills documentation](https://developers.openai.com/codex/skills) and [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md). Restart Codex if a skill is not discovered, then start a new conversation to load changed instructions.

The managed block preserves surrounding instruction text. Later installs add newly selected skill names to the existing block; deselecting a skill does not remove it. Malformed or manually edited managed blocks are refused for manual repair. To turn off the default preference, remove the exact region beginning `<!-- getonmylevel-skills:begin -->` and ending `<!-- getonmylevel-skills:end -->`; this leaves installed skill directories in place. Instructions are subject to higher-priority guidance and Codex's `project_doc_max_bytes` limit, so a large instruction file may prevent the block from being read.

### Suggested skillsets and tools

The GUI includes an unchecked-by-default **Suggested skillsets and tools** section with independent choices for [RTK](https://github.com/rtk-ai/rtk), [Last 30 Days](https://github.com/mvanhorn/last30days-skill), and [CLI-Anything](https://github.com/HKUDS/CLI-Anything). These are user-wide installations and are separate from the bundled skill scope controls. All selected items are preflighted before confirmation; if any selected item cannot be prepared, none are installed. After confirmation, each selected installer runs in sequence, continues after individual failures, and reports each result. A failed upstream installer can leave partial changes, which are reported.

Last 30 Days requires Git and installs the complete upstream `skills/last30days` directory to `~/.agents/skills/last30days`. CLI-Anything requires Git plus PowerShell on Windows or Bash on macOS/Linux. It runs the upstream Codex skill installer, which installs the generator skill and its supporting resources to `$CODEX_HOME/skills/cli-anything` or `~/.codex/skills/cli-anything`; it does not install all application harnesses. Both clone the current upstream default branch, which is not pinned, and refuse to overwrite an existing destination. Last 30 Days files are copied without executing their code. CLI-Anything executes the upstream installer with your user privileges.

RTK is a standalone command-output optimizer. Windows uses Winget to install the full `rtk-ai.rtk` edition, with Apache-2.0 and BUSL-1.1 components; proceeding accepts Winget's source and package agreements. macOS/Linux use Homebrew's Apache-2.0 `rtk-oss` edition, which has command filters but not the RTK pipeline engine. Homebrew runs in noninteractive mode. The installer refuses to proceed if an `rtk` executable is already on PATH because it may be an unrelated tool. RTK package installation does not activate it or configure Codex. Review [RTK setup instructions](https://github.com/rtk-ai/rtk) separately before running `rtk init -g --codex`, which can change global Codex configuration. Open a new terminal if PATH has not refreshed; verify with `rtk --version` and `rtk gain`. Use the [RTK installation guide](https://www.rtk-ai.app/docs/getting-started/installation/) if a package manager is unavailable.

The confirmation shows planned commands/actions, destinations, prerequisites, network activity, and execution effects. Canceling makes no changes. The clone and installer commands use argument arrays without shell interpretation. Restart Codex after installing skills if they are not discovered.

### Terminal fallback

The same selection is available without Tkinter for **new installations only**. Existing skill destinations are refused to prevent overwriting them. To update an existing installation with a backup of its current contents, use the graphical installer above. Run the terminal commands from this repository root and edit the exact allowlisted names, scopes, and repository root. The script preflights selected source files and every destination, including symlinks, before it creates directories or copies files. The terminal fallback only copies skills; add equivalent default-use instructions to the applicable `AGENTS.md` yourself, or use the GUI installer for integrated instructions.

PowerShell:

```powershell
$ErrorActionPreference = 'Stop'
$allowedNames = @('getonmylevel-communication', 'getonmylevel-context', 'getonmylevel-engineering', 'getonmylevel-design')
$names = @('getonmylevel-communication', 'getonmylevel-context', 'getonmylevel-engineering', 'getonmylevel-design')
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
names='getonmylevel-communication getonmylevel-context getonmylevel-engineering getonmylevel-design'
scopes='user' # 'repo' or 'user repo' are also supported
target_repo='/path/to/target-repository'
allowed_names=' getonmylevel-communication getonmylevel-context getonmylevel-engineering getonmylevel-design '
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

The optional selector instruction in [`optional/global-session-selector.md`](optional/global-session-selector.md) supports **On**, **Off**, and **Ask** preferences for the four skills. It also states that Simple/Agent-based development choice is independent of skill selection. Merge it manually with your effective global instructions; it does not edit or override them. These are conversation conventions, not enforced Codex settings. The GUI can copy a generated instruction block without changing any file.

Explicit skill invocation uses `$getonmylevel-communication`, `$getonmylevel-context`, `$getonmylevel-engineering`, or `$getonmylevel-design`. Higher-priority instructions and available tools always constrain activation; the installed client determines whether a skill is discovered and invoked.

## Optional agent roles

The optional TOML templates in [`optional/agents`](optional/agents) configure designer, implementer, reviewer, and tester roles separately from the skills. Run the GUI with:

```sh
python tools/agents_gui.py
```

Choose roles and global user, repository, or both scopes. Global files go to `$CODEX_HOME/agents` when set, otherwise `~/.codex/agents`. Repository files go to `<target-repository>/.codex/agents`. The tool shows a preview and requires confirmation. It updates only files bearing its management marker and exact template instructions, preserving existing model and reasoning-effort values in editable controls. Unknown or hand-edited templates and symlinks are refused. Each file replacement is atomic; a set of files is not transactional. It never edits `AGENTS.md` or Codex configuration.

Model and effort fields are editable. Blank values inherit Codex defaults. **Refresh available models** is an explicit request to the local `codex app-server`; it requires Codex on `PATH` or, on Windows, the Codex VS Code extension installed in its standard location. It uses the documented [`model/list` API](https://developers.openai.com/codex/app-server) and [`agents` configuration](https://developers.openai.com/codex/multi-agent). Model discovery may be unavailable; in that case enter values manually. A listed model does not guarantee account access or entitlement. The tool does not log credentials or make network calls itself.

Agent-based development automatically spawns the configured designer then implementer, followed by fresh reviewer and tester agents when independently enabled. The session still controls whether delegation and checks are permitted. If the platform cannot provide the roles, explain the limitation and use the authorized fallback; never claim an agent was spawned without an agent identity.

## Context tools

For this environment, a practical default is existing CodeGraph when available and useful, paired with focused `rg` searches and authoritative source reads. Add a small local architecture summary only when recurring navigation justifies its upkeep. The context skill explains tradeoffs among CodeGraph, Graphify, language-server/AST indexes, targeted search, and local summaries. CodeGraph is optional and is not installed by these tools.

If you choose CodeGraph, review its current [repository and setup instructions](https://github.com/colbymchenry/codegraph) first. Its documented setup includes `npm install -g @colbymchenry/codegraph`, `codegraph install`, and `codegraph init`. It may change global MCP configuration and AGENTS instructions. Inspect your existing setup and the upstream commands before running them. The getonmylevel tools never install or initialize CodeGraph.

## Platform notes

The GUIs use Python's standard-library Tkinter and work on Windows, macOS, and Linux when Tk support is available. Run scripts directly with Python; they locate repository content relative to their own files. If no graphical display or Tk is available, the skill installer has terminal instructions above and agent templates can be edited manually. No credentials are needed for local installation. Codex is needed only for the optional model refresh.

## License and attribution

This repository is source-available under a custom license: personal, noncommercial use and private modifications are permitted; commercial use and public distribution of modified or derivative work require prior written permission. This is not an open-source license. See [`LICENSE`](LICENSE) and [`ATTRIBUTION.md`](ATTRIBUTION.md). The license wording is a starting point and should receive legal review before publication.
