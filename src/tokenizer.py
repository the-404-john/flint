from enum import Enum
from typing import Self

from error import *
from common import *

# Tokenizer
# Validates input structure based on grammar rules. If the input is
# not recognized by the grammar, it's rejected.
#
# NOTE: This validates syntax at the word level, not the structural
# or semantic level. For example, it recognizes a number as a
# "numeric literal" without verifying its bit-length, sign, or
# specific type compatibility or if the number was correctly used
# within the program.
#
# Analogy (Natural Language):
#


class TokenTag(Enum):
    keyword = "keyword"
    identifier = "identifier"
    number_literal = "number literal"
    string_literal = "string literal"
    char_literal = "character literal"
    line_comment = "document line comment"
    multi_line_comment = "document multi-line comment"
    punctuator = "punctuator"
    invalid = "invalid"
    eof = "eof"


class NumberTag(Enum):
    int_bin = {"0b", "0B"}
    int_oct = {"0"}
    int_dec = {""}
    int_hex = {"0x", "0X"}
    float_dec = {""}
    float_hex = {"0x", "0X"}


class IntSuffix(Enum):
    width_bit = {"wb", "WB"}
    long_long = {"ll", "LL"}
    long = {"l", "L"}
    unsigned = {"u", "U"}


class FloatSuffix(Enum):
    float = {"f", "F"}
    long_double = {"l", "L"}
    decimal_32 = {"df", "DF"}
    decimal_64 = {"dd", "DD"}
    decimal_128 = {"dl", "DL"}


class EncodingPrefix(Enum):
    utf_8 = "u8"
    utf_16 = "u"
    utf_32 = "U"
    wide_literal = "L"


keywords: list[str] = [
    # Built-in keywords.
    "assert", "println", "NULL",

    # Standard keywords.
    "alignas", "alignof", "auto", "bool", "break", "case", "char",
    "const", "constexpr", "continue", "default", "do", "double",
    "else", "enum", "extern", "false", "float", "for", "goto",
    "if", "inline", "int", "long", "nullptr", "register", "restrict",
    "return", "short", "signed", "sizeof", "static", "static_assert",
    "struct", "switch", "thread_local", "true", "typedef", "typeof",
    "typeof_unqual", "union", "unsigned", "void", "volatile", "while",
    "_Atomic", "_BitInt", "_Complex", "_Decimal128", "_Decimal32",
    "_Decimal64", "_Generic", "_Imaginary", "_Noreturn"
]

puncts_one: set[str] = {
    "[", "]", "(", ")", "{", "}", ".",
    "&", "*", "+", "-", "~", "!",
    "/", "%", "<", ">", "^", "|",
    "?", ":", ";",
    "=", ",",
    "#"
}

puncts_two: set[str] = {
    "->",
    "++", "--",
    "<<", ">>", "<=", ">=", "==", "!=", "&&", "||",
    "::",
    "*=", "/=", "%=", "+=", "-=", "&=", "^=", "|=",
    "##",
    "<:", ":>", "<%", "%>", "%:"
}

puncts_three: set[str] = { "<<=", ">>=", "..." }

puncts_four: set[str] = { "%:%:" }

signs: list[str] = ['-', '+']
exponents: list[str] = ['e', 'E', 'p', 'P']
num_special = ['\'', '.']

simple_escape_seq: set[str] = {
    '\'', '\"', '?', '\\', 'a', 'b', 'f', 'n', 'r', 't', 'v'
}

max_keyword_len: int = max(len(keyword) for keyword in keywords)

class Loc:
    def __init__(self, start: int, end: int) -> None:
        self.start = start
        self.end = end


class Token:
    def __init__(self, tag: TokenTag, loc: Loc) -> None:
        self.tag = tag
        self.loc = loc

        # Error metadata
        self.err: ErrorCode | None = None

        # Number literal metadata
        self.num_base: NumberTag | None = None
        self.int_suffix: set[IntSuffix] | None= None
        self.float_suffix: FloatSuffix | None = None

        # Character and string literal metadata
        self.encoding: EncodingPrefix | None = None

    def assign_error(self, err: ErrorCode) -> Self:
        assert self.tag == TokenTag.invalid

        self.err = err
        return self

    def assign_num_base(self, num_base: NumberTag) -> Self:
        assert self.tag == TokenTag.number_literal
        assert self.num_base is None

        self.num_base = num_base
        return self

    def assign_int_suffix(self, suffix: set[IntSuffix] | None) -> Self:
        assert self.tag == TokenTag.number_literal
        assert self.int_suffix is None

        self.int_suffix = suffix
        return self

    def assign_float_suffix(self, suffix: FloatSuffix | None) -> Self:
        assert self.tag == TokenTag.number_literal
        assert self.float_suffix is None

        self.float_suffix = suffix
        return self

    def assign_encoding(self, encoding: EncodingPrefix | None) -> Self:
        assert (self.tag == TokenTag.char_literal or
                self.tag == TokenTag.string_literal)

        self.encoding = encoding
        return self


class Tokenizer:
    def __init__(self, buffer: str) -> None:
        self.index = 0
        self.buffer = buffer

        # Ensure all line splices were removed during translation
        # phase 2.
        assert "\\\n" not in self.buffer

    def peek(self) -> str:
        if self.index >= len(self.buffer):
            return '\0'

        return self.buffer[self.index]

    def peek_nth(self, offset: int) -> str:
        assert offset >= 0

        if self.index + offset >= len(self.buffer):
            return '\0'

        return self.buffer[self.index + offset]

    def peek_many(self, length: int) -> str:
        assert length > 0

        start = self.index
        end = min(self.index + length, len(self.buffer))

        return self.buffer[start:end]

    def fetch(self) -> str:
        char = self.peek()
        self.index += 1

        return char

    def fetch_many(self, length: int) -> str:
        assert length > 0

        string = self.peek_many(length)
        self.index += length

        return string

    def match_prefix(self, prefix: str) -> bool:
        if self.peek_many(len(prefix)) == prefix:
            self.fetch_many(len(prefix))
            return True

        return False

    def expect(self, expected_char: str) -> None:
        char = self.fetch()
        assert char == expected_char

    def expect_many(self, expected_string: str) -> None:
        string = self.fetch_many(len(expected_string))
        assert string == expected_string

    def expect_one_of(self, expected_options: list[str]) -> None:
        for expected_string in expected_options:
            if self.match_prefix(expected_string):
                return

        assert False

    def pos(self) -> int:
        return self.index

    def end(self) -> int:
        return len(self.buffer)

    def rewind(self, pos: int) -> None:
        assert self.index >= pos >= 0
        self.index = pos

    def encoding_prefix(self) -> EncodingPrefix | None:
        for member in EncodingPrefix:
            if self.match_prefix(member.value):
                return member

        return None

    def has_int_suffix(self, suffix: IntSuffix) -> bool:
        for variation in suffix.value:
            if self.match_prefix(variation):
                return True

        return False

    def int_suffix(self) -> set[IntSuffix]:
        combi: set[IntSuffix] = set()
        unsigned = IntSuffix.unsigned

        if self.has_int_suffix(unsigned):
            combi.add(unsigned)

        for member in IntSuffix:
            if member != unsigned and self.has_int_suffix(member):
                combi.add(member)
                break

        if unsigned not in combi and self.has_int_suffix(unsigned):
            combi.add(unsigned)

        return combi

    def float_suffix(self) -> FloatSuffix | None:
        for member in FloatSuffix:
            for suffix in member.value:
                if self.match_prefix(suffix):
                    return member

        return None

    def invalid(self, start: int, err: ErrorCode) -> Token:
        while self.peek() != '\n' and self.peek() != '\0':
            self.fetch()

        loc = Loc(start, self.pos())
        return Token(TokenTag.invalid, loc).assign_error(err)

    def line_comment(self) -> Token:
        start = self.pos()

        self.expect_many("//")

        while self.peek() != '\n' and self.peek() != '\0':
            self.fetch()

        return Token(TokenTag.line_comment, Loc(start, self.pos()))

    def multi_line_comment(self) -> Token:
        start = self.pos()

        self.expect_many("/*")

        while True:
            if self.peek() == '\0':
                return self.invalid(start, ErrorCode.E0001)

            if self.peek() == '*':
                self.fetch()

                if self.peek() == '/':
                    self.fetch()
                    break

            self.fetch()

        return Token(TokenTag.multi_line_comment, Loc(start, self.pos()))

    def has_encoding_prefix(self, seq_start: str) -> bool:
        for member in EncodingPrefix:
            prefix = member.value + seq_start

            if prefix == self.peek_many(len(prefix)):
                return True

        return False

    def has_char_prefix(self) -> bool:
        return self.peek() == '\'' or self.has_encoding_prefix('\'')

    def has_string_prefix(self) -> bool:
        return self.peek() == '\"' or self.has_encoding_prefix('\"')

    def universal_character_name(self) -> ErrorCode | None:
        self.expect('\\')

        length = 4 if self.peek() == 'u' else 8
        self.expect_one_of(["u", "U"])

        for _ in range(length):
            if not is_hex_digit(self.peek()):
                return ErrorCode.E0022

            self.fetch()

        return None

    def octal_escape_sequence(self) -> ErrorCode | None:
        self.expect('\\')

        if not is_oct_digit(self.peek()):
            return ErrorCode.E0023

        for _ in range(3):
            if not is_oct_digit(self.peek()):
                break

            self.fetch()

        return None

    def hex_escape_sequence(self) -> ErrorCode | None:
        self.expect_many("\\x")

        if not is_hex_digit(self.peek()):
            return ErrorCode.E0020

        while is_hex_digit(self.peek()):
            self.fetch()

        return None

    def simple_escape_sequence(self) -> ErrorCode | None:
        self.expect('\\')

        if self.peek() not in simple_escape_seq:
            return ErrorCode.E0021

        self.fetch()
        return None

    def dec_digit_sequence(self) -> ErrorCode | None:
        if self.peek() == '\'':
            return ErrorCode.E0017

        prev = '\0'

        while is_dec_digit(self.peek()) or self.peek() == '\'':
            if self.peek() == '\'' and prev == '\'':
                return ErrorCode.E0007

            prev = self.fetch()

        if prev == '\'':
            return ErrorCode.E0008

    def hex_digit_sequence(self) -> ErrorCode | None:
        if self.peek() == '\'':
            return ErrorCode.E0017

        prev = '\0'

        while is_hex_digit(self.peek()) or self.peek() == '\'':
            if self.peek() == '\'' and prev == '\'':
                return ErrorCode.E0007

            prev = self.fetch()

        if prev == '\'':
            return ErrorCode.E0008

    def escape_sequence(self) -> ErrorCode | None:
        assert self.peek() == '\\'

        if self.peek_nth(1).isdigit():
            return self.octal_escape_sequence()

        if self.peek_nth(1) == 'x':
            return self.hex_escape_sequence()

        if self.peek_nth(1) == 'u' or self.peek_nth(1) == 'U':
            return self.universal_character_name()

        return self.simple_escape_sequence()

    def char_literal(self) -> Token:
        start = self.pos()

        encoding: EncodingPrefix | None = self.encoding_prefix()
        self.expect('\'')

        if self.peek() == '\'':
            return self.invalid(start, ErrorCode.E0026)

        while self.peek() != '\'':
            if self.peek() == '\0':
                return self.invalid(start, ErrorCode.E0002)

            if self.peek() == '\n':
                return self.invalid(start, ErrorCode.E0004)

            if self.peek() != '\\':
                self.fetch()
                continue

            if self.peek_nth(1) == '\0':
                return self.invalid(start, ErrorCode.E0002)

            if self.peek_nth(1) == '\n':
                return self.invalid(start, ErrorCode.E0004)

            err: ErrorCode | None = self.escape_sequence()
            if err is not None:
                return self.invalid(start, err)

        self.expect('\'')

        return Token(TokenTag.char_literal, Loc(start, self.pos())) \
                .assign_encoding(encoding)

    def string_literal(self) -> Token:
        start = self.pos()

        encoding: EncodingPrefix | None = self.encoding_prefix()
        self.expect('\"')

        while self.peek() != '\"':
            if self.peek() == '\0':
                return self.invalid(start, ErrorCode.E0003)

            if self.peek() == '\n':
                return self.invalid(start, ErrorCode.E0005)

            if self.peek() != '\\':
                self.fetch()
                continue

            if self.peek_nth(1) == '\0':
                return self.invalid(start, ErrorCode.E0003)

            if self.peek_nth(1) == '\n':
                return self.invalid(start, ErrorCode.E0005)

            err: ErrorCode | None = self.escape_sequence()
            if err is not None:
                return self.invalid(start, err)

        self.expect('\"')

        return Token(TokenTag.string_literal, Loc(start, self.pos())) \
                .assign_encoding(encoding)

    def int_bin(self) -> Token:
        start = self.pos()

        self.expect_one_of(["0b", "0B"])

        if self.peek() == '\'':
            return self.invalid(start, ErrorCode.E0006)

        if self.peek() == '\0' or self.peek().isspace():
            return self.invalid(start, ErrorCode.E0009)

        if not is_bin_digit(self.peek()):
            err = ErrorCode.E0013

            if is_hex_digit(self.peek()):
                err = ErrorCode.E0011

            return self.invalid(start, err)

        prev = self.fetch()

        while is_bin_digit(self.peek()) or self.peek() == '\'':
            if self.peek() == '\'' and prev == '\'':
                return self.invalid(start, ErrorCode.E0007)

            prev = self.fetch()

        if prev == '\'':
            return self.invalid(start, ErrorCode.E0008)

        suffix = self.int_suffix()

        return Token(TokenTag.number_literal, Loc(start, self.pos())) \
                .assign_num_base(NumberTag.int_bin) \
                .assign_int_suffix(suffix)

    def int_oct(self) -> Token:
        start = self.pos()
        self.expect('0')

        if self.peek() == '\'':
            return self.invalid(start, ErrorCode.E0006)

        if self.peek() == '\0' or self.peek().isspace():
            return self.invalid(start, ErrorCode.E0009)

        if not is_oct_digit(self.peek()):
            err = ErrorCode.E0013

            if is_hex_digit(self.peek()):
                err = ErrorCode.E0011

            return self.invalid(start, err)

        prev = self.fetch()

        while is_oct_digit(self.peek()) or self.peek() == '\'':
            if self.peek() == '\'' and prev == '\'':
                return self.invalid(start, ErrorCode.E0007)

            prev = self.fetch()

        if prev == '\'':
            return self.invalid(start, ErrorCode.E0008)

        suffix = self.int_suffix()

        return Token(TokenTag.number_literal, Loc(start, self.pos())) \
                .assign_num_base(NumberTag.int_oct) \
                .assign_int_suffix(suffix)

    def int_dec(self) -> Token:
        start = self.pos()

        if not is_dec_digit(self.peek()):
            err = ErrorCode.E0013

            if is_hex_digit(self.peek()):
                err = ErrorCode.E0011

            return self.invalid(start, err)

        assert self.peek_nth(0) != '0' or not self.peek_nth(1).isdigit()

        err: ErrorCode | None = self.dec_digit_sequence()
        if err is not None:
            return self.invalid(start, err)

        suffix = self.int_suffix()

        return Token(TokenTag.number_literal, Loc(start, self.pos())) \
                .assign_num_base(NumberTag.int_dec) \
                .assign_int_suffix(suffix)

    def int_hex(self) -> Token:
        start = self.pos()
        self.expect_one_of(["0x", "0X"])

        if self.peek() == '\'':
            return self.invalid(start, ErrorCode.E0006)

        if self.peek() == '\0' or self.peek().isspace():
            return self.invalid(start, ErrorCode.E0009)

        if not is_hex_digit(self.peek()):
            return self.invalid(start, ErrorCode.E0013)

        err: ErrorCode | None = self.hex_digit_sequence()
        if err is not None:
            return self.invalid(start, err)

        suffix = self.int_suffix()

        return Token(TokenTag.number_literal, Loc(start, self.pos())) \
                .assign_num_base(NumberTag.int_hex) \
                .assign_int_suffix(suffix)

    def float_dec(self) -> Token:
        start = self.pos()
        has_digit = has_dot_or_exp = False

        if not (is_dec_digit(self.peek()) or self.peek() == '.'):
            return self.invalid(start, ErrorCode.E0013)

        has_digit |= is_dec_digit(self.peek())

        err: ErrorCode | None = self.dec_digit_sequence()
        if err is not None:
            return self.invalid(start, err)

        if self.peek() == '.':
            has_dot_or_exp = True
            self.fetch()

        has_digit |= is_dec_digit(self.peek())

        err: ErrorCode | None = self.dec_digit_sequence()
        if err is not None:
            return self.invalid(start, err)

        if self.peek().lower() == 'e':
            has_dot_or_exp = True
            self.fetch()

            if self.peek() == '+' or self.peek() == '-':
                self.fetch()

            if not is_dec_digit(self.peek()):
                return self.invalid(start, ErrorCode.E0016)

            if (err := self.dec_digit_sequence()) is not None:
                return self.invalid(start, err)

        assert has_digit
        assert has_dot_or_exp

        suffix: FloatSuffix | None = self.float_suffix()

        return Token(TokenTag.number_literal, Loc(start, self.pos())) \
                .assign_num_base(NumberTag.float_dec) \
                .assign_float_suffix(suffix)

    def float_hex(self) -> Token:
        start = self.pos()
        has_digit = False

        self.expect_one_of(["0x", "0X"])

        if not (is_hex_digit(self.peek()) or self.peek() == '.'):
            return self.invalid(start, ErrorCode.E0013)

        has_digit |= is_hex_digit(self.peek())

        err: ErrorCode | None = self.hex_digit_sequence()
        if err is not None:
            return self.invalid(start, err)

        if self.peek() == '.':
            self.fetch()

        has_digit |= is_hex_digit(self.peek())

        err: ErrorCode | None = self.hex_digit_sequence()
        if err is not None:
            return self.invalid(start, err)

        if self.peek().lower() != 'p':
            return self.invalid(start, ErrorCode.E0018)

        self.fetch()
        if self.peek() == '+' or self.peek() == '-':
            self.fetch()

        if not is_dec_digit(self.peek()):
            return self.invalid(start, ErrorCode.E0016)

        err: ErrorCode | None = self.dec_digit_sequence()
        if err is not None:
            return self.invalid(start, err)

        if not has_digit:
            return self.invalid(start, ErrorCode.E0024)

        suffix: FloatSuffix | None = self.float_suffix()

        return Token(TokenTag.number_literal, Loc(start, self.pos())) \
                .assign_num_base(NumberTag.float_hex) \
                .assign_float_suffix(suffix)

    def number_literal_stats(self) -> tuple[int, bool, bool, bool]:
        start = self.pos()

        prev = '\0'
        has_dot = has_exp_p = has_exp_e = False

        while True:
            ch = self.peek()

            has_dot |= ch == '.'
            has_exp_e |= ch == 'e'
            has_exp_p |= ch == 'p'

            if ch.isalnum() or ch in num_special:
                prev = self.fetch()

            elif ch in signs and (prev in exponents or prev in signs):
                prev = self.fetch()

            else:
                break

        end = self.pos()
        self.rewind(start)

        return (end, has_dot, has_exp_e, has_exp_p)

    def number_literal(self) -> Token:
        start = self.pos()
        assert self.peek().isdigit() or \
              (self.peek_nth(0) == '.' and self.peek_nth(1).isdigit())

        end, has_dot, has_exp_e, has_exp_p = self.number_literal_stats()

        token: Token | None = None
        is_float = has_dot or has_exp_e or has_exp_p

        if self.peek_many(2).lower() == "0b":
            if has_dot:
                token = self.invalid(start, ErrorCode.E0019)
            else:
                token = self.int_bin()

        elif self.peek_many(2).lower() == "0x":
            if has_dot or has_exp_p:
                token = self.float_hex()
            else:
                token = self.int_hex()

        elif self.peek() == '0' and not is_float and end - start > 1:
            token = self.int_oct()

        else:
            if has_exp_p:
                token = self.invalid(start, ErrorCode.E0025)

            elif has_dot or has_exp_e:
                token = self.float_dec()
            else:
                token = self.int_dec()

        assert token is not None

        if token.tag == TokenTag.invalid:
            return token

        if token.loc.end != end:
            return self.invalid(start, ErrorCode.E0014)

        return token

    def keyword_or_identifier(self) -> Token:
        start = self.pos()

        while True:
            if is_letter_or_num(self.peek()) or self.peek() == '_':
                self.fetch()

            elif self.peek_many(2).lower() == "\\u":
                err: ErrorCode | None = self.universal_character_name()

                if err is not None:
                    return self.invalid(start, err)
            else:
                break

        loc = Loc(start, self.pos())
        seq_len = loc.end - loc.start

        if seq_len <= max_keyword_len and \
           self.buffer[loc.start:loc.end] in keywords:
            return Token(TokenTag.keyword, loc)
        else:
            return Token(TokenTag.identifier, loc)

    def punctuator(self) -> Token | None:
        puncts: list[tuple[int, set[str]]] = [
            (4, puncts_four),
            (3, puncts_three),
            (2, puncts_two),
            (1, puncts_one)
        ]

        for (length, punct_table) in puncts:
            if self.peek_many(length) in punct_table:
                start, _ = self.pos(), self.fetch_many(length)

                return Token(TokenTag.punctuator, Loc(start, self.pos()))

        return None

    def whitespace(self) -> None:
        while self.peek().isspace():
            self.fetch()

    def next(self) -> Token:
        self.whitespace()

        if self.peek() == '\0':
            assert self.pos() == self.end()
            return Token(TokenTag.eof, Loc(self.pos(), self.pos()))

        if self.peek_many(2) == "//":
            return self.line_comment()

        if self.peek_many(2) == "/*":
            return self.multi_line_comment()

        if self.has_char_prefix():
            return self.char_literal()

        if self.has_string_prefix():
            return self.string_literal()

        if self.peek().isdigit():
            return self.number_literal()

        if self.peek_nth(0) == '.' and self.peek_nth(1).isdigit():
            return self.number_literal()

        if self.peek().isalpha() or self.peek() == '_':
            return self.keyword_or_identifier()

        if self.peek_many(2).lower() == "\\u":
            return self.keyword_or_identifier()

        punct: Token | None = self.punctuator()

        if punct is None:
            return self.invalid(self.pos(), ErrorCode.E0015)

        return punct


def test_token(token_string: str, tag: TokenTag) -> None:
    token = Tokenizer(token_string).next()
    assert token.tag == tag
    assert token.loc.start == 0
    assert token.loc.end == len(token_string)


def test_token_retrieve(tok: Tokenizer, tag: TokenTag, target: str) -> None:
    i = tok.pos()

    if len(target) == 0:
        i = len(tok.buffer)
        assert tag == TokenTag.eof
    else:
        i = tok.buffer.find(target, i)
        assert i != -1, f"Token \"{target}\" not found."

    token = tok.next()
    assert token.tag == tag
    assert token.loc.start == i
    assert token.loc.end == i + len(target)


def test_keywords() -> None:
    tag = TokenTag.keyword

    # Test: Recognition of built-in keywords.
    test_token("assert", tag)
    test_token("println", tag)
    test_token("NULL", tag)

    # Test: Recognition of all keywords from C23 language standard.
    test_token("alignas", tag)
    test_token("alignof", tag)
    test_token("auto", tag)
    test_token("bool", tag)
    test_token("break", tag)
    test_token("case", tag)
    test_token("char", tag)
    test_token("const", tag)
    test_token("constexpr", tag)
    test_token("continue", tag)
    test_token("default", tag)
    test_token("do", tag)
    test_token("double", tag)
    test_token("else", tag)
    test_token("enum", tag)
    test_token("extern", tag)
    test_token("false", tag)
    test_token("float", tag)
    test_token("for", tag)
    test_token("goto", tag)
    test_token("if", tag)
    test_token("inline", tag)
    test_token("int", tag)
    test_token("long", tag)
    test_token("nullptr", tag)
    test_token("register", tag)
    test_token("restrict", tag)
    test_token("return", tag)
    test_token("short", tag)
    test_token("signed", tag)
    test_token("sizeof", tag)
    test_token("static", tag)
    test_token("static_assert", tag)
    test_token("struct", tag)
    test_token("switch", tag)
    test_token("thread_local", tag)
    test_token("true", tag)
    test_token("typedef", tag)
    test_token("typeof", tag)
    test_token("typeof_unqual", tag)
    test_token("union", tag)
    test_token("unsigned", tag)
    test_token("void", tag)
    test_token("volatile", tag)
    test_token("while", tag)
    test_token("_Atomic", tag)
    test_token("_BitInt", tag)
    test_token("_Complex", tag)
    test_token("_Decimal128", tag)
    test_token("_Decimal32", tag)
    test_token("_Decimal64", tag)
    test_token("_Generic", tag)
    test_token("_Imaginary", tag)
    test_token("_Noreturn", tag)

    # Test: Recognition of keywords with leading whitespace.
    tok = Tokenizer("    \t\n\rtrue")
    test_token_retrieve(tok, tag, "true")

    tok = Tokenizer("    \t\n\rfalse")
    test_token_retrieve(tok, tag, "false")

    # Test: Recognition of multiple keywords in a single buffer.
    tok = Tokenizer("    true    false    nullptr    ")
    test_token_retrieve(tok, tag, "true")
    test_token_retrieve(tok, tag, "false")
    test_token_retrieve(tok, tag, "nullptr")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_identifier_success() -> None:
    tag = TokenTag.identifier

    # Test: Recognition of common short-form identifiers.
    test_token("a", tag)
    test_token("b", tag)
    test_token("x", tag)
    test_token("y", tag)

    test_token("foo", tag)
    test_token("bar", tag)
    test_token("baz", tag)

    # Test: Recognition of multi-word identifiers with snake_case.
    test_token("buffer_size", tag)
    test_token("row_length", tag)

    test_token("close_or_warn", tag)
    test_token("unlink_if_exists", tag)

    # Test: Recognition of identifier grammar characters, excluding
    #       universal character names.
    string = ("_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
              "0123456789")

    test_token(string, tag)

    # Test: Recognition of identifiers that contain keywords.
    test_token("_true", tag)
    test_token("_false", tag)

    test_token("_if", tag)
    test_token("_while", tag)

    test_token("truefalse", tag)
    test_token("whiletrue", tag)

    test_token("true_false", tag)
    test_token("while_true", tag)

    test_token("__Atomic", tag)
    test_token("_Atomic_", tag)
    test_token("_Atomicly", tag)

    # Test: Recognition of 16-bit universal character names
    #       in identifiers.
    test_token("\\u0000", tag)
    test_token("\\uffff", tag)
    test_token("\\uFFFF", tag)
    test_token("\\uFfFf", tag)

    test_token("\\u0123", tag)
    test_token("\\u4567", tag)
    test_token("\\u89ab", tag)
    test_token("\\ucdef", tag)
    test_token("\\uABCD", tag)
    test_token("\\uEF00", tag)

    test_token("caf\\u00E9", tag)   # café
    test_token("ma\\u00F1ana", tag) # mañana

    # Test: Recognition of 32-bit universal character names
    #       in identifiers.
    test_token("\\U00000000", tag)
    test_token("\\Uffffffff", tag)
    test_token("\\UFFFFFFFF", tag)
    test_token("\\uFfFfFffF", tag)

    test_token("\\U012345678", tag)
    test_token("\\U9abcdefAB", tag)
    test_token("\\UCDEF00000", tag)

    test_token("smile_\\U0001F600", tag) # smile_😀
    test_token("music_\\U0001D11E", tag) # music_𝄞

    # Test: Recognition of identifiers with leading whitespace.
    tok = Tokenizer("    \t\n\rarray")
    test_token_retrieve(tok, tag, "array")

    tok = Tokenizer("    \t\n\r_Atomic_")
    test_token_retrieve(tok, tag, "_Atomic_")

    tok = Tokenizer("    \t\n\r\\u0000")
    test_token_retrieve(tok, tag, "\\u0000")

    tok = Tokenizer("    \t\n\r\\U00000000")
    test_token_retrieve(tok, tag, "\\U00000000")

    # Test: Recognition of multiple identifiers in a single buffer.
    buffer = "    array    _Atomic_    \\u0000    \\U00000000    a0"

    tok = Tokenizer(buffer)
    test_token_retrieve(tok, tag, "array")
    test_token_retrieve(tok, tag, "_Atomic_")
    test_token_retrieve(tok, tag, "\\u0000")
    test_token_retrieve(tok, tag, "\\U00000000")
    test_token_retrieve(tok, tag, "a0")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_identifier_failure() -> None:
    tag = TokenTag.invalid

    # Test: Detection of incomplete 4-hex-digit universal character
    #       names in identifiers.
    test_token("\\u", tag)
    test_token("\\uf", tag)
    test_token("\\uff", tag)
    test_token("\\ufff", tag)

    test_token("caf\\u00E", tag)  # café
    test_token("se\\u00For", tag) # señor

    # Test: Detection of invalid format of 4-hex-digit universal
    #       character names in identifiers.
    test_token("\\uΩ", tag)
    test_token("\\u000x", tag)
    test_token("\\uu0000", tag)

    # Test: Detection of incomplete 8-hex-digit universal character
    #       names in identifiers.
    test_token("\\Uf", tag)
    test_token("\\Uff", tag)
    test_token("\\Ufff", tag)
    test_token("\\Uffff", tag)
    test_token("\\Ufffff", tag)
    test_token("\\Uffffff", tag)
    test_token("\\Ufffffff", tag)

    # Test: Detection of invalid format of 8-hex-digit universal
    #       character names in identifiers.
    test_token("\\U0000000x", tag)
    test_token("\\UU0000000", tag)

    test_token("smile_\\U0001F60", tag) # smile_😀
    test_token("music_\\U0001D11", tag) # music_𝄞

    # Test: Detection of invalid characters breaking an identifier.
    tok = Tokenizer("iden$")
    test_token_retrieve(tok, TokenTag.identifier, "iden")
    test_token_retrieve(tok, TokenTag.invalid, "$")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("email@address")
    test_token_retrieve(tok, TokenTag.identifier, "email")
    test_token_retrieve(tok, TokenTag.invalid, "@address")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_punctuators() -> None:
    tag = TokenTag.punctuator

    # Test: Recognition of all punctuators from C23 language standard.
    test_token("[", tag)
    test_token("]", tag)
    test_token("(", tag)
    test_token(")", tag)
    test_token("{", tag)
    test_token("}", tag)
    test_token(".", tag)
    test_token("->", tag)

    test_token("++", tag)
    test_token("--", tag)
    test_token("&", tag)
    test_token("*", tag)
    test_token("+", tag)
    test_token("-", tag)
    test_token("~", tag)
    test_token("!", tag)

    test_token("/", tag)
    test_token("%", tag)
    test_token("<<", tag)
    test_token(">>", tag)
    test_token("<", tag)
    test_token(">", tag)
    test_token("<=", tag)
    test_token(">=", tag)
    test_token("==", tag)
    test_token("!=", tag)
    test_token("^", tag)
    test_token("|", tag)
    test_token("&&", tag)
    test_token("||", tag)

    test_token("?", tag)
    test_token(":", tag)
    test_token("::", tag)
    test_token(";", tag)
    test_token("...", tag)

    test_token("=", tag)
    test_token("*=", tag)
    test_token("/=", tag)
    test_token("%=", tag)
    test_token("+=", tag)
    test_token("-=", tag)
    test_token("<<=", tag)
    test_token(">>=", tag)
    test_token("&=", tag)
    test_token("^=", tag)
    test_token("|=", tag)

    test_token(",", tag)
    test_token("#", tag)
    test_token("##", tag)

    test_token("<:", tag)
    test_token(":>", tag)
    test_token("<%", tag)
    test_token("%>", tag)
    test_token("%:", tag)
    test_token("%:%:", tag)

    # Test: Recognition of punctuator with leading whitespace.
    tok = Tokenizer("    \t\r\n]")
    test_token_retrieve(tok, tag, "]")

    tok = Tokenizer("    \t\r\n)")
    test_token_retrieve(tok, tag, ")")

    tok = Tokenizer("    \t\r\n}")
    test_token_retrieve(tok, tag, "}")

    # Test: Recognition of multiple punctuators in a single buffer.
    tok = Tokenizer("[({})]")
    test_token_retrieve(tok, tag, "[")
    test_token_retrieve(tok, tag, "(")
    test_token_retrieve(tok, tag, "{")
    test_token_retrieve(tok, tag, "}")
    test_token_retrieve(tok, tag, ")")
    test_token_retrieve(tok, tag, "]")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("+++")
    test_token_retrieve(tok, tag, "++")
    test_token_retrieve(tok, tag, "+")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("=====")
    test_token_retrieve(tok, tag, "==")
    test_token_retrieve(tok, tag, "==")
    test_token_retrieve(tok, tag, "=")
    test_token_retrieve(tok, TokenTag.eof, "")

    # Test: Ignoration of whitespace between punctuators.
    tok = Tokenizer("    ==    ==    =    ")
    test_token_retrieve(tok, tag, "==")
    test_token_retrieve(tok, tag, "==")
    test_token_retrieve(tok, tag, "=")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("    =    =    =    ")
    test_token_retrieve(tok, tag, "=")
    test_token_retrieve(tok, tag, "=")
    test_token_retrieve(tok, tag, "=")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("    ++    +    ")
    test_token_retrieve(tok, tag, "++")
    test_token_retrieve(tok, tag, "+")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("    +    ++    ")
    test_token_retrieve(tok, tag, "+")
    test_token_retrieve(tok, tag, "++")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("    +    +    +    ")
    test_token_retrieve(tok, tag, "+")
    test_token_retrieve(tok, tag, "+")
    test_token_retrieve(tok, tag, "+")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("--> <--")
    test_token_retrieve(tok, tag, "--")
    test_token_retrieve(tok, tag, ">")
    test_token_retrieve(tok, tag, "<")
    test_token_retrieve(tok, tag, "--")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_int_literals_suffix_success(num_tag: NumberTag) -> None:
    tag = TokenTag.number_literal

    if num_tag == NumberTag.int_bin:
        prefix = "0b"

    elif num_tag == NumberTag.int_oct:
        prefix = "0"

    elif num_tag == NumberTag.int_hex:
        prefix = "0x"

    else:
        prefix = ""
        assert num_tag == NumberTag.int_dec

    # Test: Recognition of basic number suffixes.
    test_token(f"{prefix}1u", tag)
    test_token(f"{prefix}1U", tag)
    test_token(f"{prefix}1l", tag)
    test_token(f"{prefix}1L", tag)
    test_token(f"{prefix}1ll", tag)
    test_token(f"{prefix}1LL", tag)
    test_token(f"{prefix}1wb", tag)
    test_token(f"{prefix}1WB", tag)

    # Test: Recognition of combined unsigned suffixes.
    test_token(f"{prefix}1ul", tag)
    test_token(f"{prefix}1uL", tag)
    test_token(f"{prefix}1ull", tag)
    test_token(f"{prefix}1uLL", tag)

    test_token(f"{prefix}1Ul", tag)
    test_token(f"{prefix}1UL", tag)
    test_token(f"{prefix}1Ull", tag)
    test_token(f"{prefix}1ULL", tag)

    test_token(f"{prefix}1lu", tag)
    test_token(f"{prefix}1lU", tag)

    test_token(f"{prefix}1Lu", tag)
    test_token(f"{prefix}1LU", tag)

    test_token(f"{prefix}1llu", tag)
    test_token(f"{prefix}1llU", tag)

    test_token(f"{prefix}1LLu", tag)
    test_token(f"{prefix}1LLU", tag)

    test_token(f"{prefix}1wbu", tag)
    test_token(f"{prefix}1wbU", tag)

    test_token(f"{prefix}1WBu", tag)
    test_token(f"{prefix}1WBU", tag)


def test_int_literals_suffix_failure(num_tag: NumberTag) -> None:
    tag = TokenTag.invalid

    if num_tag == NumberTag.int_bin:
        prefix = "0b"

    elif num_tag == NumberTag.int_oct:
        prefix = "0"

    elif num_tag == NumberTag.int_hex:
        prefix = "0x"

    else:
        prefix = ""
        assert num_tag == NumberTag.int_dec

    # Test: Detection of invalid float suffixes on non-decimal or
    #       non-hexadecimal number formats.
    if num_tag == NumberTag.int_bin or num_tag == NumberTag.int_oct:
        test_token(f"{prefix}1f", tag)
        test_token(f"{prefix}1F", tag)
        test_token(f"{prefix}1df", tag)
        test_token(f"{prefix}1dd", tag)
        test_token(f"{prefix}1dl", tag)
        test_token(f"{prefix}1DF", tag)
        test_token(f"{prefix}1DD", tag)
        test_token(f"{prefix}1DL", tag)

    # Test: Detection of duplicated unsigned suffixes.
    test_token(f"{prefix}1uu", tag)
    test_token(f"{prefix}1uU", tag)

    test_token(f"{prefix}1Uu", tag)
    test_token(f"{prefix}1UU", tag)

    test_token(f"{prefix}1luU", tag)
    test_token(f"{prefix}1lUu", tag)

    test_token(f"{prefix}1LuU", tag)
    test_token(f"{prefix}1LUu", tag)

    test_token(f"{prefix}1lluU", tag)
    test_token(f"{prefix}1llUu", tag)

    test_token(f"{prefix}1LLuU", tag)
    test_token(f"{prefix}1LLUu", tag)

    # Test: Detection of invalid suffix combinations.
    test_token(f"{prefix}1Ll", tag)
    test_token(f"{prefix}1lL", tag)

    test_token(f"{prefix}1lll", tag)
    test_token(f"{prefix}1llL", tag)
    test_token(f"{prefix}1lLl", tag)
    test_token(f"{prefix}1Lll", tag)

    test_token(f"{prefix}1llwb", tag)
    test_token(f"{prefix}1LLwb", tag)

    test_token(f"{prefix}1llWB", tag)
    test_token(f"{prefix}1LLWB", tag)

    test_token(f"{prefix}1wbuU", tag)
    test_token(f"{prefix}1WBUu", tag)

    test_token(f"{prefix}1wbll", tag)
    test_token(f"{prefix}1wbLL", tag)

    test_token(f"{prefix}1WBll", tag)
    test_token(f"{prefix}1WBLL", tag)


def test_float_literals_suffix_failure(num_tag: NumberTag) -> None:
    tag = TokenTag.invalid

    if num_tag == NumberTag.float_hex:
        prefix = "0x"
        exponent = "p"
    else:
        prefix = ""
        exponent = "e"
        assert num_tag == NumberTag.float_dec

    # Test: Detection of invalid combinations of upper and lower case
    #       in float suffix format.
    test_token(f"{prefix}0.0dF", tag)
    test_token(f"{prefix}0.0Df", tag)

    test_token(f"{prefix}0.0dL", tag)
    test_token(f"{prefix}0.0Dl", tag)

    test_token(f"{prefix}0.0dD", tag)
    test_token(f"{prefix}0.0Dd", tag)

    # Test: Detection of multiple suffixes in single float literal
    #       - for float suffix 'f'.
    test_token(f"{prefix}0.0ff", tag)
    test_token(f"{prefix}0.0Ff", tag)

    test_token(f"{prefix}0.0fF", tag)
    test_token(f"{prefix}0.0FF", tag)

    test_token(f"{prefix}0.0fl", tag)
    test_token(f"{prefix}0.0Fl", tag)

    test_token(f"{prefix}0.0fL", tag)
    test_token(f"{prefix}0.0FL", tag)

    test_token(f"{prefix}0.0fdf", tag)
    test_token(f"{prefix}0.0Fdf", tag)

    test_token(f"{prefix}0.0fDF", tag)
    test_token(f"{prefix}0.0FDF", tag)

    test_token(f"{prefix}0.0fdd", tag)
    test_token(f"{prefix}0.0Fdd", tag)

    test_token(f"{prefix}0.0fDD", tag)
    test_token(f"{prefix}0.0FDD", tag)

    test_token(f"{prefix}0.0fdl", tag)
    test_token(f"{prefix}0.0Fdl", tag)

    test_token(f"{prefix}0.0fDL", tag)
    test_token(f"{prefix}0.0FDL", tag)

    # Test: Detection of multiple suffixes in single float literal
    #       - for float suffix 'l'.
    test_token(f"{prefix}0.0lf", tag)
    test_token(f"{prefix}0.0Lf", tag)

    test_token(f"{prefix}0.0lF", tag)
    test_token(f"{prefix}0.0LF", tag)

    test_token(f"{prefix}0.0ll", tag)
    test_token(f"{prefix}0.0Ll", tag)

    test_token(f"{prefix}0.0lL", tag)
    test_token(f"{prefix}0.0LL", tag)

    test_token(f"{prefix}0.0ldf", tag)
    test_token(f"{prefix}0.0Ldf", tag)

    test_token(f"{prefix}0.0lDF", tag)
    test_token(f"{prefix}0.0LDF", tag)

    test_token(f"{prefix}0.0ldd", tag)
    test_token(f"{prefix}0.0Ldd", tag)

    test_token(f"{prefix}0.0lDD", tag)
    test_token(f"{prefix}0.0LDD", tag)

    test_token(f"{prefix}0.0ldl", tag)
    test_token(f"{prefix}0.0Ldl", tag)

    test_token(f"{prefix}0.0lDL", tag)
    test_token(f"{prefix}0.0LDL", tag)

    # Test: Detection of multiple suffixes in single float literal
    #       - for float suffix 'df'.
    test_token(f"{prefix}0.0dff", tag)
    test_token(f"{prefix}0.0DFf", tag)

    test_token(f"{prefix}0.0dfF", tag)
    test_token(f"{prefix}0.0DFF", tag)

    test_token(f"{prefix}0.0dfl", tag)
    test_token(f"{prefix}0.0DFl", tag)

    test_token(f"{prefix}0.0dfL", tag)
    test_token(f"{prefix}0.0DFL", tag)

    test_token(f"{prefix}0.0dfdf", tag)
    test_token(f"{prefix}0.0DFdf", tag)

    test_token(f"{prefix}0.0dfDF", tag)
    test_token(f"{prefix}0.0DFDF", tag)

    test_token(f"{prefix}0.0dfdd", tag)
    test_token(f"{prefix}0.0DFdd", tag)

    test_token(f"{prefix}0.0dfDD", tag)
    test_token(f"{prefix}0.0DFDD", tag)

    test_token(f"{prefix}0.0dfdl", tag)
    test_token(f"{prefix}0.0DFdl", tag)

    test_token(f"{prefix}0.0dfDL", tag)
    test_token(f"{prefix}0.0DFDL", tag)

    # Test: Detection of multiple suffixes in single float literal
    #       - for float suffix 'dd'.
    test_token(f"{prefix}0.0ddf", tag)
    test_token(f"{prefix}0.0DDf", tag)

    test_token(f"{prefix}0.0ddF", tag)
    test_token(f"{prefix}0.0DDF", tag)

    test_token(f"{prefix}0.0ddl", tag)
    test_token(f"{prefix}0.0DDl", tag)

    test_token(f"{prefix}0.0ddL", tag)
    test_token(f"{prefix}0.0DDL", tag)

    test_token(f"{prefix}0.0dddf", tag)
    test_token(f"{prefix}0.0DDdf", tag)

    test_token(f"{prefix}0.0ddDF", tag)
    test_token(f"{prefix}0.0DDDF", tag)

    test_token(f"{prefix}0.0dddd", tag)
    test_token(f"{prefix}0.0DDdd", tag)

    test_token(f"{prefix}0.0ddDD", tag)
    test_token(f"{prefix}0.0DDDD", tag)

    test_token(f"{prefix}0.0dddl", tag)
    test_token(f"{prefix}0.0DDdl", tag)

    test_token(f"{prefix}0.0ddDL", tag)
    test_token(f"{prefix}0.0DDDL", tag)

    # Test: Detection of multiple suffixes in single float literal
    #       - for float suffix 'dl'.
    test_token(f"{prefix}0.0dlf", tag)
    test_token(f"{prefix}0.0DLf", tag)

    test_token(f"{prefix}0.0dlF", tag)
    test_token(f"{prefix}0.0DLF", tag)

    test_token(f"{prefix}0.0dll", tag)
    test_token(f"{prefix}0.0DLl", tag)

    test_token(f"{prefix}0.0dlL", tag)
    test_token(f"{prefix}0.0DLL", tag)

    test_token(f"{prefix}0.0dldf", tag)
    test_token(f"{prefix}0.0DLdf", tag)

    test_token(f"{prefix}0.0dlDF", tag)
    test_token(f"{prefix}0.0DLDF", tag)

    test_token(f"{prefix}0.0dldd", tag)
    test_token(f"{prefix}0.0DLdd", tag)

    test_token(f"{prefix}0.0dlDD", tag)
    test_token(f"{prefix}0.0DLDD", tag)

    test_token(f"{prefix}0.0dldl", tag)
    test_token(f"{prefix}0.0DLdl", tag)

    test_token(f"{prefix}0.0dlDL", tag)
    test_token(f"{prefix}0.0DLDL", tag)

    # Test: Detection of invalid character in suffix of float literal.
    test_token(f"{prefix}0.0uf", tag)
    test_token(f"{prefix}0.0ul", tag)
    test_token(f"{prefix}0.0udf", tag)
    test_token(f"{prefix}0.0udd", tag)
    test_token(f"{prefix}0.0udl", tag)

    test_token(f"{prefix}0.0fu", tag)
    test_token(f"{prefix}0.0lu", tag)
    test_token(f"{prefix}0.0dfu", tag)
    test_token(f"{prefix}0.0ddu", tag)
    test_token(f"{prefix}0.0dlu", tag)

    test_token(f"{prefix}0.0Uf", tag)
    test_token(f"{prefix}0.0Ul", tag)
    test_token(f"{prefix}0.0Udf", tag)
    test_token(f"{prefix}0.0Udd", tag)
    test_token(f"{prefix}0.0Udl", tag)

    test_token(f"{prefix}0.0fU", tag)
    test_token(f"{prefix}0.0lU", tag)
    test_token(f"{prefix}0.0dfU", tag)
    test_token(f"{prefix}0.0ddU", tag)
    test_token(f"{prefix}0.0dlU", tag)

    # Test: Detection of invalid separator before suffix of float
    #       literal.
    test_token(f"{prefix}0.0'f", tag)
    test_token(f"{prefix}0.0'F", tag)

    test_token(f"{prefix}0.0'l", tag)
    test_token(f"{prefix}0.0'L", tag)

    test_token(f"{prefix}0.0'df", tag)
    test_token(f"{prefix}0.0'DF", tag)

    test_token(f"{prefix}0.0'dd", tag)
    test_token(f"{prefix}0.0'DD", tag)

    test_token(f"{prefix}0.0'dl", tag)
    test_token(f"{prefix}0.0'DL", tag)

    # Test: Detection of missing exponent sequence before the float
    #       suffix.
    test_token(f"{prefix}0.0{exponent}f", tag)
    test_token(f"{prefix}0.0{exponent}F", tag)

    test_token(f"{prefix}0.0{exponent}f", tag)
    test_token(f"{prefix}0.0{exponent}F", tag)

    # Test: Detection of invalid specific decimal float literals with
    #       non-terminal suffixes.
    if num_tag == NumberTag.float_dec:
        test_token("0.0f0", tag)
        test_token("0.0Fe0", tag)

        test_token("0.0dfe0", tag)
        test_token("0.0DFe0", tag)

        test_token("0.0dde0", tag)
        test_token("0.0DDe0", tag)

    # Test: Detection of invalid float literals with non-terminal
    #       suffixes.
    test_token(f"{prefix}0.0l{exponent}0", tag)
    test_token(f"{prefix}0.0L{exponent}0", tag)

    test_token(f"{prefix}0.0dl{exponent}0", tag)
    test_token(f"{prefix}0.0DL{exponent}0", tag)


def test_int_literals_bin_success() -> None:
    tag = TokenTag.number_literal

    # Test: Recognition of binary digits.
    test_token("0b0", tag)
    test_token("0B0", tag)

    test_token("0b1", tag)
    test_token("0B1", tag)

    # Test: Recognition of binary literals suffixes.
    test_int_literals_suffix_success(NumberTag.int_bin)

    # Test: Recognition of multi-digit binary literals.
    test_token("0b0101", tag)
    test_token("0b1010", tag)
    test_token("0b1100", tag)
    test_token("0b0110", tag)
    test_token("0b1111", tag)

    # Test: Recognition of multi-digit binary literals with separators.
    test_token("0b1'1'1'1", tag)
    test_token("0b0'0'0'0", tag)
    test_token("0b1'0'1'0", tag)
    test_token("0b0'1'0'1", tag)

    test_token("0b11'00'11", tag)
    test_token("0b00'11'00", tag)

    test_token("0b1'100", tag)
    test_token("0b11'00", tag)
    test_token("0b110'0", tag)

    # Test: Recognition of binary literals with leading whitespace.
    tok = Tokenizer("    \t\r\n0b0")
    test_token_retrieve(tok, TokenTag.number_literal, "0b0")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("    \t\r\n0b1")
    test_token_retrieve(tok, TokenTag.number_literal, "0b1")
    test_token_retrieve(tok, TokenTag.eof, "")

    # Test: Recognition of big binary literal without need of specific
    #       suffix (e.g. u, ll).
    u32_max = "0b1111'1111'1111'1111'1111'1111'1111'1111"
    test_token(u32_max, tag)


def test_int_literals_bin_failure() -> None:
    tag = TokenTag.invalid

    # Test: Detection of incomplete binary literals.
    test_token("0b", tag)
    test_token("0B", tag)

    # Test: Detection of invalid binary literals suffixes.
    test_int_literals_suffix_failure(NumberTag.int_bin)

    # Test: Detection of invalidly placed separator.
    test_token("0b'", tag)
    test_token("0b1'", tag)
    test_token("0b0'", tag)

    test_token("0b'1", tag)
    test_token("0b'0", tag)

    test_token("0b11'00'", tag)
    test_token("0b'11'00", tag)
    test_token("0b11''00", tag)

    # Test: Detection of invalidly placed whitespace.
    tok = Tokenizer("0b 1")
    test_token_retrieve(tok, tag, "0b 1")

    tok = Tokenizer("0b\t1")
    test_token_retrieve(tok, tag, "0b\t1")

    tok = Tokenizer("0b\n1")
    test_token_retrieve(tok, tag, "0b")

    tok = Tokenizer("0b\r\n1")
    test_token_retrieve(tok, tag, "0b\r")

    # Test: Detection of non-binary digits in binary number format.
    test_token("0b2", tag)
    test_token("0b3", tag)
    test_token("0b4", tag)
    test_token("0b5", tag)
    test_token("0b6", tag)
    test_token("0b7", tag)
    test_token("0b8", tag)
    test_token("0b9", tag)
    test_token("0ba", tag)
    test_token("0bb", tag)
    test_token("0bc", tag)
    test_token("0bd", tag)
    test_token("0be", tag)
    test_token("0bf", tag)
    test_token("0bz", tag)

    test_token("0bA", tag)
    test_token("0bB", tag)
    test_token("0bC", tag)
    test_token("0bD", tag)
    test_token("0bE", tag)
    test_token("0bF", tag)
    test_token("0bZ", tag)

    test_token("0b0b", tag)

    # Test: Detection of unsupported exponents in binary number
    #       format.
    test_token("0b1e1", tag)
    test_token("0b1p1", tag)

    # Test: Detection of unsupported float format on binary number
    #       format.
    test_token("0b1.", tag)
    test_token("0b1.0", tag)


def test_int_literals_oct_success() -> None:
    tag = TokenTag.number_literal

    # Test: Recognition of octal literals suffixes.
    test_int_literals_suffix_success(NumberTag.int_oct)

    # Test: Recognition of octal digits.
    test_token("00", tag)
    test_token("01", tag)
    test_token("02", tag)
    test_token("03", tag)
    test_token("04", tag)
    test_token("05", tag)
    test_token("06", tag)
    test_token("07", tag)

    # Test: Recognition of multi-digit octal literals.
    test_token("001234567", tag)
    test_token("076543210", tag)

    # Test: Recognition of multi-digit octal literals with separators.
    test_token("00000'0", tag)
    test_token("000'000", tag)
    test_token("00'00'00", tag)

    test_token("001'234'567", tag)

    # Test: Recognition of octal literals with leading whitespace.
    tok = Tokenizer("    \t\r\n00")
    test_token_retrieve(tok, tag, "00")

    tok = Tokenizer("    \t\r\n07")
    test_token_retrieve(tok, tag, "07")

    # Test: Recognition of big octal literal without need of specific
    #       suffix (e.g. u, ll).
    test_token("037777777777", tag)


def test_int_literals_oct_failure() -> None:
    tag = TokenTag.invalid

    # Test: Detection of invalid octal literals suffixes.
    test_int_literals_suffix_failure(NumberTag.int_oct)

    # Test: Detection of invalidly placed separator.
    test_token("0'0", tag)
    test_token("0'1", tag)
    test_token("0'2", tag)
    test_token("0'3", tag)
    test_token("0'4", tag)
    test_token("0'5", tag)
    test_token("0'6", tag)
    test_token("0'7", tag)

    test_token("00'", tag)
    test_token("01'", tag)
    test_token("02'", tag)
    test_token("03'", tag)
    test_token("04'", tag)
    test_token("05'", tag)
    test_token("06'", tag)
    test_token("07'", tag)

    test_token("0'0'0'0'0'0", tag)
    test_token("0'00000", tag)
    test_token("0'0'0'0", tag)
    test_token("00'0'0'", tag)
    test_token("00''00", tag)

    # Test: Detection of non-octal digits in octal number format.
    test_token("08", tag)
    test_token("09", tag)
    test_token("0a", tag)
    test_token("0b", tag)
    test_token("0c", tag)
    test_token("0d", tag)
    test_token("0e", tag)
    test_token("0f", tag)
    test_token("0z", tag)

    test_token("0A", tag)
    test_token("0B", tag)
    test_token("0C", tag)
    test_token("0D", tag)
    test_token("0E", tag)
    test_token("0F", tag)
    test_token("0Z", tag)

    # Test: Detection of unsupported exponents in octal number
    #       format.
    test_token("07p4", tag)


def test_int_literals_dec_success() -> None:
    tag = TokenTag.number_literal

    # Test: Recognition of decimal literals suffixes.
    test_int_literals_suffix_success(NumberTag.int_dec)

    # Test: Recognition of decimal digits.
    test_token("0", tag)
    test_token("1", tag)
    test_token("2", tag)
    test_token("3", tag)
    test_token("4", tag)
    test_token("5", tag)
    test_token("6", tag)
    test_token("7", tag)
    test_token("8", tag)
    test_token("9", tag)

    # Test: Recognition of multi-digit decimal literals.
    test_token("1234567890", tag)
    test_token("9876543210", tag)

    # Test: Recognition of multi-digit octal literals with separators.
    test_token("1'23456", tag)
    test_token("12345'6", tag)
    test_token("123'456", tag)
    test_token("12'34'56", tag)
    test_token("1'2'3'4'5'6", tag)

    # Test: Recognition of decimal literals with leading whitespace.
    tok = Tokenizer("    \t\r\n0")
    test_token_retrieve(tok, tag, "0")

    tok = Tokenizer("    \t\r\n9")
    test_token_retrieve(tok, tag, "9")

    # Test: Recognition of big decimal literal without need of specific
    #       suffix (e.g. u, ll).
    test_token("4294967295", tag)


def test_int_literals_dec_failure() -> None:
    tag = TokenTag.invalid

    # Test: Detection of invalid decimal literals suffixes.
    test_int_literals_suffix_failure(NumberTag.int_dec)

    # Test: Detection of invalidly placed separator.
    test_token("'1", tag)
    test_token("1'", tag)
    test_token("1'2'3'", tag)

    # Test: Detection of non-decimal digits in decimal number format.
    test_token("1a", tag)
    test_token("1b", tag)
    test_token("1c", tag)
    test_token("1d", tag)
    test_token("1e", tag)
    test_token("1f", tag)
    test_token("1z", tag)

    test_token("1A", tag)
    test_token("1B", tag)
    test_token("1C", tag)
    test_token("1D", tag)
    test_token("1E", tag)
    test_token("1F", tag)
    test_token("1Z", tag)


def test_int_literals_hex_success() -> None:
    tag = TokenTag.number_literal

    # Test: Recognition of octal literals suffixes.
    test_int_literals_suffix_success(NumberTag.int_hex)

    # Test: Recognition of different hexadecimal prefix formats.
    test_token("0x0", tag)
    test_token("0X0", tag)

    test_token("0xa", tag)
    test_token("0Xa", tag)

    test_token("0xA", tag)
    test_token("0XA", tag)

    # Test: Recognition of hexadecimal digits.
    test_token("0x0", tag)
    test_token("0x1", tag)
    test_token("0x2", tag)
    test_token("0x3", tag)
    test_token("0x4", tag)
    test_token("0x5", tag)
    test_token("0x6", tag)
    test_token("0x7", tag)
    test_token("0x8", tag)
    test_token("0x9", tag)
    test_token("0xa", tag)
    test_token("0xb", tag)
    test_token("0xc", tag)
    test_token("0xd", tag)
    test_token("0xe", tag)
    test_token("0xf", tag)

    test_token("0xA", tag)
    test_token("0xB", tag)
    test_token("0xC", tag)
    test_token("0xD", tag)
    test_token("0xE", tag)
    test_token("0xF", tag)

    # Test: Recognition of multi-digit hexadecimal literals.
    test_token("0x0123456789abcdefABCDEF", tag)
    test_token("0xFEDCBAfedcba9876543210", tag)

    # Test: Recognition of multi-digit hexadecimal literals with
    #       separators.
    test_token("0x0'12345", tag)
    test_token("0x01234'5", tag)
    test_token("0x012'345", tag)
    test_token("0x01'23'45", tag)
    test_token("0x0'1'2'3'4'5", tag)

    # Test: Recognition of hexadecimal literals with leading
    #       whitespace.
    tok = Tokenizer("    \t\r\n0x0")
    test_token_retrieve(tok, tag, "0x0")

    tok = Tokenizer("    \t\r\n0xf")
    test_token_retrieve(tok, tag, "0xf")

    # Test: Recognition of big hexadecimal literal without need
    #       of specific suffix (e.g. u, ll).
    test_token("0x7FFFFFFF", tag)


def test_int_literals_hex_failure() -> None:
    tag = TokenTag.invalid

    # Test: Detection of incomplete hexadecimal literals.
    test_token("0x", tag)
    test_token("0X", tag)

    # Test: Detection of invalid hexadecimal literals suffixes.
    test_int_literals_suffix_failure(NumberTag.int_hex)

    # Test: Detection of invalidly placed separator.
    test_token("0x'1", tag)
    test_token("0x1'", tag)

    test_token("0x'01'23'45", tag)
    test_token("0x01'23'45'", tag)
    test_token("0x'01'23'45'", tag)

    # Test: Detection of invalidly placed whitespace.
    tok = Tokenizer("0x 1")
    test_token_retrieve(tok, tag, "0x 1")

    tok = Tokenizer("0x\t1")
    test_token_retrieve(tok, tag, "0x\t1")

    tok = Tokenizer("0x\n1")
    test_token_retrieve(tok, tag, "0x")

    tok = Tokenizer("0x\r\n1")
    test_token_retrieve(tok, tag, "0x\r")

    # Test: Detection of non-hexadecimal digits in hexadecimal number
    #       format.
    test_token("0x1g", tag)
    test_token("0x1z", tag)

    test_token("0x1G", tag)
    test_token("0x1Z", tag)

    test_token("0x0x", tag)


def test_float_literals_dec_success() -> None:
    tag = TokenTag.number_literal

    # Test: Recognition of decimal point in float decimal number
    #       format.
    test_token("1.", tag)
    test_token(".1", tag)
    test_token("1.1", tag)

    test_token("1234567890.", tag)
    test_token(".0987654321", tag)
    test_token("1234567890.0987654321", tag)

    test_token(".10000", tag)
    test_token(".00001", tag)

    # Test: Recognition of exponent in float decimal number format.
    test_token("1e1", tag)
    test_token("1e+1", tag)
    test_token("1e-1", tag)

    test_token("1234567890e1", tag)
    test_token("1e0987654321", tag)

    test_token("1234567890e+1", tag)
    test_token("1e+0987654321", tag)
    test_token("1e-0987654321", tag)
    test_token("1234567890e+0987654321", tag)
    test_token("1234567890e-0987654321", tag)

    test_token("0e10000", tag)
    test_token("0e00001", tag)

    # Test: Recognition of decimal point and exponent in float decimal
    #       number format.
    test_token("1.e1", tag)
    test_token(".1e1", tag)
    test_token("1.1e1", tag)

    test_token("1.e+1", tag)
    test_token("1.e-1", tag)

    test_token("12345677890.0987654321e0987654321", tag)
    test_token("12345677890.0987654321e+0987654321", tag)
    test_token("12345677890.0987654321e-0987654321", tag)

    # Test: Recognition of digit separator in float decimal number
    #       format.
    test_token("1'0.", tag)
    test_token(".1'0", tag)
    test_token(".1'0", tag)

    test_token("1'0e0", tag)
    test_token(".1'0e0", tag)
    test_token(".1e1'0", tag)

    num = ("1'2'3'4'5'6'7'8'9'0"
           ".0'9'8'7'6'5'4'3'2'1"
           "e0'9'8'7'6'5'4'3'2'1")
    test_token(num, tag)

    num = ("12'34'56'78'90"
           ".09'87'65'43'21"
           "e09'87'65'43'21")
    test_token(num, tag)

    num = ("1234'5678'90"
           ".0987'6543'21"
           "e0987'6543'21")
    test_token(num, tag)

    num = ("12'3456'7890"
           ".09'8765'4321"
           "e09'8765'4321")
    test_token(num, tag)

    num = ("1234'5'67890"
           ".09876'5'4321"
           "e09876'5'4321")
    test_token(num, tag)

    # Test: Recognition of tailing and leading zeros in float decimal
    #       number format.
    test_token("00.", tag)
    test_token("0e0", tag)
    test_token("00.00e00", tag)

    # Test: Recognition of leading punctuator before decimal float
    #       literal.
    tok = Tokenizer("..0")
    test_token_retrieve(tok, TokenTag.punctuator, ".")
    test_token_retrieve(tok, TokenTag.number_literal, ".0")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer(".e0.0")
    test_token_retrieve(tok, TokenTag.punctuator, ".")
    test_token_retrieve(tok, TokenTag.identifier, "e0")
    test_token_retrieve(tok, TokenTag.number_literal, ".0")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_float_literals_dec_failure() -> None:
    tag = TokenTag.invalid

    # Test: Detection of invalid separator position in decimal float
    #       number format.
    test_token("0'.0", tag)
    test_token("0.'0", tag)

    test_token("0.0'e0", tag)
    test_token("0.0e'0", tag)

    test_token("0.0e'", tag)

    # Test: Detection of multiple periods in decimal float number
    #       format.
    test_token("0..", tag)
    test_token("0..0", tag)

    test_token("0.0.0", tag)
    test_token("0.00.0", tag)

    test_token("0.e0.0", tag)
    test_token(".0e0.0", tag)
    test_token("0.0e0.0", tag)

    # Test: Detection of malformed exponent sequences in decimal float
    #       number format.
    test_token("0e", tag)
    test_token("0.0e", tag)
    test_token("0e0.0", tag)

    # Test: Detection of multiple signs in decimal float number format.
    test_token("0.0e-+0", tag)
    test_token("0.0e+-0", tag)

    # Test: Detection of invalid suffixes in decimal float number
    #       format.
    test_float_literals_suffix_failure(NumberTag.float_dec)


def test_float_literals_hex_success() -> None:
    tag = TokenTag.number_literal

    # Test: Recognition of hexadecimal point in float hexadecimal
    #       number format.
    test_token("0x1.p0", tag)
    test_token("0x.1p0", tag)
    test_token("0x1.1p0", tag)

    test_token("0x1234567890abcdef.p0", tag)
    test_token("0x.fedcba0987654321p0", tag)
    test_token("0x1234567890abcdef.fedcba0987654321p0", tag)

    test_token("0x.10000p0", tag)
    test_token("0x.00001p0", tag)

    # Test: Recognition of different exponents in float hexadecimal
    #       number format.
    test_token("0x1p1", tag)
    test_token("0x1p+1", tag)
    test_token("0x1p-1", tag)

    test_token("0x1234567890abcdefp1", tag)
    test_token("0x1p0987654321", tag)

    test_token("0x1234567890abcdefp+1", tag)
    test_token("0x1p+0987654321", tag)
    test_token("0x1p-0987654321", tag)
    test_token("0x1234567890abcdefp+0987654321", tag)
    test_token("0x1234567890abcdefp-0987654321", tag)

    test_token("0x0p10000", tag)
    test_token("0x0p00001", tag)

    # Test: Recognition of hexadecimal point and exponent in float
    #       hexadecimal number format.
    test_token("0x1.p+1", tag)
    test_token("0x1.p-1", tag)

    test_token("0x12345677890.0987654321p0987654321", tag)
    test_token("0x12345677890.0987654321p+0987654321", tag)
    test_token("0x12345677890.0987654321p-0987654321", tag)

    # Test: Recognition of digit separator in float hexadecimal number
    #       format.
    test_token("0x1'0.p0", tag)
    test_token("0x.1'0p0", tag)
    test_token("0x.1'0p0", tag)
    test_token("0x.1p1'0", tag)

    num = ("0x1'2'3'4'5'6'7'8'9'0'a'b'c'd'e'f"
           ".f'e'd'c'b'a'0'9'8'7'6'5'4'3'2'1"
           "p0'9'8'7'6'5'4'3'2'1")
    test_token(num, tag)

    num = ("0x12'34'56'78'90'ab'cd'ef"
           ".fe'dc'ba'09'87'65'43'21"
           "p09'87'65'43'21")
    test_token(num, tag)

    num = ("0x1234'5678'90ab'cdef"
           ".fedc'ba09'8765'4321"
           "p09'8765'4321")
    test_token(num, tag)

    num = ("0x12'3456'7890'abcd'ef"
           ".fe'dcba'0987'6543'21"
           "p0987'6543'21")
    test_token(num, tag)

    # Test: Recognition of tailing and leading zeros in float
    #       hexadecimal number format.
    test_token("0x0p0", tag)
    test_token("0x00.p0", tag)
    test_token("0x00.00p00", tag)


def test_float_literals_hex_failure() -> None:
    tag = TokenTag.invalid

    # Test: Detection of invalid separator position in hexadecimal
    #       float number format.
    test_token("0x0'.0p0", tag)
    test_token("0x0.'0p0", tag)

    test_token("0x0.0'p0", tag)
    test_token("0x0.0p'0", tag)

    test_token("0x'0.0p0", tag)
    test_token("0x0.0p'", tag)

    # Test: Detection of missing exponent in hexadecimal float number
    #       format.
    test_token("0x.0", tag)
    test_token("0x0.", tag)
    test_token("0x0.0", tag)

    # Test: Detection of multiple periods in hexadecimal float number
    #       format.
    test_token("0x..0p0", tag)
    test_token("0x0..p0", tag)
    test_token("0x0..0p0", tag)

    test_token("0x0.0.0p0", tag)
    test_token("0x0.00.0p0", tag)

    test_token("0x.p0.0", tag)
    test_token("0x0.p0.0", tag)
    test_token("0x.0p0.0", tag)
    test_token("0x0.0p0.0", tag)

    # Test: Detection of malformed exponent sequences in decimal float
    #       number format.
    test_token("0x0p", tag)
    test_token("0x0.0p", tag)
    test_token("0x0p0.0", tag)

    # Test: Detection of multiple signs in hexadecimal float number
    #       format.
    test_token("0x0.0p-+0", tag)
    test_token("0x0.0p+-0", tag)

    # Test: Detection of invalid suffixes in hexadecimal float number
    #       format.
    test_float_literals_suffix_failure(NumberTag.float_hex)


def test_x_char_sequence_success(tag: TokenTag)-> None:
    assert tag == TokenTag.string_literal or tag == TokenTag.char_literal

    punct = ""

    if tag == TokenTag.string_literal:
        punct = "\""
    else:
        punct = "\'"

    # Test: Recognition of individual, representative ASCII characters.
    test_token(f"{punct}0{punct}", tag)
    test_token(f"{punct}a{punct}", tag)
    test_token(f"{punct}A{punct}", tag)
    test_token(f"{punct}.{punct}", tag)
    test_token(f"{punct},{punct}", tag)
    test_token(f"{punct}[{punct}", tag)
    test_token(f"{punct}+{punct}", tag)
    test_token(f"{punct}@{punct}", tag)

    # Test: Recognition of standard ASCII character set.
    test_token(f"{punct}01234566789{punct}", tag)
    test_token(f"{punct}abcdefghijklmnopqrstuvwxyz{punct}", tag)
    test_token(f"{punct}ABCDEFGHIJKLMNOPQRSTUVWXYZ{punct}", tag)
    test_token(f"{punct}.?!{punct}", tag)
    test_token(f"{punct},;:-—_{punct}", tag)
    test_token(f"{punct}[]{{}}()\\\'\\\'\\\"\\\"{punct}", tag)
    test_token(f"{punct}+-=<>{punct}", tag)
    test_token(f"{punct}@#&%/|*^`\\\\{punct}", tag)

    # Test: Recognition of encoding prefixes.
    text = "Injustice anywhere is a threat to justice everywhere."
    test_token(f"u8{punct}{text}{punct}", tag)
    test_token(f"u{punct}{text}{punct}", tag)
    test_token(f"U{punct}{text}{punct}", tag)
    test_token(f"L{punct}{text}{punct}", tag)

    # Test: Recognition of UTF-8 characters.
    test_token(f"u8{punct}✅{punct}", tag)
    test_token(f"u8{punct}❌{punct}", tag)

    # Test: Recognition of UTF-8 characters even without the UTF-8
    #       encoding prefix.
    test_token(f"{punct}✅{punct}", tag)
    test_token(f"{punct}❌{punct}", tag)

    # Test: Recognition of multi-byte UTF-8 characters.
    chinese = "磨杵成针 (mó chǔ chéng zhēn)"
    korean = "고생 끝에 낙이 온다 (Gosaeng kkeute nagi onda)"
    japanese = "雨降って地固まる (Ame futte ji katamaru)"
    vietnamese = "Giấy rách phải giữ lấy lề (Giay rach phai giu lay le)"
    arabic = "كل آتٍ قريب (Kullu ātin qarīb)"
    russian = "Глаза боятся, а руки делают (Glaza boyatsya, a ruki delayut)"
    czech = "Učený z nebe nespadl"
    slovak = "V núdzi poznáš priateľa"

    test_token(f"{punct}{chinese}{punct}", tag)
    test_token(f"{punct}{korean}{punct}", tag)
    test_token(f"{punct}{japanese}{punct}", tag)
    test_token(f"{punct}{vietnamese}{punct}", tag)
    test_token(f"{punct}{arabic}{punct}", tag)
    test_token(f"{punct}{russian}{punct}", tag)
    test_token(f"{punct}{czech}{punct}", tag)
    test_token(f"{punct}{slovak}{punct}", tag)

    arithmetic_symbols = "+ − ± ∓ × ÷ ∗ ⋅ √ ∛ ∜ ∞"
    relational_symbols = "= ≠ ≈ ≅ ≡ < > ≤ ≥ ≪ ≫ ∝"
    set_symbols = "∅ ∈ ∉ ⊂ ⊆ ⊄ ⊃ ⊇ ∪ ∩ ∖ ⊕ "
    calculus_symbols = "∑ ∏ ∐ ∫ ∬ ∭ ∮ ∂ ∇ ∆ ∴ ∵"
    greek_lower = "α β γ δ ε ζ η θ ι κ λ μ ν ξ ο π ρ σ τ υ φ χ ψ ω"
    greek_upper = "Α Β Γ Δ Ε Ζ Η Θ Ι Κ Λ Μ Ν Ξ Ο Π Ρ Σ Τ Υ Φ Χ Ψ Ω"

    test_token(f"{punct}{arithmetic_symbols}{punct}", tag)
    test_token(f"{punct}{relational_symbols}{punct}", tag)
    test_token(f"{punct}{set_symbols}{punct}", tag)
    test_token(f"{punct}{calculus_symbols}{punct}", tag)
    test_token(f"{punct}{greek_lower}{punct}", tag)
    test_token(f"{punct}{greek_upper}{punct}", tag)

    # Test: Recognition of simple escape sequences.
    test_token(f"{punct}\\\'{punct}", tag)
    test_token(f"{punct}\\\"{punct}", tag)
    test_token(f"{punct}\\?{punct}", tag)
    test_token(f"{punct}\\\\{punct}", tag)
    test_token(f"{punct}\\a{punct}", tag)
    test_token(f"{punct}\\b{punct}", tag)
    test_token(f"{punct}\\f{punct}", tag)
    test_token(f"{punct}\\n{punct}", tag)
    test_token(f"{punct}\\r{punct}", tag)
    test_token(f"{punct}\\t{punct}", tag)
    test_token(f"{punct}\\v{punct}", tag)

    # Test: Recognition of octal escape sequences.
    test_token(f"{punct}\\0{punct}", tag)
    test_token(f"{punct}\\7{punct}", tag)
    test_token(f"{punct}\\12{punct}", tag)
    test_token(f"{punct}\\123{punct}", tag)

    test_token(f"{punct}\\1{punct}", tag)
    test_token(f"{punct}\\01{punct}", tag)
    test_token(f"{punct}\\001{punct}", tag)

    test_token(f"{punct}\\000{punct}", tag)
    test_token(f"{punct}\\777{punct}", tag)

    test_token(f"{punct}\\089{punct}", tag)

    # Test: Recognition of hexadecimal escape sequences.
    test_token(f"{punct}\\x00{punct}", tag)
    test_token(f"{punct}\\x09{punct}", tag)
    test_token(f"{punct}\\x0a{punct}", tag)
    test_token(f"{punct}\\x0f{punct}", tag)
    test_token(f"{punct}\\x1b{punct}", tag)
    test_token(f"{punct}\\x20{punct}", tag)

    test_token(f"{punct}\\x0A{punct}", tag)
    test_token(f"{punct}\\x0F{punct}", tag)
    test_token(f"{punct}\\x1B{punct}", tag)

    test_token(f"{punct}\\xaA{punct}", tag)

    test_token(f"{punct}\\x123456789abcdefABCDEF{punct}", tag)

    # Test: Recognition of universal character names.
    test_token(f"{punct}\\u0123{punct}", tag)
    test_token(f"{punct}\\u4567{punct}", tag)
    test_token(f"{punct}\\u89ab{punct}", tag)
    test_token(f"{punct}\\ucdef{punct}", tag)

    test_token(f"{punct}\\u89AB{punct}", tag)
    test_token(f"{punct}\\u89aB{punct}", tag)

    test_token(f"{punct}\\U12345678{punct}", tag)
    test_token(f"{punct}\\U9abcdef0{punct}", tag)

    test_token(f"{punct}\\U9aBcDef0{punct}", tag)

    test_token(f"{punct}\\u0001{punct}", tag)
    test_token(f"{punct}\\u00001{punct}", tag)
    test_token(f"{punct}\\u000001{punct}", tag)
    test_token(f"{punct}\\u0000001{punct}", tag)
    test_token(f"{punct}\\u00000001{punct}", tag)

    test_token(f"{punct}\\U00000001{punct}", tag)
    test_token(f"{punct}\\U000000001{punct}", tag)

def test_x_char_sequence_failure(seq_tag: TokenTag) -> None:
    tag = TokenTag.invalid

    punct = ""

    if seq_tag == TokenTag.string_literal:
        punct = "\""
    else:
        punct = "\'"
        assert seq_tag == TokenTag.char_literal

    # Test: Detection of non-terminated char sequences.
    text = "Injustice anywhere is a threat to justice everywhere."
    author = "Martin Luther King Jr."
    test_token(f"{punct}", tag)
    test_token(f"{punct}a", tag)
    test_token(f"{punct}0", tag)
    test_token(f"{punct}{text}", tag)

    test_token(f"{punct}\\0", tag)
    test_token(f"{punct}\\x00", tag)

    test_token(f"u8{punct}", tag)
    test_token(f"u{punct}", tag)
    test_token(f"U{punct}", tag)
    test_token(f"L{punct}", tag)

    # Test: Detection of invalid octal escape sequences digit limit.
    test_token("\\0000", tag)
    test_token("\\1234567", tag)

    # Test: Detection of invalid octal escape sequences digit
    #       boundaries.
    test_token(f"{punct}\\8text{punct}", tag)
    test_token(f"{punct}\\9text{punct}", tag)

    # Test: Detection of invalid format of universal character names.
    test_token(f"{punct}\\u1{punct}", tag)
    test_token(f"{punct}\\u01{punct}", tag)
    test_token(f"{punct}\\u001{punct}", tag)

    test_token(f"{punct}\\U1{punct}", tag)
    test_token(f"{punct}\\U01{punct}", tag)
    test_token(f"{punct}\\U001{punct}", tag)
    test_token(f"{punct}\\U0001{punct}", tag)
    test_token(f"{punct}\\U00001{punct}", tag)
    test_token(f"{punct}\\U000001{punct}", tag)
    test_token(f"{punct}\\U0000001{punct}", tag)

    # Test: Detection of invalid newline in sequence.
    tok = Tokenizer(f"{punct}\n{punct}")
    test_token_retrieve(tok, tag, f"{punct}")

    tok = Tokenizer(f"{punct}a\n{punct}")
    test_token_retrieve(tok, tag, f"{punct}a")

    tok = Tokenizer(f"{punct}0\n{punct}")
    test_token_retrieve(tok, tag, f"{punct}0")

    tok = Tokenizer(f"{punct}{text}-{author}\n{punct}")
    test_token_retrieve(tok, tag, f"{punct}{text}-{author}")

    tok = Tokenizer(f"{punct}{text}\n{author}{punct}")
    test_token_retrieve(tok, tag, f"{punct}{text}")


def test_string_literals_success() -> None:
    tag = TokenTag.string_literal

    test_x_char_sequence_success(tag)

    # Test: Recognition of special char sequences in string format
    #       by C23 language standard.
    #
    # (Ref: ISO/IEC 9899:2024, Section 6.4.5, Paragraph 3 and 4).
    punct = "\""
    test_token(f"{punct}{punct}", tag)

    test_token(f"{punct}\'{punct}", tag)
    test_token(f"{punct}\\\'{punct}", tag)


def test_string_literals_failure() -> None:
    test_x_char_sequence_failure(TokenTag.string_literal)


def test_char_literals_success() -> None:
    tag = TokenTag.char_literal

    test_x_char_sequence_success(tag)

    # Test: Recognition of special char sequences in character format
    #       by C23 language standard.
    #
    # (Ref: ISO/IEC 9899:2024, Section 6.4.4.5, Paragraph 4).
    punct = "\'"
    test_token(f"{punct}\"{punct}", tag)
    test_token(f"{punct}\\\"{punct}", tag)

    test_token(f"{punct}?{punct}", tag)
    test_token(f"{punct}\\?{punct}", tag)

    test_token(f"{punct}\\\'{punct}", tag)
    test_token(f"{punct}\\\\{punct}", tag)


def test_char_literals_failure() -> None:
    test_x_char_sequence_failure(TokenTag.char_literal)
    test_token("\'\'", TokenTag.invalid)


def test_line_comments_success() -> None:
    tag = TokenTag.line_comment
    # Test: Recognition of basic line comments.
    test_token("//", tag)
    test_token("//Crab", tag)
    test_token("// Crab", tag)
    test_token("// Ferris – the crab.", tag)

    # Test: Recognition of line comment while containing various
    #       whitespace characters.
    test_token("//    \t\v\f\rtext", tag)

    # Test: Recognition of UTF-8 characters in line comments.
    test_token("// Crab 🦀!", tag)
    test_token("// T∅P: Overcompensate ☡", tag)

    # Test: Ignoration of multi-line comments inside line comment.
    test_token("// /* Crab! */", tag)
    test_token("// /* Crab! */ */", tag)

    # Test: Recognition of multiple sequential line comments.
    tok = Tokenizer("//\n\n// Crab!\n//\tCrab nation!")
    test_token_retrieve(tok, tag, "//")
    test_token_retrieve(tok, tag, "// Crab!")
    test_token_retrieve(tok, tag, "//\tCrab nation!")
    test_token_retrieve(tok, TokenTag.eof, "")

    tok = Tokenizer("// a / b / / Crab!\n//\tCrab nation!//")
    test_token_retrieve(tok, tag, "// a / b / / Crab!")
    test_token_retrieve(tok, tag, "//\tCrab nation!//")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_multi_line_comments_success() -> None:
    tag = TokenTag.multi_line_comment

    # Test: Recognition of multi-line comments.
    test_token("/**/", tag)
    test_token("/*Crab*/", tag)
    test_token("/* Crab */", tag)
    test_token("/* Ferris – the crab. */", tag)

    # Test: Recognition of multi-line comments while containing mixed
    #       whitespace.
    test_token("/* A\n * B\n * C\n */", tag)
    test_token("/*\tA\n *\tB\n *\tC\n */", tag)
    test_token("/* A\r\n * B\r\n * C\r\n */", tag)

    # Test: Recognition of proper ending of multi-line comments.
    test_token("/* a * b / c */", tag)
    test_token("/* * / */", tag)
    test_token("/** /*/", tag)

    # Test: Recognition of UTF-8 characters in multi-line comments.
    comment = """
    /* [ Bands & Solo Artists ]
     * - [ 📻 ] Twenty ∅ne Pilots
     * - [ 📼 ] X Ambassadors
     * - [ 🧢 ] Nathan John Feuerstein
     * - [ 🎻 ] Adam, Jack, and Ryan
     * - [ 🏃 ] OneRepublic */
    """.strip()
    test_token(comment, tag)

    # Test: Recognition of multi-line comment without multi-line
    #       nesting.
    comment = "/* Crab! /* Crab nation! */"
    tok = Tokenizer(f"{comment} */ ")
    test_token_retrieve(tok, TokenTag.multi_line_comment, comment)
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.punctuator, "/")
    test_token_retrieve(tok, TokenTag.eof, "")

    # Test: Ignoration of multi-line comments between operation.
    tok = Tokenizer("g/**//h")
    test_token_retrieve(tok, TokenTag.identifier, "g")
    test_token_retrieve(tok, TokenTag.multi_line_comment, "/**/")
    test_token_retrieve(tok, TokenTag.punctuator, "/")
    test_token_retrieve(tok, TokenTag.identifier, "h")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_simple_code_success_01() -> None:
    c_source_code = """
    int fib( int n )
    {
        int a = 1, b = 1;

        for ( int i = 0; i < n - 2; ++i )
        {
            int c = a + b;

            a = b;
            b = c;
        }

        return b;
    }

    int main() /* demo */
    {
        assert( fib( 1 ) == 1 );
        return 0;
    }
    """
    tok = Tokenizer(c_source_code)

    # int fib( int n )
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "fib")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "n")
    test_token_retrieve(tok, TokenTag.punctuator, ")")

    # {
    test_token_retrieve(tok, TokenTag.punctuator, "{")

    # int a = 1, b = 1;
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "a")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "1")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "1")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # for ( int i = 0; i < n - 2; ++i )
    test_token_retrieve(tok, TokenTag.keyword, "for")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, "<")
    test_token_retrieve(tok, TokenTag.identifier, "n")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.number_literal, "2")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.punctuator, "++")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, ")")

    # {
    test_token_retrieve(tok, TokenTag.punctuator, "{")

    # int c = a + b;
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "c")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "a")
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # a = b;
    test_token_retrieve(tok, TokenTag.identifier, "a")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # b = c;
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "c")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # }
    test_token_retrieve(tok, TokenTag.punctuator, "}")

    # return b;
    test_token_retrieve(tok, TokenTag.keyword, "return")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # }
    test_token_retrieve(tok, TokenTag.punctuator, "}")

    # int main() /* demo */
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "main")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.multi_line_comment, "/* demo */")

    # {
    test_token_retrieve(tok, TokenTag.punctuator, "{")

    # assert( fib( 1 ) == 1 );
    test_token_retrieve(tok, TokenTag.keyword, "assert")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "fib")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.number_literal, "1")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "==")
    test_token_retrieve(tok, TokenTag.number_literal, "1")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # return 0;
    test_token_retrieve(tok, TokenTag.keyword, "return")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # }
    test_token_retrieve(tok, TokenTag.punctuator, "}")

    # eof
    test_token_retrieve(tok, TokenTag.eof, "")


def test_simple_code_success_02() -> None:
    c_source_code = """
    (*(void(*)())0)();

    void (*reset)(void) = 0;

    long foo( int a, int b ) {
        return a;
    }

    int main() {
        int x = 4-2,
            y = 4- 2,
            z = 4 -2;

        while ( x --> 0 );
        while ( 0 <-- y );

        bool tmp = !!( x );
        int *p = (int[]){1, 2, 3};

        int arr[ 4 ];
        2[ arr ] = 0;

        <%
            int arr<:5:> = <% 0, 1, 2, 3, 4 %>;
            if ( arr<:0:> == 1 ) <%
                char tmp[] = "Wait, where are my brackets?!\\n";
            %>
        %>

        char *matrix[ 4 ][ 4 ] = { 0 };
        if(matrix[0][0] == "#");
        else
        {
            matrix[0][0] = "@";
        }

        foo ( 10, 5 );
        reset();
    }
    """

    tok = Tokenizer(c_source_code)

    # (*(void(*)())0)();
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.keyword, "void")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # void (*reset)(void) = 0;
    test_token_retrieve(tok, TokenTag.keyword, "void")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "reset")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.keyword, "void")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # long foo( int a, int b ) {
    test_token_retrieve(tok, TokenTag.keyword, "long")
    test_token_retrieve(tok, TokenTag.identifier, "foo")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "a")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "{")

    # return a;
    test_token_retrieve(tok, TokenTag.keyword, "return")
    test_token_retrieve(tok, TokenTag.identifier, "a")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # }
    test_token_retrieve(tok, TokenTag.punctuator, "}")

    # int main() {
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "main")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "{")

    # int x = 4-2,
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "x")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "4")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.number_literal, "2")
    test_token_retrieve(tok, TokenTag.punctuator, ",")

    # y = 4- 2,
    test_token_retrieve(tok, TokenTag.identifier, "y")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "4")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.number_literal, "2")
    test_token_retrieve(tok, TokenTag.punctuator, ",")

    # z = 4 -2;
    test_token_retrieve(tok, TokenTag.identifier, "z")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "4")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.number_literal, "2")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # while ( x --> 0 );
    test_token_retrieve(tok, TokenTag.keyword, "while")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "x")
    test_token_retrieve(tok, TokenTag.punctuator, "--")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # while ( 0 <-- y );
    test_token_retrieve(tok, TokenTag.keyword, "while")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "<")
    test_token_retrieve(tok, TokenTag.punctuator, "--")
    test_token_retrieve(tok, TokenTag.identifier, "y")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # bool tmp = !!( x );
    test_token_retrieve(tok, TokenTag.keyword, "bool")
    test_token_retrieve(tok, TokenTag.identifier, "tmp")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.punctuator, "!")
    test_token_retrieve(tok, TokenTag.punctuator, "!")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "x")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # int *p = (int[]){1, 2, 3};
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "p")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "{")
    test_token_retrieve(tok, TokenTag.number_literal, "1")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "2")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "3")
    test_token_retrieve(tok, TokenTag.punctuator, "}")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # int arr[ 4 ];
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "arr")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.number_literal, "4")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # 2[ arr ] = 0;
    test_token_retrieve(tok, TokenTag.number_literal, "2")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.identifier, "arr")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # <%
    test_token_retrieve(tok, TokenTag.punctuator, "<%")

    # int arr<:5:> = <% 0, 1, 2, 3, 4 %>;
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "arr")
    test_token_retrieve(tok, TokenTag.punctuator, "<:")
    test_token_retrieve(tok, TokenTag.number_literal, "5")
    test_token_retrieve(tok, TokenTag.punctuator, ":>")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.punctuator, "<%")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "1")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "2")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "3")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "4")
    test_token_retrieve(tok, TokenTag.punctuator, "%>")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # if ( arr<:0:> == 1 ) <%
    test_token_retrieve(tok, TokenTag.keyword, "if")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "arr")
    test_token_retrieve(tok, TokenTag.punctuator, "<:")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ":>")
    test_token_retrieve(tok, TokenTag.punctuator, "==")
    test_token_retrieve(tok, TokenTag.number_literal, "1")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "<%")

    # char tmp[] = "Wait, where are my brackets?!\n";
    test_token_retrieve(tok, TokenTag.keyword, "char")
    test_token_retrieve(tok, TokenTag.identifier, "tmp")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.string_literal,
                        "\"Wait, where are my brackets?!\\n\"")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # %>
    test_token_retrieve(tok, TokenTag.punctuator, "%>")

    # %>
    test_token_retrieve(tok, TokenTag.punctuator, "%>")

    # char *matrix[ 4 ][ 4 ] = { 0 };
    test_token_retrieve(tok, TokenTag.keyword, "char")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "matrix")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.number_literal, "4")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.number_literal, "4")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.punctuator, "{")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "}")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # if(matrix[0][0] == "#");
    test_token_retrieve(tok, TokenTag.keyword, "if")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "matrix")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "==")
    test_token_retrieve(tok, TokenTag.string_literal, "\"#\"")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # else
    test_token_retrieve(tok, TokenTag.keyword, "else")

    # {
    test_token_retrieve(tok, TokenTag.punctuator, "{")

    # matrix[0][0] = "@";
    test_token_retrieve(tok, TokenTag.identifier, "matrix")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.string_literal, "\"@\"")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # }
    test_token_retrieve(tok, TokenTag.punctuator, "}")

    # foo ( 10, 5 );
    test_token_retrieve(tok, TokenTag.identifier, "foo")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.number_literal, "10")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "5")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # reset();
    test_token_retrieve(tok, TokenTag.identifier, "reset")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # }
    test_token_retrieve(tok, TokenTag.punctuator, "}")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_simple_code_success_03() -> None:
    not_c_source_code = """
    "string" + "string" -= 'string'
    )( ][ }{
    char->short-->int-- >long- ->long long
    float x = "text";
    123"123'123'"
    """

    tok = Tokenizer(not_c_source_code)

    # "string" + "string" -= 'string'
    test_token_retrieve(tok, TokenTag.string_literal, "\"string\"")
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.string_literal, "\"string\"")
    test_token_retrieve(tok, TokenTag.punctuator, "-=")
    test_token_retrieve(tok, TokenTag.char_literal, "\'string\'")

    # )( ][ }{
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.punctuator, "}")
    test_token_retrieve(tok, TokenTag.punctuator, "{")

    # char->short-->int-- >long- ->long long
    test_token_retrieve(tok, TokenTag.keyword, "char")
    test_token_retrieve(tok, TokenTag.punctuator, "->")
    test_token_retrieve(tok, TokenTag.keyword, "short")
    test_token_retrieve(tok, TokenTag.punctuator, "--")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.punctuator, "--")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.keyword, "long")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.punctuator, "->")
    test_token_retrieve(tok, TokenTag.keyword, "long")
    test_token_retrieve(tok, TokenTag.keyword, "long")

    # float x = "text";
    test_token_retrieve(tok, TokenTag.keyword, "float")
    test_token_retrieve(tok, TokenTag.identifier, "x")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.string_literal, "\"text\"")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # 123"123'123'"
    test_token_retrieve(tok, TokenTag.number_literal, "123")
    test_token_retrieve(tok, TokenTag.string_literal, "\"123'123'\"")
    test_token_retrieve(tok, TokenTag.eof, "")


def test_simple_code_success_04() -> None:
    c_source_code = """
                 k;double sin()
             ,cos();main(){float A=
           0,B=0,i,j,z[1760];char b[
         1760];printf("\\x1b[2J");for(;;
      ){memset(b,32,1760);memset(z,0,7040)
      ;for(j=0;6.28>j;j+=0.07)for(i=0;6.28
     >i;i+=0.02){float c=sin(i),d=cos(j),e=
     sin(A),f=sin(j),g=cos(A),h=d+2,D=1/(c*
     h*e+f*g+5),l=cos      (i),m=cos(B),n=sin
    (B),t=c*h*g-f*           e;int x=40+30*D*
    (l*h*m-t*n),y=            12+15*D*(l*h*n
    +t*m),o=x+80*y,          N=8*((f*e-c*d*g
     )*m-c*d*e-f*g-l        *d*n);if(22>y&&
     y>0&&x>0&&80>x&&D>z[o]){z[o]=D;;;b[o]=
     ".,-~:;=!*#$@"[N>0?N:0];}}/*#****!!-*/
      printf("\\x1b[H");for(k=0;1761>k;k++)
       putchar(k%80?b[k]:10);A+=0.04;B+=
         0.02;}}/*****####*******!!=;:~
           ~::==!!!**********!!!==::-
             .,~~;;;========;;;:~-.
                 ..,--------,*/
    """

    tok = Tokenizer(c_source_code)

    # k;double sin()
    test_token_retrieve(tok, TokenTag.identifier, "k")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.keyword, "double")
    test_token_retrieve(tok, TokenTag.identifier, "sin")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")

    # ,cos();main(){float A=
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "cos")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "main")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "{")
    test_token_retrieve(tok, TokenTag.keyword, "float")
    test_token_retrieve(tok, TokenTag.identifier, "A")
    test_token_retrieve(tok, TokenTag.punctuator, "=")

    # 0,B=0,i,j,z[1760];char b[
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "B")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "j")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "z")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.number_literal, "1760")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.keyword, "char")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, "[")

    # 1760];printf("\\x1b[2J");for(;;
    test_token_retrieve(tok, TokenTag.number_literal, "1760")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "printf")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.string_literal, "\"\\x1b[2J\"")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.keyword, "for")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.punctuator, ";")

    # ){memset(b,32,1760);memset(z,0,7040)
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "{")
    test_token_retrieve(tok, TokenTag.identifier, "memset")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "32")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "1760")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "memset")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "z")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.number_literal, "7040")
    test_token_retrieve(tok, TokenTag.punctuator, ")")

    # ;for(j=0;6.28>j;j+=0.07)for(i=0;6.28
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.keyword, "for")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "j")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.number_literal, "6.28")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.identifier, "j")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "j")
    test_token_retrieve(tok, TokenTag.punctuator, "+=")
    test_token_retrieve(tok, TokenTag.number_literal, "0.07")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.keyword, "for")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.number_literal, "6.28")

    # >i;i+=0.02){float c=sin(i),d=cos(j),e=
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, "+=")
    test_token_retrieve(tok, TokenTag.number_literal, "0.02")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "{")
    test_token_retrieve(tok, TokenTag.keyword, "float")
    test_token_retrieve(tok, TokenTag.identifier, "c")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "sin")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "d")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "cos")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "j")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "e")
    test_token_retrieve(tok, TokenTag.punctuator, "=")

    # sin(A),f=sin(j),g=cos(A),h=d+2,D=1/(c*
    test_token_retrieve(tok, TokenTag.identifier, "sin")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "A")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "f")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "sin")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "j")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "g")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "cos")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "A")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "h")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "d")
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.number_literal, "2")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "D")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "1")
    test_token_retrieve(tok, TokenTag.punctuator, "/")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "c")
    test_token_retrieve(tok, TokenTag.punctuator, "*")

    # h*e+f*g+5),l=cos      (i),m=cos(B),n=sin
    test_token_retrieve(tok, TokenTag.identifier, "h")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "e")
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.identifier, "f")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "g")
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.number_literal, "5")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "l")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "cos")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "i")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "m")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "cos")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "B")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "n")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "sin")

    # (B),t=c*h*g-f*          e;int x=40+30*D*
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "B")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "t")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "c")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "h")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "g")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.identifier, "f")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "e")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "x")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "40")
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.number_literal, "30")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "D")
    test_token_retrieve(tok, TokenTag.punctuator, "*")

    # (l*h*m-t*n),y=            12+15*D*(l*h*n
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "l")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "h")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "m")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.identifier, "t")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "n")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "y")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "12")
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.number_literal, "15")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "D")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "l")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "h")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "n")

    # +t*m),o=x+80*y,          N=8*((f*e-c*d*g
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.identifier, "t")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "m")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "o")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "x")
    test_token_retrieve(tok, TokenTag.punctuator, "+")
    test_token_retrieve(tok, TokenTag.number_literal, "80")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "y")
    test_token_retrieve(tok, TokenTag.punctuator, ",")
    test_token_retrieve(tok, TokenTag.identifier, "N")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "8")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "f")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "e")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.identifier, "c")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "d")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "g")

    #  )*m-c*d*e-f*g-l        *d*n);if(22>y&&
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "m")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.identifier, "c")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "d")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "e")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.identifier, "f")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "g")
    test_token_retrieve(tok, TokenTag.punctuator, "-")
    test_token_retrieve(tok, TokenTag.identifier, "l")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "d")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "n")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.keyword, "if")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.number_literal, "22")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.identifier, "y")
    test_token_retrieve(tok, TokenTag.punctuator, "&&")

    #  y>0&&x>0&&80>x&&D>z[o]){z[o]=D;;;b[o]=
    test_token_retrieve(tok, TokenTag.identifier, "y")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "&&")
    test_token_retrieve(tok, TokenTag.identifier, "x")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "&&")
    test_token_retrieve(tok, TokenTag.number_literal, "80")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.identifier, "x")
    test_token_retrieve(tok, TokenTag.punctuator, "&&")
    test_token_retrieve(tok, TokenTag.identifier, "D")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.identifier, "z")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.identifier, "o")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, "{")
    test_token_retrieve(tok, TokenTag.identifier, "z")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.identifier, "o")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.identifier, "D")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.identifier, "o")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, "=")

    #  ".,-~:;=!*#$@"[N>0?N:0];}}/*#****!!-*/
    test_token_retrieve(tok, TokenTag.string_literal, "\".,-~:;=!*#$@\"")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.identifier, "N")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "?")
    test_token_retrieve(tok, TokenTag.identifier, "N")
    test_token_retrieve(tok, TokenTag.punctuator, ":")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.punctuator, "}")
    test_token_retrieve(tok, TokenTag.punctuator, "}")
    test_token_retrieve(tok, TokenTag.multi_line_comment, "/*#****!!-*/")

    #   printf("\\x1b[H");for(k=0;1761>k;k++)
    test_token_retrieve(tok, TokenTag.identifier, "printf")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.string_literal, "\"\\x1b[H\"")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.keyword, "for")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "k")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.number_literal, "0")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.number_literal, "1761")
    test_token_retrieve(tok, TokenTag.punctuator, ">")
    test_token_retrieve(tok, TokenTag.identifier, "k")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "k")
    test_token_retrieve(tok, TokenTag.punctuator, "++")
    test_token_retrieve(tok, TokenTag.punctuator, ")")

    #    putchar(k%80?b[k]:10);A+=0.04;B+=
    test_token_retrieve(tok, TokenTag.identifier, "putchar")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.identifier, "k")
    test_token_retrieve(tok, TokenTag.punctuator, "%")
    test_token_retrieve(tok, TokenTag.number_literal, "80")
    test_token_retrieve(tok, TokenTag.punctuator, "?")
    test_token_retrieve(tok, TokenTag.identifier, "b")
    test_token_retrieve(tok, TokenTag.punctuator, "[")
    test_token_retrieve(tok, TokenTag.identifier, "k")
    test_token_retrieve(tok, TokenTag.punctuator, "]")
    test_token_retrieve(tok, TokenTag.punctuator, ":")
    test_token_retrieve(tok, TokenTag.number_literal, "10")
    test_token_retrieve(tok, TokenTag.punctuator, ")")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "A")
    test_token_retrieve(tok, TokenTag.punctuator, "+=")
    test_token_retrieve(tok, TokenTag.number_literal, "0.04")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.identifier, "B")
    test_token_retrieve(tok, TokenTag.punctuator, "+=")

    #      0.02;}}/*****####*******!!=;:~
    #        ~::==!!!**********!!!==::-
    #          .,~~;;;========;;;:~-.
    #              ..,--------,*/
    test_token_retrieve(tok, TokenTag.number_literal, "0.02")
    test_token_retrieve(tok, TokenTag.punctuator, ";")
    test_token_retrieve(tok, TokenTag.punctuator, "}")
    test_token_retrieve(tok, TokenTag.punctuator, "}")

    text = """/*****####*******!!=;:~
           ~::==!!!**********!!!==::-
             .,~~;;;========;;;:~-.
                 ..,--------,*/"""
    test_token_retrieve(tok, TokenTag.multi_line_comment, text)
    test_token_retrieve(tok, TokenTag.eof, "")


def test_simple_code_success() -> None:
    test_simple_code_success_01()
    test_simple_code_success_02()
    test_simple_code_success_03()
    test_simple_code_success_04()


def test_simple_code_failure_01() -> None:
    c_source_code = """
    int main()
    {
        char *str = "Text;
    }
    """

    tok = Tokenizer(c_source_code)

    # int main()
    test_token_retrieve(tok, TokenTag.keyword, "int")
    test_token_retrieve(tok, TokenTag.identifier, "main")
    test_token_retrieve(tok, TokenTag.punctuator, "(")
    test_token_retrieve(tok, TokenTag.punctuator, ")")

    # {
    test_token_retrieve(tok, TokenTag.punctuator, "{")

    # char *str = "Text;
    test_token_retrieve(tok, TokenTag.keyword, "char")
    test_token_retrieve(tok, TokenTag.punctuator, "*")
    test_token_retrieve(tok, TokenTag.identifier, "str")
    test_token_retrieve(tok, TokenTag.punctuator, "=")
    test_token_retrieve(tok, TokenTag.invalid, "\"Text;")

    # }
    test_token_retrieve(tok, TokenTag.punctuator, "}")


def test_simple_code_failure_02() -> None:
    pass


def test_simple_code_failure_03() -> None:
    pass


def test_simple_code_failure_04() -> None:
    pass


def test_simple_code_failure() -> None:
    test_simple_code_failure_01()
    test_simple_code_failure_02()
    test_simple_code_failure_03()
    test_simple_code_failure_04()


def test_identifier() -> None:
    test_identifier_success()
    test_identifier_failure()


def test_int_literals() -> None:
    test_int_literals_bin_success()
    test_int_literals_bin_failure()

    test_int_literals_oct_success()
    test_int_literals_oct_failure()

    test_int_literals_dec_success()
    test_int_literals_dec_failure()

    test_int_literals_hex_success()
    test_int_literals_hex_failure()


def test_float_literals() -> None:
    test_float_literals_dec_success()
    test_float_literals_dec_failure()

    test_float_literals_hex_success()
    test_float_literals_hex_failure()


def test_string_literals() -> None:
    test_string_literals_success()
    test_string_literals_failure()


def test_char_literals() -> None:
    test_char_literals_success()
    test_char_literals_failure()


def test_line_comments() -> None:
    test_line_comments_success()


def test_multi_line_comments() -> None:
    test_multi_line_comments_success()


def test_simple_code() -> None:
    test_simple_code_success()
    test_simple_code_failure()


def test_tokenizer() -> None:
    test_keywords()
    test_punctuators()
    test_identifier()
    test_int_literals()
    test_float_literals()
    test_string_literals()
    test_char_literals()
    test_line_comments()
    test_multi_line_comments()

    test_simple_code()

if __name__ == "__main__":
    test_tokenizer()
