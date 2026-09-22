"""Run a learned-model rehearsal under the same lease used by live family adapters."""
from __future__ import annotations

import argparse
import subprocess
import sys

from backend.services.perception_lab.model_lease import ModelLeaseBusy, learned_model_lease


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", required=True)
    parser.add_argument("--timeout", type=float, default=0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("a command is required after --")
    try:
        with learned_model_lease(family=args.family, timeout=args.timeout):
            return subprocess.call(command)
    except ModelLeaseBusy as exc:
        print(str(exc), file=sys.stderr)
        return 75


if __name__ == "__main__":
    raise SystemExit(main())
