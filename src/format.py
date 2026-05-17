import sys

from error import *
from limits import *
from common import int_to_str

from parser import BINDING_POWER as binding_power
from flint_ast import *
from value_objects import *

# Formater
# Formats source code by serializing an abstract syntax tree (AST)
# into a visually consistent representation that adheres to defined
# stylistic conventions.


assert PTR_SIZE // 2 != 0

PTR_HALF_SIZE: int = PTR_SIZE // 2

INDENT: str = "    "

ESCAPE_MAP: dict[str, str] = {
    '\a': '\\a', '\b': '\\b', '\f': '\\f', '\n': '\\n',
    '\r': '\\r', '\t': '\\t', '\v': '\\v', '\\': '\\\\',
    '\'': '\\\'', '\"': '\\\"'
}

ASSIGN_OPS: set[BinOpTag] = {
    BinOpTag.assign,
    BinOpTag.mul_assign,
    BinOpTag.div_assign,
    BinOpTag.mod_assign,
    BinOpTag.add_assign,
    BinOpTag.sub_assign,
    BinOpTag.shl_assign,
    BinOpTag.shr_assign,
    BinOpTag.bit_and_assign,
    BinOpTag.bit_xor_assign,
    BinOpTag.bit_or_assign,
}

UNARY_BP: int = 140


def get_bp(op: OpTag | str) -> tuple[int, int]:
    if isinstance(op, UnaPrefOpTag):
        return (UNARY_BP, UNARY_BP)

    key: str = op if isinstance(op, str) else op.value
    return binding_power[key]


class Formater:
    def __init__(self, ast: AST, file_name: str) -> None:
        self.ast = ast
        self.file_name = file_name

        self.indents: list[str] = []
        self.contents: list[str] = []

    def push(self, content: str) -> None:
        self.contents.append(content)

    def indent(self) -> None:
        self.push("".join(self.indents))

    def push_indent(self) -> None:
        self.indents.append(INDENT)

    def pop_indent(self) -> None:
        self.indents.pop()

    # Initialisers.
    def expr_or_init(self, node: InitNode | ExprNode) -> None:
        if isinstance(node, ExprNode):
            self.expr(node, 0)
        else:
            self.init(node)

    def assign_init(self, node: InitMember | InitIndex) -> None:
        if node.rec_init is not None:
            return self.init(node.rec_init)

        assert node.expr_or_init is not None

        self.push(" = ")
        self.expr_or_init(node.expr_or_init)

    def init_member(self, node: InitMember) -> None:
        self.push(f".{node.member_iden}")
        self.assign_init(node)

    def init_index(self, node: InitIndex) -> None:
        self.push("[")
        self.expr(node.idx_expr, 0)
        self.push("]")
        self.assign_init(node)

    def init_list(self, node: InitList) -> None:
        self.push("{")

        if len(node.init_elems) != 0:
            self.expr_or_init(node.init_elems[0])

        for i in range(1, len(node.init_elems)):
            self.push(", ")
            self.expr_or_init(node.init_elems[i])

        self.push("}")

    def init(self, node: InitNode) -> None:
        if isinstance(node, InitMember):
            return self.init_member(node)

        if isinstance(node, InitIndex):
            return self.init_index(node)

        if isinstance(node, InitList):
            return self.init_list(node)

        assert False

    # Types.
    def needs_parens(self, node: TypeNode) -> bool:
        if isinstance(node, (ArrayType, FunType)):
            return True

        if isinstance(node, QualifiedType):
            return self.needs_parens(node.base_type)

        return False

    def param_spec(self, spec: ParamSpec) -> None:
        self.type_prefix(spec.param_type)

        if spec.iden is not None:
            self.push(f" {spec.iden}")

        self.type_suffix(spec.param_type)

    def void_type(self, node: VoidType) -> None:
        self.push("void")

    def bool_type(self, node: BoolType) -> None:
        self.push("bool")

    def nullptr_type(self, node: NullPtrType) -> None:
        self.push("nullptr_t")

    def sign_kind(self, kind: SignKind) -> None:
        if kind == SignKind.default:
            return None

        self.push(kind.value)
        self.push(" ")

    def int_type(self, node: IntType) -> None:
        self.sign_kind(node.sign_kind)
        self.push(node.kind.value)

    def bit_int_type(self, node: BitIntType) -> None:
        self.sign_kind(node.sign_kind)
        self.push("_BitInt(")
        self.expr(node.width_expr, 0)
        self.push(")")

    def char_type(self, node: CharType) -> None:
        if node.sign_kind is not None:
            self.sign_kind(node.sign_kind)

        self.push(node.kind.value)

    def real_float_type(self, node: RealFloatType) -> None:
        self.push(node.kind.value)

    def decimal_float_type(self, node: DecimalFloatType) -> None:
        self.push(node.kind.value)

    def complex_type(self, node: ComplexType) -> None:
        self.push(node.kind.value)
        self.push(" _Complex")

    def imaginary_type(self, node: ImaginaryType) -> None:
        self.push(node.kind.value)
        self.push(" _Imaginary")

    def type_qualifiers(self, qualifiers: set[TypeQualifier]) -> None:
        for qualifier in sorted(qualifiers, key=lambda q: q.value):
            self.push(qualifier.value)
            self.push(" ")

    def ptr_type_prefix(self, node: PtrType) -> None:
        self.type_prefix(node.pointee)

        if self.needs_parens(node.pointee):
            self.push(" (*")
        else:
            self.push(" *")

        self.type_qualifiers(node.qualifiers)

    def ptr_type_suffix(self, node: PtrType) -> None:
        if self.needs_parens(node.pointee):
            self.push(")")

        self.type_suffix(node.pointee)

    def array_type_prefix(self, node: ArrayType) -> None:
        self.type_prefix(node.elem_type)

    def array_type_suffix(self, node: ArrayType) -> None:
        self.push("[")

        if node.is_static:
            self.push("static ")

        self.type_qualifiers(node.qualifiers)

        if node.is_unspec_vla:
            self.push("*")

        elif node.elem_count is not None:
            self.expr(node.elem_count, 0)

        self.push("]")
        self.type_suffix(node.elem_type)

    def fun_type_prefix(self, node: FunType) -> None:
        self.type_prefix(node.ret_type)

    def fun_type_suffix(self, node: FunType) -> None:
        self.push("(")

        if len(node.params) != 0:
            self.param_spec(node.params[0])

        for i in range(1, len(node.params)):
            self.push(", ")
            self.param_spec(node.params[i])

        if node.is_variadic:
            if node.params:
                self.push(", ")

            self.push("...")

        self.push(")")
        self.type_suffix(node.ret_type)

    def enum_val_spec(self, member: EnumValSpec) -> None:
        self.indent()
        self.push(member.iden)

        if member.expr is not None:
            self.push(" = ")
            self.expr(member.expr, 0)

    def enum_members(self, members: list[EnumValSpec]) -> None:
        self.push(" {\n")
        self.push_indent()

        if len(members) != 0:
            self.enum_val_spec(members[0])

        for i in range(1, len(members)):
            self.push(",\n")
            self.enum_val_spec(members[i])

        if len(members) != 0:
            self.push("\n")

        self.pop_indent()
        self.indent()
        self.push("}")

    def enum_type(self, node: EnumType) -> None:
        self.push("enum")

        if node.iden is not None:
            self.push(f" {node.iden}")

        if node.member_type is not None:
            self.push(" : ")
            self.type(node.member_type)

        if node.members is not None:
            self.enum_members(node.members)

    def struct_or_union_members(self,
                                members: list[DeclNode]) -> None:
        self.push(" {\n")
        self.push_indent()

        for member in members:
            self.decl(member)

        self.pop_indent()
        self.indent()
        self.push("}")

    def struct_type(self, node: StructType) -> None:
        self.push("struct")

        if node.iden is not None:
            self.push(f" {node.iden}")

        if node.members is not None:
            self.struct_or_union_members(node.members)

    def union_type(self, node: UnionType) -> None:
        self.push("union")

        if node.iden is not None:
            self.push(f" {node.iden}")

        if node.members is not None:
            self.struct_or_union_members(node.members)  # fix: was node.union_type.members

    def atomic_type(self, node: AtomicType) -> None:
        self.push("_Atomic(")
        self.type(node.base_type)
        self.push(")")

    def expr_or_type(self, node: ExprNode | TypeNode) -> None:
        if isinstance(node, ExprNode):
            self.expr(node, 0)
        else:
            self.type(node)

    def typeof_type(self, node: TypeOfType) -> None:
        self.push("typeof(")
        self.expr_or_type(node.expr_or_type)
        self.push(")")

    def typeof_unqual_type(self, node: TypeOfUnqualType) -> None:
        self.push("typeof_unqual(")
        self.expr_or_type(node.expr_or_type)
        self.push(")")

    def typedef_type(self, node: TypeDefType) -> None:
        self.push(node.iden)

    def qualified_type_prefix(self, node: QualifiedType) -> None:
        if node.storage is not None:
            self.push(node.storage.value)
            self.push(" ")

        if node.fun_spec is not None:
            self.push(node.fun_spec.value)
            self.push(" ")

        if node.alignment is not None:
            self.push("alignas(")
            self.expr_or_type(node.alignment)
            self.push(") ")

        self.type_qualifiers(node.qualifiers)
        self.type_prefix(node.base_type)

    def qualified_type_suffix(self, node: QualifiedType) -> None:
        self.type_suffix(node.base_type)

    def type_prefix(self, node: TypeNode) -> None:
        if isinstance(node, VoidType):
            return self.void_type(node)

        if isinstance(node, BoolType):
            return self.bool_type(node)

        if isinstance(node, NullPtrType):
            return self.nullptr_type(node)

        if isinstance(node, IntType):
            return self.int_type(node)

        if isinstance(node, BitIntType):
            return self.bit_int_type(node)

        if isinstance(node, CharType):
            return self.char_type(node)

        if isinstance(node, RealFloatType):
            return self.real_float_type(node)

        if isinstance(node, DecimalFloatType):
            return self.decimal_float_type(node)

        if isinstance(node, ComplexType):
            return self.complex_type(node)

        if isinstance(node, ImaginaryType):
            return self.imaginary_type(node)

        if isinstance(node, PtrType):
            return self.ptr_type_prefix(node)

        if isinstance(node, ArrayType):
            return self.array_type_prefix(node)

        if isinstance(node, FunType):
            return self.fun_type_prefix(node)

        if isinstance(node, EnumType):
            return self.enum_type(node)

        if isinstance(node, StructType):
            return self.struct_type(node)

        if isinstance(node, UnionType):
            return self.union_type(node)

        if isinstance(node, AtomicType):
            return self.atomic_type(node)

        if isinstance(node, TypeOfType):
            return self.typeof_type(node)

        if isinstance(node, TypeOfUnqualType):
            return self.typeof_unqual_type(node)

        if isinstance(node, TypeDefType):
            return self.typedef_type(node)

        if isinstance(node, QualifiedType):
            return self.qualified_type_prefix(node)

        assert False

    def type_suffix(self, node: TypeNode) -> None:
        if isinstance(node, PtrType):
            return self.ptr_type_suffix(node)

        if isinstance(node, ArrayType):
            return self.array_type_suffix(node)

        if isinstance(node, FunType):
            return self.fun_type_suffix(node)

        if isinstance(node, QualifiedType):
            self.qualified_type_suffix(node)

    def type(self, node: TypeNode) -> None:
        self.type_prefix(node)
        self.type_suffix(node)

    # Expressions.
    def char_seq(self, seq: str) -> None:
        new_seq: list[str] = []

        for ch in seq:
            if ch in ESCAPE_MAP:
                new_seq.append(ESCAPE_MAP[ch])

            elif ord(ch) < 32 or ord(ch) == 127:
                new_seq.append(f"\\x{ord(ch):02x}")

            else:
                new_seq.append(ch)

        self.push("".join(new_seq))

    def char_prefix(self, char_type: CharType) -> None:
        if char_type.kind == CharKind.wchar:
            return self.push("L")

        if char_type.kind == CharKind.char8:
            return self.push("u8")

        if char_type.kind == CharKind.char16:
            return self.push("u")

        if char_type.kind == CharKind.char32:
            return self.push("U")

    def iden_expr(self, node: IdenExpr) -> None:
        self.push(node.iden)

    def nullptr_lit_expr(self, node: NullPtrLitExpr) -> None:
        self.push("nullptr")

    def bool_lit_expr(self, node: BoolLitExpr) -> None:
        if node.bool_expr:
            self.push("true")
        else:
            self.push("false")

    def int_lit_expr(self, node: IntLitExpr) -> None:
        self.push(int_to_str(node.int_expr))

        if isinstance(node.int_type, BitIntType):
            return self.push("wb")

        assert isinstance(node.int_type, IntType)

        if node.int_type.sign_kind == SignKind.unsigned:
            self.push("U")

        if node.int_type.kind == IntKind.long:
            self.push("L")

        elif node.int_type.kind == IntKind.long_long:
            self.push("LL")

    def real_float_lit_expr(self, node: RealFloatLitExpr) -> None:
        self.push(repr(node.float_expr))

        if node.float_type.kind == RealFloatKind.float:
            return self.push("f")

        if node.float_type.kind == RealFloatKind.long_double:
            return self.push("L")

    def dec_float_lit_expr(self, node: DecFloatLitExpr) -> None:
        self.push(str(node.float_expr))

        if node.float_type.kind == DecimalFloatKind.decimal32:
            return self.push("df")

        if node.float_type.kind == DecimalFloatKind.decimal64:
            return self.push("dd")

        if node.float_type.kind == DecimalFloatKind.decimal128:
            return self.push("dl")

    def char_lit_expr(self, node: CharLitExpr) -> None:
        self.char_prefix(node.char_type)
        self.push("\'")
        self.char_seq(node.char_expr)
        self.push("\'")

    def str_lit_expr(self, node: StrLitExpr) -> None:
        self.char_prefix(node.char_type)
        self.push("\"")
        self.char_seq(node.str_expr)
        self.push("\"")

    def generic_sel_expr(self, node: GenericSelExpr) -> None:
        self.push("_Generic(")
        self.expr(node.ctrl_expr, 0)

        for type_key, case_expr in node.assoc_table.items():
            self.push(", ")

            if type_key is None:
                self.push("default")
            else:
                self.type(type_key)

            self.push(": ")
            self.expr(case_expr, 0)

        self.push(")")

    def array_sub_expr(self, node: ArraySubExpr) -> None:
        self.expr(node.base_expr, 0)
        self.push("[")
        self.expr(node.idx_expr, 0)
        self.push("]")

    def call_expr(self, node: CallExpr) -> None:
        self.expr(node.callee_expr, 0)
        self.push("(")

        if len(node.arg_exprs) != 0:
            self.expr(node.arg_exprs[0], 0)

        for i in range(1, len(node.arg_exprs)):
            self.push(", ")
            self.expr(node.arg_exprs[i], 0)

        self.push(")")

    def member_expr(self, node: MemberExpr) -> None:
        self.expr(node.base_expr, 0)

        if node.is_arrow:
            self.push("->")
        else:
            self.push(".")

        self.push(node.member_iden)

    def compound_lit_expr(self, node: CompoundLitExpr) -> None:
        self.push("(")
        self.type(node.expr_type)
        self.push(")")
        self.init(node.init)

    def cast_expr(self, node: CastExpr) -> None:
        self.push("(")
        self.type(node.expr_type)
        self.push(")")
        self.expr(node.expr, 0)

    def op_una_pref(self, node: OpExpr, parent_bp: int) -> None:
        l_bp, r_bp = get_bp(node.op)

        if l_bp < parent_bp:
            self.push("(")

        self.push(node.op.value)
        self.expr(node.exprs[0], r_bp)

        if l_bp < parent_bp:
            self.push(")")

    def op_una_post(self, node: OpExpr, parent_bp: int) -> None:
        l_bp, r_bp = get_bp(node.op)

        if l_bp < parent_bp:
            self.push("(")

        self.expr(node.exprs[0], r_bp + 1)
        self.push(node.op.value)

        if l_bp < parent_bp:
            self.push(")")

    def op_bin(self, node: OpExpr, parent_bp: int) -> None:
        op = node.op
        l_bp, _ = get_bp(op)

        if l_bp < parent_bp:
            self.push("(")

        if op in ASSIGN_OPS:
            self.expr(node.exprs[0], l_bp + 1)
            self.push(f" {op.value} ")
            self.expr(node.exprs[1], l_bp)
        else:
            self.expr(node.exprs[0], l_bp)
            self.push(f" {op.value} ")
            self.expr(node.exprs[1], l_bp + 1)

        if l_bp < parent_bp:
            self.push(")")

    def op_expr(self, node: OpExpr, parent_bp: int) -> None:
        if isinstance(node.op, UnaPrefOpTag):
            return self.op_una_pref(node, parent_bp)

        if isinstance(node.op, UnaPostOpTag):
            return self.op_una_post(node, parent_bp)

        if isinstance(node.op, BinOpTag):
            return self.op_bin(node, parent_bp)

        assert False

    def cond_expr(self, node: CondExpr) -> None:
        l_bp, _ = get_bp("?")

        self.expr(node.cond_expr, l_bp + 1)
        self.push(" ? ")
        self.expr(node.true_expr, 0)
        self.push(" : ")
        self.expr(node.false_expr, l_bp)

    def comma_expr(self, node: CommaExpr) -> None:
        l_bp, _ = get_bp(",")

        fst_expr, snd_expr = node.exprs

        self.expr(fst_expr, l_bp)
        self.push(", ")
        self.expr(snd_expr, l_bp + 1)

    def sizeof_expr(self, node: SizeOfExpr) -> None:
        self.push("sizeof(")

        if isinstance(node.expr_or_type, ExprNode):
            self.expr(node.expr_or_type, 0)
        else:
            self.type(node.expr_or_type)

        self.push(")")

    def alignof_expr(self, node: AlignOfExpr) -> None:
        self.push("alignof(")
        self.type(node.align_type)
        self.push(")")

    def expr(self, node: ExprNode, min_bp: int) -> None:
        if isinstance(node, IdenExpr):
            return self.iden_expr(node)

        if isinstance(node, NullPtrLitExpr):
            return self.nullptr_lit_expr(node)

        if isinstance(node, BoolLitExpr):
            return self.bool_lit_expr(node)

        if isinstance(node, IntLitExpr):
            return self.int_lit_expr(node)

        if isinstance(node, RealFloatLitExpr):
            return self.real_float_lit_expr(node)

        if isinstance(node, DecFloatLitExpr):
            return self.dec_float_lit_expr(node)

        if isinstance(node, CharLitExpr):
            return self.char_lit_expr(node)

        if isinstance(node, StrLitExpr):
            return self.str_lit_expr(node)

        if isinstance(node, GenericSelExpr):
            return self.generic_sel_expr(node)

        if isinstance(node, ArraySubExpr):
            return self.array_sub_expr(node)

        if isinstance(node, CallExpr):
            return self.call_expr(node)

        if isinstance(node, MemberExpr):
            return self.member_expr(node)

        if isinstance(node, CompoundLitExpr):
            return self.compound_lit_expr(node)

        if isinstance(node, CastExpr):
            return self.cast_expr(node)

        if isinstance(node, OpExpr):
            return self.op_expr(node, min_bp)

        if isinstance(node, CondExpr):
            cond_bp, _ = get_bp("?")

            if cond_bp < min_bp:
                self.push("(")

            self.cond_expr(node)

            if cond_bp < min_bp:
                self.push(")")

            return

        if isinstance(node, CommaExpr):
            comma_bp, _ = get_bp(",")

            if comma_bp < min_bp:
                self.push("(")

            self.comma_expr(node)

            if comma_bp < min_bp:
                self.push(")")

            return

        if isinstance(node, SizeOfExpr):
            return self.sizeof_expr(node)

        if isinstance(node, AlignOfExpr):
            return self.alignof_expr(node)

        assert False

    # Declarations.
    def trans_unit_decl(self, node: TransUnitDecl) -> None:
        for decl_node in node.decls:
            self.decl(decl_node)

    def empty_decl(self, node: EmptyDecl) -> None:
        self.push(";\n")

    def var(self, node: VarDecl) -> None:  # fix: was -> Node (undefined)
        self.type_prefix(node.var_type)
        self.push(f" {node.iden}")
        self.type_suffix(node.var_type)

        if node.init is not None:
            self.push(" = ")

            if isinstance(node.init, ExprNode):
                self.expr(node.init, 0)
            else:
                self.init(node.init)

    def var_decl(self, node: VarDecl) -> None:
        self.indent()
        self.var(node)  # fix: was self.var() with no argument
        self.push(";\n")

    def fun_decl(self, node: FunDecl) -> None:
        self.indent()

        self.type_prefix(node.fun_type)
        self.push(f" {node.iden}")
        self.type_suffix(node.fun_type)

        if node.body is None:
            return self.push(";\n")

        self.body(node.body)
        self.push("\n")

    def enum_decl(self, node: EnumDecl) -> None:
        self.indent()
        self.type(node.enum_type)  # fix: node.enum_type is QualifiedType, not EnumType
        self.push(";\n")

    def struct_decl(self, node: StructDecl) -> None:
        self.indent()
        self.type(node.struct_type)  # fix: node.struct_type is QualifiedType
        self.push(";\n")

    def union_decl(self, node: UnionDecl) -> None:
        self.indent()
        self.type(node.union_type)  # fix: node.union_type is QualifiedType
        self.push(";\n")

    def typedef_decl(self, node: TypedefDecl) -> None:
        self.indent()

        self.push("typedef ")

        self.type_prefix(node.base_type)
        self.push(f" {node.alias_iden}")
        self.type_suffix(node.base_type)

        self.push(";\n")

    def static_assert_decl(self, node: StaticAssertDecl) -> None:
        self.indent()

        self.push("static_assert(")
        self.expr(node.cond_expr, 0)

        if node.str_expr is not None:
            self.push(", ")
            self.str_lit_expr(node.str_expr)

        self.push(");\n")

    def decl(self, node: DeclNode) -> None:
        if isinstance(node, TransUnitDecl):
            return self.trans_unit_decl(node)

        if isinstance(node, EmptyDecl):
            return self.empty_decl(node)

        if isinstance(node, VarDecl):
            return self.var_decl(node)

        if isinstance(node, FunDecl):
            return self.fun_decl(node)

        if isinstance(node, EnumDecl):
            return self.enum_decl(node)

        if isinstance(node, StructDecl):
            return self.struct_decl(node)

        if isinstance(node, UnionDecl):
            return self.union_decl(node)

        if isinstance(node, TypedefDecl):
            return self.typedef_decl(node)

        if isinstance(node, StaticAssertDecl):
            return self.static_assert_decl(node)

        assert False

    # Statements.
    def cond(self, node: ExprNode) -> None:
        self.push("(")
        self.expr(node, 0)
        self.push(")")

    def body(self, node: StmtNode) -> None:
        self.push(" {\n")
        self.push_indent()

        if isinstance(node, CompoundStmt):
            for stmt_node in node.stmts:
                self.stmt(stmt_node)
        else:
            self.stmt(node)

        self.pop_indent()
        self.indent()
        self.push("}")

    def assert_stmt(self, node: AssertStmt) -> None:
        self.indent()

        self.push("assert(")
        self.expr(node.cond_expr, 0)

        if node.str_expr is not None:
            self.push(", ")
            self.str_lit_expr(node.str_expr)

            for expr_node in node.arg_exprs:
                self.push(", ")
                self.expr(expr_node, 0)

        self.push(");\n")

    def println_stmt(self, node: PrintLnStmt) -> None:
        # fix: old code called msg() which prepended a leading comma,
        # producing println(,"str") when str_expr was the first argument.
        self.indent()

        self.push("println(")

        if node.str_expr is not None:
            self.str_lit_expr(node.str_expr)

            for expr_node in node.arg_exprs:
                self.push(", ")
                self.expr(expr_node, 0)

        self.push(");\n")

    def compound_stmt(self, node: CompoundStmt) -> None:
        self.indent()

        self.push("{\n")
        self.push_indent()

        for stmt_node in node.stmts:
            self.stmt(stmt_node)

        self.pop_indent()
        self.indent()  # fix: was missing, leaving closing brace unindented
        self.push("}\n")

    def decl_stmt(self, node: DeclStmt) -> None:
        self.decl(node.decl)

    def expr_stmt(self, node: ExprStmt) -> None:
        self.indent()
        self.expr(node.expr, 0)
        self.push(";\n")

    def else_stmt(self, node: StmtNode) -> None:
        self.push(" else")
        self.body(node)
        self.push("\n")

    def elif_stmt(self, node: IfStmt) -> None:
        self.push(" else if")
        self.cond(node.cond_expr)
        self.body(node.then_stmt)

        if node.else_stmt is None:
            return self.push("\n")

        if isinstance(node.else_stmt, IfStmt):
            self.elif_stmt(node.else_stmt)
        else:
            self.else_stmt(node.else_stmt)

    def if_stmt(self, node: IfStmt) -> None:
        self.indent()

        self.push("if")
        self.cond(node.cond_expr)
        self.body(node.then_stmt)

        if node.else_stmt is None:
            return self.push("\n")

        if isinstance(node.else_stmt, IfStmt):
            self.elif_stmt(node.else_stmt)
        else:
            self.else_stmt(node.else_stmt)

    def case_label_stmt(self, node: CaseLabelStmt) -> None:
        self.pop_indent()
        self.indent()

        if node.cond_expr is None:
            self.push("default:\n")
        else:
            self.push("case ")
            self.expr(node.cond_expr, 0)
            self.push(":\n")

        self.push_indent()

    def switch_stmt(self, node: SwitchStmt) -> None:  # fix: was swtich_stmt (typo)
        self.indent()

        self.push("switch")
        self.cond(node.cond_expr)
        self.body(node.then_stmt)
        self.push("\n")

    def for_stmt(self, node: ForStmt) -> None:
        self.indent()
        self.push("for (")

        if isinstance(node.init_clause, ExprNode):
            self.expr(node.init_clause, 0)

        elif isinstance(node.init_clause, VarDecl):
            self.var(node.init_clause)

        self.push(";")

        if node.cond_expr is not None:
            self.push(" ")
            self.expr(node.cond_expr, 0)

        self.push(";")

        if node.inc_expr is not None:
            self.push(" ")
            self.expr(node.inc_expr, 0)

        self.push(")")
        self.body(node.then_stmt)
        self.push("\n")

    def while_stmt(self, node: WhileStmt) -> None:
        self.indent()

        self.push("while")
        self.cond(node.cond_expr)
        self.body(node.then_stmt)
        self.push("\n")

    def do_while_stmt(self, node: DoWhileStmt) -> None:
        self.indent()

        self.push("do")
        self.body(node.do_stmt)

        self.push(" while")
        self.cond(node.cond_expr)
        self.push(";\n")

    def goto_stmt(self, node: GotoStmt) -> None:
        self.indent()
        self.push(f"goto {node.label_iden};\n")

    def label_stmt(self, node: LabelStmt) -> None:
        self.push(f"{node.iden}:\n")

    def break_stmt(self, node: BreakStmt) -> None:
        self.indent()
        self.push("break;\n")

    def continue_stmt(self, node: ContinueStmt) -> None:
        self.indent()
        self.push("continue;\n")

    def return_stmt(self, node: ReturnStmt) -> None:
        self.indent()
        self.push("return")

        if node.ret_expr is not None:
            self.push(" ")
            self.expr(node.ret_expr, 0)

        self.push(";\n")

    def stmt(self, node: StmtNode) -> None:
        if isinstance(node, AssertStmt):
            return self.assert_stmt(node)

        if isinstance(node, PrintLnStmt):
            return self.println_stmt(node)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, DeclStmt):
            return self.decl_stmt(node)

        if isinstance(node, ExprStmt):
            return self.expr_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, CaseLabelStmt):
            return self.case_label_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)  # fix: was self.swtich_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, GotoStmt):
            return self.goto_stmt(node)

        if isinstance(node, LabelStmt):
            return self.label_stmt(node)

        if isinstance(node, BreakStmt):
            return self.break_stmt(node)

        if isinstance(node, ContinueStmt):
            return self.continue_stmt(node)

        if isinstance(node, ReturnStmt):
            return self.return_stmt(node)

        assert False

    def gen_source_code(self) -> str:
        assert self.ast.root is not None

        self.indents = []
        self.contents = []

        self.trans_unit_decl(self.ast.root)

        return "".join(self.contents)

    def format(self) -> None | Error:
        source_code: str = self.gen_source_code()

        try:
            with open(self.file_name, "w") as file:
                file.write(source_code)

        except PermissionError:
            return Error()

        except OSError:
            return Error()


# Value Formater
#
class ValueFormater:
    def __init__(self) -> None:
        self.indents: list[str] = []
        self.contents: list[str] = []

    def push(self, content: str) -> None:
        return self.contents.append(content)

    def push_indent(self) -> None:
        self.indents.append(INDENT)

    def pop_indent(self) -> None:
        self.indents.pop()

    def indent(self) -> None:
        return self.push("".join(self.indents))

    def fmt_bool_obj(self, val_obj: BoolValue) -> None:
        self.indent()

        if val_obj.value:
            return self.push("true")
        else:
            return self.push("false")

    def fmt_int_obj(self, val_obj: IntValue) -> None:
        self.indent()
        pass

    def fmt_float_obj(self, val_obj: FloatValue) -> None:
        self.indent()
        pass

    def fmt_dec_obj(self, val_obj: DecValue) -> None:
        self.indent()
        pass

    def fmt_ptr_obj(self, val_obj: PtrValue) -> None:
        self.indent()

        if val_obj.ptr_type.target_type is None:
            return self.push("nullptr")

        self.push(f"{val_obj.block_id:#0{PTR_HEX_LENGTH // 2}x}")
        self.push(" | ")
        self.push(f"{val_obj.offet:0{PTR_HEX_LENGTH // 2}x}")

        return None

    def fmt_array_obj(self) -> None:
        pass

    def fmt_enum_obj(self, val_obj: EnumValue) -> None:
        pass

    def fmt_struct_obj(self, val_obj: StructValue) -> None:
        pass

    def fmt_union_obj(self, val_obj: UnionValue) -> None:
        pass

    def fmt(self, val_obj: ValueObject) -> None:
        if isinstance(val_obj, BoolValue):
            return self.fmt_bool_obj(val_obj)

        if isinstance(val_obj, IntValue):
            return self.fmt_int_obj(val_obj)

        if isinstance(val_obj, FloatValue):
            return self.fmt_float_obj(val_obj)

        if isinstance(val_obj, DecValue):
            return self.fmt_dec_obj(val_obj)

        if isinstance(val_obj, PtrValue):
            return self.fmt_ptr_obj(val_obj)

        if isinstance(val_obj, EnumValue):
            return self.fmt_enum_obj(val_obj)

        if isinstance(val_obj, StructValue):
            return self.fmt_struct_obj(val_obj)

        if isinstance(val_obj, UnionValue):
            return self.fmt_union_obj(val_obj)

        assert False

    def format(self, val_obj: ValueObject) -> str:
        self.fmt(val_obj)
        return "".join(self.contents)


def test_format() -> None:
    pass


if __name__ == "__main__":
    test_format()
