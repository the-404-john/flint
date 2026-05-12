import sys

from error import *
from flint_ast import AST

# Builder
#


class Builder:
    def __init__(self, save_comments: bool, file_name: str) -> None:
        self.save_comments = save_comments

    def build_source(self, source_code: str) -> AST | Error:
        ast = AST(source_code)

        result = ast.build(save_comments)
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
            return Error()

        except PermissionError:
            return Error()

        except UnicodeDecodeError as e:
            return Error()

        except OSError as e:
            return Error()

        # Translation phase 2.
        if source_code.find("\\\n") != -1:
            return Error()

        return self.build_source(source_code)
