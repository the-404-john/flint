from enum import Enum

from error import ErrorCode
from tokenizer import Tokenizer
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

Designator = InitNode | None
InitValue = ExprNode | InitNode | None

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

binding_power: dict[str, tuple[int, int]]= {
    '+':
}

class PrimitiveType(Type, Enum):
    bool = "bool"
    char = "char"
    short = "short"
    int = "int"
    long = "long"
    long_long = "long long"
    float = "float"
    double = "double"
    long_double = "long double"
    void = "void"
    bit_int = "_BitInt"
    decimal_32 = "_Decimal32"
    decimal_64 = "_Decimal64"
    decimal_128 = "_Decimal128"
    complex = "_Complex"


class TypeQualifier(Enum):
    const = "const"
    restrict = "restrict"
    volatile = "volatile"
    atomic = "_Atomic"


class TypeStorage(Enum):
    auto = "auto"
    constexpr = "constexpr"
    extern = "extern"
    register = "register"
    static = "static"
    thread_local = "_Thread_local"
    typedef = "typedef"


class Parser:
    def __init__(self, buffer: str, tokens: list[Token]) -> None:
        self.index = 0
        self.buffer = buffer
        self.tokens = tokens

    def token_str(self, token: Token) -> str:
        return self.buffer[token.loc.start:token.loc.end]

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

    def check_type_name(self) -> bool:
        pass

    #
    def iden(self) -> str:
        pass

    def expr_or_decl(self) -> ExprNode | DeclNode | ErrorCode:
        pass

    def expr_or_type(self) -> ExprNode | TypeNode |:
        pass

    # Declarations.
    def typeof_spec(self) -> :TypeOfSpec | ErrorCode:
        self.expect(TokenTag.keyword, "typeof")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        expr_or_type: ExprNode | Type | ErrorCode = self.expr_or_type()
        if isinstance(expr_or_type, ErrorCode):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return TypeOfSpec(expr_or_type)

    def typeof_unqual_spec(self) -> TypeOfUnqualSpec | ErrorCode:
        self.expect(TokenTag.keyword, "typeof_unqual")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.Ej

        expr_or_type: ExprNode | Type | ErrorCode = self.expr_or_type()
        if isinstance(expr_or_type, ErrorCode):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return TypeOfUnqualSpec(expr_or_type)

    def alignas_spec(self) -> AlignAsSpec | ErrorCode:
        self.expect(TokenTag.keyword, "alignas")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.Ej

        expr_or_type: ExprNode | Type | ErrorCode = self.expr_or_type()
        if isinstance(expr_or_type, ErrorCode):
            return expr_or_type

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return AlignAsSpec(expr_or_type)

    def var_decl(self) -> VarDecl | ErrorCode:
        pass

    def fun_param_list(self) -> list[tuple[TypeNode, str | None]]:
        param_list: list[tuple[TypeNode, str | None] = []

        while True:
            param_iden: str | None | ErrorCode = None
            param_type: TypeNode | ErrorCode = self.type()

            if isinstance(param_type, ErrorCode):
                return param_type

            if self.check(TokenTag.identifier, None):
                param_iden = self.iden()

                if isinstance(param_iden, ErrorCode):
                    return param_iden

            param_list.append((param_type, param_iden))

            if not self.match(TokenTag.punctuator, ","):
                break

        return param_list

    def fun_decl(self) -> FunDecl | ErrorCode:
        ret_type: TypeNode | ErrorCode = self.type()
        if isinstance(ret_type, ErrorCode):
            return ret_type

        fun_iden: str | ErrorCode = self.iden()
        if isinstance(fun_iden, ErrorCode):
            return fun_iden

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        param_list: list[tuple[TypeNode, str | None] = []
        if not self.check(TokenTag.punctuator, ")"):
            param_list = self.fun_param_list()

            if isinstance(param_list, ErrorCode):
                return param_list

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        fun_def: CompoundStmt | None | ErrorCode = None
        if self.check(TokenTag.punctuator, "{"):
            fun_def = self.compound_stmt()

            if isinstance(fun_def, ErrorCode):
                return fun_def

        return FunDecl(ret_type, fun_iden, param_list, fun_def)

    def static_assert_decl(self) -> StaticAssertDecl | ErrorCode:
        self.expect(TokenTag.keyword, "static_assert")

        if not self.match(TokenTag.punctuator, "("):
            return ErrorCode.E

        # FIX: Make sure, to not consume the comma operator.
        cond_expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(cond_expr, ErrorCode):
            return cond_expr

        str_expr: StrListExpr | None | ErrorCode = None

        if self.match(TokenTag.punctuator, ","):
            str_expr = self.str_expr()

            if isinstance(str_expr, ErrorCode):
                return str_expr

        if not self.match(TokenTag.punctuator, ")"):
            return ErrorCode.E

        return StaticAssertDecl(cond_expr, str_expr)

    def array_decl(self) -> :
        pass

    def decl(self) -> DeclNode | ErrorCode:
        self.type_name()

        self.iden_expr()

        if not self.check(, ";"):
            pass

        if not self.match(, ";"):
            return ErrorCode

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



    def

    def char_expr(self) -> CharLitExpr | ErrorCode:
        token: Token = self.expect(TokenTag.char_literal, None)

        char_expr: str | None = None
        char_bit_length: int | None = None

        if token.encoding is None:
            char_bit_length = 7

        elif token.encoding == EncodingPrefix.utf_8:
            char_bit_length = 8

        elif token.encoding == EncodingPrefix.utf_16:
            char_bit_length = 16

        else:
            # WARNING: Implementation defined for wide character.
            assert token.encoding == EncodingPrefix.utf_32 or \
                   token.encoding == EncodingPrefix.wide_literal:

            char_bit_length = 32

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

        # FIX: not a comma
        expr: ExprNode | ErrorCode = self.expr(0)
        if isinstance(expr, ErrorCode):
            return expr

        if not self.match(TokenTag.punctuator, ","):
            return ErrorCode.E

        table: dict[TypeNode | None, ExprNode] = dict()

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

            # FIX: not a comma
            case_expr: ExprNode | ErrorCode = self.expr(0)
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

        while True:
            arg_expr: ExprNode | ErrorCode = self.expr(0)

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
            expr_or_init = self.expr(0)

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

        if self.check(TokenTag.punctuator, "}"):
            return InitList(init_list)

        while True:
            elem: ExprNode | InitNode | None | ErrorCode = None

            if self.check(TokenTag.punctuator, "."):
                elem = self.init_member()

            elif self.check(TokenTag.punctuator, "["):
                elem = self.init_index()

            elif self.check(TokenTag.punctuator, "{"):
                elem = self.init_list()

            else:
                # FIX: set so it stops on ,
                elem = self.expr()

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





    def expr_nud(self) -> ExprNode | ErrorCode:
        # cast
        # compound
        # -1[ arr ] => - ( 1[ arr ]) | => something something bp
        have_nop_plus = self.match(TokenTag.punctuator, "+")

        if self.match(TokenTag.punctuator, "("):
            expr: ExprNode | ErrorCode = self.expr()
            if isinstance(expr, ErrorCode):
                return expr

            if not self.match(TokenTag.punctuator, ")"):
                return ErrorCode.E

            return expr

        if self.check(TokenTag.identifier, None):
            return self.iden_expr()

        if self.check(TokenTag.number_literal, None):
            return self.num_expr()

        if self.check(Token.char_literal, None):
            return self.char_expr()

        if have_nop_plus:
            return ErrorCode.E

        if self.check(TokenTag.string_literal, None):
            return self.str_expr()

        for op in UnaPrefOpTag:
            if not self.match(TokenTag.punctuator, op.value):
                continue

            una_expr: ExprNode | ErrorCode = self.expr()
            if isinstance(una_expr, ErrorCode):
                return una_expr

            return OpExpr(op, [una_expr])

        # NOTE: Not an atom
        return ErrorCode.E

    def expr_led(self,
                 left_expr: ExprNode,
                 rbp: int) -> ExprNode | ErrorCode:
        # something something, bp
        # There is something wrong, i should collect the operator in
        # the function I think??
        # also something something assignment operators, just parse them
        # and the in the analysis check that it's valid
        if self.check(TokenTag.punctuator, "("):
            return self.call_expr(left_expr)

        if self.check(TokenTag.punctuator, "["):
            return self.array_sub_expr(left_expr)

        if self.check(TokenTag.punctuator, ".") or \
           self.check(TokenTag.punctuator, "->"):
            return self.member_expr(left_expr)

        if self.check(TokenTag.punctuator, ","):
            return self.comma_expr(left_expr)

        if self.check(TokenTag.punctuator, "?"):
            return self.cond_expr(left_expr)

        # FIX: THIS SHIT
        for op in UnsaPostOpTag:
            if not self.match(TokenTag.punctuator, op.value):
                continue

            return OpExpr(op, [left_expr])

        for op in BinOpTag:
            if not self.match(TokenTag.punctuator, op.value):
                continue

            right_expr: ExprNode | ExprNode = self.expr()
            if isinstance(right_expr, ErrorCode):
                return right_expr

            return OpExpr(op, [left_expr, right_expr])

        return ErrorCode.E

    def expr(self, min_bp: int) -> ExprNode | ErrorCode:
        left_expr: ExprNode | ErrorCode = self.expr_nud()

        if isinstance(left_expr, ErrorCode):
            return left_expr

        while True:
            if self.check(TokenTag.eof, None):
                break

            # if not in infix, break
            if self.check(TokenTag.punctuator, ")"):
                break

            # check if it's operator

            lbp, _ = self.peek_bp()

            if min_bp > lbp:
                break

            left_expr = self.expr_led(left_expr)

            if isinstance(left_expr, ErrorCode):
                return left_expr

        return left_expr






    # Statements.
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
        decl: DeclNode | ErrorCode = self.decl()
        if isinstance(decl, ErrorCode):
            return decl

        if isinstance(decl, FunDecl) and decl.fun_def is not None:
            return DeclStmt(decl)

        if not self.match(TokenTag.punctuator, ";"):
            return ErrorCode.E

        return DeclStmt(decl)

    def expr_or_decl_stmt(self) -> ExprStmt | DeclStmt | ErrorCode:
        if self.match(TokenTag.punctuator, ";"):
            return ExprStmt(None)

        if self.check_type_name():
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

    def parse(self) -> ASTRoot | ErrorCode:
        # gcc -E
        while self.peek().tag != TokenTag.eof:
            pass

        return


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


def test_expr_bin_op_success() -> None:
    test_expr_bin_bit_and_success()
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
    test_expr_bin_bit_xor_success()
    test_expr_bin_bit_or_success()
    test_expr_bin_bool_and_success()
    test_expr_bin_bool_or_success()


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


def test_expr_assign_assign_success() -> None:
    # Test:
    test_expr_assign_op("=")


def test_expr_assign_mul_success() -> None:
    # Test:
    test_expr_assign_op("*=")


def test_expr_assign_div_success() -> None:
    # Test:
    test_expr_assign_op("/=")


def test_expr_assign_mod_success() -> None:
    # Test:
    test_expr_assign_op("%=")


def test_expr_assign_add_success() -> None:
    # Test:
    test_expr_assign_op("+=")


def test_expr_assign_sub_success() -> None:
    # Test:
    test_expr_assign_op("-=")


def test_expr_assign_shl_success() -> None:
    # Test:
    test_expr_assign_op("<<=")


def test_expr_assign_shr_success() -> None:
    # Test:
    test_expr_assign_op(">>=")


def test_expr_assign_bit_and_success() -> None:
    # Test:
    test_expr_assign_op("&=")


def test_expr_assign_bit_xor_success() -> None:
    # Test:
    test_expr_assign_op("^=")


def test_expr_assign_bit_or_success() -> None:
    # Test:
    test_expr_assign_op("|=")


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


def test_expr_assign_op_success() -> None:
    test_expr_assign_assign_success()
    test_expr_assign_mul_success()
    test_expr_assign_div_success()
    test_expr_assign_mod_success()
    test_expr_assign_add_success()
    test_expr_assign_sub_success()
    test_expr_assign_shl_success()
    test_expr_assign_shr_success()
    test_expr_assign_bit_and_success()
    test_expr_assign_bit_xor_success()
    test_expr_assign_bit_or_success()


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
