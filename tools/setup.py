"""Headless setup commands for roles, CodeGraph, and suggested integrations."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys

import common
import agent_operations as agents
import codegraph_installer as codegraph
import suggested_installers as suggested


def _mapping(values: list[str], option: str) -> dict[str, str]:
    result = {}
    for value in values:
        role, separator, setting = value.partition("=")
        if not separator or role not in common.AGENT_NAMES:
            raise ValueError(f"{option} expects ROLE=VALUE for a supported role: {value!r}")
        if role in result:
            raise ValueError(f"{option} was supplied more than once for role {role}.")
        result[role] = setting
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="area", required=True)
    roles = commands.add_parser("roles", help="manage optional agent role files")
    roles.add_argument("action", choices=("install", "update", "remove"))
    roles.add_argument("--client", choices=("codex", "claude", "copilot"), default="codex")
    roles.add_argument("--scope", choices=("global", "repo", "both"), default="global")
    roles.add_argument("--repo", help="existing target repository for repo or both scope")
    roles.add_argument("--roles", nargs="+", choices=common.AGENT_NAMES, required=True)
    roles.add_argument("--model", action="append", default=[], metavar="ROLE=VALUE", help="set a model; ROLE= clears it")
    roles.add_argument("--effort", action="append", default=[], metavar="ROLE=VALUE", help="set reasoning effort; ROLE= clears it")
    roles.add_argument("--dry-run", action="store_true")
    roles.add_argument("--yes", action="store_true", help="confirm changes to global role configuration")

    graph = commands.add_parser("codegraph", help="inspect or configure CodeGraph globally")
    graph.add_argument("action", choices=("status", "setup"))
    graph.add_argument("--client", choices=("codex", "claude", "copilot"), default="codex")
    graph.add_argument("--dry-run", action="store_true")
    graph.add_argument("--yes", action="store_true", help="confirm network install and global client configuration")

    integrations = commands.add_parser("suggested", help="manage suggested skills and tools")
    integrations.add_argument("action", choices=("status", "install", "remove"))
    integrations.add_argument("--client", choices=("codex", "claude", "copilot"), default="codex")
    integrations.add_argument("--items", nargs="+", choices=tuple(item.id for item in suggested.SUGGESTED_ITEMS))
    integrations.add_argument("--dry-run", action="store_true")
    integrations.add_argument("--yes", action="store_true", help="confirm third-party install or suggested integration removal")
    return parser


def _print_suggested_status(client: str) -> None:
    if client == "copilot":
        print("Suggested integrations are not supported for GitHub Copilot.")
        return
    status = suggested.suggested_status(client)
    by_id = {item.id: item for item in suggested.SUGGESTED_ITEMS}
    for item_id, value in status.items():
        name = by_id[item_id].name if item_id in by_id else "RTK command-output optimizer"
        if isinstance(value, tuple):
            text = ", ".join(map(str, value)) if value else "not detected"
            print(f"{name}: {text}; version and provenance are unknown")
        else:
            print(f"{name}: {value or 'not detected on PATH'}; identity, version, and provenance are unknown")


def _codegraph_dry_plan(client: str) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None, str]:
    detected = codegraph.detected_command()
    if detected:
        plan = codegraph.plan_install(client)
        return plan.executable, None, plan.details
    if os.name == "nt" or codegraph.platform.system() == "Windows":
        node, npm_cli = codegraph._windows_node_npm()
        prefix_command = (str(node), str(npm_cli), "prefix", "-g")
        install_command = (str(node), str(npm_cli), "install", "-g", codegraph.PINNED_PACKAGE)
        config_executable = (str(node), "<npm-global-prefix>/node_modules/@colbymchenry/codegraph/<npm-shim.js|dist/bin/codegraph.js>")
    else:
        npm, node = shutil.which("npm"), shutil.which("node")
        if not npm or not node:
            raise RuntimeError("Node.js and npm are required to install CodeGraph.")
        prefix_command = (str(Path(npm).resolve()), "prefix", "-g")
        install_command = (str(Path(npm).resolve()), "install", "-g", codegraph.PINNED_PACKAGE)
        config_executable = ("<npm-global-prefix>/bin/codegraph",)
    details = (f"Selected package: {codegraph.PINNED_PACKAGE}; version and provenance of any existing installation are unknown. "
               f"The global npm prefix and exact executable/configuration paths are unresolved until confirmed prefix lookup. "
               f"Network: npm downloads the package and dependencies; package lifecycle code may execute. "
               f"Global configuration target: {client} MCP settings and managed instructions. No project is initialized or indexed. "
               f"Prefix lookup command (deferred until --yes): {' '.join(prefix_command)}")
    return config_executable, install_command, details


def _run_codegraph(args) -> int:
    path = codegraph.detected_command()
    print(f"Status: {codegraph.status_text(path)}")
    print(f"Selected package for new installs: {codegraph.PINNED_PACKAGE}")
    print(f"Detected executable: {path or '(none)'}; detected presence does not prove identity, version, or provenance")
    print(f"Global configuration target: {args.client}: {codegraph.install_args(args.client)}")
    print(f"Network/execution effects: a missing installation uses {codegraph.PINNED_PACKAGE}; npm downloads packages and dependencies and may run package lifecycle code. Existing commands are not upgraded.")
    if args.action == "status":
        print("Project indexing: not performed; global setup is separate from project initialization and indexing. Use 'codegraph setup --dry-run' to inspect exact commands and resolved targets.")
        return 0
    executable, npm_install, details = _codegraph_dry_plan(args.client)
    print(details)
    print("Planned commands:")
    if npm_install:
        print("  " + " ".join(npm_install))
    if executable:
        print("  " + " ".join((*executable, *codegraph.install_args(args.client))))
    if args.dry_run:
        return 0
    if not args.yes:
        print("Refusing to install packages or change global client configuration without --yes.", file=sys.stderr)
        return 2
    try:
        plan = codegraph.plan_install(args.client)
        result = codegraph.install(plan)
        print(result)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"CodeGraph setup failed; package installation may have completed before failure: {exc}", file=sys.stderr)
        return 1


def _run_suggested(args) -> int:
    if args.client == "copilot":
        print("Suggested integrations are not supported for GitHub Copilot; no action was taken.", file=sys.stderr)
        return 2 if args.action != "status" else 0
    if args.action == "status":
        _print_suggested_status(args.client)
        return 0
    if not args.items:
        print("Select one or more --items.", file=sys.stderr)
        return 2
    if args.action == "remove":
        plans = []
        for item_id in args.items:
            plan, error = suggested.plan_removal(item_id, args.client)
            if error:
                print(f"Cannot remove {item_id}: {error}", file=sys.stderr)
                return 1
            plans.append(plan)
        for plan in plans:
            print(f"Remove: {plan.name}")
            for path, _identity in plan.destinations:
                print(f"  {path}")
        if args.dry_run:
            return 0
        if not args.yes:
            print("Refusing to remove suggested integrations without --yes.", file=sys.stderr)
            return 2
        results = suggested.remove_selected(plans)
    else:
        plans, error = suggested.plan_selected(args.items, args.client)
        if error:
            print(error, file=sys.stderr)
            return 1
        for plan in plans:
            print(f"Install: {plan.name}\n{plan.details}")
            print(f"Destination: {plan.destination or '(installer managed)'}")
            for command in plan.commands:
                print("  Command: " + " ".join(command))
            print("Network: pinned source fetch where listed; execution effects: " + plan.details)
        if args.dry_run:
            return 0
        if not args.yes:
            print("Refusing third-party suggested integration installation without --yes.", file=sys.stderr)
            return 2
        results = suggested.install_selected(plans)
    failed = False
    for name, success, detail in results:
        print(f"{'Completed' if success else 'Failed'}: {name}\n{detail}")
        failed |= not success
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.area == "roles":
            models, efforts = _mapping(args.model, "--model"), _mapping(args.effort, "--effort")
            if any(role not in args.roles for role in (*models, *efforts)):
                raise ValueError("--model and --effort may only be set for selected roles.")
            repo = Path(args.repo).expanduser() if args.repo else None
            plan = agents.role_plan(args.client, args.scope, repo, args.roles, models, efforts, action=args.action)
            for role, path, _content in plan:
                print(f"{'Remove' if args.action == 'remove' else 'Install/update'}: {role}: {path}")
                if args.action != "remove":
                    print(f"  model: {models.get(role, 'preserve existing; inherit client default for new files')}")
                    if args.client != "copilot":
                        print(f"  effort: {efforts.get(role, 'preserve existing; inherit client default for new files')}")
            print("Execution: atomic per-file managed role update; no network or third-party code; no backup files are created.")
            if args.dry_run:
                return 0
            if args.scope in ("global", "both") and not args.yes:
                print("Refusing to change global client role configuration without --yes.", file=sys.stderr)
                return 2
            completed, backups = agents.perform_role_plan(plan, args.client, args.action)
            for path in completed:
                print(f"Completed: {path}")
            for path in backups:
                print(f"Backup: {path}")
            print("No backups were created.")
            return 0
        if args.area == "codegraph":
            return _run_codegraph(args)
        return _run_suggested(args)
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        print(f"Operation stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
