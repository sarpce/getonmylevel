# getonmylevel

Three independently installable Codex skills for communication, project context, and software engineering, plus optional role-agent templates and local setup tools.

## Prerequisites

- Git to clone this repository.
- Python 3.11 or newer for the setup tools. They use the standard library; the graphical tools also require a Python build with Tkinter.
- A Codex client supporting local skills and custom agents. See the official [skills documentation](https://developers.openai.com/codex/skills), [AGENTS.md guide](https://developers.openai.com/codex/guides/agents-md), and [multi-agent documentation](https://developers.openai.com/codex/multi-agent).

```sh
git clone https://github.com/sarpce/getonmylevel.git
cd getonmylevel
```

Each skill is independent. Its `agents/openai.yaml` disables implicit invocation, so select the skill through the optional session convention or invoke it explicitly. None of the installer tools modifies global instructions or Codex settings.

## Install skills

Run the graphical installer from any working directory:

```sh
python tools/install_gui.py
```

Select one or more skills and a scope: **User-wide**, **Target repository**, or **Both**. For repository scope, choose an existing target repository. The preview shows all destinations. The tool validates every source and destination before writing and asks for confirmation. Existing files, directories, symlinks, junctions, and other detected reparse points are refused in the selected base and managed path. An I/O error during a multi-skill copy can leave earlier completed copies in place; the tool reports them.

User-wide skills go to `$HOME/.agents/skills`. Repository skills go to `<target-repository>/.agents/skills` and may be tracked by that repository. Installing in both places may cause duplicate discovery; usually choose one. The built-in `$skill-installer` uses `$CODEX_HOME/skills`; locations may differ by client. Follow current [Codex skills documentation](https://developers.openai.com/codex/skills). Restart Codex if a new skill is not discovered.

### Terminal fallback

The same selection is available without Tkinter. Run from this repository root and edit the exact allowlisted names, scopes, and repository root. The script preflights selected source files and every destination, including symlinks, before it creates directories or copies files.

PowerShell:

```powershell
$ErrorActionPreference = 'Stop'
$allowedNames = @('getonmylevel-communication', 'getonmylevel-context', 'getonmylevel-engineering')
$names = @('getonmylevel-communication', 'getonmylevel-context', 'getonmylevel-engineering')
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
names='getonmylevel-communication getonmylevel-context getonmylevel-engineering'
scopes='user' # 'repo' or 'user repo' are also supported
target_repo='/path/to/target-repository'
allowed_names=' getonmylevel-communication getonmylevel-context getonmylevel-engineering '
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

The optional selector instruction in [`optional/global-session-selector.md`](optional/global-session-selector.md) supports **On**, **Off**, and **Ask** preferences for the three skills. It also states that Simple/Agent-based development choice is independent of skill selection. Merge it manually with your effective global instructions; it does not edit or override them. These are conversation conventions, not enforced Codex settings. The GUI can copy a generated instruction block without changing any file.

Explicit skill invocation uses `$getonmylevel-communication`, `$getonmylevel-context`, or `$getonmylevel-engineering`. Higher-priority instructions and available tools always constrain activation.

## Optional agent roles

The optional TOML templates in [`optional/agents`](optional/agents) configure designer, implementer, reviewer, and tester roles separately from the skills. Run the GUI with:

```sh
python tools/agents_gui.py
```

Choose roles and global user, repository, or both scopes. Global files go to `$CODEX_HOME/agents` when set, otherwise `~/.codex/agents`. Repository files go to `<target-repository>/.codex/agents`. The tool shows a preview and requires confirmation. It updates only files bearing its management marker and exact template instructions, preserving existing model and reasoning-effort values in editable controls. Unknown or hand-edited templates and symlinks are refused. Each file replacement is atomic; a set of files is not transactional. It never edits `AGENTS.md` or Codex configuration.

Model and effort fields are editable. Blank values inherit Codex defaults. **Refresh available models** is an explicit request to the local `codex app-server`; it requires Codex installed and available in `PATH`. It uses the documented [`model/list` API](https://developers.openai.com/codex/app-server) and [`agents` configuration](https://developers.openai.com/codex/multi-agent). Model discovery may be unavailable; in that case enter values manually. A listed model does not guarantee account access or entitlement. The tool does not log credentials or make network calls itself.

Agent-based development automatically spawns the configured designer then implementer, followed by fresh reviewer and tester agents when independently enabled. The session still controls whether delegation and checks are permitted. If the platform cannot provide the roles, explain the limitation and use the authorized fallback; never claim an agent was spawned without an agent identity.

## Context tools

For this environment, a practical default is existing CodeGraph when available and useful, paired with focused `rg` searches and authoritative source reads. Add a small local architecture summary only when recurring navigation justifies its upkeep. The context skill explains tradeoffs among CodeGraph, Graphify, language-server/AST indexes, targeted search, and local summaries. CodeGraph is optional and is not installed by these tools.

If you choose CodeGraph, review its current [repository and setup instructions](https://github.com/colbymchenry/codegraph) first. Its documented setup includes `npm install -g @colbymchenry/codegraph`, `codegraph install`, and `codegraph init`. It may change global MCP configuration and AGENTS instructions. Inspect your existing setup and the upstream commands before running them. The getonmylevel tools never install or initialize CodeGraph.

## Platform notes

The GUIs use Python's standard-library Tkinter and work on Windows, macOS, and Linux when Tk support is available. Run scripts directly with Python; they locate repository content relative to their own files. If no graphical display or Tk is available, the skill installer has terminal instructions above and agent templates can be edited manually. No credentials are needed for local installation. Codex is needed only for the optional model refresh.

## License and attribution

This repository is source-available under a custom license: personal, noncommercial use and private modifications are permitted; commercial use and public distribution of modified or derivative work require prior written permission. This is not an open-source license. See [`LICENSE`](LICENSE) and [`ATTRIBUTION.md`](ATTRIBUTION.md). The license wording is a starting point and should receive legal review before publication.
