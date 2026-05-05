from enum import Enum
import numpy as np
from typing import TypeVar, Generic

from error import ErrorCode
from tokenizer import TokenTag, NumberTag
from parser import Parser


non_supported: set[TokenTag] = {

}

ParamSpec = tuple[str | None, TypeNode]

EnumValueSpec = tuple[str, ExprNode | None]

MemberSpec = tuple[str, TypeNode]
StructOrUnionSpec = tuple[str | None, list[MemberSpec] | None]

FmtSpec = tuple[StrLitExpr | None, list[ExprNode]]

Designator = InitNode | None
InitValue = ExprNode | InitNode | None


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
    eq = "==",
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
    mul = "*="
    # lhs /= rhs
    div = "/="
    # lhs %= rhs
    mod = "%="
    # lhs += rhs
    add = "+="
    # lhs -= rhs
    sub = "-="
    # lhs <<= rhs
    shl = "<<="
    # lhs >>= rhs
    shr = ">>="
    # lhs &= rhs
    bit_and = "&="
    # lhs ^= rhs
    bit_xor = "^="
    # lhs |= rhs
    bit_or = "|="


# Abstract syntax tree nodes.
class ASTNode:
    pass


class InitNode(ASTNode):
    pass


class ExprNode(ASTNode):
    pass


class DeclNode(ASTNode);
    pass


class StmtNode(ASTNode):
    pass


# Types.
class Type:
    pass

# change representation, probably tree
class TypeName:
    def __init__(self,
                 type: Type,
                 storage_spec: TypeStorage,
                 qualifier_specs: list[TypeQualifier],
                 align_spec: int | None) -> None:
        self.type = type
        self.storage_spec = storage_spec
        self.qualifier_specs = qualifier_specs

        self.align_spec = align_spec
        # self.funtion_spec = funtion_spec


class PointerType(Type):
    def __init__(self, ref_type: TypeName) -> None:
        self.ref_type = ref_type


class ArrayType(Type):
    def __init__(self,
                 elem_type: TypeName,
                 elem_count: int | None) -> None:
        self.elem_type = elem_type
        self.elem_count = elem_count









# Expressions.
class IdenExpr(ExprNode):
    def __init__(self, name: str) -> None:
        self.name = name


class IntLitExpr(ExprNode):
    def __init__(self, int_expr: int, bit_length: int) -> None:
        self.int_expr = int_expr
        self.bit_length = bit_length


class FloatLitExpr(ExprNode):
    def __init__(self, float_expr: np.floating, bit_length: int) -> None:
        self.float_expr = float_expr
        self.bit_length = bit_length


class CharLitExpr(ExprNode):
    def __init__(self, char_expr: str, char_bit_length: int) -> None:
        self.char_expr = char_expr
        self.char_bit_length = char_bit_length


class StrLitExpr(ExprNode):
    def __init__(self, str_expr: str, char_bit_length: int) -> None:
        self.str_expr = str_expr
        self.char_bit_length = char_bit_length


class GenericSelExpr(ExprNode):
    def __init__(self,
                 expr: ExprNode,
                 table: dict[Type | None, ExprNode]) -> None:
        self.expr = expr
        self.table = table


class ArraySubExpr(ExprNode):
    def __init__(self, base_expr: ExprNode, idx_expr: ExprNode) -> None:
        self.base_expr = base_expr
        self.idx_expr = idx_expr


class CallExpr(ExprNode):
    def __init__(self,
                 callee_expr: ExprNode,
                 arg_expr_list: list[ExprNode]) -> None:
        self.callee_expr = callee_expr
        self.arg_expr_list = arg_expr_list


class MemberExpr(ExprNode):
    def __init__(self,
                 base_expr: ExprNode,
                 member_iden: str,
                 is_arrow: bool) -> None:
        self.base_expr = base_expr
        self.member_iden = member_iden
        self.is_arrow = is_arrow


class InitMember(InitNode):
    def __init__(self,
                 member_iden: str,
                 rec_init: InitNode | None,
                 assign_expr_or_init: ExprNode | InitNode | None) -> None:
        self.member_iden = member_iden
        self.rec_init = rec_init
        self.assign_expr_or_init = expr_or_init


class InitIndex(InitNode):
    def __init__(self,
                 idx_expr: ExprNode,
                 rec_init: InitNode | None,
                 assign_expr_or_init: ExprNode | InitNode | None) -> None:
        self.idx_expr = idx_expr
        self.rec_init = rec_init
        self.assign_expr_or_init = expr_or_init


class InitList(InitNode):
    def __init__(self,
                 init_elems: list[ExprNode | InitNode]) -> None:
        self.init_elems = init_elems


class CompoundLitExpr(ExprNode):
    def __init__(self,
                 expr_type: TypeNode,
                 init_list: InitNode) -> None:
        self.expr_type = expr_type
        self.init_list = init_list


class CastExpr(ExprNode):
    def __init__(self,
                 expr_type: TypeNode,
                 val_expr: ExprNode) -> None:
        self.expr_type = expr_type
        self.val_expr = val_expr


class OpExpr(ExprNode):
    def __init__(self, op: OpTag, expr_arg: list[ExprNode]) -> None:
        self.op = op
        self.expr = expr


class CondExpr(ExprNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 true_expr: ExprNode,
                 false_expr: ExprNode,
                 ) -> None:
        self.cond_expr = cond_expr
        self.true_expr = true_expr
        self.false_expr = false_expr


class AssignmentExpr(ASTNode):
    def __init__(self,
                 op: AssignOpTag,
                 var_expr: ExprNode,
                 val_expr: ExprNode) -> None:
        self.op = op
        self.var_expr = var_expr
        self.val_expr = val_expr


class CommaExpr(ExprNode):
    def __init__(self, expr: tuple[ExprNode, ExprNode]) -> None:
        self.expr = expr


class SizeOfExpr(ExprNode):
    def __init__(self, expr_or_type: ExprNode | TypeNode) -> None:
        self.expr_or_type = expr_or_type


class AlignOfExpr(ExprNode):
    def __init__(self, align_type: TypeNode) -> None:
        self.align_type = align_type






# Declarations.
class TypeOfSpec():
    def __init__(self, expr_or_type: ExprNode | TypeNode) -> None:
        self.expr_or_type = expr_or_type


class TypeOfUnqualSpec():
    def __init__(self, expr_or_type: ExprNode | TypeNode) -> None:
        self.expr_or_type = expr_or_type


class AlignAsSpec():
    def __init__(self, expr_or_type: ExprNode | TypeNode) -> None:
        self.expr_or_type = expr_or_type


class TransUnitDecl(DeclNode):
    def __init__(self, decls: list[DeclNode]) -> None:
        self.decls = decls


class VarDecl(DeclNode):
    def __init__(self,
                 var_type: TypeNode,
                 var_iden: str,
                 init: ExprNode | InitList | None) -> None:
        self.var_type= var_type
        self.iden = iden
        self.init = init


class FunDecl(DeclNode):
    def __init__(self,
                 ret_type: TypeNode,
                 iden: str,
                 params: list[tuple[TypeNode, str | None]],
                 body: CompoundStmt | None) -> None:
        self.ret_type = ret_type
        self.iden = iden
        self.params = params
        self.body = body


class EnumDecl(DeclNode):
    def __init__(self,
                 iden: str | None,
                 members: list[tuple[str, ExprNode | None]] | None,
                 member_type: TypeNode | None) -> None:
        self.iden = iden
        self.members = members
        self.member_type = member_type


class StructDecl(DeclNode):
    def __init__(self,
                 iden: str | None,
                 fields: list[DeclNode] | None) -> None:
        self.iden = iden
        self.fields = fields


class UnionDecl(DeclNode):
    def __init__(self,
                 iden: str | None,
                 members: list[DeclNode] | None) -> None:
        self.iden = iden
        self.members = members


class TypedefDecl(DeclNode):
    def __init__(self, ) -> None:
        pass

class StaticAssertDecl(DeclNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 str_expr: StrLitExpr | None) -> None:
        self.cond_expr = cond_expr
        self.str_expr = str_expr

# TODO: Missing declarations







class ArrayDecl(DeclNode):
    def __init__(self, ) -> None:
        pass






# Statements.
class PrintLnStmt(StmtNode):
    def __init__(self,
                 str_expr: StrLitExpr | None,
                 arg_exprs: list[ExprNode]) -> None:
        self.str_expr = str_expr
        self.arg_exprs = arg_exprs


class AssertStmt(StmtNode):
    def __init__(self,
                 cond_expr: ExprNode,
                 str_expr: StrLitExpr | None,
                 arg_exprs: list[ExprNode]) -> None:
        self.cond_expr = cond_expr
        self.str_expr = str_expr
        self.arg_exprs = arg_exprs


class CompoundStmt(StmtNode):
    def __init__(self,
                 block_items: list[StmtNode]) -> None:
        self.block_items = block_items


class DeclStmt(StmtNode):
    def __init__(self, decl: DeclNode | None) -> None:
        self.decl = decl


class ExprStmt(StmtNode):
    def __init__(self, expr: ExprNode | None) -> None:
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
        self.then_stmt = then_stmt


class CycleStmt(StmtNode):
    def __init__(self,
                 init_clause: ExprNode | DeclNode | None,
                 cond_expr: ExprNode | None,
                 inc_expr: StmtNode | None,
                 then_stmt: StmtNode | None) -> None:
        self.init_clause = init_clause
        self.cond_expr = cond_expr
        self.inc_expr = inc_expr
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
        self.root: ASTRoot | None = None

    def build(self) -> None | ErrorCode:
        tok = Tokenizer(buffer)
        tokens: list[Token] = []

        while True:
            token: Token = tok.next()

            if token.tag == TokenTag.invalid:
                return ErrorCode.E

            if token.tag in not non_supported:
                return ErrorCode.E

            tokens.append(token)

            if token.tag == TokenTag.eof:
                break

        parser =

    def analyze(self) -> None | ErrorCode:
        pass

    def normalize(self) -> None:
        pass

    def dump_posfix(self) -> str:
        pass

    def dump_tree(self) -> str:
        pass

# TODO: Fix AST initialization
# TODO: Fix types
