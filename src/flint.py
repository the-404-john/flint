import sys

from cli import CLI


def main() -> None:
    args = sys.argv[:]
    # Allow `flint file.c` as shorthand for `flint run file.c`.
    if len(args) > 1 and args[1].endswith(".c"):
        args.insert(1, "run")

    cli = CLI(args)
    cli.exec()
    sys.exit(cli.exit_code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
