from enum import Enum
from decimal import Decimal

from error import *
from tokenizer import Tokenizer, Token, TokenTag, NumberTag

# Abstract Syntax Tree
# Represents the hierarchical logical structure of the source code.
#
# NOTE: The AST omits concrete syntactic details (e.g. parentheses or
# semicolons) to purely focus on language semantics.
#
# Analogy (Natural Language):
# 1. Tokenizer: Sees a string of letters and separates them into
#    distinct words and marks.
# 2. Parser: Figures out how those words fit together according to
#    the rules of language. It identifies which word is the actor and
#    which is the action.
# 3. Abstract Syntax Tree: Throws away the "flavor" words and
#    punctuation to focus entirely on the core intent — "Who-Does-What".


FORMAT_SPEC: str = "{}"

COMMENT_TAGS: set[TokenTag] = {
    TokenTag.line_comment,
    TokenTag.multi_line_comment
}

NOT_SUPPORTED_KEYWORDS: set[str] = {
    "alignas", "alignof", "auto", "case", "constexpr", "extern",
    "goto", "register", "restrict", "static_assert", "thread_local",
    "typeof", "typeof_unqual", "_Atomic", "_Complex", "_Generic",
    "_Imaginary",  "_Noreturn",
}

NOT_SUPPORTED_PUNTS: set[str] = {
    "#", "##", "%:", "...", "%:%:"
}


# Abstract syntax tree nodes.
class ASTNode:
    pass


class InitNode(ASTNode):
    pass


class TypeNode(ASTNode):
    pass


class ExprNode(ASTNode):
    pass


class DeclNode(ASTNode):
    pass


class StmtNode(ASTNode):
    pass


# Type specifiers.
class TypeQualifier(Enum):
    const = "const"
    restrict = "restrict"
    volatile = "volatile"
    atomic = "_Atomic"


class StorageSpec(Enum):
    auto = "auto"
    constexpr = "constexpr"
    extern = "extern"
    register = "register"
    static = "static"
    thread_local = "thread_local"
    typedef = "typedef"


class FunctionSpec(Enum):
    inline = "inline"
    noreturn = "_Noreturn"


class SignKind(Enum):
    signed = "signed"
    unsigned = "unsigned"
    default = ""


class IntKind(Enum):
    short = "short"
    int = "int"
    long = "long"
    long_long = "long long"


class CharKind(Enum):
    char = "char"
    wchar = "wchar_t"
    char8 = "char8_t"
    char16 = "char16_t"
    char32 = "char32_t"


class RealFloatKind(Enum):
    float = "float"
    double = "double"
    long_double = "long double"


class DecimalFloatKind(Enum):
    decimal32 = "_Decimal32"
    decimal64 = "_Decimal64"
    decimal128 = "_Decimal128"


# Types.
class VoidType(TypeNode):
    pass


class NullPtrType(TypeNode):
    pass


class BoolType(TypeNode):
    pass


class CharType(TypeNode):
    def __init__(self,
                 kind: CharKind,
                 sign_kind: SignKind | None) -> None:
        self.kind = kind
        self.sign_kind = sign_kind


class IntType(TypeNode):
    def __init__(self, kind: IntKind, sign_kind: SignKind) -> None:
        self.kind = kind
        self.sign_kind = sign_kind


class BitIntType(TypeNode):
    def __init__(self,
                 width_expr: ExprNode,
                 sign_kind: SignKind) -> None:
        self.width_expr = width_expr
        self.sign_kind = sign_kind


class RealFloatType(TypeNode):
    def __init__(self, kind: RealFloatKind) -> None:
        self.kind = kind


class DecimalFloatType(TypeNode):
    def __init__(self, kind: DecimalFloatKind) -> None:
        self.kind = kind


class ComplexType(TypeNode):
    def __init__(self, kind: RealFloatKind) -> None:
        self.kind = kind


class ImaginaryType(TypeNode):
    def __init__(self, kind: RealFloatKind) -> None:
        self.kind = kind


class PtrType(TypeNode):
    def __init__(self,
                 pointee: TypeNode,
                 qualifiers: set[TypeQualifier]) -> None:
        self.pointee = pointee
        self.qualifiers = qualifiers


# Have to cover:
# • T[N]         — constant-length array
# • T[expr]      — VLA with a runtime bound
# • T[]          — incomplete array (elem_count = None)
# • T[*]         — VLA of unspecified size in a prototype (is_unspec_vla)
# • T[static N]  — minimum-size hint for pointers (is_static = True)
class ArrayType(TypeNode):
    def __init__(self,
                 elem_type: TypeNode,
                 elem_count: ExprNode | None,
                 is_static: bool,
                 is_unspec_vla: bool,
                 qualifiers: set[TypeQualifier]) -> None:
        self.elem_type = elem_type
        self.elem_count = elem_count
        self.is_static = is_static
        self.is_unspec_vla = is_unspec_vla
        self.qualifiers = qualifiers


class ParamSpec:
    def __init__(self, iden: str | None, param_type: TypeNode) -> None:
        self.iden = iden
        self.param_type = param_type


class FunType(TypeNode):
    def __init__(self,
                 ret_type: TypeNode,
                 params: list[ParamSpec],
                 is_variadic: bool) -> None:
        self.ret_type = ret_type
        self.params = params
        self.is_variadic = is_variadic


class EnumType(TypeNode):
    def __init__(self,
                 iden: str | None,
                 members: list[EnumValSpec] | None,
                 member_type: TypeNode | None) -> None:
        self.iden = iden
        self.members = members
        self.member_type = member_type


class StructType(TypeNode):
    def __init__(self,
                 iden: str | None,
                 members: list[DeclNode] | None) -> None:
        self.iden = iden
        self.members = members


class UnionType(TypeNode):
    def __init__(self,
                 iden: str | None,
                 members: list[DeclNode] | None) -> None:
        self.iden = iden
        self.members = members


class AtomicType(TypeNode):
    def __init__(self, base_type: TypeNode) -> None:
        self.base_type = base_type


class TypeOfType(TypeNode):
    def __init__(self, expr_or_type: ExprNode | TypeNode) -> None:
        self.expr_or_type = expr_or_type


class TypeOfUnqualType(TypeNode):
    def __init__(self, expr_or_type: ExprNode | TypeNode) -> None:
        self.expr_or_type = expr_or_type


class TypeDefType(TypeNode):
    def __init__(self, iden: str) -> None:
        self.iden = iden


class QualifiedType(TypeNode):
    def __init__(self,
                 base_type: TypeNode,
                 qualifiers: set[TypeQualifier],
                 storage: StorageSpec | None,
                 alignment: ExprNode | TypeNode | None,
                 fun_spec: FunctionSpec | None) -> None:
        assert not isinstance(base_type, QualifiedType)

        self.base_type = base_type
        self.qualifiers = qualifiers
        self.storage = storage
        self.alignment = alignment
        self.fun_spec = fun_spec


# Initialisers.
class InitMember(InitNode):
    def __init__(self,
                 member_iden: str,
                 rec_init: InitNode | None,
                 expr_or_init: ExprNode | InitNode | None) -> None:
        self.member_iden = member_iden
        self.rec_init = rec_init
        self.expr_or_init = expr_or_init


class InitIndex(InitNode):
    def __init__(self,
                 idx_expr: ExprNode,
                 rec_init: InitNode | None,
                 expr_or_init: ExprNode | InitNode | None) -> None:
        self.idx_expr = idx_expr
        self.rec_init = rec_init
        self.expr_or_init = expr_or_init


class InitList(InitNode):
    def __init__(self,
                 init_elems: list[ExprNode | InitNode]) -> None:
        self.init_elems = init_elems


# Operators.
class OpTag(Enum):
    pass


class UnaOpTag(OpTag):
    pass


class UnaPrefOpTag(UnaOpTag):
    # ++expr
    prefix_inc = "++"
    # --expr
    prefix_dec = "--"
    # &expr
    addr_of = "&"
    # *expr
    deref = "*"
    # +expr
    plus = "+"
    # -expr
    neg = "-"
    # ~expr
    bit_neg = "~"
    # !expr
    bool_neg = "!"


class UnaPostOpTag(UnaOpTag):
    # expr++
    postfix_inc = "++"
    # expr--
    postfix_dec = "--"


class BinOpTag(OpTag):
    # lhs & rhs
    bit_and = "&"
    # lhs * rhs
    mul = "*"
    # lhs + rhs
    add = "+"
    # lhs - rhs
    sub = "-"
    # lhs / rhs
    div = "/"
    # lhs % rhs
    mod = "%"
    # lhs << rhs
    shl = "<<"
    # lhs >> rhs
    shr = ">>"
    # lhs < rhs
    lt = "<"
    # lhs > rhs
    gt = ">"
    # lhs <= rhs
    le = "<="
    # lhs >= rhs
    ge = ">="
    # lhs == rhs
    eq = "=="
    # lhs != rhs
    ne = "!="
    # lhs ^ rhs
    bit_xor = "^"
    # lhs | rhs
    bit_or = "|"
    # lhs && rhs
    bool_and = "&&"
    # lhs || rhs
    bool_or = "||"
    # lhs = rhs
    assign = "="
    # lhs *= rhs
    mul_assign = "*="
    # lhs /= rhs
    div_assign = "/="
    # lhs %= rhs
    mod_assign = "%="
    # lhs += rhs
    add_assign = "+="
    # lhs -= rhs
    sub_assign = "-="
    # lhs <<= rhs
    shl_assign = "<<="
    # lhs >>= rhs
    shr_assign = ">>="
    # lhs &= rhs
    bit_and_assign = "&="
    # lhs ^= rhs
    bit_xor_assign = "^="
    # lhs |= rhs
    bit_or_assign = "|="


# Expressions.
class IdenExpr(ExprNode):
    def __init__(self, iden: str) -> None:
        self.iden = iden


class NullPtrLitExpr(ExprNode):
    pass


class BoolLitExpr(ExprNode):
    def __init__(self, bool_expr: bool) -> None:
        self.bool_expr = bool_expr


class IntLitExpr(ExprNode):
    def __init__(self,
                 int_expr: int,
                 int_type: IntType | BitIntType) -> None:
        self.int_expr = int_expr
        self.int_type = int_type


class RealFloatLitExpr(ExprNode):
    def __init__(self,
                 float_expr: float,
                 float_type: RealFloatType) -> None:
        self.float_expr = float_expr
        self.float_type = float_type


class DecFloatLitExpr(ExprNode):
    def __init__(self,
                 float_expr: Decimal,
                 float_type: DecimalFloatType) -> None:
        self.float_expr = float_expr
        self.float_type = float_type


class CharLitExpr(ExprNode):
    def __init__(self, char_expr: str, char_type: CharType) -> None:
        self.char_expr = char_expr
        self.char_type = char_type


class StrLitExpr(ExprNode):
    def __init__(self, str_expr: str, char_type: CharType) -> None:
        self.str_expr = str_expr
        self.char_type = char_type


AssocTable = dict[TypeNode | None, ExprNode]


class GenericSelExpr(ExprNode):
    def __init__(self,
                 ctrl_expr: ExprNode,
                 assoc_table: AssocTable) -> None:
        self.ctrl_expr = ctrl_expr
        self.assoc_table = assoc_table


class ArraySubExpr(ExprNode):
    def __init__(self, base_expr: ExprNode, idx_expr: ExprNode) -> None:
        self.base_expr = base_expr
        self.idx_expr = idx_expr


class CallExpr(ExprNode):
    def __init__(self,
                 callee_expr: ExprNode,
                 arg_exprs: list[ExprNode]) -> None:
        self.callee_expr = callee_expr
        self.arg_exprs = arg_exprs


class MemberExpr(ExprNode):
    def __init__(self,
                 base_expr: ExprNode,
                 member_iden: str,
                 is_arrow: bool) -> None:
        self.base_expr = base_expr
        self.member_iden = member_iden
        self.is_arrow = is_arrow


class CompoundLitExpr(ExprNode):
    def __init__(self,
                 expr_type: TypeNode,
                 init: InitList) -> None:
        self.expr_type = expr_type
        self.init = init


class CastExpr(ExprNode):
    def __init__(self,
                 expr_type: TypeNode,
                 expr: ExprNode) -> None:
        self.expr_type = expr_type
        self.expr = expr


class OpExpr(ExprNode):
    def __init__(self, op: OpTag, exprs: list[ExprNode]) -> None:
        self.op = op
        self.exprs = exprs


class CondExpr(ExprNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 true_expr: ExprNode,
                 false_expr: ExprNode,
                 ) -> None:
        self.cond_expr = cond_expr
        self.true_expr = true_expr
        self.false_expr = false_expr


class CommaExpr(ExprNode):
    def __init__(self, exprs: tuple[ExprNode, ExprNode]) -> None:
        self.exprs = exprs


class SizeOfExpr(ExprNode):
    def __init__(self, expr_or_type: ExprNode | TypeNode) -> None:
        self.expr_or_type = expr_or_type


class AlignOfExpr(ExprNode):
    def __init__(self, align_type: TypeNode) -> None:
        self.align_type = align_type


# Declarations.
class TransUnitDecl(DeclNode):
    def __init__(self, decls: list[DeclNode]) -> None:
        self.decls = decls


class EmptyDecl(DeclNode):
    pass


class VarDecl(DeclNode):
    def __init__(self,
                 var_type: QualifiedType,
                 iden: str,
                 init: ExprNode | InitList | None) -> None:
        self.var_type = var_type
        self.iden = iden
        self.init = init


class FunDecl(DeclNode):
    def __init__(self,
                 fun_type: FunType,
                 iden: str,
                 body: CompoundStmt | None) -> None:
        self.fun_type = fun_type
        self.iden = iden
        self.body = body


class EnumValSpec:
    def __init__(self, iden: str, expr: ExprNode | None) -> None:
        self.iden = iden
        self.expr = expr


class EnumDecl(DeclNode):
    def __init__(self, enum_type: QualifiedType) -> None:
        self.enum_type = enum_type


class StructDecl(DeclNode):
    def __init__(self, struct_type: QualifiedType) -> None:
        self.struct_type = struct_type


class UnionDecl(DeclNode):
    def __init__(self, union_type: QualifiedType) -> None:
        self.union_type = union_type


class TypedefDecl(DeclNode):
    def __init__(self,
                 base_type: QualifiedType,
                 alias_iden: str) -> None:
        self.base_type = base_type
        self.alias_iden = alias_iden


class StaticAssertDecl(DeclNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 str_expr: StrLitExpr | None) -> None:
        self.cond_expr = cond_expr
        self.str_expr = str_expr


# Statements.
# Flint build-in statement.
class AssertStmt(StmtNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 str_expr: StrLitExpr | None,
                 arg_exprs: list[ExprNode]) -> None:
        self.cond_expr = cond_expr
        self.str_expr = str_expr
        self.arg_exprs = arg_exprs


# Flint build-in statement.
class PrintLnStmt(StmtNode):
    def __init__(self,
                 str_expr: StrLitExpr | None,
                 arg_exprs: list[ExprNode]) -> None:
        self.str_expr = str_expr
        self.arg_exprs = arg_exprs


class CompoundStmt(StmtNode):
    def __init__(self, stmts: list[StmtNode]) -> None:
        self.stmts = stmts


class DeclStmt(StmtNode):
    def __init__(self, decl: DeclNode) -> None:
        self.decl = decl


class ExprStmt(StmtNode):
    def __init__(self, expr: ExprNode) -> None:
        self.expr = expr


class IfStmt(StmtNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 then_stmt: StmtNode,
                 else_stmt: StmtNode | None) -> None:
        self.cond_expr = cond_expr
        self.then_stmt = then_stmt
        self.else_stmt = else_stmt


class CaseLabelStmt(StmtNode):
    def __init__(self, cond_expr: ExprNode | None) -> None:
        self.cond_expr = cond_expr


class SwitchStmt(StmtNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 then_stmt: StmtNode) -> None:
        self.cond_expr = cond_expr
        self.then_stmt = then_stmt


class ForStmt(StmtNode):
    def __init__(self,
                 init_clause: ExprNode | DeclNode | None,
                 cond_expr: ExprNode | None,
                 inc_expr: ExprNode | None,
                 then_stmt: StmtNode) -> None:
        self.init_clause = init_clause
        self.cond_expr = cond_expr
        self.inc_expr = inc_expr
        self.then_stmt = then_stmt


class WhileStmt(StmtNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 then_stmt: StmtNode) -> None:
        self.cond_expr = cond_expr
        self.then_stmt = then_stmt


class DoWhileStmt(StmtNode):
    def __init__(self, do_stmt: StmtNode, cond_expr: ExprNode) -> None:
        self.do_stmt = do_stmt
        self.cond_expr = cond_expr


class GotoStmt(StmtNode):
    def __init__(self, label_iden: str) -> None:
        self.label_iden = label_iden


class LabelStmt(StmtNode):
    def __init__(self, iden: str) -> None:
        self.iden = iden


class BreakStmt(StmtNode):
    pass


class ContinueStmt(StmtNode):
    pass


class ReturnStmt(StmtNode):
    def __init__(self, ret_expr: ExprNode | None) -> None:
        self.ret_expr = ret_expr


# Abstract syntax tree.
class AST:
    def __init__(self, buffer: str) -> None:
        self.buffer = buffer
        self.root: TransUnitDecl | None = None

    # NOTE: Maybe should refactor it to tokenizer.
    def token_str(self, token: Token) -> str:
        return self.buffer[token.loc.start:token.loc.end]

    def is_token_supported(self, token: Token) -> bool:
        if token.tag == TokenTag.keyword:
            return self.token_str(token) not in NOT_SUPPORTED_KEYWORDS

        if token.tag == TokenTag.punctuator:
            return self.token_str(token) not in NOT_SUPPORTED_PUNTS

        return True

    def build(self, save_comments: bool) -> None | Error:
        from parser import Parser

        tok = Tokenizer(self.buffer)
        tokens: list[Token] = []

        while True:
            token: Token = tok.next()

            if token.tag == TokenTag.invalid:
                desc = token.err.value if token.err is not None else "invalid token"
                snippet = self.buffer[token.loc.start:token.loc.end]
                line = self.buffer.count('\n', 0, token.loc.start) + 1
                return Error(f"error:{line}: {desc}: '{snippet}'")

            if not self.is_token_supported(token):
                snippet = self.buffer[token.loc.start:token.loc.end]
                line = self.buffer.count('\n', 0, token.loc.start) + 1
                return Error(f"error:{line}: unsupported token '{snippet}'")

            if not save_comments and token.tag in COMMENT_TAGS:
                continue

            tokens.append(token)

            if token.tag == TokenTag.eof:
                break

        parser = Parser(self.buffer, tokens)

        decls: TransUnitDecl | Error = parser.parse()
        if isinstance(decls, Error):
            return decls

        self.root = decls

    def analyze(self) -> None | Error:
        from analysis import (
            Analysis01, Analysis02, Analysis03, Analysis04, Analysis05,
            Analysis06, Analysis07, Analysis08, Analysis09, Analysis10,
            Analysis11, Analysis12, Analysis13, Analysis14,
        )

        passes = [
            Analysis01(),   # break/continue context
            Analysis02(),   # switch / case label validity
            Analysis03(),   # declaration uniqueness per block scope
            Analysis04(),   # identifier declared before use
            Analysis05(),   # function signature consistency
            # Analysis06(),   # goto label existence and uniqueness
            # Analysis07(),   # goto forward-jump over declarations
            Analysis08(),   # format-string specifier count
            Analysis09(),   # typedef base-type validity
            Analysis10(),   # return expression type compatibility
            # Analysis11(),   # constexpr initializer is a constant expression
            Analysis12(),   # variable initializer type compatibility
            Analysis13(),   # no assignment to const-qualified lvalue
            Analysis14(),   # operator and expression type validation
        ]

        for analysis in passes:
            result = analysis.analyze(self)
            if result is not None:
                return result

        return None

    def optimize(self) -> None:
        pass

    def dump_posfix(self) -> str:
        pass

    def dump_tree(self) -> str:
        pass
