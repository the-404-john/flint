import sys

from error import *
from flint_ast import AST


class Builder:
    def __init__(self, save_comments: bool, file_name: str) -> None:
        # save comments in ast for the formater...
        self.store_comments = save_comments

    def build_source(self, source_code: str) -> AST | Error:
        ast = AST(source_code)

        result = ast.build()
        if isinstance(result, ErrorCode):
            return result

        result = ast.analyze()
        if isinstance(result, ErrorCode):
            return result

        ast.normalize()
        return ast

    def build_file(self, file_name) -> AST | Error:
        # Use try-except approach to catch underlying OS errors
        # and format them into user-friendly error messages.

        source_code: str = ""

        try:
            with open(file_name, mode="r", encoding="utf-8-sig") as file:
                source_code = file.read()

                # Translation phase 2.
                source_code = source_code.replace("\\\n", "")

                # NOTE: Potentially rewrite the tokenizer as a single
                # deterministic state machine to process the file in
                # a single pass. This would include more precise token
                # tagging to better define the loaded sequence.
                #
                # Although the tokenizer implementation would be more
                # complex, it will simplify downstream phases
                # and prevent several classes of potential issues
                # (e.g. translation phase 2).

        except FileNotFoundError:
            return ErrorCode.E

        except PermissionError:
            return ErrorCode.E

        except UnicodeDecodeError as e:
            return ErrorCode.E

        except OSError as e:
            return ErrorCode.E

        return self.build_source(source_code)
