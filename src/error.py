from enum import Enum

class ErrorCode(Enum):
    E0001 = "unterminated comment"
    E0002 = "unterminated character literal"
    E0003 = "unterminated string literal"
    E0004 = "character literal may not contain newline character"
    E0005 = "string literal may not contain newline character"
    E0006 = "digit separator after base prefix"
    E0007 = "adjacent digit separators"
    E0008 = "digit separator outside digit sequence"
    E0009 = "missing a digit after base prefix"
    E0010 = "invalid digit in binary literal"
    E0011 = "invalid digit in octal literal"
    E0012 = "invalid digit in decimal literal"
    E0013 = "unrecognized digit in number literal"
    E0014 = "invalid suffix in number literal"
    E0015 = "unrecognized sequence"
    E0016 = "exponent has no digits"
    E0017 = "invalid digit separator"
    E0018 = "hexadecimal floating literals require an exponent"
    E0019 = "invalid base for floating literal"
    E0020 = "hexadecimal escape sequence has no digits"
    E0021 = "unknown escape sequence"
    E0022 = "incomplete universal character name"
    E0023 = "octal escape sequence has no digits"
    E0024 = "hexadecimal floating literal has no digits"
    E0025 = "invalid hexadecimal exponent in decimal floating literal"
    E0026 = "empty character literal"


class Span:
    def __init__(self, start: int, end: int) -> None:
        self.start = start
        self.end = end


class Error:
    def __init__(self, msg: str = "") -> None:
        self.msg = msg

    def code(self) -> int:
        return 1

    def report(self) -> str:
        return self.msg
