from enum import Enum

from error import ErrorCode
from tokenizer import Tokenizer, is_oct_digit, is_dec_digit
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


num_bases: dict[NumberTag, int] = {
    NumberTag.int_bin: 2,
    NumberTag.int_oct: 8,
    NumberTag.int_dec: 10,
    NumberTag.int_hex: 16,
    NumberTag.float_dec: 10,
    NumberTag.float_hex: 16,
}

int_bases: set[NumberTag] = {
    NumberTag.int_bin,
    NumberTag.int_oct,
    NumberTag.int_dec,
    NumberTag.int_hex
}

float_bases: set[NumberTag] = {
    NumberTag.float_dec,
    NumberTag.float_hex
}

char_encoding_len: dict[EncodingPrefix | None, int] = {
    None = CHAR_BIT_LEN
    EncodingPrefix.utf_8 = 8
    EncodingPrefix.utf_16 = 16
    EncodingPrefix.utf_32 = 32
    EncodingPrefix.wide_literal = WCHAR_BIT_LEN
}

simple_escapes: dict[str, str] = {
    'a': '\a',
    'b': '\b',
    'f': '\f',
    'n': '\n',
    'r': '\r',
    't': '\t',
    'v': '\v',
}

binding_power: dict[str, tuple[int, int]]= {
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


class StrFormater:
    def __init__(self, string: str) -> None:
        self.index = 0
        self.string = string

    def peek(self) -> str:
        if self.index >= len(self.string):
            return '\0'

        return self.string[self.index]

    def fetch(self) -> str:
        chr: str = self.peek()
        self.index += 1

        return chr

    def fetch_oca_seq(self) -> str | ErrorCode:
        val: int = 0

        for _ in range(3):
            if is_oct_digit(self.peek()):
                break

            val *= 8
            val += ord(self.fetch()) - ord('0')

        if not (0 <= val <= 0xffff_ffff):
            return ErrorCode.E

        return chr(val)

    def fetch_hex_seq(self) -> str | ErrorCode:
        val: int = 0

        while is_hex_digit(self.peek()):
            val *= 16

            if self.peek().isdigit():
                val += ord(self.fetch()) - ord('0')
            else:
                val += ord(self.fetch()) - ord('a') + 10

        if not (0 <= val <= 0xffff_ffff):
            return ErrorCode.E

        return chr(val)

    def fetch_uni_seq(self, digits: int) -> str | ErrorCode:
        assert digits == 4 or digits == 8

        val: int = 0

        for _ in range(digits):
            val *= 16

            if self.peek().isdigit():
                val += ord(self.fetch()) - ord('0')
            else:
                val += ord(self.fetch()) - ord('a') + 10

        if not (0x0000_0000 <= val <= 0x0010_ffff):
            return ErrorCode.E

        if 0xd800 <= val <= 0xdfff:
            return ErrorCode.E

        if 0x000 <= val <= 0x009f and val not in [0x0024, 0x0040, 0x0060]:
            return ErrorCode.E

        return chr(val)

    def fetch_esc_seq(self) -> str | ErrorCode:
        self.expect('\\')

        if self.match_digit():
            self.fetch()
            return self.fetch_oca_seq()

        if self.match('x'):
            return self.fetch_hex_seq()

        if self.match('u'):
            return self.fetch_uni_seq(4)

        if self.match('U'):
            return self.fetch_uni_seq(8)

        chr = self.fetch()
        return simple_escapes.get(chr, chr)

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

    def refmt(self, char_bit_len: int) -> str | ErrorCode:
        new_str: list[str] = []

        while self.peek() != '\0':
            new_part: str | ErrorCode = ""

            if self.peek() != '\\':
                new_part = fetch()
            else:
                new_part = fetch_esc_seq()

            if isinstance(new_part, ErrorCode):
                return new_part

            # TODO: check if the new_part that should represent one
            #       character is within the encoding limit
            new_str.append(new_part)

        return "".join(new_str)


class Parser:
    def __init__(self, buffer: str, tokens: list[Token]) -> None:
        self.index = 0
        self.buffer = buffer
        self.tokens = tokens

    def op_bp(self, op: str) -> tuple[int, int]:
        return binding_power.get(op, (0, 0))

    def token_str(self, token: Token) -> str:
        return self.buffer[token.loc.start:token.loc.end]

    def token_bp(self, token: Token) -> tuple[int, int]:
        return self.op_bp(self.token_str(token))

    def token_is_type(self, token: Token) -> bool:
        pass

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
              expeted_tag: TokenTag,
              expected_str: str | None) -> bool:
        token = self.peek()

        if token.tag != expeted_tag:
            return False;

        return expected_str is None or \
               self.token_str(token) == expected_str

    def check_nth(self,
                  offset: int,
                  expeted_tag: TokenTag,
                  expected_str: str | None) -> bool:
        token: Token | None = self.peek_nth(offset)

        if token is None:
            return False

        if token.tag != expeted_tag:
            return False;

        return expected_str is None or \
               self.token_str(token) == expected_str

    def match(self,
              expected_tag: TokenTag,
              expected_str: str | None) -> bool:
        token = self.peek()

        if not self.check(expected_tag, expected_str):
            return False

        self.fetch()
        return True

    def expect(self,
               expected_tag: TokenTag,
               expected_str: str | None) -> Token:
        assert self.check(expected_tag, expected_str)
        return self.fetch()

    def expect_one_of(self,
                      expected_opts: list[tuple[TokenTag, str]]) -> None:
        for (expected_tag, expected_str) in expected_options:
            if self.match(expected_tag, expected_str):
                return

        assert False

    # Types.
    def type_name(self) -> :
        pass

    def type(self) -> :
        pass


    #
    def iden(self) -> str | ErrorCode:
        if not self.check(TokenTag.identifier, None):
            return ErrorCode.E

        return StrFormater(self.token_str(self.fetch())).refmt()

    def expr_or_decl(self) -> ExprNode | DeclNode | ErrorCode:
        pass

    def expr_or_type(self) -> ExprNode | TypeNode | ErrorCode:
        pass

    # Declarations.
    def typeof_spec(self) -> :TypeOfSpec | ErrorCode:
        self.expect(TokenTag.keyword, "typeof")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        expr_or_type: ExprNode | TypeNode | ErrorCode = self.expr_or_type()
        if isinstance(expr_or_type, ErrorCode):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return TypeOfSpec(expr_or_type)

    def typeof_unqual_spec(self) -> TypeOfUnqualSpec | ErrorCode:
        self.expect(TokenTag.keyword, "typeof_unqual")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.Ej

        expr_or_type: ExprNode | TypeNode | ErrorCode = self.expr_or_type()
        if isinstance(expr_or_type, ErrorCode):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return TypeOfUnqualSpec(expr_or_type)

    def alignas_spec(self) -> AlignAsSpec | ErrorCode:
        self.expect(TokenTag.keyword, "alignas")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        expr_or_type: ExprNode | TypeNode | ErrorCode = self.expr_or_type()
        if isinstance(expr_or_type, ErrorCode):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return AlignAsSpec(expr_or_type)

    def var_decl(self) -> VarDecl | ErrorCode:
        var_type: TypeNode | ErrorCode = self.type()
        if isinstance(var_type, ErrorCode):
            return var_type

        iden: str | ErrorCode = self.iden()
        if isinstance(iden, ErrorCode):
            return iden

        init: ExprNode | InitList | None | ErrorCode = None

        if not self.check(TokenTag.punctuator, ";"):
            if self.check(TokenTag.punctuator, "{"):
                init = self.init_list()
            else:
                init = self.expr(0)

            if isinstance(init, ErrorCode):
                return init

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return VarDecl(var_type, iden, init)

    def fun_params(self) -> list[ParamSpec]:
        params: list[ParamSpec] = []

        while True:
            param_type: TypeNode | ErrorCode = self.type()
            if isinstance(param_type, ErrorCode):
                return param_type

            param_iden: str | None | ErrorCode = None
            if self.check(TokenTag.identifier, None):
                param_iden = self.iden()

                if isinstance(param_iden, ErrorCode):
                    return param_iden

            params.append((param_iden, param_type))

            if not self.match(TokenTag.punctuator, ","):
                break

        return params

    def fun_decl(self) -> FunDecl | ErrorCode:
        ret_type: TypeNode | ErrorCode = self.type()
        if isinstance(ret_type, ErrorCode):
            return ret_type

        iden: str | ErrorCode = self.iden()
        if isinstance(iden, ErrorCode):
            return iden

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        params: list[ParamSpec] = []
        if not self.check(TokenTag.punctuator, ")"):
            params = self.fun_params()

            if isinstance(params, ErrorCode):
                return params

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        body: CompoundStmt | None | ErrorCode = None
        if self.check(TokenTag.punctuator, "{"):
            body = self.compound_stmt()

            if isinstance(body, ErrorCode):
                return body

        elif not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return FunDecl(ret_type, iden, params, body)

    def static_assert_decl(self) -> StaticAssertDecl | ErrorCode:
        self.expect(TokenTag.keyword, "static_assert")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        min_bp, _ = self.op_bp(",")

        cond_expr: ExprNode | ErrorCode = self.expr(min_bp)
        if isinstance(cond_expr, ErrorCode):
            return cond_expr

        str_expr: StrListExpr | None | ErrorCode = None

        if self.match(TokenTag.punctuator, ","):
            str_expr = self.str_expr()

            if isinstance(str_expr, ErrorCode):
                return str_expr

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return StaticAssertDecl(cond_expr, str_expr)

    def enum_members(self) -> list[EnumValue] | ErrorCode:
        self.expect(TokenTag.punctuator, "{")

        min_bp, _ = self.op_bp(",")
        members: list[EnumValue] = []

        while self.check(TokenTag.identifier, None):
            iden: str | ErrorCode = self.iden()
            if isinstance(iden, ErrorCode):
                return iden

            expr: ExprNode | None | ErrorCode = None

            if self.match(TokenTag.punctuator, "="):
                expr = self.expr(min_bp)

                if isinstance(expr, ErrorCode):
                    return expr

            members.append((iden, expr))

            if not self.match(TokenTag.punctuator, ","):
                return ErrorCode.E

        if not self.match(TokenTag.punctuator, "}"):
            return ErrorCode.E

        return members

    def enum_decl(self) -> EnumDecl | ErrorCode:
        self.expect(TokenTag.keyword, "enum")

        iden: str | None | ErrorCode = None

        if self.check(TokenTag.identifier, None):
            iden = self.iden()

            if isinstance(iden, ErrorCode):
                return iden

        member_type: TypeNode | None | ErroCode = None

        if self.match(TokenTag.punctuator, ":"):
            member_type = self.type()

            if isinstance(member_type, ErrorCode):
                return member_type

        members: list[EnumValue] | None | ErrorCode = None

        if self.check(TokenTag.punctuator, "{"):
            members = self.enum_members()

            if isinstance(members, ErrorCode):
                return members

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return EnumDecl(iden, members, member_type)

    def members(self) -> list[MemberSpec] | ErrorCode:
        self.expect(TokenTag.punctuator, "{")

        members: list[MemberSpec] = []

        while self.token_is_type(self.peek()):
            decl: DeclNode | ErrorCode = self.decl()

            if isinstance(decl, ErrorCode):
                return decl

            members.append(decl)

        if not self.match(TokenTag.punctuator, "}"):
            return ErrorCode.E

        return members

    def struct_or_union_spec(self) -> StructOrUnionSpec | ErrorCode:
        iden: str | None | ErrorCode = None

        if self.check(TokenTag.identifier, None):
            iden = self.iden()

            if isinstance(iden, ErrorCode):
                return iden

        members: list[MemberSpec] | None | ErrorCode = None

        if self.check(TokenTag.punctuator, "{"):
            members = self.members()

            if isinstance(members, ErrorCode):
                return members

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return (iden, members)

    def struct_decl(self) -> StructDecl | ErrorCode:
        self.expect(TokenTag.keyword, "struct")

        result StructOrUnionSpec | ErrorCode = self.struct_or_union_spec()
        if isinstance(result, ErrorCode):
            return result

        iden, members = result
        return StructDecl(iden, fields)

    def union_decl(self) -> UnionDecl | ErrorCode:
        self.expect(TokenTag.keyword, "union")

        result StructOrUnionSpec | ErrorCode = self.struct_or_union_spec()
        if isinstance(result, ErrorCode):
            return result

        iden, members = result
        return UnionDecl(iden, members)

    def typedef_decl(self) -> | ErrorCode:
        self.expect(TokenTag.keyword, "typedef")

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        pass

    def decl(self) -> DeclNode | ErrorCode:
        if self.check(TokenTag.keyword, "static_assert"):
            return self.static_assert_decl()

        if self.check(TokenTag.keyword, "typedef"):
            return self.typedef_decl()

        #   - typedef
        return




    # Expressions.
    def iden_expr(self) -> IdenExpr | ErrorCode:
        iden: str | ErrorCode = self.iden()
        if isinstance(iden, ErrorCode):
            return iden

        return IdenExpr(iden)

    def int_expr(self) -> IntLitExpr | ErrorCode:
        token: Token = self.expect(TokenTag.number_literal, None)

        assert token.num_base in int_bases
        assert token.int_suffix is not None

        num: int = 0
        base: int = num_base[token.num_base]

        num_str: str = self.token_str(token)

        if token.num_base != NumberTag.int_dec:
            num_str = num_str[2:]

        for chr in num_str:
            if chr == '\'':
                continue

            num *= base
            num += ord(chr) - ord('0')

        bit_length: int = INT_BIT_LEN

        if NumberTag.width_bit in token.int_suffix:
            bit_length = num.bit_length()

        elif NumberTag.long in token.int_suffix:
            bit_length = INT_LONG_BIT_LEN

        elif NumberTag.long_long in token.int_suffix:
            bit_length = INT_LONG_LONG_BIT_LEN

        if NumberTag.unsigned in token.int_suffix:
            bit_length += 1

        if num.bit_length() > bit_length:
            return ErrorCode.E

        return IntLiteralExpr(num, bit_length)

    def float_expr(self) -> FloatLitExpr | ErrorCode:
        pass

    def num_expr(self) -> IntLiExpr | FloatLitExpr | ErrorCode:
        assert self.check(TokenTag.number_literal, None)

        if self.peek().num_base in int_base:
            return self.int_expr()
        else:
            return self.float_expr()

    def char_expr(self) -> CharLitExpr | ErrorCode:
        token: Token = self.expect(TokenTag.char_literal, None)
        token_str: str = self.token_str(token)

        char_expr: str | ErrorCode = StrFormater(token_str).refmt()
        if isinstance(char_expr, ErrorCode):
            return char_expr

        char_bit_len: int = char_encoding_len[token.encoding]
        char_max_val = (1 << char_bit_len) - 1

        for chr in char_expr:
            if ord(chr) > char_max_val:
                return ErrorCode.E

        return CharLitExpr(char_expr, char_bit_length)

    def (self, encoding: EncodingPrefix | None) -> str | ErrorCode:

        token: Token = self.expect(TokenTag.string_literal, None)
        self.token_str(token)

        str_expr = str_expr.encode("utf-8").decode("unicode_escape")


    def str_expr(self) -> StrLitExpr | ErrorCode:
        assert self.check(TokenTag.string_literal, None)

        str_expr_list: list[str] = []
        encoding: EncodingPrefix | None = self.peek().encoding

        while self.check(TokenTag.string_literal, None):
            : str | ErrorCode = self.()
            if isinstance(, ErrorCode):
                return

            str_expr_list.append(str_expr)

        return StrLitExpr("".join(str_expr_list), )







    def generic_sel_expr(self) -> GenericSelExpr | ErrorCode:
        self.expect(TokenTag.keyword, "_Generic")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        min_bp, _ = self.op_bp(",")

        expr: ExprNode | ErrorCode = self.expr(min_bp)
        if isinstance(expr, ErrorCode):
            return expr

        if not self.match(TokenTag.punctuator, ","):
            return ErrorCode.E

        table: dict[TypeNode | None, ExprNode] = {}

        while True:
            case_type: TypeNode | None | ErrorCode = None

            if not self.match(TokenTag.keyword, "default"):
                case_type: = self.type()

                if isinstance(case_type, ErrorCode):
                    return case_type

            if case_type in table:
                return ErrorCode.E

            if not self.match(TokenTag.punctuator, ":"):
                return ErrorCode.E

            case_expr: ExprNode | ErrorCode = self.expr(min_bp)
            if isinstance(case_expr, ErrorCode):
                return case_expr

            table[case_type_name] = case_expr

            if not self.match(TokenTag.punctuator, ","):
                break

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return GenericSelExpr(expr, table)

    def array_sub_expr(self, base_expr: ExprNode) -> ArraySubExpr | ErrorCode:
        self.expect(TokenTag.punctuator, "[")

        idx_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(idx_expr, ErrorCode):
            return idx_expr

        if self.match(TokenTag.punctuator, "]"):
            return ErrorCode.E

        return ArraySubExpr(base_expr, idx_expr)

    def call_expr(self, callee_expr: ExprNode) -> CallExpr | ErrorCode:
        self.expect(TokenTag.punctuator, "(")

        arg_expr_list: list[ExprNode] = []

        if self.match(TokenTag.punctuator, ")"):
            return CallExpr(callee_expr, arg_expr_list)

        min_bp, _ = self.op_bp(",")

        while True:
            arg_expr: ExprNode | ErrorCode = self.expr(min_bp)
            if isinstance(arg_expr, ErrorCode):
                return arg_expr

            if self.match(TokenTag.punctuator, ")"):
                break

            if not self.match(TokenTag.punctuator, ","):
                return ErrorCode.E

        return CallExpr(callee_expr, arg_expr_list)

    def member_expr(self, base_expr: ExprNode) -> MemberExpr | ErrorCode:
        is_arrow = self.check(TokenTag.punctuator, "->")

        tag = TokenTag.punctuator
        self.expect_one_of([(tag, "."), (tag, "->")])

        member_iden: str | ErrorCode = self.iden()
        if isinstance(member_iden, ErrorCode):
            return member_iden

        return MemberExpr(base_expr, member_iden, is_arrow)

    def comma_expr(self, left_expr: ExprNode) -> CommaExpr | ErrorCode:
        self.expect(TokenTag.punctuator, ",")

        right_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(right_expr, ErrorCode):
            return right_expr

        return CommaExpr((left_expr, right_expr))

    def init_entry(self) -> tuple[Designator, InitValue] | ErrorCode:
        if self.check(TokenTag.punctuator, "."):
            rec_init: InitMember | ErrorCode = self.init_member()
            if isinstance(rec_init, ErrorCode):
                return rec_init

            return rec_init, None

        if self.check(TokenTag.punctuator, "["):
            rec_init: InitIndex | ErrorCode = self.init_index()
            if isinstance(rec_init, ErrorCode):
                return rec_init

            return rec_init, None

        if not self.match(TokenTag.punctuator, "="):
            return ErrorCode.E

        expr_or_init: ExprNode | InitIndex | None | ErrorCode = None

        if self.check(TokenTag.punctuator, "{"):
            expr_or_init = self.init_list()
        else:
            min_bp, _ = self.op_bp(",")
            expr_or_init = self.expr(min_bp)

        if isinstance(expr_or_init, ErrorCode):
            return expr_or_init

        return None, expr_or_init

    def init_member(self) -> InitMember | ErrorCode:
        self.expect(TokenTag.punctuator, ".")

        member_iden: str | ErrorCode = self.iden()
        if isinstance(member_iden, ErrorCode):
            return ErrorCode.E

        init_entry = self.init_entry()
        if isinstance(init_entry, ErrorCode):
            return init_entry

        rec_init, expr_or_init = init_entry
        return InitMember(member_iden, rec_init, expr_or_init)

    def init_index(self) -> InitIndex | ErrorCode:
        self.expect(TokenTag.punctuator, "[")

        idx_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(idx_expr, ErrorCode):
            return ErrorCode.E

        if not self.match(TokenTag.punctuator, "]"):
            return ErrorCode.E

        init_entry = self.init_entry()
        if isinstance(init_entry, ErrorCode):
            return init_entry

        rec_init, expr_or_init = init_entry
        return InitIndex(idx_expr, rec_init, expr_or_init)

    def init_list(self) -> InitList | ErrorCode:
        self.expect(TokenTag.punctuator, "{")

        init_elems: list[ExprNode | InitNode] = []

        if self.match(TokenTag.punctuator, "}"):
            return InitList(init_list)

        min_bp, _ = self.op_bp(",")

        while True:
            elem: ExprNode | InitNode | None | ErrorCode = None

            if self.check(TokenTag.punctuator, "."):
                elem = self.init_member()

            elif self.check(TokenTag.punctuator, "["):
                elem = self.init_index()

            elif self.check(TokenTag.punctuator, "{"):
                elem = self.init_list()

            else:
                elem = self.expr(min_bp)

            if isinstance(elem, ErrorCode):
                return elem

            init_list.append(elem)

            if not self.match(TokenTag.punctuator, ","):
                break

        if not self.match(TokenTag.punctuator, "}"):
            return ErrorCode.E

        return InitList(init_list)

    def compound_expr(self, expr_type: TypeNode) -> CompundLitExpr | ErrorCode:
        init_list: InitList | ErrorCode = self.init_list()
        if isinstance(init_list, ErrorCode):
            return init_list

        return CompoundLitExpr(expr_type, init_list)

    def cast_expr(self, expr_type: TypeNode) -> CastExpr | ErrorCode:
        val_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(val_expr, ErrorCode):
            return val_expr

        return CastExpr(expr_type_name, val_expr)

    def cast_or_compound_expr(self) -> CastExpr | CompoundLitExpr | ErrorCode:
        self.expect(TokenTag.punctuator, "("):

        expr_type: TypeNode | ErrorCode = self.type()
        if isinstance(expr_type, ErrorCode):
            return expr_type

        if not match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        if self.check(TokenTag.punctuator, "{"):
            return self.compound_expr(expr_type)
        else:
            return self.cast_expr(expr_type)

    def cond_expr(self, cond_expr: ExprNode) -> CondExpr | ErrorCode:
        self.expect(TokenTag.punctuator, "?")

        true_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(true_expr, ErrorCode):
            return true_expr

        if not self.match(TokenTag.punctuator, ":"):
            return ErrorCode.E

        false_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(false_expr, ErrorCode):
            return false_expr

        return CondExpr(cond_expr, true_expr, false_expr)

    def sizeof_expr(self) -> SizeOfExpr | ErrorCode:
        self.expect(TokenTag.keyword, "sizeof")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        expr_or_type: ExprNode | TypeNode | ErrorCode = self.expr_or_type()
        if isinstance(expr_or_type, ErrorCode):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return SizeOfExpr(expr_or_type)

    def alignof_expr(self) -> AlignOfExpr | ErrorCode:
        self.expect(TokenTag.keyword, "alignof")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        align_type: TypeNode | ErrorCode = self.type()
        if isinstance(align_type, ErrorCode):
            return align_type

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return AlignOfExpr(align_type)

    def paren_expr(self) -> ExprNode | ErrorCode:
        self.expect(TokenTag.punctuator, "(")

        expr: ExprNode | ErrorCode = self.expr()
        if isinstance(expr, ErrorCode):
            return expr

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return expr

    def paren_or_cast_or_compound_expr(self) -> None:
        assert self.check(TokenTag.punctuator, "(")

        token: Token | None = self.peek_nth(1)

        if token is None:
            return ErrorCode.

        if self.token_is_type(token):
            return self.cast_or_compound_expr()
        else:
            return self.parent_expr()

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
    def expr_nud(self) -> ExprNode | ErrorCode:
        if self.check(TokenTag.identifier, None):
            return self.iden_expr()

        if self.check(TokenTag.number_literal, None):
            return self.num_expr()

        if self.check(Token.char_literal, None):
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

            una_expr: ExprNode | ErrorCode = self.expr(0)
            if isinstance(una_expr, ErrorCode):
                return una_expr

            return OpExpr(op, [una_expr])

        return ErrorCode.E

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
                 min_bp: int) -> ExprNode | ErrorCode:
        if self.check(TokenTag.punctuator, "("):
            return self.call_expr(left_expr)

        if self.check(TokenTag.punctuator, "["):
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

            right_expr: ExprNode | ExprNode = self.expr(min_bp)
            if isinstance(right_expr, ErrorCode):
                return right_expr

            return OpExpr(op, [left_expr, right_expr])

        return ErrorCode.E

    # Pratt expression parser:
    # Consumes tokens as long as their left binding power (l_bp)
    # exceeds the current min_bp.
    def expr(self, min_bp: int) -> ExprNode | ErrorCode:
        left_expr: ExprNode | ErrorCode = self.expr_nud()
        if isinstance(left_expr, ErrorCode):
            return left_expr

        while True:
            l_bp, r_bp = self.token_bp(self.peek())
            if min_bp > l_bp:
                break

            left_expr = self.expr_led(left_expr, r_bp)
            if isinstance(left_expr, ErrorCode):
                return left_expr

        return left_expr

    # Statements.
    # NOTE: Using built-in statements for "assert" and "println" helps us
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
    def fmt_spec(self) -> FmtSpec | ErrorCode:
        str_expr: StrLitExpr | None | ErrorCode = None

        if self.match(TokenTag.punctuator, ","):
            str_expr = self.str_expr()

            if isinstance(str_expr, ErrorCode):
                return str_expr

        arg_exprs: list[ExprNode] | ErrorCode = []

        if self.match(TokenTag.punctuator, ","):
            arg_exprs = self.
            if isinstance(str_expr, ErrorCode):
                return str_expr

        return (str_expr, arg_exprs)

    def println_stmt(self) -> PrintLnStmt | ErrorCode:
        self.expect(TokenTag.keyword, "println")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        result: FmtSpec | ErrorCode = self.fmt_spec()
        if isinstance(result, ErrorCode):
            return result

        str_expr, arg_exprs = result

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return PrintLn(str_expr, arg_exprs)

    def assert_stmt(self) -> AssertStmt | ErrorCode:
        self.expect(TokenTag.keyword, "assert")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        min_bp, _ = self.op_bp(",")

        cond_expr: ExprNode | ErrorCode = self.expr(min_bp)
        if isinstance(cond_expr, ErrorCode):
            return cond_expr

        result: FmtSpec | ErrorCode = self.fmt_spec()
        if isinstance(result, ErrorCode):
            return result

        str_expr, arg_exprs = result

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return AssertStmt(cond_expr, str_expr, arg_exprs)

    def compound_stmt(self) -> CompoundStmt | ErrorCode:
        self.expect(TokenTag.keyword, "{")

        block_items: list[StmtNode] = []

        while not self.check(TokenTag.punctuator, "}"):
            stmt: StmtNode | ErrorCode = self.stmt()
            if isinstance(stmt, ErrorCode):
                return stmt

        self.expect(TokenTag.punctuator, "}")

        return CompoundStmt(block_items)

    def expr_stmt(self) -> ExprStmt | ErrorCode:
        expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(expr, ErrorCode):
            return expr

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return ExprStmt(expr)

    def decl_stmt(self) -> DeclStmt | ErrorCode:
        # decl: DeclNode | ErrorCode = self.decl()
        # if isinstance(decl, ErrorCode):
        #     return decl
        #
        # FIX: maybe do not allow this?
        # if isinstance(decl, FunDecl) and decl.fun_def is not None:
        #     return DeclStmt(decl)

        return DeclStmt(decl)

    def expr_or_decl_stmt(self) -> ExprStmt | DeclStmt | ErrorCode:
        if self.match(TokenTag.punctuator, ";"):
            return ExprStmt(None)

        if self.check_if_type(0):
            return self.decl_stmt()
        else
            return self.expr_stmt()

    def if_stmt(self) -> IfStmt | ErrorCode:
        self.expect(TokenTag.keyword, "if")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        cond_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(cond_expr, ErrorCode):
            return cond_expr

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        then_stmt: StmtNode | ErrorCode = self.stmt()
        if isinstance(then_stmt, ErrorCode):
            return then_stmt

        else_stmt: StmtNode | None = None

        if self.match(TokenTag.keyword, "else"):
            else_stmt = self.stmt()

            if isinstance(else_stmt, ErrorCode):
                return else_stmt

        return IfStmt(cond_expr, then_stmt, else_stmt)

    def case_stmt(self) -> CaseLabelStmt | ErrorCode:
        self.expect(TokenTag.keyword, "case")

        cond_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(cond_expr, ErrorCode):
            return cond_expr

        if not self.match(TokenTag.punctuator, ":"):
            return ErrorCode.E

        return CaseLabelStmt(cond_expr)

    def default_stmt(self) -> CaseLabelStmt | ErrorCode:
        self.expect(TokenTag.keyword, "default")

        if not self.match(TokenTag.punctuator, ":"):
            return ErrorCode.E

        return CaseLabelStmt(None)

    def switch_stmt(self) -> SwitchStmt | ErrorCode:
        self.expect(TokenTag.keyword, "switch")

        if not self.match(TokenTag.keyword, "("):
            return ErrorCode.E

        cond_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(cond_expr, ErrorCode):
            return cond_expr

        if not self.match(TokenTag.keyword, ")"):
            return ErrorCode.E

        then_stmt: StmtNode | ErrorCode = self.stmt()
        if isinstance(then_stmt, ErrorCode):
            return then_stmt

        return SwitchStmt(cond_expr, then_stmt)

    def while_stmt(self) -> CycleStmt | ErrorCode:
        self.expect(TokenTag.keyword, "while")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        cond_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(cond_expr, ErrorCode):
            return cond_expr

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        then_stmt: StmtNode | ErrorCode = self.stmt()
        if isinstance(then_stmt, ErrorCode):
            return then_stmt

        return CycleStmt(None, cond_expr, then_stmt, None)

    def do_while_stmt(self) -> DoWhileStmt | ErrorCode:
        self.expect(TokenTag.keyword, "do")

        do_stmt: StmtNode | ErrorCode = self.stmt()
        if isinstance(do_stmt, ErrorCode):
            return do_stmt

        if not self.match(TokenTag.keyword, "while"):
            return ErrorCode.E00

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E00

        cond_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(cond_expr, ErrorCode):
            return cond_expr

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E00

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E00

        return DoWhileStmt(do_stmt, cond_expr)

    def for_stmt(self) -> CycleStmt | ErrorCode:
        self.expect(TokenTag.keyword, "for")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        init: ExprNode | DeclNode | None | ErrorCode = None

        if not self.check(TokenTag.punctuator, ";"):
            init = self.expr_or_decl()

            if isinstance(init, ErrorCode):
                return init

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        cond_expr: ExprNode | None | ErrorCode = None

        if not self.check(TokenTag.punctuator, ";"):
            cond_expr = self.expr(0)

            if isinstance(cond_expr, ErrorCode):
                return cond_expr

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        inc_expr: ExprNode | None | ErrorCode = None

        if not self.check(TokenTag.punctuator, ")"):
            inc_expr = self.expr(0)

            if isinstance(inc_expr, ErrorCode):
                return inc_expr

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E00

        then_stmt = self.stmt()
        if isinstance(then_stmt, ErrorCode):
            return ErrorCode.E00

        return CycleStmt(init, cond_expr, inc_expr, then_stmt)

    def goto_stmt(self) -> GotoStmt | ErrorCode:
        self.expect(TokenTag.keyword, "goto")

        if not self.check(TokenTag.identifier, None):
            return ErrorCode.E

        label_iden: str | ErrorCode = self.iden()
        if isinstance(label_iden, ErrorCode):
            return label_iden

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return GotoStmt(label_iden)

    def label_stmt(self) -> LabelStmt:
        iden: str | ErrorCode = self.iden()
        if isinstance(iden, ErrorCode):
            return iden

        self.expect(TokenTag.punctuator, ";")

        return LabelStmt(iden)

    def break_stmt(self) -> BreakStmt | ErrorCode:
        self.expect(TokenTag.keyword, "break")

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return BreakStmt()

    def continue_stmt(self) -> ContinueStmt | ErrorCode:
        self.expect(TokenTag.keyword, "continue")

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E00

        return ContinueStmt()

    def return_stmt(self) -> ReturnStmt | ErrorCode:
        self.expect(TokenTag.keyword, "return")

        ret_expr: ExprNode | None | ErrorCode = None

        if not self.check(TokenTag.punctuator, ";"):
            ret_expr = self.expr(0)

            if isinstance(ret_expr, ErrorCode):
                return ret_expr

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E00

        return ReturnStmt(ret_expr)

    def stmt(self) -> Stmt | ErrorCode:
        if self.check(TokenTag.keyword, "assert"):
            return self.assert_stmt()

        if self.check(TokenTag.keyword, "println"):
            return self.println_stmt()

        if self.check(TokenTag.keyword, "{"):
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

    def parse(self) -> TransUnitDecl | ErrorCode:
        decls: list[DeclNode] = []

        while not self.check(TokenTag.eof, None):
            decl: DeclNode | ErrorCode = self.decl()

            if isinstance(decl, ErrorCode):
                return decl

            decls.append(decl)

        return TransUnitDecl(decls)


def test_ast_compare(buffer: str, expected: str) -> None:
    ast = AST(buffer)

    assert ast.build() is None
    assert ast.dump() == expected


def test_ast(buffer: str) -> None:
    expected =
    test_ast_compare(buffer, expected)


def test_expr_iden_success() -> None:
    pass


def test_expr_int_success() -> None:
    ""
    pass


def test_expr_float_success() -> None:
    pass


def test_expr_char_success() -> None:
    pass


def test_expr_str_success() -> None:
    pass


def test_expr_generic_sel_success() -> None:
    pass


def test_expr_una_array_sub_success() -> None:
    # Test: Recognition
    test_ast(f"arr[0]")
    test_ast(f"arr[1]")
    test_ast(f"arr[-1]")
    test_ast(f"arr[{INT_MAX}]")

    # Test: Recognition
    test_ast(f"0[arr]")
    test_ast(f"1[arr]")
    test_ast(f"{INT_MAX}[arr]")

    # Test:
    test_ast("arr[1 + 2]")
    test_ast("arr['a' - 'a']")

    # Test:
    test_ast("arr[(1 + 2) + 3]")
    test_ast("(arr)[1 + 2]")

    # Test:
    test_ast("arr[n]")
    test_ast("arr[fun(1, 2, 3)]")

    # Test:
    test_ast("arr[0][0]")
    test_ast("arr[x][y][z]")

    # Test:
    test_ast("arr[0, 1]")

    # Test:
    test_ast("-arr[0]", )
    test_ast("-(arr)[0]", )

    # Test:
    test_ast("-1[arr]", )
    test_ast("(-1)[arr]", )


def test_expr_una_call_success() -> None:
    # Test:
    test_ast("foo()")
    test_ast("+foo()")
    test_ast("-foo()")

    # Test:
    test_ast("foo(1 + 2)")
    test_ast("foo('a' - 'a')")

    # Test:
    test_ast("foo(x + y, z)")
    test_ast("foo(x, y + z)")
    test_ast("foo(x, y, z)")

    # Test:
    test_ast("foo(1, 2, 3)")
    test_ast("foo(1.23, 0.01)")

    # Test:
    test_ast("foo(n, 1 )")
    test_ast("foo(1, n )")

    # Test:
    test_ast("foo(a, b, c, d, e, f, g, h, i, j, k, l)")


def test_expr_una_member_success() -> None:
    # Test:
    test_ast("vec.length")
    test_ast("vec->length")

    # Test:
    test_ast("node.next->data")

    # Test:
    test_ast("points[0].x")
    test_ast("points[0]->x")

    test_ast("vec.data[0]")
    test_ast("vec->data[0]")


def test_expr_una_compound_success() -> None:
    # Test:
    test_ast("(struct Vector){}")
    test_ast("(struct Vector){1.0f, 2.0f, 3.0f}")

    # Test:
    test_ast("(struct Point){.x = 1, .y = 2}")
    test_ast("(struct Point){.x = x, .y = y}")
    test_ast("(struct Point){.x = 1, .y = y}")
    test_ast("(struct Point){.x = x, .y = 2}")
    test_ast("(struct Point){.x = foo(), .y = bar()}")

    # Test:
    test_ast("(int[2]){}")
    test_ast("(int[2]){1}")
    test_ast("(int[]){1, 2, 3}[0]")

    # Test:
    test_ast("(struct Point){.x = 1, .y = 2}.x", )


def test_expr_una_cast_success() -> None:
    # Test:
    test_ast("(double)42")

    # Test:
    test_ast("(void)foo()")

    # Test:
    test_ast("(int)x")
    test_ast("(char *)ptr")
    test_ast("(struct stat)sb")

    # Test:
    test_ast("(int)x")
    test_ast("(char *)ptr")
    test_ast("(struct stat)sb")

    test_ast("(const int)x")

    # Test:
    test_ast("(volatile void *)ptr")
    test_ast("(int ***)ptr")
    test_ast(f"(int (*)[16])ptr")
    test_ast("(int (*)(int))ptr")
    test_ast("(double)(int)x")


def test_expr_una_prefix_inc_success() -> None:
    # Test:
    test_ast("++a")
    test_ast("-++a")
    test_ast("+(++a)")

    # Test:
    test_ast("++5")
    test_ast("+++a")
    test_ast("++(+a)")


def test_expr_una_prefix_dec_success() -> None:
    # Test:
    test_ast("--a")
    test_ast("+--a")
    test_ast("-(--a)")

    # Test:
    test_ast("--5")
    test_ast("---a")
    test_ast("--(+a)")


def test_expr_una_addr_of_success() -> None:
    # Test:
    test_ast("&x")
    test_ast("&1")

    # Test:
    test_ast("&ptr->member")
    test_ast("&((struct Point){.x = 1, .y = 2})")

    # Test:
    test_ast("&(x + 1)")
    test_ast("&*x")
    test_ast("&&x")


def test_expr_una_deref_success() -> None:
    # Test:
    test_ast("*ptr")
    test_ast("**ptr")
    test_ast("*5")

    # Test:
    test_ast("*++ptr")
    test_ast("++*ptr++")

    # Test:
    test_ast("*--ptr")
    test_ast("--*ptr--")


def test_expr_una_neg_success() -> None:
    # Test:
    test_ast("-0")
    test_ast("-'a'")

    # Test:
    test_ast("- -a")
    test_ast("-(a + b)")


def test_expr_una_bit_neg_success() -> None:
    # Test:
    test_ast("~0")
    test_ast("~(1 + 2)")

    # Test:
    test_ast("~a")
    test_ast("~++a")


def test_expr_una_bool_neg_success() -> None:
    # Test:
    test_ast("!true")
    test_ast("!0")

    # Test:
    test_ast("node.value--")
    test_ast("node->value--")

    # Test:
    test_ast("*ptr--")


def test_expr_una_sizeof() -> None:
    # Test:
    test_ast("sizeof(int)")
    test_ast("sizeof(struct stat)")

    test_ast("sizeof(int *)")
    test_ast("sizeof(int[16])")

    test_ast("sizeof(const int)")
    test_ast("sizeof(volatile int)")

    test_ast("sizeof(struct {int a; int b;})")

    # Test:
    test_ast("sizeof 0")
    test_ast("sizeof 'a'")
    test_ast("sizeof 1.23")

    test_ast("sizeof a")
    test_ast("sizeof(a)")

    test_ast("sizeof(a++)")
    test_ast("sizeof(*a)")
    test_ast("sizeof(a = 10)")

    test_ast("sizeof(foo())")
    test_ast("sizeof(sizeof(int))")


def test_expr_una_alignof() -> None:
    # Test:
    test_ast("sizeof(int)")
    test_ast("sizeof(struct stat)")

    test_ast("sizeof(int *)")
    test_ast("sizeof(int[16])")

    test_ast("sizeof(const int)")
    test_ast("sizeof(volatile int)")

    test_ast("sizeof(struct {int a; int b;})")


def test_expr_una_op_success() -> None:
    test_expr_una_array_sub_success()
    test_expr_una_call_success()
    test_expr_una_member_success()
    test_expr_una_compound_success()
    test_expr_una_cast_success()
    test_expr_una_prefix_inc_success()
    test_expr_una_prefix_dec_success()
    test_expr_una_addr_of_success()
    test_expr_una_deref_success()
    test_expr_una_neg_success()
    test_expr_una_bit_neg_success()
    test_expr_una_bool_neg_success()
    test_expr_una_posfix_inc_success()
    test_expr_una_postfix_dec_success()
    test_expr_una_sizeof()
    test_expr_una_alignof()


def test_expr_bin_op(op: str) -> None:
    # Test:
    test_ast(f"1 {op} 2")
    test_ast(f"a {op} b")

    test_ast(f"a {op} 2")
    test_ast(f"1 {op} b")

    # Test:
    test_ast(f"1 {op} 'a'")
    test_ast(f"'a' {op} 2")
    test_ast(f"'a' {op} 'a'")

    # Test:
    test_ast(f"1 {op} bar()")
    test_ast(f"foo() {op} 2")
    test_ast(f"foo() {op} bar()")

    # Test:
    test_ast(f"*ptr {op} 2")
    test_ast(f"1 {op} *ptr")
    test_ast(f"*ptr {op} *ptr")

    test_ast(f"node.value {op} 2")
    test_ast(f"1 {op} node.value")

    test_ast(f"node->value {op} 2")
    test_ast(f"1 {op} node->value")


def test_expr_bin_bit_and_success() -> None:
    # Test:
    test_expr_bin_op("&")

    # Test:
    test_ast("a & &b")


def test_expr_bin_mul_success() -> None:
    # Test:
    test_expr_bin_op("*")

    # Test:
    test_ast("a * *b")
    test_ast("a * +b")
    test_ast("a * +b")


def test_expr_bin_add_success() -> None:
    # Test:
    test_expr_bin_op("+")

    # Test:
    test_ast("a + *b")
    test_ast("a + +b")
    test_ast("a + -b")


def test_expr_bin_sub_success() -> None:
    # Test:
    test_expr_bin_op("-")

    # Test:
    test_ast("a - *b")
    test_ast("a - +b")
    test_ast("a - -b")


def test_expr_bin_div_success() -> None:
    # Test:
    test_expr_bin_op("/")


def test_expr_bin_mod_success() -> None:
    # Test:
    test_expr_bin_op("%")


def test_expr_bin_shl_success() -> None:
    # Test:
    test_expr_bin_op("<<")


def test_expr_bin_shr_success() -> None:
    # Test:
    test_expr_bin_op(">>")


def test_expr_bin_lt_success() -> None:
    # Test:
    test_expr_bin_op("<")


def test_expr_bin_gt_success() -> None:
    # Test:
    test_expr_bin_op(">")


def test_expr_bin_le_success() -> None:
    # Test:
    test_expr_bin_op("<=")


def test_expr_bin_ge_success() -> None:
    # Test:
    test_expr_bin_op(">=")


def test_expr_bin_eq_success() -> None:
    # Test:
    test_expr_bin_op("==")


def test_expr_bin_ne_success() -> None:
    # Test:
    test_expr_bin_op("!=")


def test_expr_bin_bit_xor_success() -> None:
    # Test:
    test_expr_bin_op("^")


def test_expr_bin_bit_or_success() -> None:
    # Test:
    test_expr_bin_op("|")


def test_expr_bin_bool_and_success() -> None:
    # Test:
    test_expr_bin_op("&&")


def test_expr_bin_bool_or_success() -> None:
    # Test:
    test_expr_bin_op("||")




def test_expr_assign_op(op: str) -> None:
    # Test:
    test_ast(f"a {op} 2")
    test_ast(f"a {op} 'a'")

    test_ast(f"a {op} b")
    test_ast(f"a {op} *ptr")

    test_ast(f"a {op} foo()")

    # Test:
    test_ast(f"*ptr {op} 2")
    test_ast(f"*ptr {op} 'a'")

    test_ast(f"*ptr {op} b")
    test_ast(f"*ptr {op} *ptr")

    test_ast(f"*ptr {op} foo()")

    # Test:
    test_ast(f"node.data {op} 2")
    test_ast(f"node.data {op} 'a'")

    test_ast(f"node.data {op} b")
    test_ast(f"node.data {op} *ptr")

    test_ast(f"node.data {op} foo()")

    # Test:
    test_ast(f"node->data {op} 2")
    test_ast(f"node->data {op} 'a'")

    test_ast(f"node->data {op} b")
    test_ast(f"node->data {op} *ptr")

    test_ast(f"node->data {op} foo()")


def test_expr_bin_assign_success() -> None:
    # Test:
    test_expr_assign_op("=")


def test_expr_bin_assign_mul_success() -> None:
    # Test:
    test_expr_assign_op("*=")


def test_expr_bin_assign_div_success() -> None:
    # Test:
    test_expr_assign_op("/=")


def test_expr_bin_assign_mod_success() -> None:
    # Test:
    test_expr_assign_op("%=")


def test_expr_bin_assign_add_success() -> None:
    # Test:
    test_expr_assign_op("+=")


def test_expr_bin_assign_sub_success() -> None:
    # Test:
    test_expr_assign_op("-=")


def test_expr_bin_assign_shl_success() -> None:
    # Test:
    test_expr_assign_op("<<=")


def test_expr_bin_assign_shr_success() -> None:
    # Test:
    test_expr_assign_op(">>=")


def test_expr_bin_assign_bit_and_success() -> None:
    # Test:
    test_expr_assign_op("&=")


def test_expr_bin_assign_bit_xor_success() -> None:
    # Test:
    test_expr_assign_op("^=")


def test_expr_bin_assign_bit_or_success() -> None:
    # Test:
    test_expr_assign_op("|=")


def test_expr_bin_op_success() -> None:
    test_expr_bin_mul_success()
    test_expr_bin_add_success()
    test_expr_bin_sub_success()
    test_expr_bin_div_success()
    test_expr_bin_mod_success()

    test_expr_bin_shl_success()
    test_expr_bin_shr_success()

    test_expr_bin_lt_success()
    test_expr_bin_gt_success()
    test_expr_bin_le_success()
    test_expr_bin_ge_success()
    test_expr_bin_eq_success()
    test_expr_bin_ne_success()

    test_expr_bin_bit_and_success()
    test_expr_bin_bit_xor_success()
    test_expr_bin_bit_or_success()

    test_expr_bin_bool_and_success()
    test_expr_bin_bool_or_success()

    test_expr_bin_assign_success()
    test_expr_bin_assign_mul_success()
    test_expr_bin_assign_div_success()
    test_expr_bin_assign_mod_success()
    test_expr_bin_assign_add_success()
    test_expr_bin_assign_sub_success()
    test_expr_bin_assign_shl_success()
    test_expr_bin_assign_shr_success()
    test_expr_bin_assign_bit_and_success()
    test_expr_bin_assign_bit_xor_success()
    test_expr_bin_assign_bit_or_success()


def test_expr_ter_op_success() -> None:
    # Test:
    test_ast("1 ? 2 : 3")
    test_ast("'a' ? 'b' ? 'c'")

    # Test:
    test_ast("a ? b : c")

    test_ast("a ? b : c ? d : e")
    test_ast("a ? b ? c : d : e")

    # Test:
    test_ast("*a ? *b ? *c")
    test_ast("a ? b = 0 : c = 1")

    test_ast("foo() ? bar() : baz()")


def test_expr_comma_success() -> None:
    # Test:
    test_ast_compare("x = a, b", )
    test_ast_compare("x = (a, b)", )
    test_ast_compare("(x = a), b", )

    test_ast_compare("foo(a, (b, c), d)", )
    test_ast_compare("x = {.value = (1, 2)}", )

    # Test:
    test_ast_compare("return (cleanup(), result);", )

    test_ast_compare("for (int x = 0; x < size; ++x, ++i) {}", )
    test_ast_compare("while ((x, y) == NULL) {}", )


def test_expr_binding_power_op_success() -> None:
    # Test:
    test_ast("a + b * c")
    test_ast("(a + b) * c")
    test_ast("a * b + c / d")

    test_ast("a, b = c, d")

    # Test:
    test_ast("a - b - c")
    test_ast("a - (b - c)")

    # Test:
    test_ast("a & b == c")
    test_ast("(a & b) == c")

    # Test:
    test_ast("a || b && c")
    test_ast("(a || b) && c")

    test_ast("!done == 0")

    # Test:
    test_ast("node->value[0]")
    test_ast("node.value[0]")

    test_ast("foo(a, b)[0]")

    # Test:
    test_ast("sizeof a + b")
    test_ast("sizeof(a + b)")


def test_expr_success() -> None:
    test_expr_iden_success()
    test_expr_int_success()
    test_expr_float_success()
    test_expr_char_success()
    test_expr_str_success()
    test_expr_generic_sel_success()
    test_expr_compound_success()
    test_expr_una_op_success()
    test_expr_bin_op_success()
    test_expr_ter_op_success()
    test_expr_assign_op_success()
    test_expr_comma_success()
    test_expr_binding_power_op_success()


def test_expr_failure() -> None:
    pass


def test_expr() -> None:
    test_expr_success()
    test_expr_failure()


def test_decl_primitive_type_success() -> None:
    # Test:
    "bool x = false"
    "bool x = true"

    # Test:
    "char x = 'a'"
    "signed char x = -128"
    "unsigned char x = 255"

    # Test:
    "short x = 0"

    "signed short x = -32768"
    "unsigned short x = 65535"

    "signed short int x = -32768"
    "unsigned short int x = 65535"

    # Test:
    "int x = 0"

    "unsigned x = 4294967295"
    "signed x = -2147483648"

    "signed int x = -2147483648"
    "unsigned int x = 4294967295"

    # Test:
    "long x = 0"
    "long int x = 0"

    "signed long x = -9'223'372'036'854'775'808"
    "unsigned long x = 9'223'372'036'854'775'807"

    "signed long int x = -9'223'372'036'854'775'808"
    "unsigned long int x = 9'223'372'036'854'775'807"

    # Test:
    "long long x = 0"
    "long long int x = 0"

    "signed long long x = -9'223'372'036'854'775'808"
    "unsgie long long x = 9'223'372'036'854'775'807"

    # Test:
    "float x = 0.0"

    # Test:
    "double x = 0.0"

    # Test:
    "long double x = 0.0"

    # Test:
    "_BitInt(32) x = 0"

    "signed _BitInt(32) x = -2147483648"
    "unsigned _BitInt(32) x = 4294967295"

    # Test:
    "_Decimal32 x = 1234567.0"
    "_Decimal64 x = 12345678.90123456"
    "_Decimal128 x = 12345678901234567890.12345678901234"


def test_decl_struct_type_success() -> None:
    # Test:
    "struct {}"

    # Test:

    # Test:
    "struct {int val; struct Node *next}"
    "struct {int id; struct {int x; int y;}}"

    # Test:
    "struct Empty {}"

    # Test:
    "struct {int a;}"
    "struct {int a; int b;}"

    "struct Value {int a;}"
    "struct Value {int a; int b;}"

    # Test:
    "struct Node {int val; struct Node *next}"

    # Test:
    "struct Object {int id; struct {int x; int y;}}"

    # Test: FAM
    "struct Buffer {unsigned len; unsigned char data[];}"

    # Test:
    "struct BitPrecise {_BitInt(7) small; _BitInt(128) huge;}"


def test_decl_enum_type_success() -> None:
    # Test:
    "enum {a}"
    "enum {a, b, c}"

    # Test:
    "enum {a = 0}"

    "enum {a = 0, b, c}"
    "enum {a, b = 2, c}"
    "enum {a, b, c = 1}"

    "enum {a = 0, b = 2, c = 1}"
    "enum {a = 'a', b = 'c', c = 'b'}"

    # Test:
    "enum {a = 1 << 2}"
    "enum {a = 1 << 2, b = 1 << 3, c = 1 << 4}"

    # Test:
    "enum {a = foo()}"
    "enum {a = foo(), b = bar(), c = baz()}"

    # Test:
    "enum Empty {}"

    # Test:
    "enum Opt {a}"
    "enum Opt {a, b, c}"

    # Test:
    "enum Opt {a = 0}"

    "enum Opt {a = 0, b, c}"
    "enum Opt {a, b = 2, c}"
    "enum Opt {a, b, c = 1}"

    "enum Opt {a = 0, b = 2, c = 1}"
    "enum Opt {a = 'a', b = 'c', c = 'b'}"

    # Test:
    "enum Opt : int {a = 0}"

    "enum Opt : int {a = 0, b, c}"
    "enum Opt : int {a, b, c = 1}"

    "enum Opt : int {a = 0, b = 2, c = 1}"
    "enum Opt : char {a = 'a', b = 'c', c = 'b'}"


def test_decl_union_type_success() -> None:
    # Test:
    "union Empty {}"

    # Test:
    "union Value {int a;}"
    "union Value {int a; float b;}"

    # Test:
    "union Value {int a; struct {int b;};};"

    # Test:
    "struct TagedUnion {int tag; union {int i; float f;};}"


def test_decl_type_storage_success() -> None:
    # Test:
    "auto x = 0"
    "auto ptr = &x"
    "auto val = (double) 0.0"

    # Test:
    "const int x = 0"

    # Test:
    "restrict int x = 0"

    # Test:
    "static int x = 0"


def test_decl_typeof_success() -> None:

    pass


def test_decl_typeof_unqual_success() -> None:
    pass


def test_decl_static_assert_success() -> None:
    pass


def test_decl_success() -> None:
    # static_assert
    # some struct declaration or enum declaration
    pass


def test_decl_failure() -> None:
    pass


def test_decl() -> None:
    test_decl_success()
    test_decl_failure()


def test_stmt_compound_success() -> None:
    # Test:
    test_ast("{}")
    test_ast("{;}")
    test_ast("{a = 0;}")

    # Test:
    test_ast("{if (x) {a = 0} else {a =1}}")
    test_ast("{for (int x = 0; x < size; ++x) {a += 1;}}")
    test_ast("{while (x < size) {x += 1;}}")
    test_ast("{do {x += 1;} while (x < size);}")
    test_ast("{a = 0; {a = 1;}}")


def test_stmt_expr_success() -> None:
    # Test:
    test_ast(";")

    # Test:
    test_ast("a;")

    test_ast("0;")
    test_ast("0.0;")

    test_ast("'a';")
    test_ast("\"a\";")

    # Test:
    test_ast("1 + 2;")
    test_ast("a + b;")

    test_ast("a + 2;")
    test_ast("1 + a;")


def test_stmt_if_success() -> None:
    # Test:
    test_ast("if (1) a = 0;")
    test_ast("if (x) a = {0};")
    test_ast("if (0 + 1) a = 0;")
    test_ast("if ('a' - 'a') a = 0;")
    test_ast("if (ptr != nullptr) a = 0;")
    test_ast("if ((x = foo()) != -1) a = 0;")

    # Test:
    test_ast("if (1) {a = 0}; b = 1;}")
    test_ast("if (x) {a = 0}; b = 1;}")
    test_ast("if (0 + 1) {a = 0; b = 1;}")
    test_ast("if ('a' - 'a') {a = 0; b = 1;}")
    test_ast("if (ptr != nullptr) { a = 0; b = 1;}")
    test_ast("if ((x = foo()) != -1) {a = 0; b = 1;}")

    # Test:
    test_ast("if (1) a = 0; else b = 1;")
    test_ast("if (x) a = 0; else b = 1;")
    test_ast("if (0 + 1) a = 0; else b = 1;")
    test_ast("if ('a' - 'a') a = 0; else b = 1;")
    test_ast("if (ptr != nullptr) a = 0; else b = 1;")
    test_ast("if ((x = foo()) != {-1}) a = 0; else b = 1;")

    # Test:
    test_ast("if (1) {a = 0; b = 1;}")
    test_ast("if (x) {a = 0; b = 1;}")
    test_ast("if (0 + 1) {a = 0; b = 1;}")
    test_ast("if ('a' - 'a') {a = 0; b = 1;}")
    test_ast("if (ptr != nullptr) { a = 0; b = 1;}")
    test_ast("if ((x = foo()) != -1) {a = 0; b = 1;}")

    # Test:
    test_ast("if (1) a = 0; b = 0;")

    # Test:
    test_ast("if (1) a = 0; else if (0) b = 1; else c = 2;")


def test_stmt_case_success() -> None:
    # Test:
    test_ast("case 0:")
    test_ast("case 'a':")

    test_ast("case x:")
    test_ast("case foo():")

    # Test:
    test_ast("default:")


def test_stmt_switch_success() -> None:
    # Test:
    test_ast("switch (0) {}")
    test_ast("switch ('a') {}")
    test_ast("switch (x) {}")

    # Test:
    test_ast("switch (1 + 2) {}")
    test_ast("switch (a + b) {}")
    test_ast("switch (1 + b) {}")
    test_ast("switch (a + 2) {}")
    test_ast("switch (foo()) {}")

    # Test:
    test_ast("switch (0) {case 'a': break; default: return 0;}")


def test_stmt_while_success() -> None:
    # Test:
    test_ast("while (1) x += 1;")
    test_ast("while (x) x += 1;")
    test_ast("while (0 + 1) x += 1;")
    test_ast("while ('a' - 'a') x += 1;")
    test_ast("while (ptr != nullptr) x += 1;")
    test_ast("while ((x = foo()) != -1) x += 1;")

    # Test:
    test_ast("while (1) {a = 0; x += 1;}")
    test_ast("while (x) {a = 0; x += 1;}")
    test_ast("while (0 + 1) {a = 0; x += 1;}")
    test_ast("while ('a' - 'a') {a = 0; x += 1;}")
    test_ast("while (ptr != nullptr) {a = 0; x += 1;}")
    test_ast("while ((x = foo()) != -1) {a = 0; x += 1;}")


def test_stmt_do_while_success() -> None:
    # Test:
    test_ast("do a += 1 while(1);")
    test_ast("do a += 1 while (x);")
    test_ast("do a += 1 while (0 + 1);")
    test_ast("do a += 1 while ('a' - 'a');")
    test_ast("do a += 1 while (ptr != nullptr);")
    test_ast("do a += 1 while ((x = foo()) != -1);")

    # Test:
    test_ast("do {a = 0; b += 1;} while (1);")
    test_ast("do {a = 0; b += 1;} while (x);")
    test_ast("do {a = 0; b += 1;} while (0 + 1);")
    test_ast("do {a = 0; b += 1;} while ('a' - 'a');")
    test_ast("do {a = 0; b += 1;} while (ptr != nullptr);")
    test_ast("do {a = 0; b += 1;} while ((x = foo()) != -1);")


def test_stmt_for_success() -> None:
    # Test:
    test_ast("for (int x = 0; x < size; ++x) a += 1;")

    # Test:
    test_ast("for (; x < size; ++x) a += 1;")
    test_ast("for (int x = 0;; ++x) a += 1;")
    test_ast("for (int x = 0; x < size;) a += 1;")

    # Test:
    test_ast("for (int x = 0;;) a += 1;")
    test_ast("for (; x < size;) a += 1;")
    test_ast("for (;; ++x) a += 1;")

    # Test:
    test_ast("for (;;) a += 1;")

    # Test:
    test_ast("for (int x = 0; x < size; ++x) {a += 1; b += 1;}")

    # Test:
    test_ast("for (; x < size; ++x) {a += 1; b += 1;}")
    test_ast("for (int x = 0;; ++x) {a += 1; b += 1;}")
    test_ast("for (int x = 0; x < size;) {a += 1; b += 1;}")

    # Test:
    test_ast("for (int x = 0;;) {a += 1; b += 1;}")
    test_ast("for (; x < size;) {a += 1; b += 1;}")
    test_ast("for (;; ++x) {a += 1; b += 1; }}")

    # Test:
    test_ast("for (;;) {a += 1; b += 1;}")


def test_stmt_goto_success() -> None:
    test_ast("goto out;")


def test_stmt_label_success() -> None:
    # Test:
    test_ast("out: a += 1;")
    test_ast("out: \nfree(x);")
    test_ast("out: ;")

    # Test:
    test_ast("out: int a = 1;")


def test_stmt_break_success() -> None:
    # Test:
    test_ast("break;")


def test_stmt_continue_success() -> None:
    # Test:
    test_ast("continue;")


def test_stmt_return_success() -> None:
    # Test:
    test_ast("return;")

    # Test:
    test_ast("return a;")
    test_ast("return 1;")
    test_ast("return (a = 1);")


def test_stmt_success() -> None:
    test_stmt_compound_success()
    test_stmt_expr_success()
    test_stmt_if_success()
    test_stmt_switch_success()
    test_stmt_while_success()
    test_stmt_do_while_success()
    test_stmt_for_success()
    test_stmt_goto_success()
    test_stmt_label_success()
    test_stmt_break_success()
    test_stmt_continue_success()
    test_stmt_return_success()


def test_stmt_failure() -> None:
    pass


def test_stmt() -> None:
    test_stmt_success()
    test_stmt_failure()


def test_simple_code_fib_01_success() -> None:
    source_code = """
    int fib(int n) {
        if (n <= 1)
            return n;

        return fib(n - 1) + fib(n - 2);
    }
    """


def test_simple_code_fib_02_success() -> None:
    source_code = """
    int fib(int n) {
        int a = 1, b = 1;

        for (int i = 0; i < n - 2; ++i) {
            int c = a + b;
            a = b;
            b = c;
        }

        return b;
    }
    """


def test_simple_code_is_prime_01_success() -> None:
    source_code = """
    bool is_prime(unsigned num) {
        if (num < 2)
            return false;

        unsigned div = 2;
        unsigned sqrt_uint_max = 1 << sizeof(unsigned) * 4;

        while (div <= sqrt_uint_max &&
                div * div <= num) {

            if (num % div == 0)
                return false;

            ++div;
        }

        return true;
    }
    """



def test_simple_code_is_prime_02_success() -> None:
    source_code = """
    bool is_prime(unsigned num) {
        assert(num < UINT_MAX);
        const unsigned size = num + 1;

        // WARNING: VLA
        bool is_prime_map[size];

        for (unsigned i = 0; i < size; ++i)
            is_prime_map[i] = true;

        assert(size >= 2);
        is_prime_map[0] = is_prime_map[1] = false;

        for (unsigned p = 2; p <= size / p; ++p) {
            if (!is_prime_map[p])
                continue;

            for (unsigned i = p * p; i <= size; i += p ) {
                is_prime_map[i] = false;

                if (size - i < p)
                    break;
            }
        }

        return is_prime_map[num]
    }
    """


def test_simple_code_duffs_device_01_success() -> None:
    source_code = """
    void copy(short *to, short *from, int count) {
        if (count <= 0) return;

        int remainder = count % 8;

        switch (remainder) {
            case 7: *to = *from++;
            case 6: *to = *from++;
            case 5: *to = *from++;
            case 4: *to = *from++;
            case 3: *to = *from++;
            case 2: *to = *from++;
            case 1: *to = *from++;
            case 0: break;
        }

        int blocks = count / 8;

        while (blocks > 0) {
            *to = *from++;
            *to = *from++;
            *to = *from++;
            *to = *from++;
            *to = *from++;
            *to = *from++;
            *to = *from++;
            *to = *from++;
            blocks--;
        }
    }
    """


def test_simple_code_duffs_device_02_success() -> None:
    # NOTE: The DUFF is an acronym in popular culture for
    # "Designated Ugly Fat Friend".

    source_code = """
    void copy(short *to, short *from, int count) {
        int n = (count + 7) / 8;
        switch (count % 8) {
            case 0: do { *to = *from++;
            case 7:      *to = *from++;
            case 6:      *to = *from++;
            case 5:      *to = *from++;
            case 4:      *to = *from++;
            case 3:      *to = *from++;
            case 2:      *to = *from++;
            case 1:      *to = *from++;
                    } while (--n > 0);
        }
    }
    """


def test_simple_code_quake_rsqrt_success() -> None:
    source_code = """
    float Q_rsqrt( float number )
    {
        long i;
        float x2, y;
        const float threehalfs = 1.5F;

        x2 = number * 0.5F;
        y  = number;
        i  = * ( long * ) &y;                       // evil floating point bit level hacking
        i  = 0x5f3759df - ( i >> 1 );               // what the fuck?
        y  = * ( float * ) &i;
        y  = y * ( threehalfs - ( x2 * y * y ) );   // 1st iteration
    //  y  = y * ( threehalfs - ( x2 * y * y ) );   // 2nd iteration, this can be removed

        return y;
    }
    """


def test_simple_code_trigraphs_success() -> None:
    source_code = """
    int main() ??<
        if (1) ??/
            (void) printf("Wait, what???/n");
        return 0;
    ??>
    """


def test_simple_code_success() -> None:
    test_simple_code_fib_01_success()
    test_simple_code_fib_02_success()
    test_simple_code_is_prime_01_success()
    test_simple_code_is_prime_02_success()
    test_simple_code_duffs_device_01_success()
    test_simple_code_duffs_device_02_success()

    test_simple_code_quake_rsqrt_success()
    test_simple_code_trigraphs_success()


def test_simple_code_failure() -> None:
    pass


def test_simple_code() -> None:
    test_simple_code_success()
    test_simple_code_failure()


def test() -> None:
    test_expr()
    test_decl()
    test_stmt()
    test_simple_code()


if __name__ == "__main__":
    test()


# will support auto
# will support typeof and typeof_un
# will support typedef
# will support static

# inline and register will just as recommendation,

# won't support constexpr
# won't support register
# won't support extern
# won't support thread_local
# won't support atomic
# won't support _complex
# won't support parsing more then one file, at least for now
# won't support alighof and alignas
# won't support bitfields


# struct Rect r2 = {.top_left.x = 0, .bot_right.y = 10};
# struct Point {
#     int x;
#     int y;
# };
#
# // An array of 20 Point structures
# struct Point curve[20] = {
#     [10].x = 1,
#     [10].y = 5,
#     [15].x = 42
# };


# struct Point { int x, y; };
# struct Path { struct Point steps[100]; };
#
# // Array of 5 Path objects
# struct Path journey[5] = {
#     [2].steps[50].x = 10,
#     [2].steps[50].y = 20
# };


# int matrix[3][3] = {
#     [1][1] = 5,
#     [2][0] = 9
# };


# won't use bit fields, because we have bit-int


# TODO: diagraphs if meee
# TODO: maybe should make everything from string, into bytes, because
#       fucking me
