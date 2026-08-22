from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence

from .auth import AuthStore
from .config import data_dir


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Portfolio Analyzer administrative recovery commands")
    commands = parser.add_subparsers(dest="command", required=True)
    reset = commands.add_parser(
        "reset-password",
        help="set a temporary password for an existing Admin user",
    )
    reset.add_argument("--username", default="admin", help="Admin username (default: admin)")
    return parser


def _reset_password(username: str) -> int:
    try:
        password = getpass.getpass("New temporary password: ")
        confirmation = getpass.getpass("Confirm temporary password: ")
    except (EOFError, KeyboardInterrupt):
        print("\nError: interactive password entry was cancelled.", file=sys.stderr)
        return 2
    if password != confirmation:
        print("Error: passwords do not match.", file=sys.stderr)
        return 2

    store = AuthStore(data_dir() / "local-portfolio.sqlite3")
    try:
        user = store.reset_admin_password(username, password)
    except (LookupError, ValueError) as exc:
        print(f"Error: {exc}.", file=sys.stderr)
        return 2

    print(
        f"Password reset for Admin '{user['username']}'. "
        "Existing sessions were revoked; a password change is required at the next sign-in."
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "reset-password":
        return _reset_password(args.username)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
