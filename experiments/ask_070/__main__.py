"""Offline-only CLI. There is intentionally no live inference subcommand."""

import argparse

from .freeze import verify
from .hashing import read_json, write_json
from .offline_guard import offline_guard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("verify-freeze")
    builder = commands.add_parser("build-freeze")
    builder.add_argument("--payload", required=True)
    corpus = commands.add_parser("audit-corpus")
    corpus.add_argument("--db", required=True)
    corpus.add_argument("--procedure", required=True)
    corpus.add_argument("--output", required=True)
    corpus.add_argument("--private-matches", required=True)
    score_parser = commands.add_parser("score-synthetic")
    score_parser.add_argument("--input", required=True)
    score_parser.add_argument("--output", required=True)
    args = parser.parse_args()
    with offline_guard():
        if args.command == "verify-freeze":
            print(verify())
        elif args.command == "build-freeze":
            from .freeze import build

            build(read_json(args.payload))
        elif args.command == "audit-corpus":
            from .corpus_presence import audit

            summary, matches = audit(args.db, read_json(args.procedure))
            write_json(args.output, summary)
            write_json(args.private_matches, matches)
        elif args.command == "score-synthetic":
            from .scorer import score

            write_json(args.output, score(read_json(args.input), synthetic=True))


if __name__ == "__main__":
    main()
