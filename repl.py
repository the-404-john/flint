import sys

from error import *
from common import *

from build import Builder
from eval import Evaluator

# Read-Eval-Print Loop
# johnatan, you can not just make the source code and then evaluate
# everything, because if some part of the code will fail on runtime,
# you don't want it to fail twice, for example assert or
# you want to redefine functions or fkcing variables
# or you don't want to print twice the same thing.
#
# new idea is, just build the fkcing ast from the new line and just
# adjust the scope I guess??

class REPL:
    def __init__(self) -> None:
        self.exit_code: int = 0

    def write_on_stdout(self, msg: str) -> None:
        print(msg, end="\n", file=sys.stdout, flush=True)

    def read_input() -> str | None:
        prompt: str = ">> "

        while True:
            try:
                line: str = input(prompt)

            except EOFError:

                break

            except KeyboardInterrupt:

                continue

            line = self.format_line(line)

            if len(line) == 0:
                continue

            self.(line)
        pass

    def eval(self, source_code: str) -> None | Error:
        ast: AST | Error = Builder().build_source(source_code)
        if isinstance(ast, Error):
            return ast



    def run() -> None:
        source_code: str = None

        while True:
            = self.read_input()

            if is None:
                break



def test() -> None:
    pass


if __name__ == "__main__":
    test()
