"""Headless setup commands for roles, the verify hook, and suggested skills."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys

import common
import agent_operations as agents
import hook_operations as hooks
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
    roles.add_argument("--client", choices=common.CLIENTS, default="codex")
    roles.add_argument("--scope", choices=("global", "repo", "both"), default="global")
    roles.add_argument("--repo", help="existing target repository for repo or both scope")
    roles.add_argument("--roles", nargs="+", choices=(*common.AGENT_NAMES, *common.RETIRED_AGENT_NAMES), required=True,
                       help="reviewer; the retired designer, implementer, and tester roles are accepted only for remove")
    roles.add_argument("--model", action="append", default=[], metavar="ROLE=VALUE", help="set a model; ROLE= clears it")
    roles.add_argument("--effort", action="append", default=[], metavar="ROLE=VALUE", help="set reasoning effort; ROLE= clears it")
    roles.add_argument("--dry-run", action="store_true")
    roles.add_argument("--yes", action="store_true", help="confirm changes to global role configuration")

    hook = commands.add_parser("hooks", help="manage the optional stop hook that runs targeted checks when the agent finishes")
    hook.add_argument("action", choices=("status", "install", "remove"))
    hook.add_argument("--client", choices=common.CLIENTS, default="claude")
    hook.add_argument("--dry-run", action="store_true")
    hook.add_argument("--yes", action="store_true", help="confirm the change to user-wide client hook settings")

    integrations = commands.add_parser("suggested", help="manage suggested skills and tools")
    integrations.add_argument("action", choices=("status", "install", "remove"))
    integrations.add_argument("--client", choices=common.CLIENTS, default="codex")
    integrations.add_argument("--items", nargs="+", choices=(*(item.id for item in suggested.SUGGESTED_ITEMS), *suggested.RETIRED_ITEMS),
                              help="retired suggestions from earlier releases are accepted only by remove")
    integrations.add_argument("--dry-run", action="store_true")
    integrations.add_argument("--yes", action="store_true", help="confirm third-party install or suggested integration removal")
    return parser


def _print_suggested_status(client: str) -> None:
    status = suggested.suggested_status(client)
    for item in suggested.SUGGESTED_ITEMS:
        value = status[item.id]
        text = ", ".join(map(str, value)) + "; version and provenance unknown" if value else "not installed"
        print(f"{item.name}: {text}")
    for item_id, copies in suggested.retired_status(client).items():
        print(f"Retired suggestion still installed: {suggested.RETIRED_ITEMS[item_id][0]} at {', '.join(map(str, copies))} "
              f"(remove with: suggested remove --client {client} --items {item_id} --yes)")


def _run_hooks(args) -> int:
    label = common.CLIENT_LABELS[args.client]
    if args.action == "status":
        print(f"{label} stop hook ({hooks.settings_path(args.client)}): {hooks.status(args.client)}")
        return 0
    plan = hooks.plan(args.action, args.client)
    print(f"{plan.action}: {plan.path}")
    if plan.command:
        print(f"  Hook command: {plan.command}")
        print(f"  Runs the targeted checks for changed files when the agent stops (timeout {hooks.TIMEOUT_SECONDS}s) "
              "and sends failures back. Turn off per repository with an empty .getonmylevel-checks file.")
    for note in plan.notes:
        print(f"  Note: {note}")
    if args.dry_run or plan.proposed == plan.original:
        return 0
    if not args.yes:
        print(f"Refusing to change user-wide {label} hook settings without --yes.", file=sys.stderr)
        return 2
    hooks.apply(plan)
    print(f"Completed: {plan.path}. Restart {label} to load the change.")
    return 0


def _run_suggested(args) -> int:
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
                    if args.client not in ("copilot", "opencode"):
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
        if args.area == "hooks":
            return _run_hooks(args)
        return _run_suggested(args)
    except (OSError, ValueError, RuntimeError, UnicodeError) as exc:
        print(f"Operation stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
