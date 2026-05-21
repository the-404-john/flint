import sys

from error import *
from flint_ast import AST

# Builder
#


class Builder:
    def __init__(self, save_comments: bool) -> None:
        self.save_comments = save_comments

    def build_source(self, source_code: str) -> AST | Error:
        ast = AST(source_code)

        result = ast.build(self.save_comments)
        if isinstance(result, Error):
            return result

        result = ast.analyze()
        if isinstance(result, Error):
            return result

        ast.optimize()
        return ast

    def build_file(self, file_name: str) -> AST | Error:
        # Use try-except approach to catch underlying OS errors
        # and format them into user-friendly error messages.

        source_code: str = ""

        try:
            with open(file_name, mode="r", encoding="utf-8-sig") as file:
                source_code = file.read()

                # Translation phase 2.
                # source_code = source_code.replace("\\\n", "")

        except FileNotFoundError:
            return Error(f"error: file not found: '{file_name}'")

        except PermissionError:
            return Error(f"error: permission denied reading '{file_name}'")

        except UnicodeDecodeError:
            return Error(f"error: '{file_name}' is not valid UTF-8")

        except OSError as e:
            return Error(f"error: failed to read '{file_name}': {e}")

        # Translation phase 2.
        if source_code.find("\\\n") != -1:
            return Error("error: line splicing ('\\\\n') is not supported")

        return self.build_source(source_code)
