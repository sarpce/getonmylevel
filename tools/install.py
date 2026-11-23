"""Scriptable installer for the bundled skills (no graphical display required)."""
import argparse
import sys
import common
import skill_operations as operations


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "update", "remove", "activate"))
    parser.add_argument("--client", choices=("codex", "claude", "copilot"), default="codex")
    parser.add_argument("--scope", choices=("user", "repo", "both"), default="user")
    parser.add_argument("--repo", help="existing target directory for repository scope")
    parser.add_argument("--skills", nargs="+", choices=("all", "none", *common.SKILL_NAMES), default=["all"])
    parser.add_argument("--dry-run", action="store_true", help="show planned changes without applying them")
    args = parser.parse_args(argv)
    if ("all" in args.skills or "none" in args.skills) and len(args.skills) != 1:
        parser.error("'all' cannot be combined with individual skills")
    names = list(common.SKILL_NAMES) if args.skills == ["all"] else [] if args.skills == ["none"] else args.skills
    if not names and args.action != "activate":
        parser.error("none is only valid for activate")
    try:
        if args.action == "activate":
            scopes = ("user", "repo") if args.scope == "both" else (args.scope,)
            copies, plans = operations.plan_activation({scope: names for scope in scopes}, args.repo, args.client)
            for copy in copies:
                print(f"Required installation: {copy.destination}")
            for plan in plans:
                print(f"Instructions ({plan.action}): {plan.path}")
            if not args.dry_run:
                operations.perform_install(copies, plans, args.client)
        elif args.action == "remove":
            paths, plans = operations.plan_remove(names, args.scope, args.repo, args.client)
            for path, _ in paths:
                print(f"Remove (preserve backup): {path}")
            for plan in plans:
                print(f"Update instructions: {plan.path}")
            if not args.dry_run:
                backups, written = operations.perform_remove(paths, plans, args.client)
                for backup in backups:
                    print(f"Backup: {backup}")
                for path in written:
                    print(f"Instructions updated: {path}")
        else:
            _, copies, plans = operations.plan_install(names, args.scope, args.repo, args.client)
            for copy in copies:
                print(f"{'Update' if copy.is_update else 'Install'}: {copy.destination}")
            for plan in plans:
                print(f"Instructions ({plan.action}): {plan.path}")
            if not args.dry_run:
                result, written = operations.perform_install(copies, plans, args.client)
                for backup in result.backups:
                    print(f"Backup: {backup}")
                for path in written:
                    print(f"Instructions updated: {path}")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Operation stopped: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
