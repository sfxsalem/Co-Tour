"""Developer commands for reviewed runtime artifact releases."""

from __future__ import annotations

import argparse
from pathlib import Path

from cotour.artifacts import build_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Co-Tour runtime artifacts")
    subparsers = parser.add_subparsers(dest="command", required=True)
    builder = subparsers.add_parser("build-manifest")
    builder.add_argument("data_directory", type=Path)
    builder.add_argument("--bundle-version", required=True)
    arguments = parser.parse_args()
    if arguments.command == "build-manifest":
        print(build_manifest(arguments.data_directory, arguments.bundle_version))


if __name__ == "__main__":
    main()
