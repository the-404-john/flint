import sys
import os
import time
import datetime
import subprocess

from enum import Enum

from error import *
from common import *
from cli_messages import *

from repl import REPL
from build import Builder
from eval import Evaluator

# Command-line Interface
# Enables users to interact with the software and manage its execution
# through a specific terimal commands.
#
# NOTE: If a standard app (GUI) is like ordering from a restaurant
# menu, then the CLI is like talking directly to the chef. You don't
# click a picture of what you want. Instead you type the exact "recipe"
# of what you want.

def receive_project_git_info() -> tuple[str, str]:
    # Retrieve Git metadata to identify the specific build during bug
    # analysis.
    #
    # Use subprocess to avoid external library dependencies and a try-except
    # approach to ensure the application remains functional if Git
    # is not installed or the environment is not a valid repository.
    try:
        sha = subprocess.check_output([
            "git",
            "rev-parse",
            "--short",
            "HEAD"
        ]).decode("ascii").strip()

        date = subprocess.check_output([
            "git",
            "log",
            "-1",
            "--format=%cd",
            "--date=format:%Y-%m-%d"
        ]).decode("ascii").strip()

        return sha, date

    except:
        return "unknown", "unknown"


class CLIOption(Enum):
    verbose     = "--verbose"
    silent      = "--silent"
    step_limit  = "--step-limit"
    cycle_limit = "--cycle-limit"
    help        = "--help"


class CLI:
    def __init__(self, args: list[str]) -> None:
        # Skip argv[0] as it contains the executable path.
        self.args = args
        self.index: int = 1

        self.exit_code: int = 0

        # Parsed CLI arguments.
        self.file_name: str = ""
        self.options: dict[CLIOption, int | None] = {}

    def peek(self) -> str | None:
        if self.index >= len(self.args):
            return None

        return self.args[self.index]

    def fetch(self) -> str | None:
        string = self.peek()
        self.index += 1

        return string

    def fetch_options(self) -> dict[CLIOption, int | None] | None:
        options: dict[CLIOption, int | None] = {}

        while True:
            prev_len = len(options)

            for opt in CLIOption:
                if not self.match(opt.value):
                    continue

                if opt in options:
                    return self.report_failure(Error())

                options[opt] = None

                if opt is {CLIOption.step_limit, CLIOption.cycle_limit}:
                    if self.peek() is None:
                        return self.report_failure(Error())

                    result: int | Error = str_to_int(self.peek())
                    if isinstance(result, Error):
                        return self.report_failure(result)

                    options[opt] = result

            if prev_len == len(options):
                break

        return options

    def expect(self, expected: str) -> str:
        assert self.peek() == expected
        return self.fetch()

    def match(self, expected: str) -> bool:
        if self.peek() == expected:
            self.fetch()
            return True

        return False

    def match_file_name(self) -> bool:
        if arg_is_file(self.peek()):
            self.file_name = self.fetch()
            return True
        else:
            self.report_failure(Error())
            return False

    def match_options(self, cmd: str) -> bool:
        options: dict[CLIOption, int | None] | None = self.fetch_options()
        if options is None:
            assert self.exit_code != 0
            return False

        if len(options) > 1 and CLIOption.help in options:
            self.report_failure(Error())
            return False

        if cmd == "run":
            if {CLIOption.verbose, CLIOption.silent}.issubset(options):
                self.report_failure(Error())
                return False

        elif cmd == "check" or cmd == "format":
            if len(options - {CLIOption.help, CLIOption.silent}) != 0:
                self.report_failure(Error())
                return False

        else:
            assert cmd == "watch":

            if len(options - {CLIOption.help}) != 0:
                self.report_failure(Error())
                return False

        self.options = options
        return True

    def match_args(self, cmd: str) -> bool:
        if not self.match_options():
            assert self.exit_code != 0
            return False

        if CLIOption.help in self.options:
            if self.peek() is not None:
                return self.report_failure(Error())

            return True

        if not self.match_file_name():
            assert self.exit_code != 0
            return

        if self.peek() is not None:
            self.report_failure(Error())
            return False

        return True

    def arg_is_file(self, arg: str | None) -> bool:
        return arg is not None and arg.endswith(".c")

    def write_on_stdout(self, msg: str) -> None:
        if not self.silent:
            print(msg, end="\n", file=sys.stdout, flush=True)

    def write_on_stderr(self, msg: str) -> None:
        if not self.options:
            print(msg, end="\n", file=sys.stderr, flush=True)

    def report_failure(self, err: Error) -> None:
        self.exit_code = err.code()
        write_on_stderr(err.report())

    def build_target(self) -> AST | Error:
        full_path = os.path.abspath(self.file_name)
        write_on_stdout(
            f"    "
            f"{GREEN}{BOLD}Checking{RESET} "
            f"`{self.file_name}` "
            f"({full_path})"
        )

        start_time = time.perf_counter()
        ast: AST | Error = Builder().build_file(self.file_name)
        end_time = time.perf_counter()

        if isinstance(ast, Error):
            return self.report_failure(ast)

        elapse_time = end_time - start_time
        write_on_stdout(
            f"    "
            f"{GREEN}{BOLD}Finished{RESET} "
            f"`default` profile [unoptimized + debuginfo] "
            f"target(s) in {elapsed_time:.3f}s"
        )

        return ast

    def update_target(self, file_path: str, prev_mtime: float) -> float:
        curr_mtime = os.path.getmtime(file_path)
        if curr_mtime == prev_mtime:
            return curr_mtime

        os.system("clear")
        time_str = (
            datetime
            .fromtimestamp(curr_mtime)
            .strftime('%Y-%m-%d %H:%M:%S')
        )

        write_on_stdout(
            f"{GREEN}{BOLD}Watching{RESET} "
            f"`{self.filen_name}` | "
            f"lastly updated: {time_str}"
        )

        ast: AST | Error = self.build_target()
        if isinstance(ast, Error):
            self.report_failure(ast)

        return curr_mtime

    def cmd_run(self) -> None:
        self.expect("run")

        if self.peek() is None:
            return REPL().run()

        if not self.match_args("run"):
            return None

        if CLIOption.help in self.options:
            return write_on_stdout(RUN_HELP_MESSAGE)

        ast: AST | Error = self.build_target()
        if isinstance(ast, Error):
            return self.report_failure(ast)

        write_on_stdout(
            f"    "
            f"{GREEN}{BOLD}Running{RESET} `{self.file_name}`"
        )

        result: None | Error = Evaluator(ast).run()
        if isinstance(result, Error):
            return self.report_failure(result)

    def cmd_check(self) -> None:
        self.expect("check")

        if not self.match_args("check"):
            return None

        if CLIOption.help in self.options:
            return write_on_stdout(CHECK_HELP_MESSAGE)

        ast: AST | Error = self.build_target()
        if isinstance(ast, Error):
            return self.report_failure(ast)

    def cmd_watch(self) -> None:
        self.expect("watch")

        if not self.match_args("watch"):
            return None

        if CLIOption.help in self.options:
            return write_on_stdout(WATCH_HELP_MESSAGE)

        assert len(self.options) == 0

        file_path: str = os.path.abspath(self.file_name)

        try:
            prev_mtime: float = os.path.getmtime(file_path)

            while True:
                time.sleep(2)

                prev_mtime = self.update_target(
                    self.file_name,
                    file_path,
                    prev_mtime
                )

        except KeyboardInterrupt:
            return write_on_stdout(
                f"\n{YELLOW}{BOLD}Watching{RESET} stopped"
            )

        except:
            return self.report_failure(Error())

    def cmd_format(self) -> None:
        self.expect("format")

        if not self.match_args("format"):
            return None

        if CLIOption.help in self.options:
            return write_on_stdout(FORMAT_HELP_MESSAGE)

        ast: AST | Error = Builder().build_file(self.file_name)
        if isinstance(ast, Error):
            return self.report_failure(ast)

        result: None | Error = Formater(ast, self.file_name).format()
        if isinstance(result, Error):
            return self.report_failure(result)

    def cmd_version(self) -> None:
        self.expect("version")

        if self.peek() is not None:
            return self.report_failure(Error())

        write_on_stdout(
            f"flint "
            f"{VERSION} "
            f"{receive_project_git_info()}"
        )

    def cmd_example(self) -> None:
        self.expect("example")

        if self.peek() is not None:
            return self.report_failure(Error())

        write_on_stdout(EXAMPLE_MESSAGE)

    def cmd_help(self) -> None:
        self.expect("help")

        if self.peek() is not None:
            return self.report_failure(Error())

        write_on_stdout(HELP_MESSAGE)

    def cmd_invalid(self) -> None:
        self.report_failure(Error())

    def exec(self) -> None:
        cmd: str | None = self.peek()

        if cmd == "run":
            return self.cmd_run()

        if cmd == "check":
            return self.cmd_check()

        if cmd == "watch":
            return self.cmd_watch()

        if cmd == "format":
            return self.cmd_format()

        if cmd == "version":
            return self.cmd_version()

        if cmd == "help" or cmd == None:
            return self.cmd_help()

        return self.cmd_invalid()


def test_cli(should_succeed: bool, args: str) -> None:
    arg_tokens: list[str] = ["flint"] + args.split()

    target_files: set[str] = {}
    file_suffixes = (".c", ".cpp", ".rs", ".py")

    tmp_dir = os.mkdtemp()

    for idx, arg_token in enumerate(arg_tokens):
        if not arg_token.endswith(file_suffixes):
            continue

        file_path = os.path.join(tmp_dir, arg_token)

        target_files.add(file_path)
        arg_tokens[idx] = file_path

    try:
        for file_path in target_files:
            with open(file_path, "w") as file:
                if file_path.endswith(".c"):
                    file.write("int main() { return 0; }\n")

        cli = CLI(arg_tokens)
        cli.exec()

        if should_succeed:
            assert cli.exit_code == 0, \
                f"Expected success, but got {cli.exit_code}"
        else:
            assert cli.exit_code != 0, \
                "Expected failure, but CLI exited with 0"
    finally:
        for file_path in target_files:
            if os.path.exists(file_path):
                os.remove(file_path)

        os.rmdir(tmp_dir)


def test_cmd_run_success() -> None:
    # Test: Verify the initiation of the interactive REPL session.
    test_cli(True, "run")

    # Test: Verify the standard execution flow of a C source file.
    test_cli(True, "run tmp.c")

    # Test: Verify individual flags.
    test_cli(True, "run --verbose tmp.c")
    test_cli(True, "run --silent tmp.c")

    test_cli(True, "run --step-limit 0 tmp.c")
    test_cli(True, "run --cycle-limit 0 tmp.c")

    # Test: Verify the combination of verbose flag with
    #       resource-limiting constraints.
    test_cli(True, "run --verbose --step-limit 0 tmp.c")
    test_cli(True, "run --verbose --cycle-limit 0 tmp.c")

    test_cli(True, "run --step-limit 0 --verbose tmp.c")
    test_cli(True, "run --cycle-limit 0 --verbose tmp.c")

    test_cli(True, "run --verbose --step-limit 0 --cycle-limit 0 tmp.c")
    test_cli(True, "run --verbose --cycle-limit 0 --step-limit 0 tmp.c")

    test_cli(True, "run --step-limit 0 --cycle-limit 0 --verbose tmp.c")
    test_cli(True, "run --cycle-limit 0 --step-limit 0 --verbose tmp.c")

    test_cli(True, "run --step-limit 0 --verbose --cycle-limit 0 tmp.c")
    test_cli(True, "run --cycle-limit 0 --verbose --step-limit 0 tmp.c")

    # Test: Verify the combination of silent flag with
    #       resource-limiting constraints.
    test_cli(True, "run --silent --step-limit 0 tmp.c")
    test_cli(True, "run --silent --cycle-limit 0 tmp.c")

    test_cli(True, "run --step-limit 0 --silent tmp.c")
    test_cli(True, "run --cycle-limit 0 --silent tmp.c")

    test_cli(True, "run --silent --step-limit 0 --cycle-limit 0 tmp.c")
    test_cli(True, "run --silent --cycle-limit 0 --step-limit 0 tmp.c")

    test_cli(True, "run --silent --step-limit 0 --cycle-limit 0 tmp.c")
    test_cli(True, "run --silent --cycle-limit 0 --step-limit 0 tmp.c")

    test_cli(True, "run --step-limit 0 --cycle-limit 0 --silent tmp.c")
    test_cli(True, "run --cycle-limit 0 --step-limit 0 --silent tmp.c")

    test_cli(True, "run --step-limit 0 --silent --cycle-limit 0 tmp.c")
    test_cli(True, "run --cycle-limit 0 --silent --step-limit 0 tmp.c")

    # Test: Verify the accessibility and display of the command help
    #       documentation.
    test_cli(True, "run --help")


def test_cmd_basic_failure(cmd: str) -> None:
    # Test: Verify the rejection of unsupported file extensions.
    test_cli(False, f"{cmd} tmp.py")
    test_cli(False, f"{cmd} tmp.rs")
    test_cli(False, f"{cmd} tmp.cpp")

    # Test: Verify the rejection of multiple source files.
    test_cli(False, f"{cmd} tmp_1.c tmp_2.c")
    test_cli(False, f"{cmd} --silent tmp_1.c tmp_1.c")

    # Test: Verify the rejection of non-standard or malformed
    #       flag prefixes.
    test_cli(False, f"{cmd} -silent tmp.c")
    test_cli(False, f"{cmd} ---silent tmp.c")

    # Test: Verify the rejection of unrecognized positional arguments
    #       or commands.
    test_cli(False, f"{cmd} something")
    test_cli(False, f"{cmd} something nothing")

    # Test: Verify the rejection of flags used in combination with
    #       the --help flag.
    test_cli(False, f"{cmd} --help tmp.c")
    test_cli(False, f"{cmd} --help --silent")


def test_cmd_run_failure() -> None:
    # Test: Verify the rejection of basic invalid arguments and flags.
    test_cmd_basic_failure("run")

    # Test: Verify the rejection of execution when the required
    #       source file is missing.
    test_cli(False, "run --verbose")
    test_cli(False, "run --silent")

    test_cli(False, "run --step-limit 0")
    test_cli(False, "run --cycle-limit 0")

    # Test: Verify the rejection of simultaneously used, mutually
    #       exclusive verbosity flags.
    test_cli(False, "run --verbose --silent tmp.c")
    test_cli(False, "run --silent --verbose tmp.c")

    # Test: Verify the rejection of resource limit arguments lacking
    #       explicit numeric values.
    test_cli(False, "run --step-limit tmp.c")
    test_cli(False, "run --cycle-limit tmp.c")

    # Test: Verify the rejection of multiple source files.
    test_cli(False, "run --verbose tmp_1.c tmp_2.c")

    test_cli(False, "run --step-limit 0 tmp_1.c tmp_2")
    test_cli(False, "run --cycle-limit 0 tmp_1.c tmp_2.c")

    # Test: Verify the rejection of signed or negative integer
    #       formatting for step and cycle constraints.
    test_cli(False, "run --step-limit -1 tmp.c")
    test_cli(False, "run --step-limit +1 tmp.c")

    test_cli(False, "run --cycle-limit -1 tmp.c")
    test_cli(False, "run --cycle-limit +1 tmp.c")

    # Test: Verify the rejection of resource limits containing
    #       syntax errors.
    test_cli(False, "run --step-limit 0 --cycle-limit +1 tmp.c")
    test_cli(False, "run --cycle-limit +1 --step-limit 0 tmp.c")

    test_cli(False, "run --step-limit +1 --cycle-limit 0 tmp.c")
    test_cli(False, "run --cycle-limit 0 --step-limit +1 tmp.c")


def test_cmd_run() -> None:
    test_cmd_run_success()
    test_cmd_run_failure()


def test_cmd_check_success() -> None:
    # Test: Verify the standard checking of a C source file.
    test_cli("check tmp.c")

    # Test: Verify individual flags.
    test_cli("check --silent tmp.c")

    # Test: Verify the accessibility and display of the command help
    #       documentation.
    test_cli("check --help")


def test_cmd_advanced_failure(cmd: str) -> None:
    # Test: Verify the rejection of basic invalid arguments and flags
    #       for given command.
    test_cmd_basic_failure(cmd)

    # Test: Verify the rejected when the required source file is missing.
    test_cli(False, cmd)

    # Test: Verify the rejection of individual runtime-specific flags.
    test_cli(False, f"{cmd} --verbose tmp.c")

    test_cli(False, f"{cmd} --step-limit 0 tmp.c")
    test_cli(False, f"{cmd} --cycle-limit 0 tmp.c")

    # Test: Verify the rejection of combined verbosity and execution
    #       limit flags during file validation.
    test_cli(False, f"{cmd} --verbose --step-limit 0 tmp.c")
    test_cli(False, f"{cmd} --verbose --cycle-limit 0 tmp.c")

    test_cli(False, f"{cmd} --step-limit 0 --verbose tmp.c")
    test_cli(False, f"{cmd} --cycle-limit 0 --verbose tmp.c")

    test_cli(False, f"{cmd} --verbose --step-limit 0 --cycle-limit 0 tmp.c")
    test_cli(False, f"{cmd} --verbose --cycle-limit 0 --step-limit 0 tmp.c")

    test_cli(False, f"{cmd} --step-limit 0 --cycle-limit 0 --verbose tmp.c")
    test_cli(False, f"{cmd} --cycle-limit 0 --step-limit 0 --verbose tmp.c")

    test_cli(False, f"{cmd} --step-limit 0 --verbose --cycle-limit 0 tmp.c")
    test_cli(False, f"{cmd} --cycle-limit 0 --verbose --step-limit 0 tmp.c")

    # Test: Verify the rejection of combined silent mode and execution
    #       limit flags during file validation.
    test_cli(False, f"{cmd} --silent --step-limit 0 tmp.c")
    test_cli(False, f"{cmd} --silent --cycle-limit 0 tmp.c")

    test_cli(False, f"{cmd} --step-limit 0 --silent tmp.c")
    test_cli(False, f"{cmd} --cycle-limit 0 --silent tmp.c")

    test_cli(False, f"{cmd} --silent --step-limit 0 --cycle-limit 0 tmp.c")
    test_cli(False, f"{cmd} --silent --cycle-limit 0 --step-limit 0 tmp.c")

    test_cli(False, f"{cmd} --silent --step-limit 0 --cycle-limit 0 tmp.c")
    test_cli(False, f"{cmd} --silent --cycle-limit 0 --step-limit 0 tmp.c")

    test_cli(False, f"{cmd} --step-limit 0 --cycle-limit 0 --silent tmp.c")
    test_cli(False, f"{cmd} --cycle-limit 0 --step-limit 0 --silent tmp.c")

    test_cli(False, f"{cmd} --step-limit 0 --silent --cycle-limit 0 tmp.c")
    test_cli(False, f"{cmd} --cycle-limit 0 --silent --step-limit 0 tmp.c")


def test_cmd_check_failure() -> None:
    # Test: Verify the rejection of advanced invalid arguments and flags.
    test_cmd_advanced_failure("check")


def test_cmd_check() -> None:
    test_cmd_check_success()
    test_cmd_check_failure()


def test_cmd_watch_success() -> None:
    # Test: Verify the accessibility and display of the command help
    #       documentation.
    test_cli("watch --help")


def test_cmd_watch_failure() -> None:
    # Test: Verify the rejection of basic invalid arguments and flags.
    test_cmd_basic_failure("watch")

    # Test: Verify the rejection
    test_cli("watch")
    test_cli("watch --silent")

    # Test: Verify the rejection of individual runtime-specific flags.
    test_cli("watch --verbose tmp.c")
    test_cli("watch --step-limit 0 tmp.c")
    test_cli("watch --cycle-limit 0 tmp.c")

    # Test: Verify the rejection of unsupported flags when provided
    #       alongside the supported --silent flag.
    test_cli("watch --silent --verbose tmp.c")
    test_cli("watch --silent --step-limit 0 tmp.c")
    test_cli("watch --silent --cycle-limit 0 tmp.c")

    test_cli("watch --verbose --silent tmp.c")
    test_cli("watch --step-limit 0 --silent tmp.c")
    test_cli("watch --cycle-limit 0 --silent tmp.c")

    test_cli("watch --silent --step-limit 0 --cycle-limit 0 tmp.c")


def test_cmd_watch() -> None:
    test_cmd_watch_success()
    test_cmd_watch_failure()


def test_cmd_format_success() -> None:
    # Test: Verify the formating command for C source file.
    test_cli("format tmp.c")

    # Test: Verify individual flags.
    test_cli("format --silent tmp.c")

    # Test: Verify the accessibility and display of the command help
    #       documentation.
    test_cli("format --help")


def test_cmd_format_failure() -> None:
    # Test: Verify the rejection of advanced invalid arguments and flags.
    test_cmd_advanced_failure("format")


def test_cmd_format() -> None:
    test_cmd_format_success()
    test_cmd_format_failure()


def test_cmd_no_args(cmd: str) -> None:
    # Test: Verify the rejection of a positional file argument.
    test_cli(False, f"{cmd} tmp.c")

    # Test: Verify the rejection of standard flags used standalone.
    test_cli(False, f"{cmd} --verbose")
    test_cli(False, f"{cmd} --silent")
    test_cli(False, f"{cmd} --step-limit 0")
    test_cli(False, f"{cmd} --cycle-limit 0")
    test_cli(False, f"{cmd} --help")

    # Test: Verify the rejection of single flags used with a file
    #       argument.
    test_cli(False, f"{cmd} --verbose tmp.c")
    test_cli(False, f"{cmd} --silent tmp.c")
    test_cli(False, f"{cmd} --step-limit 0 tmp.c")
    test_cli(False, f"{cmd} --cycle-limit 0 tmp.c")
    test_cli(False, f"{cmd} --help tmp.c")

    # Test: Verify the rejection of combined verbose and resource limit
    #       flags.
    test_cli(False, f"{cmd} --verbose --step-limit 0 --cycle-limit 0 tmp.c")
    test_cli(False, f"{cmd} --verbose --cycle-limit 0 --step-limit 0 tmp.c")

    # Test: Verify the rejection of combined silent and resource limit
    #       flags.
    test_cli(False, f"{cmd} --silent --step-limit 0 --cycle-limit 0 tmp.c")
    test_cli(False, f"{cmd} --silent --cycle-limit 0 --step-limit 0 tmp.c")

    # Test: Verify the rejection of arbitrary positional arguments.
    test_cli(False, f"{cmd} something")
    test_cli(False, f"{cmd} something nothing")


def test_cmd_version_success() -> None:
    # Test: Verify the successful execution
    test_cli(True, "version")


def test_cmd_version_failure() -> None:
    # Test: Verify the rejection of arguments and flags for a static
    #       command.
    test_cmd_no_args("version")


def test_cmd_version() -> None:
    test_cmd_version_success()
    test_cmd_version_failure()


def test_cmd_example_success() -> None:
    # Test: Verify the successful execution
    test_cli(True, "example")


def test_cmd_example_failure() -> None:
    # Test: Verify the rejection of arguments and flags for a static
    #       command.
    test_cmd_no_args("example")


def test_cmd_example() -> None:
    test_cmd_example_success()
    test_cmd_example_failure()


def test_cmd_help_success() -> None:
    # Test: Verify the successful execution
    test_cli(True, "help")


def test_cmd_help_failure() -> None:
    # Test: Verify the rejection of arguments and flags for a static
    #       command.
    test_cmd_no_args("help")


def test_cmd_help() -> None:
    test_cmd_help_success()
    test_cmd_help_failure()


def test() -> None:
    test_cmd_run()
    test_cmd_check()
    test_cmd_watch()
    test_cmd_format()
    test_cmd_version()
    test_cmd_help()


if __name__ == "__main__":
    test()
