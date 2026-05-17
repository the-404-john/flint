from colors import *

commands: dict[str, str] = {
    "run":     "Execute file or start the interactive mode (REPL).",
    "check":   "Perform static analysis and syntax validation.",
    "watch":   "Continuously re-check when source files are modified.",
    "format":  "Rewrite file using default or flintfmt.toml style.",
    "version": "Print version information and exit.",
    "example": "Print usage example and exit.",
    "help":    "Print this message and exit."
}

options: dict[str, str] = {
    "--verbose":     "Trace each evaluation step as the program runs.",
    "--silent":      "Suppress all output, including warnings and errors.",
    "--step-limit":  f"Abort execution after {BOLD}number{RESET} evaluation steps.",
    "--cycle-limit": f"Abort execution after {BOLD}number{RESET} simulated clock cycles.",
    "--help":        "Print detailed information about the command."
}

VERSION: str = "0.1.0"
REPOSITORY: str = "https://github.com/the-404-john/flint"

FOOTER_MESSAGE: str = f"{DIM}Learn more or report issues at: {REPOSITORY}{RESET}"

HELP_MESSAGE: str = f"""\
{BLUE}{BOLD}flint{RESET} — A lightweight C23 interpreter and development toolchain.

{BOLD}{GREEN}Usage{RESET}:
    {BLUE}{BOLD}flint{NORMAL} <command> [options] [file]{RESET}

{BOLD}{GREEN}Commands{RESET}:
    {BOLD}{BLUE}run      {NORMAL} [options] [file]{RESET}    {commands["run"]}
    {BOLD}{BLUE}check    {NORMAL} [options] <file>{RESET}    {commands["check"]}
    {BOLD}{BLUE}watch    {NORMAL} [options] <file>{RESET}    {commands["watch"]}
    {BOLD}{BLUE}format   {NORMAL} [options] <file>{RESET}    {commands["format"]}
    {BOLD}{BLUE}version  {NORMAL}                 {RESET}    {commands["version"]}
    {BOLD}{BLUE}example  {NORMAL}                 {RESET}    {commands["example"]}
    {BOLD}{BLUE}help     {NORMAL}                 {RESET}    {commands["help"]}

{BOLD}{GREEN}Options{RESET}:
    {BOLD}{BLUE}--verbose    {RESET}                 {options["--verbose"]}
    {BOLD}{BLUE}--silent     {RESET}                 {options["--silent"]}
    {BOLD}{BLUE}--step-limit {RESET} {BLUE}<number>{RESET}        {options["--step-limit"]}
    {BOLD}{BLUE}--cycle-limit{RESET} {BLUE}<number>{RESET}        {options["--cycle-limit"]}
    {BOLD}{BLUE}--help       {RESET}                 {options["--help"]}

{FOOTER_MESSAGE}
"""

EXAMPLE_MESSAGE: str = f"""\
{BOLD}{GREEN}Examples{RESET}:
    # Start the interactive mode.
    $ {BLUE}{BOLD}flint{NORMAL} run{RESET}

    # Verify a specific program without running it.
    $ {BLUE}{BOLD}flint{NORMAL} check{RESET} main.c

    # Automatically re-check on every save.
    $ {BLUE}{BOLD}flint{NORMAL} watch{RESET} main.c

    # Format a specific program.
    $ {BLUE}{BOLD}flint{NORMAL} format{RESET} main.c

    # Print the version information and associated repository
    # metadata for the flint interpret.
    $ {BLUE}{BOLD}flint{NORMAL} version{RESET}

    # Print this list of command examples.
    $ {BLUE}{BOLD}flint{NORMAL} example{RESET}

    # Print the general help documentation.
    $ {BLUE}{BOLD}flint{NORMAL} help{RESET}

    # Trace each evaluation step as the program runs.
    # Abort program execution after 23 evaluation steps.
    $ {BLUE}{BOLD}flint{NORMAL} run --verbose --step-limit 23{RESET} main.c

    # Suppress all output, including warnings and errors.
    # Abort program execution after 23 simulated clock cycles.
    $ {BLUE}{BOLD}flint{NORMAL} run --silent --cycle-limit 23{RESET} main.c
"""

RUN_HELP_MESSAGE: str = f"""\
{BOLD}{GREEN}Description{RESET}: {commands["run"]}

{BOLD}{GREEN}Usage{RESET}: {BOLD}{BLUE}flint run{RESET} [options] [file]

{BOLD}{GREEN}Options{RESET}:
    {BOLD}{BLUE}--verbose    {RESET}                 {options["--verbose"]}
    {BOLD}{BLUE}--silent     {RESET}                 {options["--silent"]}
    {BOLD}{BLUE}--step-limit {RESET} {BLUE}<number>{RESET}        {options["--step-limit"]}
    {BOLD}{BLUE}--cycle-limit{RESET} {BLUE}<number>{RESET}        {options["--cycle-limit"]}
    {BOLD}{BLUE}--help       {RESET}                 {options["--help"]}

{BOLD}{GREEN}Examples{RESET}:
    # Launch the interactive mode of the interpret (REPL).
    $ {BLUE}{BOLD}flint{NORMAL} run{RESET}

    # Execute a specific file and provide detailed output for every
    # evaluation step.
    $ {BLUE}{BOLD}flint{NORMAL} run --verbose{RESET} main.c

    # Execute a specific file without emitting diagnostic output,
    # including error and warning messages.
    $ {BLUE}{BOLD}flint{NORMAL} run --silent{RESET} main.c

    # Restrict execution of a specific file to 23 evaluation steps.
    $ {BLUE}{BOLD}flint{NORMAL} run --step-limit 23{RESET} main.c

    # Restrict execution of a specific file to 23 simulated processor
    # cycles.
    $ {BLUE}{BOLD}flint{NORMAL} run --cycle-limit 23{RESET} main.c

    # Execute a specific file with combined and detailed step-by-step
    # logging.
    $ {BLUE}{BOLD}flint{NORMAL} run --verbose --step-limit 23 --cycle-limit 23{RESET} main.c

    # Execute a specific file with combined and without diagnostic
    # output.
    $ {BLUE}{BOLD}flint{NORMAL} run --silent --step-limit 23 --cycle-limit 23{RESET} main.c

    # Print this help message.
    $ {BLUE}{BOLD}flint{NORMAL} run --help{RESET}

{FOOTER_MESSAGE}
"""

CHECK_HELP_MESSAGE: str = f"""\
{BOLD}{GREEN}Description{RESET}: {commands["check"]}

{BOLD}{GREEN}Usage{RESET}: {BOLD}{BLUE}flint check{RESET} [options] <file>

{BOLD}{GREEN}Options{RESET}:
    {BOLD}{BLUE}--silent{RESET}    {options["--silent"]}
    {BOLD}{BLUE}--help  {RESET}    {options["--help"]}

{BOLD}{GREEN}Examples{RESET}:
    # Execute syntax validation and static analysis on a specific file.
    $ {BLUE}{BOLD}flint{NORMAL} check{RESET} main.c

    # Perform analysis without emitting diagnostic output, including
    # error and warning messages.
    $ {BLUE}{BOLD}flint{NORMAL} check --silent{RESET} main.c

    # Print this help message.
    $ {BLUE}{BOLD}flint{NORMAL} check --help{RESET}

{FOOTER_MESSAGE}
"""

WATCH_HELP_MESSAGE: str = f"""\
{BOLD}{GREEN}Description{RESET}: {commands["watch"]}

{BOLD}{GREEN}Usage{RESET}: {BOLD}{BLUE}flint watch{RESET} [options] <file>

{BOLD}{GREEN}Options{RESET}:
    {BOLD}{BLUE}--help{RESET}    {options["--help"]}

{BOLD}{GREEN}Examples{RESET}:
    # Monitor the specified file for changes and automatically execute
    # diagnostic checks.
    $ {BLUE}{BOLD}flint{NORMAL} watch{RESET} main.c

    # Print this help message.
    $ {BLUE}{BOLD}flint{NORMAL} watch --help{RESET}

{FOOTER_MESSAGE}\
"""

FORMAT_HELP_MESSAGE: str = f"""\
{BOLD}{GREEN}Description{RESET}: {commands["format"]}

{BOLD}{GREEN}Usage{RESET}: {BOLD}{BLUE}flint format{NORMAL} [options] <file>{RESET}

{BOLD}{GREEN}Options{RESET}:
    {BOLD}{BLUE}--silent{RESET}    {options["--silent"]}
    {BOLD}{BLUE}--help  {RESET}    {options["--help"]}

{BOLD}{GREEN}Examples{RESET}:
    # Format a specific file according to the style defined
    # in `flintfmt.toml` or the system defaults.
    $ {BLUE}{BOLD}flint{NORMAL} format{RESET} main.c

    # Format a specific file without emitting warning or error
    # messages.
    $ {BLUE}{BOLD}flint{NORMAL} format --silent{RESET} main.c

    # Print this help message.
    $ {BLUE}{BOLD}flint{NORMAL} format --help{RESET}

{FOOTER_MESSAGE}
"""


def visualize_messages() -> None:
    msgs: list[str] = [
        ("VERSION", VERSION),
        ("REPOSITORY", REPOSITORY),
        ("FOOTER_MESSAGE", FOOTER_MESSAGE),
        ("HELP_MESSAGE", HELP_MESSAGE),
        ("EXAMPLE_MESSAGE", EXAMPLE_MESSAGE),
        ("RUN_HELP_MESSAGE", RUN_HELP_MESSAGE),
        ("CHECK_HELP_MESSAGE", CHECK_HELP_MESSAGE),
        ("WATCH_HELP_MESSAGE", WATCH_HELP_MESSAGE),
        ("FORMAT_HELP_MESSAGE", FORMAT_HELP_MESSAGE)
    ]

    for (var_name, msg) in msgs:
        print(f"{var_name}\n{msg}\n")


def test_help_msg(cmd: str, msg: str) -> None:
    assert len(msg) != 0

    assert f"flint {cmd}" in msg

    assert "Description" in msg
    assert commands[cmd] in msg

    assert "Usage" in msg
    assert "Options" in msg
    assert "Examples" in msg

    assert FOOTER_MESSAGE in msg


def test_help_msgs() -> None:
    test_help_msg("run", RUN_HELP_MESSAGE)
    test_help_msg("check", CHECK_HELP_MESSAGE)
    test_help_msg("watch", WATCH_HELP_MESSAGE)
    test_help_msg("format", FORMAT_HELP_MESSAGE)


def test() -> None:
    # Test: Verify the structural integrity of all command help
    #       messages.
    test_help_msgs()

    # Test: Verify that the version message is defined.
    assert len(VERSION) != 0

    # Test: Verify that the repository URL is correctly initialized to
    #       author's GitHub account.
    assert len(REPOSITORY) != 0
    assert "https://github.com/the-404-john" in REPOSITORY

    # Test: Verify that the footer message exists and includes
    #       the repository link.
    assert len(FOOTER_MESSAGE) != 0
    assert REPOSITORY in FOOTER_MESSAGE

    # Test: Verify that the main help message contains mandatory
    #       documentation sections.
    assert "Usage" in HELP_MESSAGE
    assert "Commands" in HELP_MESSAGE
    assert "Options" in HELP_MESSAGE

    # Test: Verify that all defined commands are present in the main
    #       help message.
    for cmd in commands.keys():
        assert cmd in HELP_MESSAGE, \
               f"Command `{cmd}` not in `HELP_MESSAGE`."

    # Test: Verify that all defined commands are represented
    #       in the examples message.
    for cmd in commands.keys():
        assert cmd in EXAMPLE_MESSAGE, \
               f"Command `{cmd}` not in `EXAMPLE_MESSAGE`."


if __name__ == "__main__":
    # NOTE: Uncomment `visualize_messages()` the line below to render
    # all formatted documentation strings for manual inspection.
    # visualize_messages()

    test()
