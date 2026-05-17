from math import isinf
from enum import Enum
from decimal import Decimal, InvalidOperation

from error import Error
from common import is_oct_digit, is_dec_digit, is_hex_digit

from tokenizer import *
from flint_ast import *

# Parser
# Validates token sequences and maps them to an Abstract Syntax Tree
# (AST).
#
# NOTE: The parser validates structural syntax — not the correctness
# of operations or the underlying semantics.
#
# Analogy (Natural Language):
# 1. Tokenizer: A "word checker" that ensures every word is valid.
# 2. Parser: A "grammar checker" that ensures nouns and verbs are in
#    the correct order (the structure).
# 3. Static Analysis: A "context checker" that ensures the sentence
#    actually makes sense (the meaning).
#
# A sentence can be grammatically correct but logically nonsensical.
# The parser handles the former, while static analysis handles
# the latter.


NUM_BASES: dict[NumberTag, int] = {
    NumberTag.int_bin: 2,
    NumberTag.int_oct: 8,
    NumberTag.int_dec: 10,
    NumberTag.int_hex: 16,
    NumberTag.float_dec: 10,
    NumberTag.float_hex: 16,
}

INT_BASES: set[NumberTag] = {
    NumberTag.int_bin,
    NumberTag.int_oct,
    NumberTag.int_dec,
    NumberTag.int_hex
}

FLOAT_BASES: set[NumberTag] = {
    NumberTag.float_dec,
    NumberTag.float_hex
}

DEC_FLOAT_SUFFIXES: set[FloatSuffix] = {
    FloatSuffix.decimal_32,
    FloatSuffix.decimal_64,
    FloatSuffix.decimal_128,
}

DEC_FLOAT_SUFFIXES: set[FloatSuffix] = {
    FloatSuffix.decimal_32,
    FloatSuffix.decimal_64,
    FloatSuffix.decimal_128,
}

ENCODING_TO_CHAR_KIND: dict[EncodingPrefix | None, CharKind] = {
    None: CharKind.char,
    EncodingPrefix.utf_8: CharKind.char8,
    EncodingPrefix.utf_16: CharKind.char16,
    EncodingPrefix.utf_32: CharKind.char32,
    EncodingPrefix.wide_literal: CharKind.wchar,
}

ENCODING_MAX: dict[EncodingPrefix | None, int] = {
    None:                        0xFF,
    EncodingPrefix.utf_8:        0xFF,
    EncodingPrefix.utf_16:       0xFFFF,
    EncodingPrefix.utf_32:       0x10FFFF,
    EncodingPrefix.wide_literal: 0x10FFFF,
}

SIMPLE_ESCAPES: dict[str, str] = {
    'a': '\a',
    'b': '\b',
    'f': '\f',
    'n': '\n',
    'r': '\r',
    't': '\t',
    'v': '\v',
}

BINDING_POWER: dict[str, tuple[int, int]]= {
    # Postfix and Member Access
    "++": (150, 149),
    "--": (150, 149),
    "(":  (150, 149),
    "[":  (150, 149),
    ".":  (150, 149),
    "->": (150, 149),

    # Multiplicative
    "*": (130, 129),
    "/": (130, 129),
    "%": (130, 129),

    # Additive
    "+": (120, 119),
    "-": (120, 119),

    # Bitwise Shift
    "<<": (110, 109),
    ">>": (110, 109),

    # Relational
    "<":  (100, 99),
    ">":  (100, 99),
    "<=": (100, 99),
    ">=": (100, 99),

    # Equality
    "==": (90, 89),
    "!=": (90, 89),

    # Bitwise AND
    "&": (80, 79),

    # Bitwise XOR
    "^": (70, 69),

    # Bitwise OR
    "|": (60, 59),

    # Logical AND
    "&&": (50, 49),

    # Logical OR
    "||": (40, 39),

    # Conditional
    "?": (30, 29),

    # Assignment
    "=":   (20, 19),
    "+=":  (20, 19),
    "-=":  (20, 19),
    "*=":  (20, 19),
    "/=":  (20, 19),
    "%=":  (20, 19),
    "<<=": (20, 19),
    ">>=": (20, 19),
    "&=":  (20, 19),
    "^=":  (20, 19),
    "|=":  (20, 19),

    # Sequence
    ",": (10, 9),
}

TYPE_START_KEYWORDS: set[str] = {
    # Type specifiers
    "void", "bool", "char", "short", "int", "long",
    "float", "double", "signed", "unsigned",
    "_BitInt", "_Complex", "_Imaginary",
    "_Decimal32", "_Decimal64", "_Decimal128",
    "_Atomic", "typeof", "typeof_unqual",
    "struct", "union", "enum",

    # Type qualifiers
    "const", "restrict", "volatile",

    # Storage class specifiers
    "auto", "constexpr", "extern", "register",
    "static", "thread_local", "typedef",

    # Function specifiers
    "inline", "_Noreturn",

    # Alignment specifier
    "alignas",
}

ARITHMETIC_TYPES: tuple[TypeNode, TypeNode, TypeNode, TypeNode] = (
    BoolType,
    CharType,
    IntType,
    BitIntType
)

STORAGE_KEYWORDS: dict[str, StorageSpec] = {
    "auto":         StorageSpec.auto,
    "constexpr":    StorageSpec.constexpr,
    "extern":       StorageSpec.extern,
    "register":     StorageSpec.register,
    "static":       StorageSpec.static,
    "thread_local": StorageSpec.thread_local,
    "typedef":      StorageSpec.typedef,
}

QUALIFIERS = {
    "const": TypeQualifier.const,
    "restrict": TypeQualifier.restrict,
    "volatile": TypeQualifier.volatile,
}

FUN_SPECS = {
    "inline": FunctionSpec.inline,
    "_Noreturn": FunctionSpec.noreturn,
}


class StrFormater:
    def __init__(self, string: str) -> None:
        self.index = 0
        self.string = string

    def peek(self) -> str:
        if self.index >= len(self.string):
            return '\0'

        return self.string[self.index]

    def fetch(self) -> str:
        ch: str = self.peek()
        self.index += 1

        return ch

    def fetch_oct_seq(self) -> str | Error:
        val: int = 0

        for _ in range(3):
            if not is_oct_digit(self.peek()):
                break

            val *= 8
            val += ord(self.fetch()) - ord('0')

        if not (0 <= val <= 0xffff_ffff):
            return Error()

        return chr(val)

    def fetch_hex_seq(self) -> str | Error:
        val: int = 0

        while is_hex_digit(self.peek()):
            val *= 16

            ch = self.fetch()
            if ch.isdigit():
                val += ord(ch) - ord('0')
            else:
                val += ord(ch.lower()) - ord('a') + 10

        if not (0 <= val <= 0xffff_ffff):
            return Error()

        return chr(val)

    def fetch_uni_seq(self, digits: int) -> str | Error:
        assert digits == 4 or digits == 8

        val: int = 0

        for _ in range(digits):
            if not is_hex_digit(self.peek()):
                return Error()

            val *= 16

            ch = self.fetch()

            if ch.isdigit():
                val += ord(ch) - ord('0')
            else:
                val += ord(ch.lower()) - ord('a') + 10

        if not (0x0000_0000 <= val <= 0x0010_ffff):
            return Error()

        if 0xd800 <= val <= 0xdfff:
            return Error()

        if 0x0000 <= val <= 0x009f and val not in [0x0024, 0x0040, 0x0060]:
            return Error()

        return chr(val)

    def fetch_esc_seq(self) -> str | Error:
        self.expect('\\')

        if is_oct_digit(self.peek()):
            return self.fetch_oct_seq()

        if self.match('x'):
            return self.fetch_hex_seq()

        if self.match('u'):
            return self.fetch_uni_seq(4)

        if self.match('U'):
            return self.fetch_uni_seq(8)

        ch = self.fetch()

        if ch not in SIMPLE_ESCAPES and ch not in ('\'', '\"', '?', '\\'):
            return Error()

        return SIMPLE_ESCAPES.get(ch, ch)

    def match(self, expected: str) -> bool:
        if self.peek() == expected:
            self.fetch()
            return True

        return False

    def match_digit(self) -> bool:
        if self.peek().isdigit():
            self.fetch()
            return True

        return False

    def expect(self, expected: str) -> str:
        assert self.peek() == expected
        return self.fetch()

    def reformat(self, encoding: EncodingPrefix | None) -> str | Error:
        new_str: list[str] = []
        max_val: int = ENCODING_MAX[encoding]

        while self.peek() != '\0':
            new_part: str | Error = ""

            if self.peek() != '\\':
                new_part = self.fetch()
            else:
                new_part = self.fetch_esc_seq()

            if isinstance(new_part, Error):
                return new_part

            if ord(new_part) > max_val:
                return Error()

            new_str.append(new_part)

        return "".join(new_str)


class Parser:
    def __init__(self, buffer: str, tokens: list[Token]) -> None:
        self.index = 0
        self.buffer = buffer
        self.tokens = tokens

    def op_bp(self, op: str) -> tuple[int, int]:
        return BINDING_POWER.get(op, (0, 0))

    def token_str(self, token: Token) -> str:
        return self.buffer[token.loc.start:token.loc.end]

    def token_bp(self, token: Token) -> tuple[int, int]:
        return self.op_bp(self.token_str(token))

    def token_is_type(self, token: Token) -> bool:
        if token.tag != TokenTag.keyword:
            return False

        return self.token_str(token) in TYPE_START_KEYWORDS

    def peek(self) -> Token:
        return self.tokens[self.index]

    def peek_nth(self, offset: int) -> Token | None:
        if self.index + offset < len(self.tokens):
            return self.tokens[self.index + offset]

        return None

    def peek_buffer(self, idx: int) -> str:
        assert idx >= 0
        return self.buffer[idx]

    def fetch(self) -> Token :
        token: Token = self.peek()
        self.index += 1

        return token

    def check(self,
              expected_tag: TokenTag,
              expected_str: str | None) -> bool:
        token = self.peek()

        if token.tag != expected_tag:
            return False;

        return expected_str is None or \
               self.token_str(token) == expected_str

    def check_nth(self,
                  offset: int,
                  expected_tag: TokenTag,
                  expected_str: str | None) -> bool:
        token: Token | None = self.peek_nth(offset)
        if token is None:
            return False

        if token.tag != expected_tag:
            return False;

        return expected_str is None or \
               self.token_str(token) == expected_str

    def check_l_bracket(self) -> bool:
        return self.check(TokenTag.punctuator, "[") or \
               self.check(TokenTag.punctuator, "<:")

    def check_r_bracket(self) -> bool:
        return self.check(TokenTag.punctuator, "]") or \
               self.check(TokenTag.punctuator, ":>")

    def check_l_brace(self) -> bool:
        return self.check(TokenTag.punctuator, "{") or \
               self.check(TokenTag.punctuator, "<%")

    def check_r_brace(self) -> bool:
        return self.check(TokenTag.punctuator, "}") or \
               self.check(TokenTag.punctuator, "%>")

    def match(self,
              expected_tag: TokenTag,
              expected_str: str | None) -> bool:
        token = self.peek()

        if not self.check(expected_tag, expected_str):
            return False

        self.fetch()
        return True

    def match_l_bracket(self) -> bool:
        return self.match(TokenTag.punctuator, "[") or \
               self.match(TokenTag.punctuator, "<:")

    def match_r_bracket(self) -> bool:
        return self.match(TokenTag.punctuator, "]") or \
               self.match(TokenTag.punctuator, ":>")

    def match_l_brace(self) -> bool:
        return self.match(TokenTag.punctuator, "{") or \
               self.match(TokenTag.punctuator, "<%")

    def match_r_brace(self) -> bool:
        return self.match(TokenTag.punctuator, "}") or \
               self.match(TokenTag.punctuator, "%>")

    def expect(self,
               expected_tag: TokenTag,
               expected_str: str | None) -> Token:
        assert self.check(expected_tag, expected_str)
        return self.fetch()

    def expect_l_bracket(self) -> Token:
        assert self.check_l_bracket()
        return self.fetch()

    def expect_r_bracket(self) -> Token:
        assert self.check_r_bracket()
        return self.fetch()

    def expect_l_brace(self) -> Token:
        assert self.check_l_brace()
        return self.fetch()

    def expect_r_brace(self) -> Token:
        assert self.check_r_brace()
        return self.fetch()

    Option = tuple[TokenTag, str]

    def expect_one_of(self,
                      expected_opts: list[Option]) -> None:
        for (expected_tag, expected_str) in expected_opts:
            if self.match(expected_tag, expected_str):
                return

        assert False

    def iden(self) -> str | Error:
        if not self.check(TokenTag.identifier, None):
            return Error()

        return self.token_str(self.fetch())

    def expr_or_decl(self) -> ExprNode | DeclNode | Error:
        if self.token_is_type(self.peek()):
            return self.decl()
        else:
            return self.expr(0)

    def expr_or_type(self) -> ExprNode | TypeNode | Error:
        if self.token_is_type(self.peek()):
            return self.type()
        else:
            return self.expr(0)

    # Types.
    def void_type(self) -> VoidType:
        self.expect(TokenTag.keyword, "void")
        return VoidType()

    def bool_type(self) -> BoolType:
        self.expect(TokenTag.keyword, "bool")
        return BoolType()

    def char_type(self, sign_kind: SignKind) -> CharType | Error:
        if self.match(TokenTag.keyword, "char"):
            return CharType(CharKind.char, sign_kind)

        if sign_kind != SignKind.default:
            return Error()

        for kind in CharKind:
            if self.match(TokenTag.keyword, kind.value):
                return CharType(kind, sign_kind)

        return Error()

    def short_int_type(self, sign_kind: SignKind) -> IntType:
        self.expect(TokenTag.keyword, "short")
        self.match(TokenTag.keyword, "int")

        return IntType(IntKind.short, sign_kind)

    def int_int_type(self, sign_kind: SignKind) -> IntType:
        self.expect(TokenTag.keyword, "int")
        return IntType(IntKind.int, sign_kind)

    def long_or_long_long_int_type(self,
                                   sign_kind: SignKind) -> IntType:
        self.expect(TokenTag.keyword, "long")

        int_kind: IntKind = IntKind.long

        if self.match(TokenTag.keyword, "long"):
            int_kind = IntKind.long_long

        self.match(TokenTag.keyword, "int")
        return IntType(int_kind, sign_kind)

    def int_type(self, sign_kind: SignKind) -> IntType | Error:
        if self.check(TokenTag.keyword, "short"):
            return self.short_int_type(sign_kind)

        if self.check(TokenTag.keyword, "int"):
            return self.int_int_type(sign_kind)

        if self.check(TokenTag.keyword, "long"):
            return self.long_or_long_long_int_type(sign_kind)

        return Error()

    def bit_int_type(self, sign_kind: SignKind) -> BitIntType | Error:
        self.expect(TokenTag.keyword, "_BitInt")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        width_expr: ExprNode | Error = self.expr(0)
        if isinstance(width_expr, Error):
            return Error()

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return BitIntType(width_expr, sign_kind)

    def float_real_float_type(self) -> RealFloatType:
        self.expect(TokenTag.keyword, "float")
        return RealFloatType(RealFloatKind.float)

    def double_real_float_type(self) -> RealFloatType:
        self.expect(TokenTag.keyword, "double")
        return RealFloatType(RealFloatKind.double)

    def long_double_real_float_type(self) -> RealFloatType | Error:
        self.expect(TokenTag.keyword, "long")

        if not self.match(TokenTag.keyword, "double"):
            return Error()

        return RealFloatType(RealFloatKind.long_double)

    def real_float_type(self) -> RealFloatType | Error:
        if self.check(TokenTag.keyword, "float"):
            return self.float_real_float_type()

        if self.check(TokenTag.keyword, "double"):
            return self.double_real_float_type()

        if self.check(TokenTag.keyword, "long"):
            return self.long_double_real_float_type()

        return Error()

    def real_or_complex_float_type(self) -> TypeNode | Error:
        real_float_type: RealFloatType | Error = self.real_float_type()
        if isinstance(real_float_type, Error):
            return real_float_type

        if self.check(TokenTag.keyword, "_Complex"):
            return self.complex_type_suffix(real_float_type.kind)

        if self.check(TokenTag.keyword, "_Imaginary"):
            return self.imaginary_type_suffix(real_float_type.kind)

        return real_float_type

    def decimal_float_type(self) -> DecimalFloatType | Error:
        for kind in DecimalFloatKind:
            if self.match(TokenTag.keyword, kind.value):
                return DecimalFloatType(kind)

        return Error()

    def complex_type_prefix(self) -> ComplexType | Error:
        self.expect(TokenTag.keyword, "_Complex")

        real_float_type: RealFloatType| Error = self.real_float_type()
        if isinstance(real_float_type, Error):
            return real_float_type

        return ComplexType(real_float_type.kind)

    def complex_type_suffix(self,
                            kind: RealFloatKind) -> ComplexType | Error:
        self.expect(TokenTag.keyword, "_Complex")
        return ComplexType(kind)

    def imaginary_type_prefix(self) -> ComplexType | Error:
        self.expect(TokenTag.keyword, "_Imaginary")

        real_float_type: RealFloatType| Error = self.real_float_type()
        if isinstance(real_float_type, Error):
            return real_float_type

        return ImaginaryType(real_float_type.kind)

    def imaginary_type_suffix(self,
                              kind: RealFloatKind) -> ImaginaryType | Error:
        self.expect(TokenTag.keyword, "_Imaginary")
        return ImaginaryType(kind)

    def arithmetic_type(self) -> TypeNode | Error:
        if self.check(TokenTag.keyword, "bool"):
            return self.bool_type()

        if self.check(TokenTag.keyword, "_Complex"):
            return self.complex_type_prefix()

        if self.check(TokenTag.keyword, "_Imaginary"):
            return self.imaginary_type_prefix()

        sign_kind: SignKind = SignKind.default

        if self.match(TokenTag.keyword, "signed"):
            sign_kind = SignKind.signed

        elif self.match(TokenTag.keyword, "unsigned"):
            sign_kind = SignKind.unsigned

        for kind in CharKind:
            if self.check(TokenTag.keyword, kind.value):
                return self.char_type(sign_kind)

        if self.check(TokenTag.keyword, "_BitInt"):
            return self.bit_int_type(sign_kind)

        if self.check_nth(0, TokenTag.keyword, "long") and \
           self.check_nth(1, TokenTag.keyword, "double"):
            if sign_kind != SignKind.default:
                return Error()

            return self.real_or_complex_float_type()

        for kind in IntKind:
            if self.check(TokenTag.keyword, kind.value):
                return self.int_type(sign_kind)

        if sign_kind != SignKind.default:
            # "signed" or "unsigned" alone means "signed int" / "unsigned int".
            return IntType(IntKind.int, sign_kind)

        for kind in RealFloatKind:
            if self.check(TokenTag.keyword, kind.value):
                return self.real_or_complex_float_type()

        for kind in DecimalFloatKind:
            if self.check(TokenTag.keyword, kind.value):
                return self.decimal_float_type()

        return Error()

    def qualifiers(self) -> set[TypeQualifier]:
        qualifiers: set[TypeQualifier] = set()

        while True:
            token = self.peek()
            val = self.token_str(token)

            if val in QUALIFIERS and self.match(TokenTag.keyword, val):
                qualifiers.add(QUALIFIERS[val])

            elif self.check(TokenTag.keyword, "_Atomic") and \
                 not self.check_nth(1, TokenTag.punctuator, "("):
                self.fetch()
                qualifiers.add(TypeQualifier.atomic)

            else:
                break

        return qualifiers

    def array_type_suffix(self,
                          elem_type: TypeNode) -> ArrayType | Error:
        self.expect_l_bracket()

        is_static = self.match(TokenTag.keyword, "static")
        qualifiers = self.qualifiers()

        if not is_static:
            is_static = self.match(TokenTag.keyword, "static")

        elem_count: ExprNode | None = None
        is_unspec_vla = False

        if self.match(TokenTag.punctuator, "*"):
            is_unspec_vla = True

        elif not self.check_r_bracket():
            min_bp, _ = self.op_bp(",")
            elem_count = self.expr(min_bp)

            if isinstance(elem_count, Error):
                return elem_count

        if not self.match_r_bracket():
            return Error()

        return ArrayType(
            elem_type,
            elem_count,
            is_static,
            is_unspec_vla,
            qualifiers
        )

    def fun_type_suffix(self, ret_type: TypeNode) -> FunType | Error:
        result: tuple[list[ParamSpec], bool] | Error = self.params()

        if isinstance(result, Error):
            return result

        params, is_variadic = result
        return FunType(ret_type, params, is_variadic)

    def type_suffix(self, base_type: TypeNode) -> TypeNode | Error:
        while True:
            if self.check(TokenTag.punctuator, "("):
                return self.fun_type_suffix(base_type)

            if not self.check_l_bracket():
                break

            base_type = self.array_type_suffix(base_type)

            if isinstance(base_type, Error):
                return base_type

        return base_type

    ####
    def _next_is_param_list(self) -> bool:
        next_tok = self.peek_nth(1)
        if next_tok is None:
            return False
        next_str = self.token_str(next_tok)
        if next_tok.tag == TokenTag.punctuator and next_str in (")", "..."):
            return True
        return self.token_is_type(next_tok)

    def declarator(self, base_type: TypeNode) -> tuple[TypeNode, str | None] | Error:
        outer_ptrs: list[set[TypeQualifier]] = []
        while self.match(TokenTag.punctuator, "*"):
            outer_ptrs.append(self.qualifiers())

        iden: str | None = None
        inner_ptrs: list[set[TypeQualifier]] = []

        if self.check(TokenTag.punctuator, "(") and not self._next_is_param_list():
            self.fetch()
            while self.match(TokenTag.punctuator, "*"):
                inner_ptrs.append(self.qualifiers())
            iden_result = self.iden()
            if not isinstance(iden_result, Error):
                iden = iden_result
            if not self.match(TokenTag.punctuator, ")"):
                return Error()
        elif self.check(TokenTag.identifier, None):
            iden = self.token_str(self.fetch())

        elem_type: TypeNode = base_type
        for q in outer_ptrs:
            elem_type = PtrType(elem_type, q)

        full_type: TypeNode | Error = self.type_suffix(elem_type)
        if isinstance(full_type, Error):
            return full_type

        for q in inner_ptrs:
            full_type = PtrType(full_type, q)

        return (full_type, iden)

    def abstract_declarator(self, base_type: TypeNode) -> TypeNode | Error:
        result = self.declarator(base_type)
        if isinstance(result, Error):
            return result
        full_type, _ = result
        return full_type

    def param_spec(self) -> ParamSpec | Error:
        prefix: QualifiedType | Error = self.type_prefix()
        if isinstance(prefix, Error):
            return prefix

        result = self.declarator(prefix)
        if isinstance(result, Error):
            return result

        param_type, iden = result
        return ParamSpec(iden, param_type)

    ####

    def params(self) -> tuple[list[ParamSpec], bool] | Error:
        if not self.match(TokenTag.punctuator, "("):
            return Error()

        params: list[ParamSpec] = []
        is_variadic: bool = False

        while not self.check(TokenTag.punctuator, ")"):
            if self.match(TokenTag.punctuator, "..."):
                is_variadic = True
                break

            param_spec: ParamSpec | Error = self.param_spec()
            if isinstance(param_spec, Error):
                return param_spec

            params.append(param_spec)

            if not self.match(TokenTag.punctuator, ","):
                break

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return (params, is_variadic)

    def enum_val_spec(self) -> EnumValSpec | Error:
        min_bp, _ = self.op_bp(",")

        iden: str | Error = self.iden()
        if isinstance(iden, Error):
            return iden

        expr: ExprNode | None | Error = None

        if self.match(TokenTag.punctuator, "="):
            expr = self.expr(min_bp)

            if isinstance(expr, Error):
                return expr

        return EnumValSpec(iden, expr)

    def enum_members(self) -> list[EnumValSpec] | Error:
        self.expect_l_brace()

        members: list[EnumValSpec] = []

        while self.check(TokenTag.identifier, None):
            enum_val_spec: EnumValSpec | Error = self.enum_val_spec()

            if isinstance(enum_val_spec, Error):
                return enum_val_spec

            members.append(enum_val_spec)

            if not self.match(TokenTag.punctuator, ","):
                break

        if not self.match_r_brace():
            return Error()

        return members

    def enum_type(self) -> EnumType | Error:
        self.expect(TokenTag.keyword, "enum")

        iden: str | Error | None = None

        if self.check(TokenTag.identifier, None):
            iden = self.iden()

            if isinstance(iden, Error):
                return iden

        member_type: TypeNode | None | Error = None

        if self.match(TokenTag.punctuator, ":"):
            member_type = self.type()

            if isinstance(member_type, Error):
                return member_type

            if not isinstance(member_type, ARITHMETIC_TYPES):
                return Error()

        members: list[EnumValSpec] | None | Error = None

        if self.check_l_brace():
            members = self.enum_members()

            if isinstance(members, Error):
                return members

        if iden is None and members is None:
            return Error()

        return EnumType(iden, members, member_type)

    def struct_or_union_members(self) -> list[DeclNode] | Error:
        self.expect_l_brace()

        members: list[DeclNode] = []

        while not self.check_r_brace():
            decl: DeclNode | Error = self.decl()

            if isinstance(decl, Error):
                return decl

            members.append(decl)

        if not self.match_r_brace():
            return Error()

        return members

    Signature = tuple[str | None, list[DeclNode] | None]

    def struct_or_union_signature(self) -> Signature | Error:
        iden: str | None | Error = None

        if self.check(TokenTag.identifier, None):
            iden = self.iden()

            if isinstance(iden, Error):
                return iden

        members: list[DeclNode] | None | Error = None

        if self.check_l_brace():
            members = self.struct_or_union_members()

            if isinstance(members, Error):
                return Error()

        if iden is None and members is None:
            return Error()

        return (iden, members)

    def struct_type(self) -> StructType | Error:
        self.expect(TokenTag.keyword, "struct")

        signature: Signature | Error = self.struct_or_union_signature()
        if isinstance(signature, Error):
            return signature

        iden, members = signature
        return StructType(iden, members)

    def union_type(self) -> UnionType | Error:
        self.expect(TokenTag.keyword, "union")

        signature: Signature | Error = self.struct_or_union_signature()
        if isinstance(signature, Error):
            return signature

        iden, members = signature
        return UnionType(iden, members)

    def atomic_type(self) -> AtomicType | Error:
        self.expect(TokenTag.keyword, "_Atomic")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        base_type: TypeNode | Error = self.type()
        if isinstance(base_type, Error):
            return base_type

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return AtomicType(base_type)

    def typeof_type(self) -> TypeOfType | Error:
        self.expect(TokenTag.keyword, "typeof")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        expr_or_type: ExprNode | TypeNode | Error = self.expr_or_type()
        if isinstance(expr_or_type, Error):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return TypeOfType(expr_or_type)

    def typeof_unqual_type(self) -> TypeOfUnqualType | Error:
        self.expect(TokenTag.keyword, "typeof_unqual")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        expr_or_type: ExprNode | TypeNode | Error = self.expr_or_type()
        if isinstance(expr_or_type, Error):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return TypeOfUnqualType(expr_or_type)

    def typedef_type(self) -> TypeDefType | Error:
        iden: str | Error = self.iden()
        if isinstance(iden, Error):
            return iden

        return TypeDefType(iden)

    def alignas_spec(self) -> ExprNode | TypeNode | Error:
        self.expect(TokenTag.keyword, "alignas")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        result: ExprNode | TypeNode | Error = self.expr_or_type()
        if isinstance(result, Error):
            return result

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return result

    def type_spec(self) -> TypeNode | Error:
        if self.check(TokenTag.keyword, "void"):
            return self.void_type()

        if self.check(TokenTag.keyword, "enum"):
            return self.enum_type()

        if self.check(TokenTag.keyword, "struct"):
            return self.struct_type()

        if self.check(TokenTag.keyword, "union"):
            return self.union_type()

        if self.check(TokenTag.keyword, "_Atomic"):
            return self.atomic_type()

        if self.check(TokenTag.keyword, "typeof"):
            return self.typeof_type()

        if self.check(TokenTag.keyword, "typeof_unqual"):
            return self.typeof_unqual_type()

        if self.check(TokenTag.identifier, None):
            return self.typedef_type()

        return self.arithmetic_type()

    ####
    def type_prefix(self) -> QualifiedType | Error:
        base_type, alignment, storage, fun_spec = None, None, None, None
        qualifiers: set[TypeQualifier] = set()

        while True:
            token = self.peek()
            tag, val = token.tag, self.token_str(token)

            if tag == TokenTag.keyword and val in STORAGE_KEYWORDS:
                storage = STORAGE_KEYWORDS[val]
                self.fetch()

            elif val in QUALIFIERS and self.match(TokenTag.keyword, val):
                qualifiers.add(QUALIFIERS[val])

            elif val in FUN_SPECS and self.match(TokenTag.keyword, val):
                fun_spec = FUN_SPECS[val]

            elif val == "_Atomic" and self.match(TokenTag.keyword, "_Atomic"):
                if self.check(TokenTag.punctuator, "("):
                    return Error()

                qualifiers.add(TypeQualifier.atomic)

            elif self.check(TokenTag.keyword, "alignas"):
                alignment = self.alignas_spec()

                if isinstance(alignment, Error):
                    return alignment

            elif base_type is None and self.token_is_type(token):
                base_type = self.type_spec()

                if isinstance(base_type, Error):
                    return base_type

            else:
                break

        if base_type is None:
            return Error()

        return QualifiedType(base_type, qualifiers, storage, alignment, fun_spec)

    def type(self) -> TypeNode | Error:
        prefix: QualifiedType | Error = self.type_prefix()
        if isinstance(prefix, Error):
            return prefix

        return self.abstract_declarator(prefix)
    ####

    # Declarations.
    def trans_unit_decl(self) -> TransUnitDecl | Error:
        decls: list[DeclNode] = []

        while not self.check(TokenTag.eof, None):
            decl: DeclNode | Error = self.decl()

            if isinstance(decl, Error):
                return decl

            decls.append(decl)

        return TransUnitDecl(decls)

    def empty_decl(self) -> EmptyDecl | Error:
        self.expect(TokenTag.punctuator, ";")
        return EmptyDecl()

    def fun_decl(self,
                 ret_type: TypeNode,
                 iden: str) -> FunDecl | Error:

        result: tuple[list[ParamSpec], bool] | Error = self.params()
        if isinstance(result, Error):
            return result

        body: CompoundStmt | None | Error = None

        if self.check_l_brace():
            body = self.compound_stmt()

            if isinstance(body, Error):
                return body

        elif not self.match(TokenTag.punctuator, ";"):
            return Error()

        params, is_variadic = result
        fun_type = FunType(ret_type, params, is_variadic)

        return FunDecl(fun_type, iden, body)

    def enum_decl(self) -> EnumDecl | Error:
        enum_type: EnumType | Error = self.enum_type()
        if isinstance(enum_type, Error):
            return enum_type

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return EnumDecl(enum_type)

    def struct_decl(self) -> StructDecl | Error:
        struct_type: StructType | Error = self.struct_type()
        if isinstance(struct_type, Error):
            return struct_type

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return StructDecl(struct_type)

    def union_decl(self) -> UnionDecl | Error:
        union_type: UnionType | Error = self.union_type()
        if isinstance(union_type, Error):
            return union_type

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return UnionDecl(union_type)

    def typedef_decl(self) -> TypedefDecl | Error:
        self.expect(TokenTag.keyword, "typedef")

        base_type: TypeNode | Error = self.type()
        if isinstance(base_type, Error):
            return base_type

        alias_iden: str | Error = self.iden()
        if isinstance(alias_iden, Error):
            return alias_iden

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return TypedefDecl(base_type, alias_iden)

    def static_assert_decl(self) -> StaticAssertDecl | Error:
        self.expect(TokenTag.keyword, "static_assert")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        min_bp, _ = self.op_bp(",")

        cond_expr: ExprNode | Error = self.expr(min_bp)
        if isinstance(cond_expr, Error):
            return cond_expr

        str_expr: StrLitExpr | None | Error = None

        if self.match(TokenTag.punctuator, ","):
            str_expr = self.str_expr()
            if isinstance(str_expr, Error):
                return str_expr

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return StaticAssertDecl(cond_expr, str_expr)

    ####
    def decl(self) -> DeclNode | Error:
        if self.check(TokenTag.punctuator, ";"):
            return self.empty_decl()

        if self.check(TokenTag.keyword, "static_assert"):
            return self.static_assert_decl()

        prefix: QualifiedType | Error = self.type_prefix()
        if isinstance(prefix, Error):
            return prefix

        result = self.declarator(prefix)
        if isinstance(result, Error):
            return result

        full_type, iden = result

        # typedef int (*fn_t)(int);
        if prefix.storage == StorageSpec.typedef:
            if iden is None:
                return Error()
            if not self.match(TokenTag.punctuator, ";"):
                return Error()
            return TypedefDecl(full_type, iden)

        # Standalone tag-type declaration: struct S {}; enum E : int {};
        if iden is None:
            if isinstance(prefix.base_type, (StructType, UnionType, EnumType)):
                if not self.match(TokenTag.punctuator, ";"):
                    return Error()
                if isinstance(prefix.base_type, StructType):
                    return StructDecl(prefix)
                if isinstance(prefix.base_type, UnionType):
                    return UnionDecl(prefix)
                return EnumDecl(prefix)
            return Error()

        # Function definition/declaration: int foo(int x) { ... }
        if isinstance(full_type, FunType):
            body: CompoundStmt | None | Error = None
            if self.check_l_brace():
                body = self.compound_stmt()
                if isinstance(body, Error):
                    return body
            elif not self.match(TokenTag.punctuator, ";"):
                return Error()
            return FunDecl(full_type, iden, body)

        # Variable declaration: const int *p = &x;
        if isinstance(full_type, QualifiedType):
            var_qual_type = full_type
        else:
            var_qual_type = QualifiedType(
                full_type,
                prefix.qualifiers,
                prefix.storage,
                prefix.alignment,
                prefix.fun_spec,
            )

        init: ExprNode | InitList | None = None
        if self.match(TokenTag.punctuator, "="):
            if self.check_l_brace():
                init = self.init_list()
            else:
                min_bp, _ = self.op_bp(",")
                init = self.expr(min_bp)
            if isinstance(init, Error):
                return init

        # Collect any additional comma-separated declarators sharing this prefix.
        var_decls: list[VarDecl] = [VarDecl(var_qual_type, iden, init)]

        while self.match(TokenTag.punctuator, ","):
            next_result = self.declarator(prefix)
            if isinstance(next_result, Error):
                return next_result

            next_full_type, next_iden = next_result
            if next_iden is None:
                return Error()

            if isinstance(next_full_type, QualifiedType):
                next_var_type = next_full_type
            else:
                next_var_type = QualifiedType(
                    next_full_type,
                    prefix.qualifiers,
                    prefix.storage,
                    prefix.alignment,
                    prefix.fun_spec,
                )

            next_init: ExprNode | InitList | None = None
            if self.match(TokenTag.punctuator, "="):
                if self.check_l_brace():
                    next_init = self.init_list()
                else:
                    min_bp, _ = self.op_bp(",")
                    next_init = self.expr(min_bp)
                if isinstance(next_init, Error):
                    return next_init

            var_decls.append(VarDecl(next_var_type, next_iden, next_init))

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        if len(var_decls) == 1:
            return var_decls[0]

        return TransUnitDecl(var_decls)
    ####

    # Initialisers.
    InitEntry = tuple[InitNode | None, ExprNode | None]

    def init_entry(self) -> InitEntry | Error:
        if self.check(TokenTag.punctuator, "."):
            rec_init: InitMember | Error = self.init_member()
            if isinstance(rec_init, Error):
                return rec_init

            return rec_init, None

        if self.check_l_bracket():
            rec_init: InitIndex | Error = self.init_index()
            if isinstance(rec_init, Error):
                return rec_init

            return rec_init, None

        if not self.match(TokenTag.punctuator, "="):
            return Error()

        expr_or_init: ExprNode | InitList | None | Error = None

        if self.check_l_brace():
            expr_or_init = self.init_list()
        else:
            min_bp, _ = self.op_bp(",")
            expr_or_init = self.expr(min_bp)

        if isinstance(expr_or_init, Error):
            return expr_or_init

        return None, expr_or_init

    def init_member(self) -> InitMember | Error:
        self.expect(TokenTag.punctuator, ".")

        member_iden: str | Error = self.iden()
        if isinstance(member_iden, Error):
            return member_iden

        init_entry: InitEntry | Error = self.init_entry()
        if isinstance(init_entry, Error):
            return init_entry

        rec_init, expr_or_init = init_entry
        assert (rec_init is None) != (expr_or_init is None)

        return InitMember(member_iden, rec_init, expr_or_init)

    def init_index(self) -> InitIndex | Error:
        self.expect_l_bracket()

        idx_expr: ExprNode | Error = self.expr(0)
        if isinstance(idx_expr, Error):
            return idx_expr

        if not self.match_r_bracket():
            return Error()

        init_entry: InitEntry | Error = self.init_entry()
        if isinstance(init_entry, Error):
            return init_entry

        rec_init, expr_or_init = init_entry
        assert (rec_init is None) != (expr_or_init is None)

        return InitIndex(idx_expr, rec_init, expr_or_init)

    def init_list(self) -> InitList | Error:
        self.expect_l_brace()

        init_elems: list[ExprNode | InitNode] = []

        if self.match_r_brace():
            return InitList(init_elems)

        min_bp, _ = self.op_bp(",")

        while True:
            elem: ExprNode | InitNode | None | Error = None

            if self.check(TokenTag.punctuator, "."):
                elem = self.init_member()

            elif self.check_l_bracket():
                elem = self.init_index()

            elif self.check_l_brace():
                elem = self.init_list()

            else:
                elem = self.expr(min_bp)

            if isinstance(elem, Error):
                return elem

            init_elems.append(elem)

            if not self.match(TokenTag.punctuator, ","):
                break

        if not self.match_r_brace():
            return Error()

        return InitList(init_elems)

    # Expressions.
    def iden_expr(self) -> IdenExpr | Error:
        iden: str | Error = self.iden()
        if isinstance(iden, Error):
            return iden

        return IdenExpr(iden)

    def nullptr_expr(self) -> NullPtrLitExpr:
        tag = TokenTag.keyword
        self.expect_one_of([(tag, "nullptr"), (tag, "NULL")])

        return NullPtrLitExpr()

    def bool_expr(self) -> BoolLitExpr:
        if self.match(TokenTag.keyword, "true"):
            return BoolLitExpr(True)
        else:
            self.expect(TokenTag.keyword, "false")
            return BoolLitExpr(False)

    def int_expr(self) -> IntLitExpr | Error:
        token: Token = self.expect(TokenTag.number_literal, None)

        assert token.num_base in INT_BASES
        assert token.int_suffix is not None

        num: int = 0
        base: int = NUM_BASES[token.num_base]

        start: int = 0
        num_str: str = self.token_str(token)

        if token.num_base != NumberTag.int_dec:
            start += 1 + (token.num_base != NumberTag.int_oct)

        # Compute how many chars at the end belong to the suffix (u, l, ll, wb…).
        suffix_len: int = 0
        if token.int_suffix is not None:
            for suf in token.int_suffix:
                suffix_len += len(next(iter(suf.value)))

        end: int = len(num_str) - suffix_len

        for i in range(start, end):
            if num_str[i] == '\'':
                continue

            num *= base

            if num_str[i].isdigit():
                num += ord(num_str[i]) - ord('0')
            else:
                num += ord(num_str[i].lower()) - ord('a') + 10

        sign_kind: SignKind = SignKind.default

        if IntSuffix.unsigned in token.int_suffix:
            sign_kind = SignKind.unsigned

        if IntSuffix.width_bit in token.int_suffix:
            # C23 §6.4.4.1: minimum _BitInt(N) width that holds the value.
            # Signed: sign bit + value bits; unsigned: value bits (min 1).
            if sign_kind == SignKind.unsigned:
                width_val = max(1, num.bit_length())
            else:
                width_val = num.bit_length() + 1
            width_expr_type = IntType(IntKind.int, SignKind.default)
            width_expr = IntLitExpr(width_val, width_expr_type)
            return IntLitExpr(num, BitIntType(width_expr, sign_kind))

        int_kind: IntKind | None = None

        if IntSuffix.long_long in token.int_suffix:
            int_kind = IntKind.long_long

        elif IntSuffix.long in token.int_suffix:
            int_kind = IntKind.long

        else:
            int_kind = IntKind.int

        return IntLitExpr(num, IntType(int_kind, sign_kind))

    def float_suffix_len(self, float_suffix: FloatSuffix) -> int:
        for s in float_suffix.value:
            return len(s)

    def real_float_expr(self) -> RealFloatLitExpr | Error:
        token: Token = self.expect(TokenTag.number_literal, None)

        assert token.num_base in FLOAT_BASES
        assert token.float_suffix not in DEC_FLOAT_SUFFIXES

        raw: str = self.token_str(token)

        suffix_len: int = 0
        if token.float_suffix is not None:
            suffix_len = self.float_suffix_len(token.float_suffix)

        num_str: str = raw[:-suffix_len] if suffix_len else raw
        num_str = num_str.replace("\'", "")

        real_val: float | None = None

        try:
            if token.num_base == NumberTag.float_hex:
                real_val = float.fromhex(num_str)
            else:
                real_val = float(num_str)

        except ValueError:
            return Error()

        if isinf(real_val):
            return Error()

        real_type: RealFloatType | None = None

        if token.float_suffix == FloatSuffix.float:
            real_type = RealFloatType(RealFloatKind.float)

        elif token.float_suffix == FloatSuffix.long_double:
            real_type = RealFloatType(RealFloatKind.long_double)

        else:
            real_type = RealFloatType(RealFloatKind.double)

        return RealFloatLitExpr(real_val, real_type)

    def dec_float_expr(self) -> DecFloatLitExpr | Error:
        token: Token = self.expect(TokenTag.number_literal, None)

        assert token.num_base == NumberTag.float_dec
        assert token.float_suffix in DEC_FLOAT_SUFFIXES

        raw: str = self.token_str(token)
        suffix_len: int = self.float_suffix_len(token.float_suffix)

        num_str: str = raw[:-suffix_len].replace("\'", "")

        try:
            dec_val: Decimal = Decimal(num_str)

        except InvalidOperation:
            return Error()

        dec_type: DecimalFloatKind | None = None

        if token.float_suffix == FloatSuffix.decimal_32:
            dec_type = DecimalFloatType(DecimalFloatKind.decimal32)

        elif token.float_suffix == FloatSuffix.decimal_64:
            dec_type = DecimalFloatType(DecimalFloatKind.decimal64)

        else:
            dec_type = DecimalFloatType(DecimalFloatKind.decimal128)

        return DecFloatLitExpr(dec_val, dec_type)

    def float_expr(self) -> RealFloatLitExpr | DecFloatLitExpr | Error:
        if self.peek().float_suffix in DEC_FLOAT_SUFFIXES:
            return self.dec_float_expr()
        else:
            return self.real_float_expr()

    NumLitExpr = IntLitExpr | RealFloatLitExpr | DecFloatLitExpr

    def num_expr(self) -> NumLitExpr | Error:
        assert self.check(TokenTag.number_literal, None)

        if self.peek().num_base in INT_BASES:
            return self.int_expr()
        else:
            return self.float_expr()

    def char_expr(self) -> CharLitExpr | Error:
        token: Token = self.expect(TokenTag.char_literal, None)

        raw: str = self.token_str(token)
        prefix_len: int = len(token.encoding.value) if token.encoding else 0
        content: str = raw[prefix_len + 1:]

        decoded: str | Error = StrFormater(content).reformat(token.encoding)
        if isinstance(decoded, Error):
            return decoded

        char_kind: CharKind = ENCODING_TO_CHAR_KIND[token.encoding]
        return CharLitExpr(decoded, CharType(char_kind, None))

    def str_expr(self) -> StrLitExpr | Error:
        token: Token = self.expect(TokenTag.string_literal, None)

        raw: str = self.token_str(token)
        prefix_len: int = len(token.encoding.value) if token.encoding else 0
        content: str = raw[prefix_len + 1:]

        decoded: str | Error = StrFormater(content).reformat(token.encoding)
        if isinstance(decoded, Error):
            return decoded

        char_kind: CharKind = ENCODING_TO_CHAR_KIND[token.encoding]
        return StrLitExpr(decoded, CharType(char_kind, None))

    AssocTable = dict[TypeNode | None, ExprNode]

    def assoc_table(self) -> AssocTable | Error:
        assoc_table: AssocTable = {}

        min_bp, _ = self.op_bp(",")

        while True:
            case_type: TypeNode | None | Error = None

            if not self.match(TokenTag.keyword, "default"):
                case_type = self.type()

                if isinstance(case_type, Error):
                    return case_type

            if case_type in assoc_table:
                return Error()

            if not self.match(TokenTag.punctuator, ":"):
                return Error()

            case_expr: ExprNode | Error = self.expr(min_bp)
            if isinstance(case_expr, Error):
                return case_expr

            assoc_table[case_type] = case_expr

            if not self.match(TokenTag.punctuator, ","):
                break

        return assoc_table

    def generic_sel_expr(self) -> GenericSelExpr | ErrorCode:
        self.expect(TokenTag.keyword, "_Generic")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        min_bp, _ = self.op_bp(",")

        ctrl_expr: ExprNode | Error = self.expr(min_bp)
        if isinstance(ctrl_expr, Error):
            return ctrl_expr

        if not self.match(TokenTag.punctuator, ","):
            return Error()

        assoc_table: AssocTable | Error = self.assoc_table()
        if isinstance(assoc_table, Error):
            return assoc_table

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return GenericSelExpr(ctrl_expr, assoc_table)

    def array_sub_expr(self,
                       base_expr: ExprNode) -> ArraySubExpr | Error:
        self.expect_l_bracket()

        idx_expr: ExprNode | Error = self.expr(0)
        if isinstance(idx_expr, Error):
            return idx_expr

        if not self.match_r_bracket():
            return Error()

        return ArraySubExpr(base_expr, idx_expr)

    def call_expr(self, callee_expr: ExprNode) -> CallExpr | Error:
        self.expect(TokenTag.punctuator, "(")

        arg_expr_list: list[ExprNode] = []

        if self.match(TokenTag.punctuator, ")"):
            return CallExpr(callee_expr, arg_expr_list)

        min_bp, _ = self.op_bp(",")

        while True:
            arg_expr: ExprNode | Error = self.expr(min_bp)
            if isinstance(arg_expr, Error):
                return arg_expr

            arg_expr_list.append(arg_expr)

            if self.match(TokenTag.punctuator, ")"):
                break

            if not self.match(TokenTag.punctuator, ","):
                return Error()

        return CallExpr(callee_expr, arg_expr_list)

    def member_expr(self, base_expr: ExprNode) -> MemberExpr | Error:
        is_arrow = self.check(TokenTag.punctuator, "->")

        tag = TokenTag.punctuator
        self.expect_one_of([(tag, "."), (tag, "->")])

        member_iden: str | Error = self.iden()
        if isinstance(member_iden, Error):
            return member_iden

        return MemberExpr(base_expr, member_iden, is_arrow)

    def compound_expr(self,
                      expr_type: TypeNode) -> CompoundLitExpr | Error:
        init: InitList | Error = self.init_list()
        if isinstance(init, Error):
            return init_list

        return CompoundLitExpr(expr_type, init)

    def cast_expr(self, expr_type: TypeNode) -> CastExpr | Error:
        expr: ExprNode | Error = self.expr(0)
        if isinstance(expr, Error):
            return expr

        return CastExpr(expr_type, expr)

    def cast_or_compound_expr(self) -> CastExpr | CompoundLitExpr | Error:
        self.expect(TokenTag.punctuator, "(")

        expr_type: TypeNode | Error = self.type()
        if isinstance(expr_type, Error):
            return expr_type

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        if self.check_l_brace():
            return self.compound_expr(expr_type)
        else:
            return self.cast_expr(expr_type)

    def cond_expr(self, cond_expr: ExprNode) -> CondExpr | Error:
        self.expect(TokenTag.punctuator, "?")

        true_expr: ExprNode | Error = self.expr(0)
        if isinstance(true_expr, Error):
            return true_expr

        if not self.match(TokenTag.punctuator, ":"):
            return Error()

        false_expr: ExprNode | Error = self.expr(0)
        if isinstance(false_expr, Error):
            return false_expr

        return CondExpr(cond_expr, true_expr, false_expr)

    def comma_expr(self, left_expr: ExprNode) -> CommaExpr | Error:
        self.expect(TokenTag.punctuator, ",")

        right_expr: ExprNode | Error = self.expr(0)
        if isinstance(right_expr, Error):
            return right_expr

        return CommaExpr((left_expr, right_expr))

    def sizeof_expr(self) -> SizeOfExpr | Error:
        self.expect(TokenTag.keyword, "sizeof")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        expr_or_type: ExprNode | TypeNode | Error = self.expr_or_type()
        if isinstance(expr_or_type, Error):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return SizeOfExpr(expr_or_type)

    def alignof_expr(self) -> AlignOfExpr | Error:
        self.expect(TokenTag.keyword, "alignof")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        align_type: TypeNode | Error = self.type()
        if isinstance(align_type, Error):
            return align_type

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return AlignOfExpr(align_type)

    def paren_expr(self) -> ExprNode | Error:
        self.expect(TokenTag.punctuator, "(")

        expr: ExprNode | Error = self.expr(0)
        if isinstance(expr, Error):
            return expr

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return expr

    def paren_or_cast_or_compound_expr(self) -> ExprNode | Error:
        assert self.check(TokenTag.punctuator, "(")

        token: Token | None = self.peek_nth(1)
        if token is None:
            return Error()

        if self.token_is_type(token):
            return self.cast_or_compound_expr()
        else:
            return self.paren_expr()

    # NOTE: The term "nud" referes to [nu]ll [d]enotation.
    #
    # It handles tokens that appear at the start of an expression
    # (e.g., literals, variables, prefix operators) because they
    # do not require a left-hand operand.
    #
    # Analogy (Natural Language):
    # Think of a "nud" as a subject or a noun, like the words "The Moon"
    # or "Seventeen".
    #
    # It is a standalone entity that carries its own meaning and can
    # initiate a thought without needing prior context.
    def expr_nud(self) -> ExprNode | Error:
        if self.check(TokenTag.identifier, None):
            return self.iden_expr()

        if self.check(TokenTag.keyword, "nullptr") or \
           self.check(TokenTag.keyword, "NULL"):
            return self.nullptr_expr()

        if self.check(TokenTag.keyword, "true") or \
           self.check(TokenTag.keyword, "false"):
            return self.bool_expr()

        if self.check(TokenTag.number_literal, None):
            return self.num_expr()

        if self.check(TokenTag.char_literal, None):
            return self.char_expr()

        if self.check(TokenTag.string_literal, None):
            return self.str_expr()

        if self.check(TokenTag.keyword, "sizeof"):
            return self.sizeof_expr()

        if self.check(TokenTag.keyword, "alignof"):
            return self.alignof_expr()

        if self.check(TokenTag.keyword, "_Generic"):
            return self.generic_sel_expr()

        if self.check(TokenTag.punctuator, "("):
            return self.paren_or_cast_or_compound_expr()

        for op in UnaPrefOpTag:
            if not self.match(TokenTag.punctuator, op.value):
                continue

            # Right binding power 130 mirrors C's precedence: unary prefix
            # binds tighter than all binary ops (≤130) but looser than
            # postfix (150), so "*p == 5" parses as "(*p) == 5", not
            # "*(p == 5)".
            una_expr: ExprNode | Error = self.expr(130)
            if isinstance(una_expr, Error):
                return una_expr

            return OpExpr(op, [una_expr])

        return Error()

    # NOTE: The term "led" referes to [le]ft [d]enotation.
    #
    # It parses tokens that consume the expression to their left
    # (e.g., infix operators like '+' or postfix operators like '++').
    #
    # Analogy (Natural Language):
    # Think of a "led" as a conjunction or relative clause, like
    # the words "and", "which" or "because".
    #
    # A "led" fundamentally "incomplete" without the words that came
    # before it. It acts as a bridge that requires a preceding subject
    # to have any meaning.
    def expr_led(self,
                 left_expr: ExprNode,
                 min_bp: int) -> ExprNode | Error:
        if self.check(TokenTag.punctuator, "("):
            return self.call_expr(left_expr)

        if self.check_l_bracket():
            return self.array_sub_expr(left_expr)

        if self.check(TokenTag.punctuator, ".") or \
           self.check(TokenTag.punctuator, "->"):
            return self.member_expr(left_expr)

        if self.check(TokenTag.punctuator, "?"):
            return self.cond_expr(left_expr)

        if self.check(TokenTag.punctuator, ","):
            return self.comma_expr(left_expr)

        for op in UnaPostOpTag:
            if self.match(TokenTag.punctuator, op.value):
                return OpExpr(op, [left_expr])

        for op in BinOpTag:
            if not self.match(TokenTag.punctuator, op.value):
                continue

            right_expr: ExprNode | Error = self.expr(min_bp)
            if isinstance(right_expr, Error):
                return right_expr

            return OpExpr(op, [left_expr, right_expr])

        return Error()

    # Pratt expression parser.
    def expr(self, min_bp: int) -> ExprNode | Error:
        left_expr: ExprNode | Error = self.expr_nud()
        if isinstance(left_expr, Error):
            return left_expr

        while True:
            l_bp, r_bp = self.token_bp(self.peek())
            if min_bp >= l_bp:
                break

            left_expr = self.expr_led(left_expr, r_bp)
            if isinstance(left_expr, Error):
                return left_expr

        return left_expr

    # Statements.
    # Using built-in statements for "assert" and "println" helps us
    # bypass two hurdles:
    #
    # - First, it removes the need for a preprocessor (which we don't
    #   have and might not want).
    #
    # - Second, it lets us provide essential debugging tools without
    #   having to build out a full standard library for I/O and signal
    #   handling.
    #
    # It's a pragmatic shortcut to give users verification power
    # early on.
    FmtSpec = tuple[StrLitExpr | None, list[ExprNode]]

    def fmt_spec(self) -> FmtSpec | Error:
        str_expr: StrLitExpr | None = None
        arg_exprs: list[ExprNode] = []

        if not self.match(TokenTag.punctuator, ","):
            return (str_expr, arg_exprs)

        str_expr = self.str_expr()
        if isinstance(str_expr, Error):
            return str_expr

        min_bp, _ = self.op_bp(",")

        while self.match(TokenTag.punctuator, ","):
            arg_expr: ExprNode | Error = self.expr(min_bp)
            if isinstance(arg_expr, Error):
                return arg_expr

            arg_exprs.append(arg_expr)

        return (str_expr, arg_exprs)

    def cond(self) -> ExprNode | Error:
        if not self.match(TokenTag.punctuator, "("):
            return Error()

        expr: ExprNode | Error = self.expr(0)
        if isinstance(expr, Error):
            return expr

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        return expr

    def for_init(self) -> ExprNode | DeclNode | None | Error:
        init: ExprNode | DeclNode | None | Error = None

        if not self.check(TokenTag.punctuator, ";"):
            init = self.expr_or_decl()

            if isinstance(init, Error):
                return init

        # decl() already consumed its own ';'; only consume it for expr inits.
        if not isinstance(init, DeclNode):
            if not self.match(TokenTag.punctuator, ";"):
                return Error()

        return init

    def for_cond(self) -> ExprNode | None | Error:
        cond_expr: ExprNode | None | Error = None

        if not self.check(TokenTag.punctuator, ";"):
            cond_expr = self.expr(0)

            if isinstance(cond_expr, Error):
                return cond_expr

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return cond_expr

    def for_inc(self) -> ExprNode | None | Error:
        inc_expr: ExprNode | None | Error = None

        if not self.check(TokenTag.punctuator, ")"):
            inc_expr = self.expr(0)

            if isinstance(inc_expr, Error):
                return inc_expr

        return inc_expr

    def assert_stmt(self) -> AssertStmt | Error:
        self.expect(TokenTag.keyword, "assert")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        min_bp, _ = self.op_bp(",")

        cond_expr: ExprNode | Error = self.expr(min_bp)
        if isinstance(cond_expr, Error):
            return cond_expr

        result: FmtSpec | Error = self.fmt_spec()
        if isinstance(result, Error):
            return result

        str_expr, arg_exprs = result

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return AssertStmt(cond_expr, str_expr, arg_exprs)

    def println_stmt(self) -> PrintLnStmt | Error:
        self.expect(TokenTag.keyword, "println")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        result: FmtSpec | Error = self.fmt_spec()
        if isinstance(result, Error):
            return result

        str_expr, arg_exprs = result

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return PrintLnStmt(str_expr, arg_exprs)

    def compound_stmt(self) -> CompoundStmt | Error:
        self.expect_l_brace()

        stmts: list[StmtNode] = []

        while not self.check_r_brace():
            stmt: StmtNode | Error = self.stmt()
            if isinstance(stmt, Error):
                return stmt

            stmts.append(stmt)

        self.expect_r_brace()
        return CompoundStmt(stmts)

    def expr_stmt(self) -> ExprStmt | Error:
        expr: ExprNode | Error = self.expr(0)
        if isinstance(expr, Error):
            return expr

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return ExprStmt(expr)

    def decl_stmt(self) -> DeclStmt | Error:
        decl: DeclNode | Error = self.decl()
        if isinstance(decl, Error):
            return decl

        return DeclStmt(decl)

    def expr_or_decl_stmt(self) -> ExprStmt | DeclStmt | Error:
        if self.check(TokenTag.punctuator, ";") or \
           self.token_is_type(self.peek()):
            return self.decl_stmt()
        else:
            return self.expr_stmt()

    def if_stmt(self) -> IfStmt | Error:
        self.expect(TokenTag.keyword, "if")

        cond_expr: ExprNode | Error = self.cond()
        if isinstance(cond_expr, Error):
            return cond_expr

        then_stmt: StmtNode | Error = self.stmt()
        if isinstance(then_stmt, Error):
            return then_stmt

        else_stmt: StmtNode | None | Error = None

        if self.match(TokenTag.keyword, "else"):
            else_stmt = self.stmt()

            if isinstance(else_stmt, Error):
                return else_stmt

        return IfStmt(cond_expr, then_stmt, else_stmt)

    def case_stmt(self) -> CaseLabelStmt | Error:
        self.expect(TokenTag.keyword, "case")

        cond_expr: ExprNode | Error = self.expr(0)
        if isinstance(cond_expr, Error):
            return cond_expr

        if not self.match(TokenTag.punctuator, ":"):
            return Error()

        return CaseLabelStmt(cond_expr)

    def default_stmt(self) -> CaseLabelStmt | Error:
        self.expect(TokenTag.keyword, "default")

        if not self.match(TokenTag.punctuator, ":"):
            return Error()

        return CaseLabelStmt(None)

    def switch_stmt(self) -> SwitchStmt | Error:
        self.expect(TokenTag.keyword, "switch")

        cond_expr: ExprNode | Error = self.cond()
        if isinstance(cond_expr, Error):
            return cond_expr

        then_stmt: StmtNode | Error = self.stmt()
        if isinstance(then_stmt, Error):
            return then_stmt

        return SwitchStmt(cond_expr, then_stmt)

    def while_stmt(self) -> WhileStmt | Error:
        self.expect(TokenTag.keyword, "while")

        cond_expr: ExprNode | Error = self.cond()
        if isinstance(cond_expr, Error):
            return cond_expr

        then_stmt: StmtNode | Error = self.stmt()
        if isinstance(then_stmt, Error):
            return then_stmt

        return WhileStmt(cond_expr, then_stmt)

    def do_while_stmt(self) -> DoWhileStmt | Error:
        self.expect(TokenTag.keyword, "do")

        do_stmt: StmtNode | Error = self.stmt()
        if isinstance(do_stmt, Error):
            return do_stmt

        if not self.match(TokenTag.keyword, "while"):
            return Error()

        cond_expr: ExprNode | Error = self.cond()
        if isinstance(cond_expr, Error):
            return cond_expr

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return DoWhileStmt(do_stmt, cond_expr)

    def for_stmt(self) -> ForStmt | Error:
        self.expect(TokenTag.keyword, "for")

        if not self.match(TokenTag.punctuator, "("):
            return Error()

        init: ExprNode | DeclNode | None | Error = self.for_init()
        if isinstance(init, Error):
            return init

        cond_expr: ExprNode | None | Error = self.for_cond()
        if isinstance(cond_expr, Error):
            return cond_expr

        inc_expr: ExprNode | None | Error = self.for_inc()
        if isinstance(inc_expr, Error):
            return inc_expr

        if not self.match(TokenTag.punctuator, ")"):
            return Error()

        then_stmt: StmtNode | Error = self.stmt()
        if isinstance(then_stmt, Error):
            return then_stmt

        return ForStmt(init, cond_expr, inc_expr, then_stmt)

    def goto_stmt(self) -> GotoStmt | Error:
        self.expect(TokenTag.keyword, "goto")

        if not self.check(TokenTag.identifier, None):
            return Error()

        label_iden: str | Error = self.iden()
        if isinstance(label_iden, Error):
            return label_iden

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return GotoStmt(label_iden)

    def label_stmt(self) -> LabelStmt | Error:
        iden: str | Error = self.iden()
        if isinstance(iden, Error):
            return iden

        self.expect(TokenTag.punctuator, ":")
        return LabelStmt(iden)

    def break_stmt(self) -> BreakStmt | Error:
        self.expect(TokenTag.keyword, "break")

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return BreakStmt()

    def continue_stmt(self) -> ContinueStmt | Error:
        self.expect(TokenTag.keyword, "continue")

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return ContinueStmt()

    def return_stmt(self) -> ReturnStmt | Error:
        self.expect(TokenTag.keyword, "return")

        ret_expr: ExprNode | None | Error = None

        if not self.check(TokenTag.punctuator, ";"):
            ret_expr = self.expr(0)

            if isinstance(ret_expr, Error):
                return ret_expr

        if not self.match(TokenTag.punctuator, ";"):
            return Error()

        return ReturnStmt(ret_expr)

    def stmt(self) -> Stmt | Error:
        if self.check(TokenTag.keyword, "assert"):
            return self.assert_stmt()

        if self.check(TokenTag.keyword, "println"):
            return self.println_stmt()

        if self.check_l_brace():
            return self.compound_stmt()

        if self.check(TokenTag.keyword, "if"):
            return self.if_stmt()

        if self.check(TokenTag.keyword, "case"):
            return self.case_stmt()

        if self.check(TokenTag.keyword, "default"):
            return self.default_stmt()

        if self.check(TokenTag.keyword, "switch"):
            return self.switch_stmt()

        if self.check(TokenTag.keyword, "while"):
            return self.while_stmt()

        if self.check(TokenTag.keyword, "do"):
            return self.do_while_stmt()

        if self.check(TokenTag.keyword, "for"):
            return self.for_stmt()

        if self.check(TokenTag.keyword, "goto"):
            return self.goto_stmt()

        if self.check(TokenTag.keyword, "break"):
            return self.break_stmt()

        if self.check(TokenTag.keyword, "continue"):
            return self.continue_stmt()

        if self.check(TokenTag.keyword, "return"):
            return self.return_stmt()

        if self.check_nth(0, TokenTag.identifier, None) and \
           self.check_nth(1, TokenTag.punctuator, ":"):
            return self.label_stmt()

        return self.expr_or_decl_stmt()

    def parse(self) -> TransUnitDecl | Error:
        return self.trans_unit_decl()


# def test_ast_compare(buffer: str, expected: str) -> None:
#     ast = AST(buffer)
#
#     assert ast.build() is None
#     assert ast.dump() == expected
#
#
# def test_ast(buffer: str) -> None:
#     expected =
#     test_ast_compare(buffer, expected)
#
#
# def test_expr_iden_success() -> None:
#     pass
#
#
# def test_expr_int_success() -> None:
#     ""
#     pass
#
#
# def test_expr_float_success() -> None:
#     pass
#
#
# def test_expr_char_success() -> None:
#     pass
#
#
# def test_expr_str_success() -> None:
#     pass
#
#
# def test_expr_generic_sel_success() -> None:
#     pass
#
#
# def test_expr_una_array_sub_success() -> None:
#     # Test: Recognition
#     test_ast(f"arr[0]")
#     test_ast(f"arr[1]")
#     test_ast(f"arr[-1]")
#     test_ast(f"arr[{INT_MAX}]")
#
#     # Test: Recognition
#     test_ast(f"0[arr]")
#     test_ast(f"1[arr]")
#     test_ast(f"{INT_MAX}[arr]")
#
#     # Test:
#     test_ast("arr[1 + 2]")
#     test_ast("arr['a' - 'a']")
#
#     # Test:
#     test_ast("arr[(1 + 2) + 3]")
#     test_ast("(arr)[1 + 2]")
#
#     # Test:
#     test_ast("arr[n]")
#     test_ast("arr[fun(1, 2, 3)]")
#
#     # Test:
#     test_ast("arr[0][0]")
#     test_ast("arr[x][y][z]")
#
#     # Test:
#     test_ast("arr[0, 1]")
#
#     # Test:
#     test_ast("-arr[0]", )
#     test_ast("-(arr)[0]", )
#
#     # Test:
#     test_ast("-1[arr]", )
#     test_ast("(-1)[arr]", )
#
#
# def test_expr_una_call_success() -> None:
#     # Test:
#     test_ast("foo()")
#     test_ast("+foo()")
#     test_ast("-foo()")
#
#     # Test:
#     test_ast("foo(1 + 2)")
#     test_ast("foo('a' - 'a')")
#
#     # Test:
#     test_ast("foo(x + y, z)")
#     test_ast("foo(x, y + z)")
#     test_ast("foo(x, y, z)")
#
#     # Test:
#     test_ast("foo(1, 2, 3)")
#     test_ast("foo(1.23, 0.01)")
#
#     # Test:
#     test_ast("foo(n, 1 )")
#     test_ast("foo(1, n )")
#
#     # Test:
#     test_ast("foo(a, b, c, d, e, f, g, h, i, j, k, l)")
#
#
# def test_expr_una_member_success() -> None:
#     # Test:
#     test_ast("vec.length")
#     test_ast("vec->length")
#
#     # Test:
#     test_ast("node.next->data")
#
#     # Test:
#     test_ast("points[0].x")
#     test_ast("points[0]->x")
#
#     test_ast("vec.data[0]")
#     test_ast("vec->data[0]")
#
#
# def test_expr_una_compound_success() -> None:
#     # Test:
#     test_ast("(struct Vector){}")
#     test_ast("(struct Vector){1.0f, 2.0f, 3.0f}")
#
#     # Test:
#     test_ast("(struct Point){.x = 1, .y = 2}")
#     test_ast("(struct Point){.x = x, .y = y}")
#     test_ast("(struct Point){.x = 1, .y = y}")
#     test_ast("(struct Point){.x = x, .y = 2}")
#     test_ast("(struct Point){.x = foo(), .y = bar()}")
#
#     # Test:
#     test_ast("(int[2]){}")
#     test_ast("(int[2]){1}")
#     test_ast("(int[]){1, 2, 3}[0]")
#
#     # Test:
#     test_ast("(struct Point){.x = 1, .y = 2}.x", )
#
#
# def test_expr_una_cast_success() -> None:
#     # Test:
#     test_ast("(double)42")
#
#     # Test:
#     test_ast("(void)foo()")
#
#     # Test:
#     test_ast("(int)x")
#     test_ast("(char *)ptr")
#     test_ast("(struct stat)sb")
#
#     # Test:
#     test_ast("(int)x")
#     test_ast("(char *)ptr")
#     test_ast("(struct stat)sb")
#
#     test_ast("(const int)x")
#
#     # Test:
#     test_ast("(volatile void *)ptr")
#     test_ast("(int ***)ptr")
#     test_ast(f"(int (*)[16])ptr")
#     test_ast("(int (*)(int))ptr")
#     test_ast("(double)(int)x")
#
#
# def test_expr_una_prefix_inc_success() -> None:
#     # Test:
#     test_ast("++a")
#     test_ast("-++a")
#     test_ast("+(++a)")
#
#     # Test:
#     test_ast("++5")
#     test_ast("+++a")
#     test_ast("++(+a)")
#
#
# def test_expr_una_prefix_dec_success() -> None:
#     # Test:
#     test_ast("--a")
#     test_ast("+--a")
#     test_ast("-(--a)")
#
#     # Test:
#     test_ast("--5")
#     test_ast("---a")
#     test_ast("--(+a)")
#
#
# def test_expr_una_addr_of_success() -> None:
#     # Test:
#     test_ast("&x")
#     test_ast("&1")
#
#     # Test:
#     test_ast("&ptr->member")
#     test_ast("&((struct Point){.x = 1, .y = 2})")
#
#     # Test:
#     test_ast("&(x + 1)")
#     test_ast("&*x")
#     test_ast("&&x")
#
#
# def test_expr_una_deref_success() -> None:
#     # Test:
#     test_ast("*ptr")
#     test_ast("**ptr")
#     test_ast("*5")
#
#     # Test:
#     test_ast("*++ptr")
#     test_ast("++*ptr++")
#
#     # Test:
#     test_ast("*--ptr")
#     test_ast("--*ptr--")
#
#
# def test_expr_una_neg_success() -> None:
#     # Test:
#     test_ast("-0")
#     test_ast("-'a'")
#
#     # Test:
#     test_ast("- -a")
#     test_ast("-(a + b)")
#
#
# def test_expr_una_bit_neg_success() -> None:
#     # Test:
#     test_ast("~0")
#     test_ast("~(1 + 2)")
#
#     # Test:
#     test_ast("~a")
#     test_ast("~++a")
#
#
# def test_expr_una_bool_neg_success() -> None:
#     # Test:
#     test_ast("!true")
#     test_ast("!0")
#
#     # Test:
#     test_ast("node.value--")
#     test_ast("node->value--")
#
#     # Test:
#     test_ast("*ptr--")
#
#
# def test_expr_una_sizeof() -> None:
#     # Test:
#     test_ast("sizeof(int)")
#     test_ast("sizeof(struct stat)")
#
#     test_ast("sizeof(int *)")
#     test_ast("sizeof(int[16])")
#
#     test_ast("sizeof(const int)")
#     test_ast("sizeof(volatile int)")
#
#     test_ast("sizeof(struct {int a; int b;})")
#
#     # Test:
#     test_ast("sizeof 0")
#     test_ast("sizeof 'a'")
#     test_ast("sizeof 1.23")
#
#     test_ast("sizeof a")
#     test_ast("sizeof(a)")
#
#     test_ast("sizeof(a++)")
#     test_ast("sizeof(*a)")
#     test_ast("sizeof(a = 10)")
#
#     test_ast("sizeof(foo())")
#     test_ast("sizeof(sizeof(int))")
#
#
# def test_expr_una_alignof() -> None:
#     # Test:
#     test_ast("sizeof(int)")
#     test_ast("sizeof(struct stat)")
#
#     test_ast("sizeof(int *)")
#     test_ast("sizeof(int[16])")
#
#     test_ast("sizeof(const int)")
#     test_ast("sizeof(volatile int)")
#
#     test_ast("sizeof(struct {int a; int b;})")
#
#
# def test_expr_una_op_success() -> None:
#     test_expr_una_array_sub_success()
#     test_expr_una_call_success()
#     test_expr_una_member_success()
#     test_expr_una_compound_success()
#     test_expr_una_cast_success()
#     test_expr_una_prefix_inc_success()
#     test_expr_una_prefix_dec_success()
#     test_expr_una_addr_of_success()
#     test_expr_una_deref_success()
#     test_expr_una_neg_success()
#     test_expr_una_bit_neg_success()
#     test_expr_una_bool_neg_success()
#     test_expr_una_posfix_inc_success()
#     test_expr_una_postfix_dec_success()
#     test_expr_una_sizeof()
#     test_expr_una_alignof()
#
#
# def test_expr_bin_op(op: str) -> None:
#     # Test:
#     test_ast(f"1 {op} 2")
#     test_ast(f"a {op} b")
#
#     test_ast(f"a {op} 2")
#     test_ast(f"1 {op} b")
#
#     # Test:
#     test_ast(f"1 {op} 'a'")
#     test_ast(f"'a' {op} 2")
#     test_ast(f"'a' {op} 'a'")
#
#     # Test:
#     test_ast(f"1 {op} bar()")
#     test_ast(f"foo() {op} 2")
#     test_ast(f"foo() {op} bar()")
#
#     # Test:
#     test_ast(f"*ptr {op} 2")
#     test_ast(f"1 {op} *ptr")
#     test_ast(f"*ptr {op} *ptr")
#
#     test_ast(f"node.value {op} 2")
#     test_ast(f"1 {op} node.value")
#
#     test_ast(f"node->value {op} 2")
#     test_ast(f"1 {op} node->value")
#
#
# def test_expr_bin_bit_and_success() -> None:
#     # Test:
#     test_expr_bin_op("&")
#
#     # Test:
#     test_ast("a & &b")
#
#
# def test_expr_bin_mul_success() -> None:
#     # Test:
#     test_expr_bin_op("*")
#
#     # Test:
#     test_ast("a * *b")
#     test_ast("a * +b")
#     test_ast("a * +b")
#
#
# def test_expr_bin_add_success() -> None:
#     # Test:
#     test_expr_bin_op("+")
#
#     # Test:
#     test_ast("a + *b")
#     test_ast("a + +b")
#     test_ast("a + -b")
#
#
# def test_expr_bin_sub_success() -> None:
#     # Test:
#     test_expr_bin_op("-")
#
#     # Test:
#     test_ast("a - *b")
#     test_ast("a - +b")
#     test_ast("a - -b")
#
#
# def test_expr_bin_div_success() -> None:
#     # Test:
#     test_expr_bin_op("/")
#
#
# def test_expr_bin_mod_success() -> None:
#     # Test:
#     test_expr_bin_op("%")
#
#
# def test_expr_bin_shl_success() -> None:
#     # Test:
#     test_expr_bin_op("<<")
#
#
# def test_expr_bin_shr_success() -> None:
#     # Test:
#     test_expr_bin_op(">>")
#
#
# def test_expr_bin_lt_success() -> None:
#     # Test:
#     test_expr_bin_op("<")
#
#
# def test_expr_bin_gt_success() -> None:
#     # Test:
#     test_expr_bin_op(">")
#
#
# def test_expr_bin_le_success() -> None:
#     # Test:
#     test_expr_bin_op("<=")
#
#
# def test_expr_bin_ge_success() -> None:
#     # Test:
#     test_expr_bin_op(">=")
#
#
# def test_expr_bin_eq_success() -> None:
#     # Test:
#     test_expr_bin_op("==")
#
#
# def test_expr_bin_ne_success() -> None:
#     # Test:
#     test_expr_bin_op("!=")
#
#
# def test_expr_bin_bit_xor_success() -> None:
#     # Test:
#     test_expr_bin_op("^")
#
#
# def test_expr_bin_bit_or_success() -> None:
#     # Test:
#     test_expr_bin_op("|")
#
#
# def test_expr_bin_bool_and_success() -> None:
#     # Test:
#     test_expr_bin_op("&&")
#
#
# def test_expr_bin_bool_or_success() -> None:
#     # Test:
#     test_expr_bin_op("||")
#
#
#
#
# def test_expr_assign_op(op: str) -> None:
#     # Test:
#     test_ast(f"a {op} 2")
#     test_ast(f"a {op} 'a'")
#
#     test_ast(f"a {op} b")
#     test_ast(f"a {op} *ptr")
#
#     test_ast(f"a {op} foo()")
#
#     # Test:
#     test_ast(f"*ptr {op} 2")
#     test_ast(f"*ptr {op} 'a'")
#
#     test_ast(f"*ptr {op} b")
#     test_ast(f"*ptr {op} *ptr")
#
#     test_ast(f"*ptr {op} foo()")
#
#     # Test:
#     test_ast(f"node.data {op} 2")
#     test_ast(f"node.data {op} 'a'")
#
#     test_ast(f"node.data {op} b")
#     test_ast(f"node.data {op} *ptr")
#
#     test_ast(f"node.data {op} foo()")
#
#     # Test:
#     test_ast(f"node->data {op} 2")
#     test_ast(f"node->data {op} 'a'")
#
#     test_ast(f"node->data {op} b")
#     test_ast(f"node->data {op} *ptr")
#
#     test_ast(f"node->data {op} foo()")
#
#
# def test_expr_bin_assign_success() -> None:
#     # Test:
#     test_expr_assign_op("=")
#
#
# def test_expr_bin_assign_mul_success() -> None:
#     # Test:
#     test_expr_assign_op("*=")
#
#
# def test_expr_bin_assign_div_success() -> None:
#     # Test:
#     test_expr_assign_op("/=")
#
#
# def test_expr_bin_assign_mod_success() -> None:
#     # Test:
#     test_expr_assign_op("%=")
#
#
# def test_expr_bin_assign_add_success() -> None:
#     # Test:
#     test_expr_assign_op("+=")
#
#
# def test_expr_bin_assign_sub_success() -> None:
#     # Test:
#     test_expr_assign_op("-=")
#
#
# def test_expr_bin_assign_shl_success() -> None:
#     # Test:
#     test_expr_assign_op("<<=")
#
#
# def test_expr_bin_assign_shr_success() -> None:
#     # Test:
#     test_expr_assign_op(">>=")
#
#
# def test_expr_bin_assign_bit_and_success() -> None:
#     # Test:
#     test_expr_assign_op("&=")
#
#
# def test_expr_bin_assign_bit_xor_success() -> None:
#     # Test:
#     test_expr_assign_op("^=")
#
#
# def test_expr_bin_assign_bit_or_success() -> None:
#     # Test:
#     test_expr_assign_op("|=")
#
#
# def test_expr_bin_op_success() -> None:
#     test_expr_bin_mul_success()
#     test_expr_bin_add_success()
#     test_expr_bin_sub_success()
#     test_expr_bin_div_success()
#     test_expr_bin_mod_success()
#
#     test_expr_bin_shl_success()
#     test_expr_bin_shr_success()
#
#     test_expr_bin_lt_success()
#     test_expr_bin_gt_success()
#     test_expr_bin_le_success()
#     test_expr_bin_ge_success()
#     test_expr_bin_eq_success()
#     test_expr_bin_ne_success()
#
#     test_expr_bin_bit_and_success()
#     test_expr_bin_bit_xor_success()
#     test_expr_bin_bit_or_success()
#
#     test_expr_bin_bool_and_success()
#     test_expr_bin_bool_or_success()
#
#     test_expr_bin_assign_success()
#     test_expr_bin_assign_mul_success()
#     test_expr_bin_assign_div_success()
#     test_expr_bin_assign_mod_success()
#     test_expr_bin_assign_add_success()
#     test_expr_bin_assign_sub_success()
#     test_expr_bin_assign_shl_success()
#     test_expr_bin_assign_shr_success()
#     test_expr_bin_assign_bit_and_success()
#     test_expr_bin_assign_bit_xor_success()
#     test_expr_bin_assign_bit_or_success()
#
#
# def test_expr_ter_op_success() -> None:
#     # Test:
#     test_ast("1 ? 2 : 3")
#     test_ast("'a' ? 'b' ? 'c'")
#
#     # Test:
#     test_ast("a ? b : c")
#
#     test_ast("a ? b : c ? d : e")
#     test_ast("a ? b ? c : d : e")
#
#     # Test:
#     test_ast("*a ? *b ? *c")
#     test_ast("a ? b = 0 : c = 1")
#
#     test_ast("foo() ? bar() : baz()")
#
#
# def test_expr_comma_success() -> None:
#     # Test:
#     test_ast_compare("x = a, b", )
#     test_ast_compare("x = (a, b)", )
#     test_ast_compare("(x = a), b", )
#
#     test_ast_compare("foo(a, (b, c), d)", )
#     test_ast_compare("x = {.value = (1, 2)}", )
#
#     # Test:
#     test_ast_compare("return (cleanup(), result);", )
#
#     test_ast_compare("for (int x = 0; x < size; ++x, ++i) {}", )
#     test_ast_compare("while ((x, y) == NULL) {}", )
#
#
# def test_expr_binding_power_op_success() -> None:
#     # Test:
#     test_ast("a + b * c")
#     test_ast("(a + b) * c")
#     test_ast("a * b + c / d")
#
#     test_ast("a, b = c, d")
#
#     # Test:
#     test_ast("a - b - c")
#     test_ast("a - (b - c)")
#
#     # Test:
#     test_ast("a & b == c")
#     test_ast("(a & b) == c")
#
#     # Test:
#     test_ast("a || b && c")
#     test_ast("(a || b) && c")
#
#     test_ast("!done == 0")
#
#     # Test:
#     test_ast("node->value[0]")
#     test_ast("node.value[0]")
#
#     test_ast("foo(a, b)[0]")
#
#     # Test:
#     test_ast("sizeof a + b")
#     test_ast("sizeof(a + b)")
#
#
# def test_expr_success() -> None:
#     test_expr_iden_success()
#     test_expr_int_success()
#     test_expr_float_success()
#     test_expr_char_success()
#     test_expr_str_success()
#     test_expr_generic_sel_success()
#     test_expr_compound_success()
#     test_expr_una_op_success()
#     test_expr_bin_op_success()
#     test_expr_ter_op_success()
#     test_expr_assign_op_success()
#     test_expr_comma_success()
#     test_expr_binding_power_op_success()
#
#
# def test_expr_failure() -> None:
#     pass
#
#
# def test_expr() -> None:
#     test_expr_success()
#     test_expr_failure()
#
#
# def test_decl_primitive_type_success() -> None:
#     # Test:
#     "bool x = false"
#     "bool x = true"
#
#     # Test:
#     "char x = 'a'"
#     "signed char x = -128"
#     "unsigned char x = 255"
#
#     # Test:
#     "short x = 0"
#
#     "signed short x = -32768"
#     "unsigned short x = 65535"
#
#     "signed short int x = -32768"
#     "unsigned short int x = 65535"
#
#     # Test:
#     "int x = 0"
#
#     "unsigned x = 4294967295"
#     "signed x = -2147483648"
#
#     "signed int x = -2147483648"
#     "unsigned int x = 4294967295"
#
#     # Test:
#     "long x = 0"
#     "long int x = 0"
#
#     "signed long x = -9'223'372'036'854'775'808"
#     "unsigned long x = 9'223'372'036'854'775'807"
#
#     "signed long int x = -9'223'372'036'854'775'808"
#     "unsigned long int x = 9'223'372'036'854'775'807"
#
#     # Test:
#     "long long x = 0"
#     "long long int x = 0"
#
#     "signed long long x = -9'223'372'036'854'775'808"
#     "unsgie long long x = 9'223'372'036'854'775'807"
#
#     # Test:
#     "float x = 0.0"
#
#     # Test:
#     "double x = 0.0"
#
#     # Test:
#     "long double x = 0.0"
#
#     # Test:
#     "_BitInt(32) x = 0"
#
#     "signed _BitInt(32) x = -2147483648"
#     "unsigned _BitInt(32) x = 4294967295"
#
#     # Test:
#     "_Decimal32 x = 1234567.0"
#     "_Decimal64 x = 12345678.90123456"
#     "_Decimal128 x = 12345678901234567890.12345678901234"
#
#
# def test_decl_struct_type_success() -> None:
#     # Test:
#     "struct {}"
#
#     # Test:
#
#     # Test:
#     "struct {int val; struct Node *next}"
#     "struct {int id; struct {int x; int y;}}"
#
#     # Test:
#     "struct Empty {}"
#
#     # Test:
#     "struct {int a;}"
#     "struct {int a; int b;}"
#
#     "struct Value {int a;}"
#     "struct Value {int a; int b;}"
#
#     # Test:
#     "struct Node {int val; struct Node *next}"
#
#     # Test:
#     "struct Object {int id; struct {int x; int y;}}"
#
#     # Test: FAM
#     "struct Buffer {unsigned len; unsigned char data[];}"
#
#     # Test:
#     "struct BitPrecise {_BitInt(7) small; _BitInt(128) huge;}"
#
#
# def test_decl_enum_type_success() -> None:
#     # Test:
#     "enum {a}"
#     "enum {a, b, c}"
#
#     # Test:
#     "enum {a = 0}"
#
#     "enum {a = 0, b, c}"
#     "enum {a, b = 2, c}"
#     "enum {a, b, c = 1}"
#
#     "enum {a = 0, b = 2, c = 1}"
#     "enum {a = 'a', b = 'c', c = 'b'}"
#
#     # Test:
#     "enum {a = 1 << 2}"
#     "enum {a = 1 << 2, b = 1 << 3, c = 1 << 4}"
#
#     # Test:
#     "enum {a = foo()}"
#     "enum {a = foo(), b = bar(), c = baz()}"
#
#     # Test:
#     "enum Empty {}"
#
#     # Test:
#     "enum Opt {a}"
#     "enum Opt {a, b, c}"
#
#     # Test:
#     "enum Opt {a = 0}"
#
#     "enum Opt {a = 0, b, c}"
#     "enum Opt {a, b = 2, c}"
#     "enum Opt {a, b, c = 1}"
#
#     "enum Opt {a = 0, b = 2, c = 1}"
#     "enum Opt {a = 'a', b = 'c', c = 'b'}"
#
#     # Test:
#     "enum Opt : int {a = 0}"
#
#     "enum Opt : int {a = 0, b, c}"
#     "enum Opt : int {a, b, c = 1}"
#
#     "enum Opt : int {a = 0, b = 2, c = 1}"
#     "enum Opt : char {a = 'a', b = 'c', c = 'b'}"
#
#
# def test_decl_union_type_success() -> None:
#     # Test:
#     "union Empty {}"
#
#     # Test:
#     "union Value {int a;}"
#     "union Value {int a; float b;}"
#
#     # Test:
#     "union Value {int a; struct {int b;};};"
#
#     # Test:
#     "struct TagedUnion {int tag; union {int i; float f;};}"
#
#
# def test_decl_type_storage_success() -> None:
#     # Test:
#     "auto x = 0"
#     "auto ptr = &x"
#     "auto val = (double) 0.0"
#
#     # Test:
#     "const int x = 0"
#
#     # Test:
#     "restrict int x = 0"
#
#     # Test:
#     "static int x = 0"
#
#
# def test_decl_typeof_success() -> None:
#
#     pass
#
#
# def test_decl_typeof_unqual_success() -> None:
#     pass
#
#
# def test_decl_static_assert_success() -> None:
#     pass
#
#
# def test_decl_success() -> None:
#     # static_assert
#     # some struct declaration or enum declaration
#     pass
#
#
# def test_decl_failure() -> None:
#     pass
#
#
# def test_decl() -> None:
#     test_decl_success()
#     test_decl_failure()
#
#
# def test_stmt_compound_success() -> None:
#     # Test:
#     test_ast("{}")
#     test_ast("{;}")
#     test_ast("{a = 0;}")
#
#     # Test:
#     test_ast("{if (x) {a = 0} else {a =1}}")
#     test_ast("{for (int x = 0; x < size; ++x) {a += 1;}}")
#     test_ast("{while (x < size) {x += 1;}}")
#     test_ast("{do {x += 1;} while (x < size);}")
#     test_ast("{a = 0; {a = 1;}}")
#
#
# def test_stmt_expr_success() -> None:
#     # Test:
#     test_ast(";")
#
#     # Test:
#     test_ast("a;")
#
#     test_ast("0;")
#     test_ast("0.0;")
#
#     test_ast("'a';")
#     test_ast("\"a\";")
#
#     # Test:
#     test_ast("1 + 2;")
#     test_ast("a + b;")
#
#     test_ast("a + 2;")
#     test_ast("1 + a;")
#
#
# def test_stmt_if_success() -> None:
#     # Test:
#     test_ast("if (1) a = 0;")
#     test_ast("if (x) a = {0};")
#     test_ast("if (0 + 1) a = 0;")
#     test_ast("if ('a' - 'a') a = 0;")
#     test_ast("if (ptr != nullptr) a = 0;")
#     test_ast("if ((x = foo()) != -1) a = 0;")
#
#     # Test:
#     test_ast("if (1) {a = 0}; b = 1;}")
#     test_ast("if (x) {a = 0}; b = 1;}")
#     test_ast("if (0 + 1) {a = 0; b = 1;}")
#     test_ast("if ('a' - 'a') {a = 0; b = 1;}")
#     test_ast("if (ptr != nullptr) { a = 0; b = 1;}")
#     test_ast("if ((x = foo()) != -1) {a = 0; b = 1;}")
#
#     # Test:
#     test_ast("if (1) a = 0; else b = 1;")
#     test_ast("if (x) a = 0; else b = 1;")
#     test_ast("if (0 + 1) a = 0; else b = 1;")
#     test_ast("if ('a' - 'a') a = 0; else b = 1;")
#     test_ast("if (ptr != nullptr) a = 0; else b = 1;")
#     test_ast("if ((x = foo()) != {-1}) a = 0; else b = 1;")
#
#     # Test:
#     test_ast("if (1) {a = 0; b = 1;}")
#     test_ast("if (x) {a = 0; b = 1;}")
#     test_ast("if (0 + 1) {a = 0; b = 1;}")
#     test_ast("if ('a' - 'a') {a = 0; b = 1;}")
#     test_ast("if (ptr != nullptr) { a = 0; b = 1;}")
#     test_ast("if ((x = foo()) != -1) {a = 0; b = 1;}")
#
#     # Test:
#     test_ast("if (1) a = 0; b = 0;")
#
#     # Test:
#     test_ast("if (1) a = 0; else if (0) b = 1; else c = 2;")
#
#
# def test_stmt_case_success() -> None:
#     # Test:
#     test_ast("case 0:")
#     test_ast("case 'a':")
#
#     test_ast("case x:")
#     test_ast("case foo():")
#
#     # Test:
#     test_ast("default:")
#
#
# def test_stmt_switch_success() -> None:
#     # Test:
#     test_ast("switch (0) {}")
#     test_ast("switch ('a') {}")
#     test_ast("switch (x) {}")
#
#     # Test:
#     test_ast("switch (1 + 2) {}")
#     test_ast("switch (a + b) {}")
#     test_ast("switch (1 + b) {}")
#     test_ast("switch (a + 2) {}")
#     test_ast("switch (foo()) {}")
#
#     # Test:
#     test_ast("switch (0) {case 'a': break; default: return 0;}")
#
#
# def test_stmt_while_success() -> None:
#     # Test:
#     test_ast("while (1) x += 1;")
#     test_ast("while (x) x += 1;")
#     test_ast("while (0 + 1) x += 1;")
#     test_ast("while ('a' - 'a') x += 1;")
#     test_ast("while (ptr != nullptr) x += 1;")
#     test_ast("while ((x = foo()) != -1) x += 1;")
#
#     # Test:
#     test_ast("while (1) {a = 0; x += 1;}")
#     test_ast("while (x) {a = 0; x += 1;}")
#     test_ast("while (0 + 1) {a = 0; x += 1;}")
#     test_ast("while ('a' - 'a') {a = 0; x += 1;}")
#     test_ast("while (ptr != nullptr) {a = 0; x += 1;}")
#     test_ast("while ((x = foo()) != -1) {a = 0; x += 1;}")
#
#
# def test_stmt_do_while_success() -> None:
#     # Test:
#     test_ast("do a += 1 while(1);")
#     test_ast("do a += 1 while (x);")
#     test_ast("do a += 1 while (0 + 1);")
#     test_ast("do a += 1 while ('a' - 'a');")
#     test_ast("do a += 1 while (ptr != nullptr);")
#     test_ast("do a += 1 while ((x = foo()) != -1);")
#
#     # Test:
#     test_ast("do {a = 0; b += 1;} while (1);")
#     test_ast("do {a = 0; b += 1;} while (x);")
#     test_ast("do {a = 0; b += 1;} while (0 + 1);")
#     test_ast("do {a = 0; b += 1;} while ('a' - 'a');")
#     test_ast("do {a = 0; b += 1;} while (ptr != nullptr);")
#     test_ast("do {a = 0; b += 1;} while ((x = foo()) != -1);")
#
#
# def test_stmt_for_success() -> None:
#     # Test:
#     test_ast("for (int x = 0; x < size; ++x) a += 1;")
#
#     # Test:
#     test_ast("for (; x < size; ++x) a += 1;")
#     test_ast("for (int x = 0;; ++x) a += 1;")
#     test_ast("for (int x = 0; x < size;) a += 1;")
#
#     # Test:
#     test_ast("for (int x = 0;;) a += 1;")
#     test_ast("for (; x < size;) a += 1;")
#     test_ast("for (;; ++x) a += 1;")
#
#     # Test:
#     test_ast("for (;;) a += 1;")
#
#     # Test:
#     test_ast("for (int x = 0; x < size; ++x) {a += 1; b += 1;}")
#
#     # Test:
#     test_ast("for (; x < size; ++x) {a += 1; b += 1;}")
#     test_ast("for (int x = 0;; ++x) {a += 1; b += 1;}")
#     test_ast("for (int x = 0; x < size;) {a += 1; b += 1;}")
#
#     # Test:
#     test_ast("for (int x = 0;;) {a += 1; b += 1;}")
#     test_ast("for (; x < size;) {a += 1; b += 1;}")
#     test_ast("for (;; ++x) {a += 1; b += 1; }}")
#
#     # Test:
#     test_ast("for (;;) {a += 1; b += 1;}")
#
#
# def test_stmt_goto_success() -> None:
#     test_ast("goto out;")
#
#
# def test_stmt_label_success() -> None:
#     # Test:
#     test_ast("out: a += 1;")
#     test_ast("out: \nfree(x);")
#     test_ast("out: ;")
#
#     # Test:
#     test_ast("out: int a = 1;")
#
#
# def test_stmt_break_success() -> None:
#     # Test:
#     test_ast("break;")
#
#
# def test_stmt_continue_success() -> None:
#     # Test:
#     test_ast("continue;")
#
#
# def test_stmt_return_success() -> None:
#     # Test:
#     test_ast("return;")
#
#     # Test:
#     test_ast("return a;")
#     test_ast("return 1;")
#     test_ast("return (a = 1);")
#
#
# def test_stmt_success() -> None:
#     test_stmt_compound_success()
#     test_stmt_expr_success()
#     test_stmt_if_success()
#     test_stmt_switch_success()
#     test_stmt_while_success()
#     test_stmt_do_while_success()
#     test_stmt_for_success()
#     test_stmt_goto_success()
#     test_stmt_label_success()
#     test_stmt_break_success()
#     test_stmt_continue_success()
#     test_stmt_return_success()
#
#
# def test_stmt_failure() -> None:
#     pass
#
#
# def test_stmt() -> None:
#     test_stmt_success()
#     test_stmt_failure()
#
#
# def test_simple_code_fib_01_success() -> None:
#     source_code = """
#     int fib(int n) {
#         if (n <= 1)
#             return n;
#
#         return fib(n - 1) + fib(n - 2);
#     }
#     """
#
#
# def test_simple_code_fib_02_success() -> None:
#     source_code = """
#     int fib(int n) {
#         int a = 1, b = 1;
#
#         for (int i = 0; i < n - 2; ++i) {
#             int c = a + b;
#             a = b;
#             b = c;
#         }
#
#         return b;
#     }
#     """
#
#
# def test_simple_code_is_prime_01_success() -> None:
#     source_code = """
#     bool is_prime(unsigned num) {
#         if (num < 2)
#             return false;
#
#         unsigned div = 2;
#         unsigned sqrt_uint_max = 1 << sizeof(unsigned) * 4;
#
#         while (div <= sqrt_uint_max &&
#                 div * div <= num) {
#
#             if (num % div == 0)
#                 return false;
#
#             ++div;
#         }
#
#         return true;
#     }
#     """
#
#
#
# def test_simple_code_is_prime_02_success() -> None:
#     source_code = """
#     bool is_prime(unsigned num) {
#         assert(num < UINT_MAX);
#         const unsigned size = num + 1;
#
#         // WARNING: VLA
#         bool is_prime_map[size];
#
#         for (unsigned i = 0; i < size; ++i)
#             is_prime_map[i] = true;
#
#         assert(size >= 2);
#         is_prime_map[0] = is_prime_map[1] = false;
#
#         for (unsigned p = 2; p <= size / p; ++p) {
#             if (!is_prime_map[p])
#                 continue;
#
#             for (unsigned i = p * p; i <= size; i += p ) {
#                 is_prime_map[i] = false;
#
#                 if (size - i < p)
#                     break;
#             }
#         }
#
#         return is_prime_map[num]
#     }
#     """
#
#
# def test_simple_code_duffs_device_01_success() -> None:
#     source_code = """
#     void copy(short *to, short *from, int count) {
#         if (count <= 0) return;
#
#         int remainder = count % 8;
#
#         switch (remainder) {
#             case 7: *to = *from++;
#             case 6: *to = *from++;
#             case 5: *to = *from++;
#             case 4: *to = *from++;
#             case 3: *to = *from++;
#             case 2: *to = *from++;
#             case 1: *to = *from++;
#             case 0: break;
#         }
#
#         int blocks = count / 8;
#
#         while (blocks > 0) {
#             *to = *from++;
#             *to = *from++;
#             *to = *from++;
#             *to = *from++;
#             *to = *from++;
#             *to = *from++;
#             *to = *from++;
#             *to = *from++;
#             blocks--;
#         }
#     }
#     """
#
#
# def test_simple_code_duffs_device_02_success() -> None:
#     # NOTE: The DUFF is an acronym in popular culture for
#     # "Designated Ugly Fat Friend".
#
#     source_code = """
#     void copy(short *to, short *from, int count) {
#         int n = (count + 7) / 8;
#         switch (count % 8) {
#             case 0: do { *to = *from++;
#             case 7:      *to = *from++;
#             case 6:      *to = *from++;
#             case 5:      *to = *from++;
#             case 4:      *to = *from++;
#             case 3:      *to = *from++;
#             case 2:      *to = *from++;
#             case 1:      *to = *from++;
#                     } while (--n > 0);
#         }
#     }
#     """
#
#
# def test_simple_code_quake_rsqrt_success() -> None:
#     source_code = """
#     float Q_rsqrt( float number )
#     {
#         long i;
#         float x2, y;
#         const float threehalfs = 1.5F;
#
#         x2 = number * 0.5F;
#         y  = number;
#         i  = * ( long * ) &y;                       // evil floating point bit level hacking
#         i  = 0x5f3759df - ( i >> 1 );               // what the fuck?
#         y  = * ( float * ) &i;
#         y  = y * ( threehalfs - ( x2 * y * y ) );   // 1st iteration
#     //  y  = y * ( threehalfs - ( x2 * y * y ) );   // 2nd iteration, this can be removed
#
#         return y;
#     }
#     """
#
#
# def test_simple_code_trigraphs_success() -> None:
#     source_code = """
#     int main() ??<
#         if (1) ??/
#             (void) printf("Wait, what???/n");
#         return 0;
#     ??>
#     """
#
#
# def test_simple_code_success() -> None:
#     test_simple_code_fib_01_success()
#     test_simple_code_fib_02_success()
#     test_simple_code_is_prime_01_success()
#     test_simple_code_is_prime_02_success()
#     test_simple_code_duffs_device_01_success()
#     test_simple_code_duffs_device_02_success()
#
#     test_simple_code_quake_rsqrt_success()
#     test_simple_code_trigraphs_success()
#
#
# def test_simple_code_failure() -> None:
#     pass
#
#
# def test_simple_code() -> None:
#     test_simple_code_success()
#     test_simple_code_failure()
#
#
# def test_parser() -> None:
#     test_expr()
#     test_decl()
#     test_stmt()
#     test_simple_code()
#
#
# if __name__ == "__main__":
#     test_parser()
#
#
# # struct Rect r2 = {.top_left.x = 0, .bot_right.y = 10};
# # struct Point {
# #     int x;
# #     int y;
# # };
# #
# # // An array of 20 Point structures
# # struct Point curve[20] = {
# #     [10].x = 1,
# #     [10].y = 5,
# #     [15].x = 42
# # };
#
#
# # struct Point { int x, y; };
# # struct Path { struct Point steps[100]; };
# #
# # // Array of 5 Path objects
# # struct Path journey[5] = {
# #     [2].steps[50].x = 10,
# #     [2].steps[50].y = 20
# # };
#
#
# # int matrix[3][3] = {
# #     [1][1] = 5,
# #     [2][0] = 9
# # };
#
#
# # won't use bit fields, because we have bit-int
# # TODO: diagraphs if meee
