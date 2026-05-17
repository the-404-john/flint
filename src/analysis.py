from error import *
from flint_ast import *


# Static Analysis
#


LITERAL_EXPRS = (
    NullPtrLitExpr,
    BoolLitExpr,
    IntLitExpr,
    RealFloatLitExpr,
    DecFloatLitExpr,
    CharLitExpr,
    StrLitExpr
)

####

# --- Tag-type unwrappers ---
# EnumDecl/StructDecl/UnionDecl store their type as either the raw
# EnumType/StructType/UnionType (from a standalone enum_decl/struct_decl
# parser path) or as a QualifiedType wrapping it (from the general
# declaration parser path).  These helpers normalise both cases.

def _unwrap_enum(node: EnumDecl) -> EnumType | None:
    t = node.enum_type
    if isinstance(t, QualifiedType):
        t = t.base_type
    return t if isinstance(t, EnumType) else None


def _unwrap_struct(node: StructDecl) -> StructType | None:
    t = node.struct_type
    if isinstance(t, QualifiedType):
        t = t.base_type
    return t if isinstance(t, StructType) else None


def _unwrap_union(node: UnionDecl) -> UnionType | None:
    t = node.union_type
    if isinstance(t, QualifiedType):
        t = t.base_type
    return t if isinstance(t, UnionType) else None


# --- Integer-expression helpers (used by Analysis02) ---

def is_int_expr(node: ExprNode) -> bool:
    if isinstance(node, (RealFloatLitExpr, DecFloatLitExpr, StrLitExpr)):
        return False
    return True


def is_int_constant_expr(node: ExprNode) -> bool:
    if isinstance(node, (IntLitExpr, BoolLitExpr, CharLitExpr)):
        return True
    if isinstance(node, (SizeOfExpr, AlignOfExpr)):
        return True
    if isinstance(node, CastExpr):
        return is_int_constant_expr(node.expr)
    if isinstance(node, CondExpr):
        return (is_int_constant_expr(node.cond_expr) and
                is_int_constant_expr(node.true_expr) and
                is_int_constant_expr(node.false_expr))
    if isinstance(node, OpExpr):
        if isinstance(node.op, UnaPrefOpTag):
            if node.op in (UnaPrefOpTag.prefix_inc, UnaPrefOpTag.prefix_dec,
                           UnaPrefOpTag.addr_of, UnaPrefOpTag.deref):
                return False
            return is_int_constant_expr(node.exprs[0])
        if isinstance(node.op, UnaPostOpTag):
            return False
        if isinstance(node.op, BinOpTag):
            if node.op in (BinOpTag.assign,
                           BinOpTag.add_assign, BinOpTag.sub_assign,
                           BinOpTag.mul_assign, BinOpTag.div_assign,
                           BinOpTag.mod_assign, BinOpTag.shl_assign,
                           BinOpTag.shr_assign, BinOpTag.bit_and_assign,
                           BinOpTag.bit_xor_assign, BinOpTag.bit_or_assign):
                return False
            return (is_int_constant_expr(node.exprs[0]) and
                    is_int_constant_expr(node.exprs[1]))
    return False


def eval_int_constant_expr(node: ExprNode) -> int:
    if isinstance(node, IntLitExpr):
        return node.int_expr
    if isinstance(node, BoolLitExpr):
        return int(node.bool_expr)
    if isinstance(node, CharLitExpr):
        return ord(node.char_expr) if len(node.char_expr) == 1 else 0
    if isinstance(node, CastExpr):
        return eval_int_constant_expr(node.expr)
    if isinstance(node, CondExpr):
        cond = eval_int_constant_expr(node.cond_expr)
        return eval_int_constant_expr(node.true_expr if cond else node.false_expr)
    if isinstance(node, OpExpr):
        if isinstance(node.op, UnaPrefOpTag):
            val = eval_int_constant_expr(node.exprs[0])
            if node.op == UnaPrefOpTag.plus:    return val
            if node.op == UnaPrefOpTag.neg:     return -val
            if node.op == UnaPrefOpTag.bit_neg: return ~val
            if node.op == UnaPrefOpTag.bool_neg: return int(not val)
        if isinstance(node.op, BinOpTag):
            lhs = eval_int_constant_expr(node.exprs[0])
            rhs = eval_int_constant_expr(node.exprs[1])
            match node.op:
                case BinOpTag.add:     return lhs + rhs
                case BinOpTag.sub:     return lhs - rhs
                case BinOpTag.mul:     return lhs * rhs
                case BinOpTag.div:     return lhs // rhs if rhs != 0 else 0
                case BinOpTag.mod:     return lhs % rhs if rhs != 0 else 0
                case BinOpTag.shl:     return lhs << rhs
                case BinOpTag.shr:     return lhs >> rhs
                case BinOpTag.bit_and: return lhs & rhs
                case BinOpTag.bit_or:  return lhs | rhs
                case BinOpTag.bit_xor: return lhs ^ rhs
                case BinOpTag.lt:      return int(lhs < rhs)
                case BinOpTag.gt:      return int(lhs > rhs)
                case BinOpTag.le:      return int(lhs <= rhs)
                case BinOpTag.ge:      return int(lhs >= rhs)
                case BinOpTag.eq:      return int(lhs == rhs)
                case BinOpTag.ne:      return int(lhs != rhs)
                case BinOpTag.bool_and: return int(bool(lhs) and bool(rhs))
                case BinOpTag.bool_or:  return int(bool(lhs) or bool(rhs))

    assert False


# Shared type-checking infrastructure.
# Provides scope management, type inference, and C23 compatibility rules
# used by Analysis10, Analysis12, and Analysis14 to eliminate duplication.
class _TypeCheckBase:

    def __init__(self) -> None:
        self.scopes: list[dict[str, TypeNode]] = []

    # Scope helpers.
    def scope_push(self) -> None:
        self.scopes.append({})

    def scope_pop(self) -> None:
        self.scopes.pop()

    def declare(self, name: str, t: TypeNode) -> None:
        self.scopes[-1][name] = t

    def lookup(self, name: str) -> TypeNode | None:
        for scope in reversed(self.scopes):
            t = scope.get(name)
            if t is not None:
                return t
        return None

    # Type helpers.
    def unqual(self, t: TypeNode) -> TypeNode:
        if isinstance(t, QualifiedType):
            return t.base_type
        return t

    def is_arithmetic(self, t: TypeNode) -> bool:
        return isinstance(self.unqual(t),
                          (BoolType, IntType, BitIntType, CharType,
                           RealFloatType, DecimalFloatType,
                           ComplexType, ImaginaryType, EnumType))

    def is_integer(self, t: TypeNode) -> bool:
        return isinstance(self.unqual(t),
                          (BoolType, IntType, BitIntType, CharType, EnumType))

    def is_float(self, t: TypeNode) -> bool:
        return isinstance(self.unqual(t),
                          (RealFloatType, DecimalFloatType,
                           ComplexType, ImaginaryType))

    def is_pointer(self, t: TypeNode) -> bool:
        return isinstance(self.unqual(t), (PtrType, NullPtrType))

    def is_scalar(self, t: TypeNode) -> bool:
        return self.is_arithmetic(t) or self.is_pointer(t)

    def is_unresolved(self, t: TypeNode) -> bool:
        return isinstance(self.unqual(t),
                          (TypeDefType, TypeOfType, TypeOfUnqualType, AtomicType))

    def is_convertible(self, from_t: TypeNode, to_t: TypeNode) -> bool:
        from_t = self.unqual(from_t)
        to_t   = self.unqual(to_t)

        # Unresolved on either side — cannot prove incompatibility.
        if isinstance(from_t, (TypeDefType, TypeOfType, TypeOfUnqualType, AtomicType)):
            return True
        if isinstance(to_t, (TypeDefType, TypeOfType, TypeOfUnqualType, AtomicType)):
            return True

        # Any scalar → bool.
        if isinstance(to_t, BoolType):
            return (self.is_arithmetic(from_t) or
                    isinstance(from_t, (PtrType, NullPtrType)))

        # Arithmetic ↔ arithmetic (includes bool, char, enum).
        if self.is_arithmetic(from_t) and self.is_arithmetic(to_t):
            return True

        # nullptr → any pointer or nullptr_t.
        if isinstance(from_t, NullPtrType):
            return isinstance(to_t, (PtrType, NullPtrType))

        # Pointer ↔ pointer: void* on either side is always compatible;
        # otherwise the unqualified pointee types must be the same class.
        if isinstance(from_t, PtrType) and isinstance(to_t, PtrType):
            from_p = self.unqual(from_t.pointee)
            to_p   = self.unqual(to_t.pointee)
            if isinstance(from_p, VoidType) or isinstance(to_p, VoidType):
                return True
            return type(from_p) is type(to_p)

        # Named aggregate types: require matching identifier.
        if isinstance(from_t, StructType) and isinstance(to_t, StructType):
            return from_t.iden is not None and from_t.iden == to_t.iden

        if isinstance(from_t, UnionType) and isinstance(to_t, UnionType):
            return from_t.iden is not None and from_t.iden == to_t.iden

        if isinstance(from_t, EnumType) and isinstance(to_t, EnumType):
            return from_t.iden is not None and from_t.iden == to_t.iden

        return False

    # Type inference — returns None when the type cannot be determined.
    def type_of(self, node: ExprNode) -> TypeNode | None:
        if isinstance(node, NullPtrLitExpr):
            return NullPtrType()

        if isinstance(node, BoolLitExpr):
            return BoolType()

        if isinstance(node, IntLitExpr):
            return node.int_type

        if isinstance(node, RealFloatLitExpr):
            return node.float_type

        if isinstance(node, DecFloatLitExpr):
            return node.float_type

        if isinstance(node, CharLitExpr):
            return node.char_type

        if isinstance(node, StrLitExpr):
            return PtrType(node.char_type, set())

        if isinstance(node, IdenExpr):
            return self.lookup(node.iden)

        if isinstance(node, CastExpr):
            return node.expr_type

        if isinstance(node, CompoundLitExpr):
            return node.expr_type

        if isinstance(node, CallExpr):
            return self.type_of_call(node)

        if isinstance(node, OpExpr):
            return self.type_of_op(node)

        if isinstance(node, CondExpr):
            return self.type_of(node.true_expr)

        if isinstance(node, CommaExpr):
            _, snd = node.exprs
            return self.type_of(snd)

        # MemberExpr, ArraySubExpr, GenericSelExpr: require struct layout
        # or ctrl-expr type not available here.
        # SizeOfExpr, AlignOfExpr: return implementation-defined size_t.
        return None

    def type_of_call(self, node: CallExpr) -> TypeNode | None:
        callee_t = self.type_of(node.callee_expr)
        if callee_t is None:
            return None

        callee_t = self.unqual(callee_t)

        if isinstance(callee_t, FunType):
            return callee_t.ret_type

        # Function pointer: peel off the pointer layer.
        if isinstance(callee_t, PtrType):
            inner = self.unqual(callee_t.pointee)
            if isinstance(inner, FunType):
                return inner.ret_type

        return None

    def type_of_op(self, node: OpExpr) -> TypeNode | None:
        if isinstance(node.op, UnaPrefOpTag):
            if node.op == UnaPrefOpTag.addr_of:
                operand_t = self.type_of(node.exprs[0])
                if operand_t is None:
                    return None
                return PtrType(operand_t, set())

            if node.op == UnaPrefOpTag.deref:
                operand_t = self.type_of(node.exprs[0])
                if operand_t is None:
                    return None
                operand_t = self.unqual(operand_t)
                if isinstance(operand_t, PtrType):
                    return operand_t.pointee
                return None

            if node.op == UnaPrefOpTag.bool_neg:
                return IntType(IntKind.int, SignKind.default)

            # prefix_inc, prefix_dec, plus, neg, bit_neg: type of operand.
            return self.type_of(node.exprs[0])

        if isinstance(node.op, UnaPostOpTag):
            # postfix_inc, postfix_dec: type of the operand.
            return self.type_of(node.exprs[0])

        if isinstance(node.op, BinOpTag):
            if node.op in (BinOpTag.lt, BinOpTag.gt, BinOpTag.le, BinOpTag.ge,
                           BinOpTag.eq, BinOpTag.ne,
                           BinOpTag.bool_and, BinOpTag.bool_or):
                return IntType(IntKind.int, SignKind.default)

            if node.op in (BinOpTag.assign,
                           BinOpTag.add_assign, BinOpTag.sub_assign,
                           BinOpTag.mul_assign, BinOpTag.div_assign,
                           BinOpTag.mod_assign,
                           BinOpTag.shl_assign, BinOpTag.shr_assign,
                           BinOpTag.bit_and_assign, BinOpTag.bit_xor_assign,
                           BinOpTag.bit_or_assign):
                return self.type_of(node.exprs[0])

            # Arithmetic and bitwise ops: use the left operand type as a
            # simplified stand-in for the usual arithmetic conversion result.
            return self.type_of(node.exprs[0])

        return None

####

# Loop Context Analysis
# Verifies that `continue` and `break` statements occur exclusively
# inside valid contexts:
#   - `break`    : inside a loop OR a switch statement
#   - `continue` : inside a loop only
class Analysis01:
    def __init__(self) -> None:
        self.in_loop: bool = False
        self.in_switch: bool = False

        self.error: None | Error = None

    def compound_stmt(self, node: CompoundStmt) -> bool:
        for stmt_node in node.stmts:
            if not self.visit(stmt_node):
                return False

        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.visit(node.then_stmt):
            return False

        return node.else_stmt is None or self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> bool:
        prev_switch_flag, self.in_switch = self.in_switch, True

        if not self.visit(node.then_stmt):
            return False

        self.in_switch = prev_switch_flag
        return True

    def loop_stmt(self, node: ForStmt | WhileStmt) -> bool:
        prev_loop_flag, self.in_loop = self.in_loop, True

        if not self.visit(node.then_stmt):
            return False

        self.in_loop = prev_loop_flag
        return True

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        prev_loop_flag, self.in_loop = self.in_loop, True

        if not self.visit(node.do_stmt):
            return False

        self.in_loop = prev_loop_flag
        return True

    def break_stmt(self, node: BreakStmt) -> bool:
        if self.in_loop or self.in_switch:
            return True

        self.error = Error()
        return False

    def continue_stmt(self, node: ContinueStmt) -> bool:
        if self.in_loop:
            return True

        self.error = Error()
        return False

    def fun_decl(self, node: FunDecl) -> bool:
        return node.body is None or self.visit(node.body)

    def trans_unit_decl(self, node: TransUnitDecl) -> None | Error:
        for decl in node.decls:
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return self.error

        return None

    def visit(self, node: StmtNode) -> bool:
        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, (ForStmt, WhileStmt)):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, BreakStmt):
            return self.break_stmt(node)

        if isinstance(node, ContinueStmt):
            return self.continue_stmt(node)

        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None
        return self.trans_unit_decl(ast.root)


# Switch Context Analysis
# Verifies the following constraints:
# - `case` and `default` labels appear exclusively within `switch`
#   statements.
# - `case` and `default` labels are unique within one `swtich`
#   statement scope.
# - `switch` statements utilize integer constant expressions.
# - `case` labels contain only constant expressions.
class Analysis02:
    def __init__(self) -> None:
        self.in_switch: bool = False
        self.labels: set[int | None] = set()

        self.error: None | Error = None

    def compound_stmt(self, node: CompoundStmt) -> bool:
        for stmt_node in node.stmts:
            if not self.visit(stmt_node):
                return False

        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.visit(node.then_stmt):
            return False

        return node.else_stmt is None or self.visit(node.else_stmt)

    def case_stmt(self, node: CaseLabelStmt) -> bool:
        if not self.in_switch:
            self.error = Error()
            return False

        label: int | None = None

        if node.cond_expr is not None:
            if not is_int_constant_expr(node.cond_expr):
                self.error = Error()
                return False

            label = eval_int_constant_expr(node.cond_expr)

        if label in self.labels:
            self.error = Error()
            return False

        self.labels.add(label)
        return True

    def switch_stmt(self, node: SwitchStmt) -> bool:
        prev_switch_flag, self.in_switch = self.in_switch, True
        prev_labels, self.labels = self.labels, set()

        if not is_int_expr(node.cond_expr):
            self.error = Error()
            return False

        if not self.visit(node.then_stmt):
            return False

        self.in_switch = prev_switch_flag
        self.labels = prev_labels
        return True

    def loop_stmt(self, node: ForStmt | WhileStmt) -> bool:
        return self.visit(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.visit(node.do_stmt)

    def fun_decl(self, node: FunDecl) -> bool:
        return node.body is None or self.visit(node.body)

    def visit(self, node: StmtNode) -> bool:
        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, CaseLabelStmt):
            return self.case_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, (ForStmt, WhileStmt)):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        for decl in ast.root.decls:
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return self.error

        return None


# Declaration Uniqueness Analysis
# Verifies the following constraints:
# - `variable` declarations are not duplicated within the same block
#    scope.
# - function parameter names are not duplicated within the same
#   `function` declaration.
# - `enum`, `struct` and `union` definitions are not duplicated within
#   the same block scope.
# - `enum`, `struct` and `union` declarations have different identifiers
#   within the same block scope, unless they are the same tag kind.
class Analysis03:
    def __init__(self) -> None:
        self.block_idens: set[str] = set()
        self.tag_defs: set[str] = set()
        self.tag_idens: dict[str, int] = {}

        self.scope: list[tuple[set[str], set[str], dict[str, int]]] = []

        self.error: None | Error = None

    def tag_id(self, node: EnumDecl | StructDecl | UnionDecl) -> int:
        if isinstance(node, EnumDecl):
            return 0

        if isinstance(node, StructDecl):
            return 1

        if isinstance(node, UnionDecl):
            return 2

        assert False

    def scope_push(self) -> None:
        self.scope.append(
            (self.block_idens, self.tag_defs, self.tag_idens)
        )

        self.block_idens = set()
        self.tag_defs = set()
        self.tag_idens = {}

    def scope_pop(self) -> None:
        self.block_idens, self.tag_defs, self.tag_idens = self.scope.pop()

    # Declarations.
    def trans_unit_decl(self, node: TransUnitDecl) -> bool:
        for decl in node.decls:
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return False

        return True

    def var_decl(self, node: VarDecl) -> bool:
        if node.iden in self.block_idens:
            self.error = Error()
            return False

        self.block_idens.add(node.iden)
        return True

    Signature = tuple[str | None, list[DeclNode] | None]

    def tag_signature(self,
                      node: EnumDecl | StructDecl | UnionDecl) -> Signature:
        if isinstance(node, EnumDecl):
            base = _unwrap_enum(node)
            iden    = base.iden    if base is not None else None
            members = base.members if base is not None else None

        elif isinstance(node, StructDecl):
            base = _unwrap_struct(node)
            iden    = base.iden    if base is not None else None
            members = base.members if base is not None else None

        else:
            base = _unwrap_union(node)
            iden    = base.iden    if base is not None else None
            members = base.members if base is not None else None

        return (iden, members)

    def tag_decl(self, node: EnumDecl | StructDecl | UnionDecl) -> bool:
        iden, members = self.tag_signature(node)

        if iden is None:
            return True

        tag_id = self.tag_id(node)

        if tag_id != self.tag_idens.get(iden, tag_id):
            self.error = Error()
            return False

        self.tag_idens[iden] = self.tag_id(node)

        if members is None:
            return True

        if iden in self.tag_defs:
            self.error = Error()
            return False

        self.tag_defs.add(iden)
        return True

    def fun_decl(self, node: FunDecl) -> bool:
        self.scope_push()
        self.block_idens.add(node.iden)

        for param in node.fun_type.params:
            if param.iden is None:
                continue

            if param.iden in self.block_idens:
                self.error = Error()
                return False

            self.block_idens.add(param.iden)

        if node.body is None:
            self.scope_pop()
            return True

        for stmt_node in node.body.stmts:
            if not self.visit(stmt_node):
                return False

        self.scope_pop()
        return True

    # Statements.
    def decl_stmt(self, node: DeclStmt) -> bool:
        if isinstance(node.decl, VarDecl):
            return self.var_decl(node.decl)

        if isinstance(node.decl, (EnumDecl, StructDecl, UnionDecl)):
            return self.tag_decl(node.decl)

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        self.scope_push()

        for stmt_node in node.stmts:
            if not self.visit(stmt_node):
                return False

        self.scope_pop()

        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.visit(node.then_stmt):
            return False

        return node.else_stmt is None or self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.visit(node.then_stmt)

    def for_stmt(self, node: ForStmt) -> bool:
        if not isinstance(node.init_clause, DeclNode):
            return self.visit(node.then_stmt)

        self.scope_push()

        if isinstance(node.init_clause, VarDecl):
            if not self.var_decl(node.init_clause):
                return False

        if not isinstance(node.then_stmt, CompoundStmt):
            if not self.visit(node.then_stmt):
                return False
        else:
            for stmt_node in node.then_stmt.stmts:
                if not self.visit(stmt_node):
                    return False

        self.scope_pop()

        return True

    def while_stmt(self, node: WhileStmt) -> bool:
        return self.visit(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.visit(node.do_stmt)

    def visit(self, node: StmtNode) -> bool:
        if isinstance(node, DeclStmt):
            return self.decl_stmt(node)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        if not self.trans_unit_decl(ast.root):
            return self.error

        return None


# Identifier Scope Analysis
# Verifies that all identifiers are declared before use, follow
# block-level scoping, and are not referenced within their own
# initializers.
class Analysis04:
    def __init__(self) -> None:
        self.scopes: list[set[str]] = []
        self.error: None | Error = None

    def lookup(self, name: str) -> bool:
        for i in range(len(self.scopes) -1, -1, -1):
            if name in self.scopes[i]:
                return True

        return False

    def declare(self, name: str) -> None:
        self.scopes[-1].add(name)

    def scope_push(self) -> None:
        self.scopes.append(set())

    def scope_pop(self) -> None:
        self.scopes.pop()

    # Types.
    def bit_int_type(self, node: BitIntType) -> bool:
        return self.expr(node.width_expr)

    def ptr_type(self, node: PtrType) -> bool:
        return self.type(node.pointee)

    def array_type(self, node: ArrayType) -> bool:
        if not self.type(node.elem_type):
            return False

        if node.elem_count is not None:
            return self.expr(node.elem_count)

        return True

    def fun_type(self, node: FunType) -> bool:
        if not self.type(node.ret_type):
            return False

        for param in node.params:
            if not self.type(param.param_type):
                return False

        return True

    def enum_type(self, node: EnumType) -> bool:
        if node.member_type is not None:
            if not self.type(node.member_type):
                return False

        if node.members is None:
            return True

        for member in node.members:
            if member.expr is not None and not self.expr(member.expr):
                return False

            self.declare(member.iden)

        return True

    def struct_or_union_type(self, node: StructType | UnionType) -> bool:
        if node.members is None:
            return True

        for member in node.members:
            if not self.decl(member):
                return False

        return True

    def atomic_type(self, node: AtomicType) -> bool:
        return self.type(node.base_type)

    def typeof_or_unqual_type(self,
                              node: TypeOfType | TypeOfUnqualType) -> bool:
        if isinstance(node.expr_or_type, ExprNode):
            return self.expr(node.expr_or_type)
        else:
            return self.type(node.expr_or_type)

    def typedef_type(self, node: TypeDefType) -> bool:
        if not self.lookup(node.iden):
            self.error = Error()
            return False

        return True

    def qualified_type(self, node: QualifiedType) -> bool:
        if not self.type(node.base_type):
            return False

        if isinstance(node.alignment, ExprNode):
            return self.expr(node.alignment)

        if isinstance(node.alignment, TypeNode):
            return self.type(node.alignment)

        return True

    def type(self, node: TypeNode) -> bool:
        if isinstance(node, BitIntType):
            return self.bit_int_type(node)

        if isinstance(node, PtrType):
            return self.ptr_type(node)

        if isinstance(node, ArrayType):
            return self.array_type(node)

        if isinstance(node, FunType):
            return self.fun_type(node)

        if isinstance(node, EnumType):
            return self.enum_type(node)

        if isinstance(node, (StructType, UnionType)):
            return self.struct_or_union_type(node)

        if isinstance(node, AtomicType):
            return self.atomic_type(node)

        if isinstance(node, (TypeOfType, TypeOfUnqualType)):
            return self.typeof_or_unqual_type(node)

        if isinstance(node, TypeDefType):
            return self.typedef_type(node)

        if isinstance(node, QualifiedType):
            return self.qualified_type(node)

        return True

    # Initialisers.
    def expr_or_init(self, node: ExprNode | InitNode) -> bool:
        if isinstance(node, ExprNode):
            return self.expr(node)

        return self.init(node)

    def init_member(self, node: InitMember) -> bool:
        if node.rec_init is not None:
            return self.init(node.rec_init)

        elif node.expr_or_init is not None:
            return self.expr_or_init(node.expr_or_init)

        assert False

    def init_index(self, node: InitIndex) -> bool:
        if not self.expr(node.idx_expr):
            return False

        if node.rec_init is not None:
            return self.init(node.rec_init)

        elif node.expr_or_init is not None:
            return self.expr_or_init(node.expr_or_init)

        assert False

    def init_list(self, node: InitList) -> bool:
        for elem in node.init_elems:
            if not self.expr_or_init(elem):
                return False

        return True

    def init(self, node: InitNode) -> bool:
        if isinstance(node, InitMember):
            return self.init_member(node)

        if isinstance(node, InitIndex):
            return self.init_index(node)

        if isinstance(node, InitList):
            return self.init_list(node)

        assert False

    # Expressions.
    def iden_expr(self, node: IdenExpr) -> bool:
        if not self.lookup(node.iden):
            self.error = Error()
            return False

        return True

    def generic_sel_expr(self, node: GenericSelExpr) -> bool:
        if not self.expr(node.ctrl_expr):
            return False

        for case_expr in node.assoc_table.values():
            if not self.expr(case_expr):
                return False

        return True

    def array_sub_expr(self, node: ArraySubExpr) -> bool:
        return self.expr(node.base_expr) and self.expr(node.idx_expr)

    def call_expr(self, node: CallExpr) -> bool:
        if not self.expr(node.callee_expr):
            return False

        for arg in node.arg_exprs:
            if not self.expr(arg):
                return False

        return True

    def member_expr(self, node: MemberExpr) -> bool:
        return self.expr(node.base_expr)

    def compound_lit_expr(self, node: CompoundLitExpr) -> bool:
        return self.init_list(node.init)

    def cast_expr(self, node: CastExpr) -> bool:
        return self.expr(node.expr)

    def op_expr(self, node: OpExpr) -> bool:
        for child in node.exprs:
            if not self.expr(child):
                return False

        return True

    def cond_expr(self, node: CondExpr) -> bool:
        return (
            self.expr(node.cond_expr) and
            self.expr(node.true_expr) and
            self.expr(node.false_expr)
        )

    def comma_expr(self, node: CommaExpr) -> bool:
        fst, snd = node.exprs
        return self.expr(fst) and self.expr(snd)

    def sizeof_expr(self, node: SizeOfExpr) -> bool:
        if isinstance(node.expr_or_type, ExprNode):
            return self.expr(node.expr_or_type)

        return True

    def expr(self, node: ExprNode) -> bool:
        if isinstance(node, IdenExpr):
            return self.iden_expr(node)

        if isinstance(node, LITERAL_EXPRS):
            return True

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
            return self.op_expr(node)

        if isinstance(node, CondExpr):
            return self.cond_expr(node)

        if isinstance(node, CommaExpr):
            return self.comma_expr(node)

        if isinstance(node, SizeOfExpr):
            return self.sizeof_expr(node)

        if isinstance(node, AlignOfExpr):
            return True

        assert False

    # Declarations.
    def var_decl(self, node: VarDecl) -> bool:
        if node.init is not None:
            if isinstance(node.init, ExprNode):
                if not self.expr(node.init):
                    return False
            else:
                if not self.init_list(node.init):
                    return False

        self.declare(node.iden)
        return True

    def fun_decl(self, node: FunDecl) -> bool:
        if node.body is None:
            return True

        self.scope_push()

        for param in node.fun_type.params:
            if param.iden is not None:
                self.declare(param.iden)

        for stmt_node in node.body.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def enum_decl(self, node: EnumDecl) -> bool:
        return self.type(node.enum_type)

    def struct_decl(self, node: StructDecl) -> bool:
        return self.type(node.struct_type)

    def union_decl(self, node: UnionDecl) -> bool:
        return self.type(node.union_type)

    def decl(self, node: DeclNode) -> bool:
        if isinstance(node, TransUnitDecl):
            for sub in node.decls:
                if not self.decl(sub):
                    return False
            return True

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

        if isinstance(node, StaticAssertDecl):
            return self.expr(node.cond_expr)

        return True

    # Statements.
    def assert_stmt(self, node: AssertStmt) -> bool:
        if not self.expr(node.cond_expr):
            return False

        for arg in node.arg_exprs:
            if not self.expr(arg):
                return False

        return True

    def println_stmt(self, node: PrintLnStmt) -> bool:
        for arg in node.arg_exprs:
            if not self.expr(arg):
                return False

        return True

    def decl_stmt(self, node: DeclStmt) -> bool:
        return self.decl(node.decl)

    def compound_stmt(self, node: CompoundStmt) -> bool:
        self.scope_push()

        for stmt_node in node.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.expr(node.cond_expr):
            return False

        if not self.stmt(node.then_stmt):
            return False

        if node.else_stmt is not None and not self.stmt(node.else_stmt):
            return False

        return True

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.expr(node.cond_expr) and self.stmt(node.then_stmt)

    def case_label_stmt(self, node: CaseLabelStmt) -> bool:
        if node.cond_expr is not None:
            return self.expr(node.cond_expr)

        return True

    def for_stmt(self, node: ForStmt) -> bool:
        self.scope_push()

        if isinstance(node.init_clause, ExprNode):
            if not self.expr(node.init_clause):
                return False

        elif isinstance(node.init_clause, VarDecl):
            if not self.var_decl(node.init_clause):
                return False

        if node.cond_expr is not None:
            if not self.expr(node.cond_expr):
                return False

        if node.inc_expr is not None:
            if not self.expr(node.inc_expr):
                return False

        if not self.stmt(node.then_stmt):
            return False

        self.scope_pop()
        return True

    def while_stmt(self, node: WhileStmt) -> bool:
        return self.expr(node.cond_expr) and self.stmt(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.stmt(node.do_stmt) and self.expr(node.cond_expr)

    def return_stmt(self, node: ReturnStmt) -> bool:
        if node.ret_expr is not None:
            return self.expr(node.ret_expr)

        return True

    def stmt(self, node: StmtNode) -> bool:
        if isinstance(node, AssertStmt):
            return self.assert_stmt(node)

        if isinstance(node, PrintLnStmt):
            return self.println_stmt(node)

        if isinstance(node, DeclStmt):
            return self.decl_stmt(node)

        if isinstance(node, ExprStmt):
            return self.expr(node.expr)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, CaseLabelStmt):
            return self.case_label_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, ReturnStmt):
            return self.return_stmt(node)

        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        self.scope_push()

        # First pass: collect all file-scope names so that file-scope
        # function definitions can reference each other freely.
        for decl in ast.root.decls:
            if isinstance(decl, (VarDecl, FunDecl)):
                self.declare(decl.iden)

            elif isinstance(decl, EnumDecl):
                base = _unwrap_enum(decl)
                if base is not None and base.members is not None:
                    for member in base.members:
                        self.declare(member.iden)

        # Second pass: check expressions inside declarations.
        for decl in ast.root.decls:
            if isinstance(decl, FunDecl):
                if not self.fun_decl(decl):
                    assert self.error is not None
                    return self.error

            elif isinstance(decl, StructDecl):
                if not self.struct_decl(decl):
                    assert self.error is not None
                    return self.error

            elif isinstance(decl, UnionDecl):
                if not self.union_decl(decl):
                    assert self.error is not None
                    return self.error

        self.scope_pop()
        return None


# Function Signature Analysis
# Verifies the following constraints:
# - `function` declarations and definitions have matching return types,
#   parameter counts, and parameter types.
# - `function` definitions are not duplicated.
class Analysis05:
    def __init__(self) -> None:
        self.decls: dict[str, FunDecl] = {}
        self.error: None | Error = None

    def match_types(self, fst: TypeNode, snd: TypeNode) -> bool:
        pass

    def match_params(self,
                     fst_params: list[ParamSpec],
                     snd_params: list[ParamSpec]) -> bool:
        if len(fst_params) != len(snd_params):
            return False

        for i in range(len(fst_params)):
            if not self.match_types(fst_params[i].param_type, snd_params[i].param_type):
                return False

        return True

    def fun_decl(self, node: FunDecl) -> bool:
        prev_decl = self.decls.get(node.iden)

        if prev_decl is None:
            self.decls[node.iden] = node
            return True

        if not self.match_types(prev_decl.fun_type.ret_type, node.fun_type.ret_type):
            self.error = Error()
            return False

        if not self.match_params(prev_decl.fun_type.params, node.fun_type.params):
            self.error = Error()
            return False

        if node.body is not None and prev_decl.body is not None:
            self.error = Error()
            return False

        if node.body is not None:
            self.decls[node.iden] = node

        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        for decl in ast.root.decls:
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return self.error

        return None


# Goto Label Analysis
# Verifies the following constraints:
# - `goto` statements have associated destination `label` statements.
# - `label` statements are not duplicated within the same function
#   declaration.
class Analysis06:
    def __init__(self) -> None:
        self.labels: set[str] = set()
        self.goto_labels: list[str] = []

        self.error: None | Error = None

    def visit(self, node: StmtNode) -> bool:
        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, (ForStmt, WhileStmt)):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, GotoStmt):
            return self.goto_stmt(node)

        if isinstance(node, LabelStmt):
            return self.label_stmt(node)

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        for stmt_node in node.stmts:
            if not self.visit(stmt_node):
                return False

        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.visit(node.then_stmt):
            return False

        return node.else_stmt is None or self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.visit(node.then_stmt)

    def loop_stmt(self, node: ForStmt | WhileStmt) -> bool:
        return self.visit(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.visit(node.do_stmt)

    def goto_stmt(self, node: GotoStmt) -> bool:
        self.goto_labels.append(node.label_iden)
        return True

    def label_stmt(self, node: LabelStmt) -> bool:
        if node.iden in self.labels:
            self.error = Error()
            return False

        self.labels.add(node.iden)
        return True

    def fun_decl(self, node: FunDecl) -> bool:
        self.labels = set()
        self.goto_labels = []

        if node.body is not None and not self.visit(node.body):
            return False

        for goto_label in self.goto_labels:
            if goto_label not in self.labels:
                self.error = Error()
                return False

        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        for decl in ast.root.decls:
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return self.error

        return None

# Goto Jump Analysis
# Verifies that 'goto' statements do not jump forward over variable
# declarations that are used after the destination label.
class IdenCollector:
    def __init__(self) -> None:
        self.idens: set[str] = set()

    def iden_expr(self, node: IdenExpr) -> None:
        self.idens.add(node.iden)

    def generic_sel_expr(self, node: GenericSelExpr) -> None:
        self.collect_from_expr(node.ctrl_expr)

        for expr_node in node.assoc_table.values():
            self.collect_from_expr(expr_node)

    def array_sub_expr(self, node: ArraySubExpr) -> None:
        self.collect_from_expr(node.base_expr)
        self.collect_from_expr(node.idx_expr)

    def call_expr(self, node: CallExpr) -> None:
        self.collect_from_expr(node.callee_expr)

        for arg_node in node.arg_exprs:
            self.collect_from_expr(arg_node)

    def member_expr(self, node: MemberExpr) -> None:
        self.collect_from_expr(node.base_expr)

    def compound_lit_expr(self, node: CompoundLitExpr) -> None:
        pass

    def cast_expr(self, node: CastExpr) -> None:
        self.collect_from_expr(node.expr)

    def op_expr(self, node: OpExpr) -> None:
        for child_expr in node.exprs:
            self.collect_from_expr(child_expr)

    def cond_expr(self, node: CondExpr) -> None:
        self.collect_from_expr(node.cond_expr)
        self.collect_from_expr(node.true_expr)
        self.collect_from_expr(node.false_expr)

    def comma_expr(self, node: CommaExpr) -> None:
        fst, snd = node.exprs

        self.collect_from_expr(fst)
        self.collect_from_expr(snd)

    def sizeof_expr(self, node: SizeOfExpr) -> None:
        if isinstance(node.expr_or_type, ExprNode):
            self.collect_from_expr(node.expr_or_type)

    def collect_from_expr(self, node: ExprNode) -> None:
        if isinstance(node, IdenExpr):
            return self.iden_expr(node)

        if isinstance(node, CallExpr):
            return self.call_expr(node)

        if isinstance(node, ArraySubExpr):
            return self.array_sub_expr(node)

        if isinstance(node, MemberExpr):
            return self.member_expr(node)

        if isinstance(node, CompoundLitExpr):
            return self.compound_lit_expr(node)

        if isinstance(node, CastExpr):
            return self.cast_expr(node)

        if isinstance(node, OpExpr):
            return self.op_expr(node)

        if isinstance(node, CondExpr):
            return self.cond_expr(node)

        if isinstance(node, CommaExpr):
            return self.comma_expr(node)

        if isinstance(node, SizeOfExpr):
            return self.sizeof_expr(node)

    def collect_from_stmt(self, node: StmtNode) -> None:
        pass


####
class Analysis07:
    def __init__(self) -> None:
        self.label_pos: dict[str, int] = {}
        self.flat: list[tuple[int, StmtNode]] = []

        self.error: None | Error = None

    def visit(self, node: StmtNode) -> None:
        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, (GotoStmt, LabelStmt, DeclStmt)):
            self.flat.append((len(self.flat), node))

            if isinstance(node, LabelStmt):
                self.label_pos[node.iden] = len(self.flat) - 1

    def compound_stmt(self, node: CompoundStmt) -> None:
        for stmt_node in node.stmts:
            self.visit(stmt_node)

    def if_stmt(self, node: IfStmt) -> None:
        self.visit(node.then_stmt)

        if node.else_stmt is not None:
            self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> None:
        self.visit(node.then_stmt)

    def for_stmt(self, node: ForStmt) -> None:
        if isinstance(node.init_clause, DeclNode):
            self.flat.append((len(self.flat), DeclStmt(node.init_clause)))

        self.visit(node.then_stmt)

    def while_stmt(self, node: WhileStmt) -> None:
        self.visit(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> None:
        self.visit(node.do_stmt)

    def _collect_idens_expr(self, node: ExprNode, out: set[str]) -> None:
        if isinstance(node, IdenExpr):
            out.add(node.iden)
            return

        if isinstance(node, (NullPtrLitExpr, BoolLitExpr, IntLitExpr,
                             RealFloatLitExpr, DecFloatLitExpr,
                             CharLitExpr, StrLitExpr, AlignOfExpr)):
            return

        if isinstance(node, GenericSelExpr):
            self._collect_idens_expr(node.ctrl_expr, out)
            for e in node.assoc_table.values():
                self._collect_idens_expr(e, out)
            return

        if isinstance(node, ArraySubExpr):
            self._collect_idens_expr(node.base_expr, out)
            self._collect_idens_expr(node.idx_expr, out)
            return

        if isinstance(node, CallExpr):
            self._collect_idens_expr(node.callee_expr, out)
            for arg in node.arg_exprs:
                self._collect_idens_expr(arg, out)
            return

        if isinstance(node, MemberExpr):
            self._collect_idens_expr(node.base_expr, out)
            return

        if isinstance(node, CastExpr):
            self._collect_idens_expr(node.expr, out)
            return

        if isinstance(node, OpExpr):
            for child in node.exprs:
                self._collect_idens_expr(child, out)
            return

        if isinstance(node, CondExpr):
            self._collect_idens_expr(node.cond_expr, out)
            self._collect_idens_expr(node.true_expr, out)
            self._collect_idens_expr(node.false_expr, out)
            return

        if isinstance(node, CommaExpr):
            fst, snd = node.exprs
            self._collect_idens_expr(fst, out)
            self._collect_idens_expr(snd, out)
            return

        if isinstance(node, SizeOfExpr):
            if isinstance(node.expr_or_type, ExprNode):
                self._collect_idens_expr(node.expr_or_type, out)

    def _collect_idens_stmt(self, node: StmtNode, out: set[str]) -> None:
        if isinstance(node, ExprStmt) and node.expr is not None:
            self._collect_idens_expr(node.expr, out)
        elif isinstance(node, DeclStmt):
            if isinstance(node.decl, VarDecl) and node.decl.init is not None:
                if isinstance(node.decl.init, ExprNode):
                    self._collect_idens_expr(node.decl.init, out)
        elif isinstance(node, CompoundStmt):
            for child in node.stmts:
                self._collect_idens_stmt(child, out)
        elif isinstance(node, IfStmt):
            self._collect_idens_expr(node.cond_expr, out)
            self._collect_idens_stmt(node.then_stmt, out)
            if node.else_stmt is not None:
                self._collect_idens_stmt(node.else_stmt, out)
        elif isinstance(node, ReturnStmt):
            if node.ret_expr is not None:
                self._collect_idens_expr(node.ret_expr, out)
        elif isinstance(node, ForStmt):
            if node.cond_expr is not None:
                self._collect_idens_expr(node.cond_expr, out)
            if node.inc_expr is not None:
                self._collect_idens_expr(node.inc_expr, out)
            self._collect_idens_stmt(node.then_stmt, out)
        elif isinstance(node, WhileStmt):
            self._collect_idens_expr(node.cond_expr, out)
            self._collect_idens_stmt(node.then_stmt, out)
        elif isinstance(node, DoWhileStmt):
            self._collect_idens_expr(node.cond_expr, out)
            self._collect_idens_stmt(node.do_stmt, out)

    def check_skipped_decls(self,
                            goto_idx: int,
                            label_idx: int) -> bool:
        skipped_decls: set[str] = set()

        for idx, node in self.flat:
            if not (goto_idx < idx < label_idx):
                continue

            # something something not only vardecls but struct
            # definitions and that but idk
            if isinstance(node, DeclStmt) and \
               isinstance(node.decl, VarDecl):
                skipped_decls.add(node.decl.iden)

        if not skipped_decls:
            return True

        used_idens: set[str] = set()

        for idx, node in self.flat:
            if idx >= label_idx:
                self._collect_idens_stmt(node, used_idens)

        if len(skipped_decls & used_idens) != 0:
            self.error = Error()
            return False

        return True

    # --- Entry points ---

    def fun_decl(self, node: FunDecl) -> bool:
        self.flat = []
        self.label_pos = {}

        if node.body is not None:
            self.visit(node.body)

        # For every forward goto, verify no skipped declaration is used after
        # the target label.
        for goto_idx, node_ in self.flat:
            if not isinstance(node_, GotoStmt):
                continue
            label = node_.label_iden
            if label not in self.label_pos:
                # Undefined label — caught by a separate analysis pass.
                continue
            label_idx = self.label_pos[label]
            if label_idx <= goto_idx:
                # Backward jump — not our concern here.
                continue
            if not self.check_skipped_decls(goto_idx, label_idx):
                return False
        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        for decl in ast.root.decls:
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return self.error

        return None
####


# Format String Analysis
# Verifies the following constraints:
# - `println` statements have a matching number of format specifiers
#   and arguments.
# - `assert` statements have a matching number of format specifiers
#   and arguments.
class Analysis08:
    def __init__(self) -> None:
        self.error: None | Error = None

    def visit(self, node: StmtNode) -> bool:
        if isinstance(node, AssertStmt):
            return self.assert_stmt(node)

        if isinstance(node, PrintLnStmt):
            return self.println_stmt(node)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, (ForStmt, WhileStmt)):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        return True

    def msg_fmt(self, node: AssertStmt | PrintLnStmt) -> bool:
        str_lit_expr: StrLitExpr | None = node.str_expr
        if str_lit_expr is None:
            return True

        count: int = str_lit_expr.str_expr.count(FORMAT_SPEC)
        if len(node.arg_exprs) != count:
            self.error = Error()
            return False

        return True

    def assert_stmt(self, node: AssertStmt) -> bool:
        return self.msg_fmt(node)

    def println_stmt(self, node: PrintLnStmt) -> bool:
        return self.msg_fmt(node)

    def compound_stmt(self, node: CompoundStmt) -> bool:
        for stmt_node in node.stmts:
            if not self.visit(stmt_node):
                return False

        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.visit(node.then_stmt):
            return False

        return node.else_stmt is None or self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.visit(node.then_stmt)

    def loop_stmt(self, node: ForStmt | WhileStmt) -> bool:
        return self.visit(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.visit(node.do_stmt)

    def fun_decl(self, node: FunDecl) -> bool:
        return node.body is None or self.visit(node.body)

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        for decl in ast.root.decls:
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return self.error

        return None




####

# Typedef Base Type Analysis
# Verifies the following constraints:
# - Each `typedef` declaration references a type name that has already
#   been declared at the point of the `typedef`.
# - Named struct, union, and enum tags used in a `typedef` base type
#   must have a prior forward declaration or definition.
# - Typedef alias names used inside a `typedef` base type must have a
#   prior `typedef` declaration.
class Analysis09:
    def __init__(self) -> None:
        self.typedef_names: set[str] = set()
        self.struct_tags: set[str] = set()
        self.union_tags: set[str] = set()
        self.enum_tags: set[str] = set()

        self.error: None | Error = None

    def check_type(self, node: TypeNode) -> bool:
        if isinstance(node, TypeDefType):
            if node.iden not in self.typedef_names:
                self.error = Error()
                return False

            return True

        if isinstance(node, StructType):
            if node.members is not None:
                if node.iden is not None:
                    self.struct_tags.add(node.iden)

                for member_decl in node.members:
                    if not self.check_decl(member_decl):
                        return False

                return True

            if node.iden is not None and node.iden not in self.struct_tags:
                self.error = Error()
                return False

            return True

        if isinstance(node, UnionType):
            if node.members is not None:
                if node.iden is not None:
                    self.union_tags.add(node.iden)

                for member_decl in node.members:
                    if not self.check_decl(member_decl):
                        return False

                return True

            if node.iden is not None and node.iden not in self.union_tags:
                self.error = Error()
                return False

            return True

        if isinstance(node, EnumType):
            if node.members is not None:
                if node.iden is not None:
                    self.enum_tags.add(node.iden)

                return True

            if node.iden is not None and node.iden not in self.enum_tags:
                self.error = Error()
                return False

            return True

        if isinstance(node, PtrType):
            return self.check_type(node.pointee)

        if isinstance(node, ArrayType):
            return self.check_type(node.elem_type)

        if isinstance(node, FunType):
            if not self.check_type(node.ret_type):
                return False

            for param in node.params:
                if not self.check_type(param.param_type):
                    return False

            return True

        if isinstance(node, QualifiedType):
            return self.check_type(node.base_type)

        if isinstance(node, AtomicType):
            return self.check_type(node.base_type)

        if isinstance(node, (TypeOfType, TypeOfUnqualType)):
            if isinstance(node.expr_or_type, TypeNode):
                return self.check_type(node.expr_or_type)

            return True

        return True

    def check_decl(self, node: DeclNode) -> bool:
        if isinstance(node, VarDecl):
            return self.check_type(node.var_type)

        if isinstance(node, StructDecl):
            if node.struct_type is not None:
                return self.check_type(node.struct_type)

            return True

        if isinstance(node, UnionDecl):
            if node.union_type is not None:
                return self.check_type(node.union_type)

            return True

        if isinstance(node, EnumDecl):
            if node.enum_type is not None:
                return self.check_type(node.enum_type)

            return True

        if isinstance(node, TypedefDecl):
            return self.typedef_decl(node)

        return True

    def register_decl(self, node: DeclNode) -> None:
        if isinstance(node, StructDecl):
            base = _unwrap_struct(node)
            if base is not None and base.iden is not None:
                self.struct_tags.add(base.iden)

        elif isinstance(node, UnionDecl):
            base = _unwrap_union(node)
            if base is not None and base.iden is not None:
                self.union_tags.add(base.iden)

        elif isinstance(node, EnumDecl):
            base = _unwrap_enum(node)
            if base is not None and base.iden is not None:
                self.enum_tags.add(base.iden)

    def typedef_decl(self, node: TypedefDecl) -> bool:
        if not self.check_type(node.base_type):
            return False

        self.typedef_names.add(node.alias_iden)
        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        for decl in ast.root.decls:
            if isinstance(decl, TypedefDecl):
                if not self.typedef_decl(decl):
                    assert self.error is not None
                    return self.error
            else:
                self.register_decl(decl)

        return None


####
# Return Type Analysis
# Verifies the following constraints:
# - Each `return` statement in a void function provides no expression.
# - Each `return` statement in a non-void function provides an expression.
# - Each return expression is implicitly convertible to the function's
#   declared return type under C23 simple-assignment rules (§6.5.16.1):
#   arithmetic ↔ arithmetic, nullptr → pointer, pointer ↔ void*,
#   scalar → bool, named aggregates require matching identifiers.
# When the expression type cannot be statically determined (member access,
# unresolved typedef aliases, sizeof, etc.) the check is skipped to
# avoid false positives.
class Analysis10(_TypeCheckBase):
    def __init__(self) -> None:
        super().__init__()
        self.ret_type: TypeNode | None = None
        self.error: None | Error = None

    # Scope maintenance — track declared names and their types.
    def var_decl(self, node: VarDecl) -> None:
        self.declare(node.iden, node.var_type)

    def enum_decl(self, node: EnumDecl) -> None:
        base = _unwrap_enum(node)
        if base is None or base.members is None:
            return
        for member in base.members:
            self.declare(member.iden, node.enum_type)

    def decl_stmt(self, node: DeclStmt) -> None:
        if isinstance(node.decl, VarDecl):
            self.var_decl(node.decl)
        elif isinstance(node.decl, EnumDecl):
            self.enum_decl(node.decl)

    # Statements.
    def stmt(self, node: StmtNode) -> bool:
        if isinstance(node, DeclStmt):
            self.decl_stmt(node)
            return True

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, ReturnStmt):
            return self.return_stmt(node)

        if isinstance(node, (ExprStmt, AssertStmt, PrintLnStmt,
                             CaseLabelStmt, GotoStmt, LabelStmt,
                             BreakStmt, ContinueStmt)):
            return True

        assert False

    def compound_stmt(self, node: CompoundStmt) -> bool:
        self.scope_push()

        for stmt_node in node.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.stmt(node.then_stmt):
            return False

        if node.else_stmt is not None:
            if not self.stmt(node.else_stmt):
                return False

        return True

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.stmt(node.then_stmt)

    def for_stmt(self, node: ForStmt) -> bool:
        self.scope_push()

        if isinstance(node.init_clause, VarDecl):
            self.var_decl(node.init_clause)

        if not self.stmt(node.then_stmt):
            return False

        self.scope_pop()
        return True

    def while_stmt(self, node: WhileStmt) -> bool:
        return self.stmt(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.stmt(node.do_stmt)

    def return_stmt(self, node: ReturnStmt) -> bool:
        assert self.ret_type is not None
        ret_base = self.unqual(self.ret_type)

        if isinstance(ret_base, VoidType):
            if node.ret_expr is not None:
                self.error = Error()
                return False
            return True

        if node.ret_expr is None:
            self.error = Error()
            return False

        expr_t = self.type_of(node.ret_expr)

        if expr_t is None:
            return True  # Cannot determine type — skip.

        if not self.is_convertible(expr_t, self.ret_type):
            self.error = Error()
            return False

        return True

    def fun_decl(self, node: FunDecl) -> bool:
        if node.body is None:
            return True

        prev_ret_type, self.ret_type = self.ret_type, node.fun_type.ret_type

        # Params and function body share one scope (C §6.2.1).
        self.scope_push()

        for param in node.fun_type.params:
            if param.iden is not None:
                self.declare(param.iden, param.param_type)

        for stmt_node in node.body.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()

        self.ret_type = prev_ret_type
        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        self.scope_push()

        # Collect all file-scope names first so function bodies can
        # reference globals and each other freely.
        for decl in ast.root.decls:
            if isinstance(decl, VarDecl):
                self.declare(decl.iden, decl.var_type)

            elif isinstance(decl, FunDecl):
                self.declare(decl.iden, decl.fun_type)

            elif isinstance(decl, EnumDecl):
                base = _unwrap_enum(decl)
                if base is not None and base.members is not None:
                    for member in base.members:
                        self.declare(member.iden, decl.enum_type)

        for decl in ast.root.decls:
            if isinstance(decl, FunDecl):
                if not self.fun_decl(decl):
                    assert self.error is not None
                    return self.error

        self.scope_pop()
        return None


####

# Constexpr Initializer Analysis
# Verifies that every `constexpr` variable is initialized with a constant
# expression as defined by C23 §6.6.  A constant expression is built from:
#   - any literal (integer, float, char, string, nullptr, bool)
#   - sizeof / alignof  (assumed non-VLA operand)
#   - references to constexpr variables or enum constants
#   - unary +, -, ~, !  applied to a constant expression
#   - address-of (&) applied to a file-scope variable or function
#     (static storage duration — the address is a compile-time constant)
#   - binary arithmetic, bitwise, logical, and comparison operators
#     applied to constant expressions
#   - cast to a scalar type of a constant expression
#   - conditional operator ?: where all three operands are constant
# The following make an expression non-constant:
#   - reference to a non-constexpr variable
#   - function call
#   - ++, --  (prefix or postfix)
#   - assignment operators
#   - * (dereference), [] (array subscript), . / -> (member access)
#   - comma operator
#   - compound literal, _Generic
#   - address-of a local (automatic-storage-duration) variable
# File-scope declarations are processed in declaration order so that a
# constexpr initializer may only reference previously declared constants.
class Analysis11:
    def __init__(self) -> None:
        self.value_const: list[set[str]] = []
        self.global_names: set[str] = set()
        self.error: None | Error = None

    def scope_push(self) -> None:
        self.value_const.append(set())

    def scope_pop(self) -> None:
        self.value_const.pop()

    def declare_const(self, name: str) -> None:
        self.value_const[-1].add(name)

    def is_const_value(self, name: str) -> bool:
        for scope in reversed(self.value_const):
            if name in scope:
                return True
        return False

    def has_const_addr(self, name: str) -> bool:
        return name in self.global_names

    def is_constexpr_var(self, node: VarDecl) -> bool:
        if isinstance(node.var_type, QualifiedType):
            return node.var_type.storage == StorageSpec.constexpr
        return False

    # Constant expression checker.
    def is_const_expr(self, node: ExprNode) -> bool:
        if isinstance(node, (NullPtrLitExpr, BoolLitExpr, IntLitExpr,
                             RealFloatLitExpr, DecFloatLitExpr,
                             CharLitExpr, StrLitExpr)):
            return True

        if isinstance(node, (SizeOfExpr, AlignOfExpr)):
            return True

        if isinstance(node, IdenExpr):
            return self.is_const_value(node.iden)

        if isinstance(node, CastExpr):
            return self.is_const_expr(node.expr)

        if isinstance(node, CondExpr):
            return (self.is_const_expr(node.cond_expr) and
                    self.is_const_expr(node.true_expr) and
                    self.is_const_expr(node.false_expr))

        if isinstance(node, OpExpr):
            return self.is_const_op_expr(node)

        # CallExpr, CommaExpr, MemberExpr, ArraySubExpr,
        # CompoundLitExpr, GenericSelExpr: not constant expressions.
        return False

    def is_const_op_expr(self, node: OpExpr) -> bool:
        if isinstance(node.op, UnaPrefOpTag):
            if node.op in (UnaPrefOpTag.prefix_inc, UnaPrefOpTag.prefix_dec):
                return False

            if node.op == UnaPrefOpTag.addr_of:
                operand = node.exprs[0]
                if isinstance(operand, IdenExpr):
                    return self.has_const_addr(operand.iden)
                return False

            if node.op == UnaPrefOpTag.deref:
                return False

            # plus, neg, bit_neg, bool_neg: constant if operand is.
            return self.is_const_expr(node.exprs[0])

        if isinstance(node.op, UnaPostOpTag):
            return False

        if isinstance(node.op, BinOpTag):
            if node.op in (BinOpTag.assign,
                           BinOpTag.add_assign, BinOpTag.sub_assign,
                           BinOpTag.mul_assign, BinOpTag.div_assign,
                           BinOpTag.mod_assign,
                           BinOpTag.shl_assign, BinOpTag.shr_assign,
                           BinOpTag.bit_and_assign, BinOpTag.bit_xor_assign,
                           BinOpTag.bit_or_assign):
                return False

            return (self.is_const_expr(node.exprs[0]) and
                    self.is_const_expr(node.exprs[1]))

        return False

    # Initializer tree checker.
    def is_const_init_list(self, node: InitList) -> bool:
        for elem in node.init_elems:
            if isinstance(elem, ExprNode):
                if not self.is_const_expr(elem):
                    return False
            else:
                if not self.is_const_init_node(elem):
                    return False
        return True

    def is_const_init_node(self, node: InitNode) -> bool:
        if isinstance(node, InitMember):
            if node.rec_init is not None:
                if not self.is_const_init_node(node.rec_init):
                    return False
            if node.expr_or_init is not None:
                if isinstance(node.expr_or_init, ExprNode):
                    return self.is_const_expr(node.expr_or_init)
                return self.is_const_init_node(node.expr_or_init)
            return True

        if isinstance(node, InitIndex):
            if not self.is_const_expr(node.idx_expr):
                return False
            if node.rec_init is not None:
                if not self.is_const_init_node(node.rec_init):
                    return False
            if node.expr_or_init is not None:
                if isinstance(node.expr_or_init, ExprNode):
                    return self.is_const_expr(node.expr_or_init)
                return self.is_const_init_node(node.expr_or_init)
            return True

        if isinstance(node, InitList):
            return self.is_const_init_list(node)

        assert False

    # VarDecl checker: only acts on constexpr declarations.
    def check_var_decl(self, node: VarDecl) -> bool:
        if not self.is_constexpr_var(node):
            return True

        if node.init is None:
            return True

        if isinstance(node.init, ExprNode):
            if not self.is_const_expr(node.init):
                self.error = Error()
                return False
        else:
            if not self.is_const_init_list(node.init):
                self.error = Error()
                return False

        return True

    def register_var_decl(self, node: VarDecl) -> None:
        if self.is_constexpr_var(node):
            self.declare_const(node.iden)

    # Statements.
    def stmt(self, node: StmtNode) -> bool:
        if isinstance(node, DeclStmt):
            return self.decl_stmt(node)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, (ExprStmt, ReturnStmt, AssertStmt, PrintLnStmt,
                             CaseLabelStmt, GotoStmt, LabelStmt,
                             BreakStmt, ContinueStmt)):
            return True

        assert False

    def decl_stmt(self, node: DeclStmt) -> bool:
        if isinstance(node.decl, VarDecl):
            if not self.check_var_decl(node.decl):
                return False
            self.register_var_decl(node.decl)

        elif isinstance(node.decl, EnumDecl):
            base = _unwrap_enum(node.decl)
            if base is not None and base.members is not None:
                for member in base.members:
                    self.declare_const(member.iden)

        elif isinstance(node.decl, StaticAssertDecl):
            if not self.is_const_expr(node.decl.cond_expr):
                self.error = Error()
                return False

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        self.scope_push()

        for stmt_node in node.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.stmt(node.then_stmt):
            return False

        if node.else_stmt is not None:
            if not self.stmt(node.else_stmt):
                return False

        return True

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.stmt(node.then_stmt)

    def for_stmt(self, node: ForStmt) -> bool:
        self.scope_push()

        if isinstance(node.init_clause, VarDecl):
            if not self.check_var_decl(node.init_clause):
                return False
            self.register_var_decl(node.init_clause)

        if not self.stmt(node.then_stmt):
            return False

        self.scope_pop()
        return True

    def while_stmt(self, node: WhileStmt) -> bool:
        return self.stmt(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.stmt(node.do_stmt)

    def fun_decl(self, node: FunDecl) -> bool:
        if node.body is None:
            return True

        self.scope_push()

        for stmt_node in node.body.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        self.scope_push()

        # Single pass in declaration order: each constexpr initializer
        # may only reference names declared before it.
        for decl in ast.root.decls:
            if isinstance(decl, VarDecl):
                self.global_names.add(decl.iden)

                if not self.check_var_decl(decl):
                    assert self.error is not None
                    return self.error

                self.register_var_decl(decl)

            elif isinstance(decl, FunDecl):
                self.global_names.add(decl.iden)

            elif isinstance(decl, EnumDecl):
                base = _unwrap_enum(decl)
                if base is not None and base.members is not None:
                    for member in base.members:
                        self.declare_const(member.iden)

            elif isinstance(decl, StaticAssertDecl):
                if not self.is_const_expr(decl.cond_expr):
                    self.error = Error()
                    return self.error

        for decl in ast.root.decls:
            if isinstance(decl, FunDecl):
                if not self.fun_decl(decl):
                    assert self.error is not None
                    return self.error

        self.scope_pop()
        return None


# Initializer Type Analysis
# Verifies that every variable initializer is compatible with its
# declared type under C23 §6.7.9:
#   - scalar: the initializer expression is convertible to the declared
#     type under simple-assignment rules (§6.5.16.1).
#   - array: each element (positional or designated) is convertible to
#     the element type; a char/wchar array may be initialized directly
#     from a matching string literal.
#   - struct / union: each element (positional or designated by member
#     name) is convertible to the corresponding member type.
#   - compound literals are checked by the same rules applied to their
#     explicitly written type.
#   - nested designators (InitIndex / InitMember with rec_init) are
#     checked recursively against the sub-aggregate's type.
# Types that cannot be resolved statically (TypeDefType, TypeOfType,
# TypeOfUnqualType, AtomicType) cause the check to be skipped to avoid
# false positives on unresolvable aliases.
class Analysis12(_TypeCheckBase):
    def __init__(self) -> None:
        super().__init__()
        self.error: None | Error = None

    # String-literal → char/wchar array special case (C23 §6.7.9 p14-15).
    def str_lit_fits_array(self, expr: StrLitExpr, arr: ArrayType) -> bool:
        elem = self.unqual(arr.elem_type)
        if not isinstance(elem, CharType):
            return False
        return expr.char_type.kind == elem.kind

    # Aggregate member lookup helpers.
    def struct_members(self, t: StructType) -> list[VarDecl]:
        if t.members is None:
            return []
        return [m for m in t.members if isinstance(m, VarDecl)]

    def struct_member_by_name(self, t: StructType, name: str) -> VarDecl | None:
        if t.members is None:
            return None
        for m in t.members:
            if isinstance(m, VarDecl) and m.iden == name:
                return m
        return None

    def union_first_member(self, t: UnionType) -> VarDecl | None:
        if t.members is None:
            return None
        for m in t.members:
            if isinstance(m, VarDecl):
                return m
        return None

    def union_member_by_name(self, t: UnionType, name: str) -> VarDecl | None:
        if t.members is None:
            return None
        for m in t.members:
            if isinstance(m, VarDecl) and m.iden == name:
                return m
        return None

    # Core init checkers.
    def check_expr_for_type(self, expr: ExprNode, t: TypeNode) -> bool:
        t_base = self.unqual(t)

        if isinstance(t_base, (TypeDefType, TypeOfType, TypeOfUnqualType, AtomicType)):
            return True

        # String literal initializing a char/wchar array directly.
        if isinstance(t_base, ArrayType) and isinstance(expr, StrLitExpr):
            if not self.str_lit_fits_array(expr, t_base):
                self.error = Error()
                return False
            return True

        expr_t = self.type_of(expr)
        if expr_t is None:
            return True  # Cannot determine type — skip.

        if not self.is_convertible(expr_t, t):
            self.error = Error()
            return False

        return True

    def check_init_elem_for_type(self,
                                  elem: ExprNode | InitNode,
                                  t: TypeNode) -> bool:
        if isinstance(elem, ExprNode):
            return self.check_expr_for_type(elem, t)

        return self.check_init_node_for_type(elem, t)

    def check_init_node_for_type(self, node: InitNode, t: TypeNode) -> bool:
        if isinstance(node, InitList):
            return self.check_init_list_for_type(node, t)

        if isinstance(node, InitMember):
            return self.check_init_member_for_type(node, t)

        if isinstance(node, InitIndex):
            return self.check_init_index_for_type(node, t)

        assert False

    def check_init_member_for_type(self, node: InitMember, t: TypeNode) -> bool:
        t_base = self.unqual(t)

        if isinstance(t_base, (TypeDefType, TypeOfType, TypeOfUnqualType, AtomicType)):
            return True

        if isinstance(t_base, StructType):
            member = self.struct_member_by_name(t_base, node.member_iden)
            if member is None:
                return True  # Opaque / incomplete struct — skip.

            member_t = member.var_type

            if node.rec_init is not None:
                return self.check_init_node_for_type(node.rec_init, member_t)

            if node.expr_or_init is not None:
                return self.check_init_elem_for_type(node.expr_or_init, member_t)

            return True

        if isinstance(t_base, UnionType):
            member = self.union_member_by_name(t_base, node.member_iden)
            if member is None:
                return True

            member_t = member.var_type

            if node.rec_init is not None:
                return self.check_init_node_for_type(node.rec_init, member_t)

            if node.expr_or_init is not None:
                return self.check_init_elem_for_type(node.expr_or_init, member_t)

            return True

        # Member designator on a non-aggregate — skip to avoid false positives.
        return True

    def check_init_index_for_type(self, node: InitIndex, t: TypeNode) -> bool:
        t_base = self.unqual(t)

        if isinstance(t_base, (TypeDefType, TypeOfType, TypeOfUnqualType, AtomicType)):
            return True

        if isinstance(t_base, ArrayType):
            elem_t = t_base.elem_type

            if node.rec_init is not None:
                return self.check_init_node_for_type(node.rec_init, elem_t)

            if node.expr_or_init is not None:
                return self.check_init_elem_for_type(node.expr_or_init, elem_t)

            return True

        # Index designator on a non-array — skip.
        return True

    def check_init_list_for_type(self, node: InitList, t: TypeNode) -> bool:
        t_base = self.unqual(t)

        if isinstance(t_base, (TypeDefType, TypeOfType, TypeOfUnqualType, AtomicType)):
            return True

        # Scalar type: C23 allows single-element brace-enclosed init (§6.7.9 p11).
        if self.is_arithmetic(t_base) or isinstance(t_base, (PtrType, NullPtrType, BoolType)):
            if len(node.init_elems) == 1:
                elem = node.init_elems[0]
                if isinstance(elem, ExprNode):
                    return self.check_expr_for_type(elem, t)
            return True

        # Array type.
        if isinstance(t_base, ArrayType):
            elem_t = t_base.elem_type

            for elem in node.init_elems:
                if isinstance(elem, InitIndex):
                    if not self.check_init_index_for_type(elem, t_base):
                        return False
                elif isinstance(elem, ExprNode):
                    # Single string literal initializes the whole array (§6.7.9 p14).
                    if isinstance(elem, StrLitExpr) and len(node.init_elems) == 1:
                        if not self.str_lit_fits_array(elem, t_base):
                            self.error = Error()
                            return False
                    else:
                        if not self.check_expr_for_type(elem, elem_t):
                            return False
                else:
                    if not self.check_init_elem_for_type(elem, elem_t):
                        return False

            return True

        # Struct type.
        if isinstance(t_base, StructType):
            members = self.struct_members(t_base)
            pos = 0

            for elem in node.init_elems:
                if isinstance(elem, InitMember):
                    if not self.check_init_member_for_type(elem, t_base):
                        return False
                    # Advance positional cursor past the designated member.
                    for i, m in enumerate(members):
                        if m.iden == elem.member_iden:
                            pos = i + 1
                            break
                elif isinstance(elem, ExprNode):
                    if pos < len(members):
                        if not self.check_expr_for_type(elem, members[pos].var_type):
                            return False
                        pos += 1
                else:
                    if pos < len(members):
                        if not self.check_init_elem_for_type(elem, members[pos].var_type):
                            return False
                        pos += 1

            return True

        # Union type: first or designated member.
        if isinstance(t_base, UnionType):
            for elem in node.init_elems:
                if isinstance(elem, InitMember):
                    if not self.check_init_member_for_type(elem, t_base):
                        return False
                else:
                    first = self.union_first_member(t_base)
                    if first is not None:
                        if not self.check_init_elem_for_type(elem, first.var_type):
                            return False
                # Only the first initializer matters for a union.
                break

            return True

        return True

    def check_var_decl(self, node: VarDecl) -> bool:
        if node.init is None:
            return True

        t = node.var_type

        if isinstance(node.init, ExprNode):
            return self.check_expr_for_type(node.init, t)

        return self.check_init_list_for_type(node.init, t)

    # Scope maintenance.
    def register_var_decl(self, node: VarDecl) -> None:
        self.declare(node.iden, node.var_type)

    def register_enum_decl(self, node: EnumDecl) -> None:
        base = _unwrap_enum(node)
        if base is None or base.members is None:
            return
        for member in base.members:
            self.declare(member.iden, node.enum_type)

    # Statements.
    def stmt(self, node: StmtNode) -> bool:
        if isinstance(node, DeclStmt):
            return self.decl_stmt(node)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, (ExprStmt, ReturnStmt, AssertStmt, PrintLnStmt,
                             CaseLabelStmt, GotoStmt, LabelStmt,
                             BreakStmt, ContinueStmt)):
            return True

        assert False

    def decl_stmt(self, node: DeclStmt) -> bool:
        if isinstance(node.decl, VarDecl):
            if not self.check_var_decl(node.decl):
                return False
            self.register_var_decl(node.decl)

        elif isinstance(node.decl, EnumDecl):
            self.register_enum_decl(node.decl)

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        self.scope_push()

        for stmt_node in node.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.stmt(node.then_stmt):
            return False

        if node.else_stmt is not None:
            if not self.stmt(node.else_stmt):
                return False

        return True

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.stmt(node.then_stmt)

    def for_stmt(self, node: ForStmt) -> bool:
        self.scope_push()

        if isinstance(node.init_clause, VarDecl):
            if not self.check_var_decl(node.init_clause):
                return False
            self.register_var_decl(node.init_clause)

        if not self.stmt(node.then_stmt):
            return False

        self.scope_pop()
        return True

    def while_stmt(self, node: WhileStmt) -> bool:
        return self.stmt(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.stmt(node.do_stmt)

    def fun_decl(self, node: FunDecl) -> bool:
        if node.body is None:
            return True

        # Params and function body share one scope (C §6.2.1).
        self.scope_push()

        for param in node.fun_type.params:
            if param.iden is not None:
                self.declare(param.iden, param.param_type)

        for stmt_node in node.body.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        self.scope_push()

        # First pass: register all file-scope names so that type_of can
        # resolve identifiers when checking file-scope initializers.
        for decl in ast.root.decls:
            if isinstance(decl, VarDecl):
                self.declare(decl.iden, decl.var_type)

            elif isinstance(decl, FunDecl):
                self.declare(decl.iden, decl.fun_type)

            elif isinstance(decl, EnumDecl):
                self.register_enum_decl(decl)

        # Second pass: check file-scope initializers and function bodies.
        for decl in ast.root.decls:
            if isinstance(decl, VarDecl):
                if not self.check_var_decl(decl):
                    assert self.error is not None
                    return self.error

            elif isinstance(decl, FunDecl):
                if not self.fun_decl(decl):
                    assert self.error is not None
                    return self.error

        self.scope_pop()
        return None


####

# Const Assignment Analysis
# Verifies the following constraints:
# - Variables declared with the `const` qualifier may not appear as the
#   lvalue of any assignment expression after their initialization.
# - Variables declared with `constexpr` storage are treated identically,
#   since `constexpr` implies `const` in C23.
# - Function parameters qualified with `const` are also protected.
# The check covers all binary assignment operators (=, +=, -=, …) and
# prefix/postfix increment/decrement.  For member-access and subscript
# lvalues the root identifier is walked to determine the base object;
# pointer-dereference lvalues are skipped to avoid false positives
# (checking pointee-constness requires full type propagation).
class Analysis13:
    def __init__(self) -> None:
        self.const_names: list[set[str]] = []
        self.error: None | Error = None

    def scope_push(self) -> None:
        self.const_names.append(set())

    def scope_pop(self) -> None:
        self.const_names.pop()

    def declare_const(self, name: str) -> None:
        self.const_names[-1].add(name)

    def is_const(self, name: str) -> bool:
        for scope in reversed(self.const_names):
            if name in scope:
                return True
        return False

    def is_const_decl(self, node: VarDecl) -> bool:
        t = node.var_type
        if isinstance(t, QualifiedType):
            if TypeQualifier.const in t.qualifiers:
                return True
            if t.storage == StorageSpec.constexpr:
                return True
        return False

    # Walk member-access / subscript chains to find the root identifier.
    def lvalue_root(self, expr: ExprNode) -> str | None:
        if isinstance(expr, IdenExpr):
            return expr.iden
        if isinstance(expr, MemberExpr):
            return self.lvalue_root(expr.base_expr)
        if isinstance(expr, ArraySubExpr):
            return self.lvalue_root(expr.base_expr)
        return None  # Pointer dereference or other complex lvalue — skip.

    def check_lvalue(self, expr: ExprNode) -> bool:
        root = self.lvalue_root(expr)
        if root is not None and self.is_const(root):
            self.error = Error()
            return False
        return True

    # Expression visitor — recurses into every sub-expression so that
    # nested assignments (e.g. f(x++, y = 0)) are caught.
    def check_expr(self, node: ExprNode) -> bool:
        if isinstance(node, (NullPtrLitExpr, BoolLitExpr, IntLitExpr,
                             RealFloatLitExpr, DecFloatLitExpr,
                             CharLitExpr, StrLitExpr, AlignOfExpr)):
            return True

        if isinstance(node, IdenExpr):
            return True

        if isinstance(node, SizeOfExpr):
            if isinstance(node.expr_or_type, ExprNode):
                return self.check_expr(node.expr_or_type)
            return True

        if isinstance(node, GenericSelExpr):
            return self.check_generic_sel_expr(node)

        if isinstance(node, ArraySubExpr):
            return self.check_expr(node.base_expr) and self.check_expr(node.idx_expr)

        if isinstance(node, CallExpr):
            return self.check_call_expr(node)

        if isinstance(node, MemberExpr):
            return self.check_expr(node.base_expr)

        if isinstance(node, CompoundLitExpr):
            return self.check_init_list(node.init)

        if isinstance(node, CastExpr):
            return self.check_expr(node.expr)

        if isinstance(node, OpExpr):
            return self.check_op_expr(node)

        if isinstance(node, CondExpr):
            return (self.check_expr(node.cond_expr) and
                    self.check_expr(node.true_expr) and
                    self.check_expr(node.false_expr))

        if isinstance(node, CommaExpr):
            fst, snd = node.exprs
            return self.check_expr(fst) and self.check_expr(snd)

        assert False

    def check_generic_sel_expr(self, node: GenericSelExpr) -> bool:
        if not self.check_expr(node.ctrl_expr):
            return False

        for case_expr in node.assoc_table.values():
            if not self.check_expr(case_expr):
                return False

        return True

    def check_call_expr(self, node: CallExpr) -> bool:
        if not self.check_expr(node.callee_expr):
            return False

        for arg in node.arg_exprs:
            if not self.check_expr(arg):
                return False

        return True

    def check_op_expr(self, node: OpExpr) -> bool:
        if isinstance(node.op, BinOpTag):
            if node.op in (BinOpTag.assign,
                           BinOpTag.mul_assign, BinOpTag.div_assign,
                           BinOpTag.mod_assign,
                           BinOpTag.add_assign, BinOpTag.sub_assign,
                           BinOpTag.shl_assign, BinOpTag.shr_assign,
                           BinOpTag.bit_and_assign, BinOpTag.bit_xor_assign,
                           BinOpTag.bit_or_assign):
                if not self.check_lvalue(node.exprs[0]):
                    return False
                return self.check_expr(node.exprs[0]) and self.check_expr(node.exprs[1])

        if isinstance(node.op, UnaPrefOpTag):
            if node.op in (UnaPrefOpTag.prefix_inc, UnaPrefOpTag.prefix_dec):
                if not self.check_lvalue(node.exprs[0]):
                    return False
                return self.check_expr(node.exprs[0])

        if isinstance(node.op, UnaPostOpTag):
            if node.op in (UnaPostOpTag.postfix_inc, UnaPostOpTag.postfix_dec):
                if not self.check_lvalue(node.exprs[0]):
                    return False
                return self.check_expr(node.exprs[0])

        for child in node.exprs:
            if not self.check_expr(child):
                return False

        return True

    # Initializer visitor — needed to catch assignments inside compound
    # literal initializers (e.g. (S){.x = (y++, 0)}).
    def check_init_list(self, node: InitList) -> bool:
        for elem in node.init_elems:
            if isinstance(elem, ExprNode):
                if not self.check_expr(elem):
                    return False
            else:
                if not self.check_init_node(elem):
                    return False

        return True

    def check_init_node(self, node: InitNode) -> bool:
        if isinstance(node, InitMember):
            if node.rec_init is not None:
                return self.check_init_node(node.rec_init)

            if node.expr_or_init is not None:
                if isinstance(node.expr_or_init, ExprNode):
                    return self.check_expr(node.expr_or_init)
                return self.check_init_node(node.expr_or_init)

            return True

        if isinstance(node, InitIndex):
            if not self.check_expr(node.idx_expr):
                return False

            if node.rec_init is not None:
                return self.check_init_node(node.rec_init)

            if node.expr_or_init is not None:
                if isinstance(node.expr_or_init, ExprNode):
                    return self.check_expr(node.expr_or_init)
                return self.check_init_node(node.expr_or_init)

            return True

        if isinstance(node, InitList):
            return self.check_init_list(node)

        assert False

    # Statements.
    def stmt(self, node: StmtNode) -> bool:
        if isinstance(node, DeclStmt):
            return self.decl_stmt(node)

        if isinstance(node, ExprStmt):
            return self.check_expr(node.expr)

        if isinstance(node, AssertStmt):
            return self.assert_stmt(node)

        if isinstance(node, PrintLnStmt):
            return self.println_stmt(node)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, CaseLabelStmt):
            return self.case_label_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, ReturnStmt):
            return self.return_stmt(node)

        if isinstance(node, (GotoStmt, LabelStmt, BreakStmt, ContinueStmt)):
            return True

        assert False

    def decl_stmt(self, node: DeclStmt) -> bool:
        if isinstance(node.decl, VarDecl):
            return self.var_decl(node.decl)

        return True

    def var_decl(self, node: VarDecl) -> bool:
        # Check the initializer expression before registering the name so
        # that `const int x = (x = 5)` style self-reference is still caught
        # by whichever prior declaration of x is in scope.
        if node.init is not None:
            if isinstance(node.init, ExprNode):
                if not self.check_expr(node.init):
                    return False
            else:
                if not self.check_init_list(node.init):
                    return False

        if self.is_const_decl(node):
            self.declare_const(node.iden)

        return True

    def assert_stmt(self, node: AssertStmt) -> bool:
        if not self.check_expr(node.cond_expr):
            return False

        for arg in node.arg_exprs:
            if not self.check_expr(arg):
                return False

        return True

    def println_stmt(self, node: PrintLnStmt) -> bool:
        for arg in node.arg_exprs:
            if not self.check_expr(arg):
                return False

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        self.scope_push()

        for stmt_node in node.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.check_expr(node.cond_expr):
            return False

        if not self.stmt(node.then_stmt):
            return False

        if node.else_stmt is not None:
            if not self.stmt(node.else_stmt):
                return False

        return True

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.check_expr(node.cond_expr) and self.stmt(node.then_stmt)

    def case_label_stmt(self, node: CaseLabelStmt) -> bool:
        if node.cond_expr is not None:
            return self.check_expr(node.cond_expr)

        return True

    def for_stmt(self, node: ForStmt) -> bool:
        self.scope_push()

        if isinstance(node.init_clause, ExprNode):
            if not self.check_expr(node.init_clause):
                return False
        elif isinstance(node.init_clause, VarDecl):
            if not self.var_decl(node.init_clause):
                return False

        if node.cond_expr is not None:
            if not self.check_expr(node.cond_expr):
                return False

        if node.inc_expr is not None:
            if not self.check_expr(node.inc_expr):
                return False

        if not self.stmt(node.then_stmt):
            return False

        self.scope_pop()
        return True

    def while_stmt(self, node: WhileStmt) -> bool:
        return self.check_expr(node.cond_expr) and self.stmt(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.stmt(node.do_stmt) and self.check_expr(node.cond_expr)

    def return_stmt(self, node: ReturnStmt) -> bool:
        if node.ret_expr is not None:
            return self.check_expr(node.ret_expr)

        return True

    def fun_decl(self, node: FunDecl) -> bool:
        if node.body is None:
            return True

        self.scope_push()

        for param in node.fun_type.params:
            if param.iden is None:
                continue

            param_t = param.param_type
            if isinstance(param_t, QualifiedType):
                if TypeQualifier.const in param_t.qualifiers:
                    self.declare_const(param.iden)

        for stmt_node in node.body.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        self.scope_push()

        # Register file-scope const/constexpr variables first so that
        # any function body that assigns to a file-scope const is caught.
        for decl in ast.root.decls:
            if isinstance(decl, VarDecl):
                if self.is_const_decl(decl):
                    self.declare_const(decl.iden)

        for decl in ast.root.decls:
            if isinstance(decl, FunDecl):
                if not self.fun_decl(decl):
                    assert self.error is not None
                    return self.error

        self.scope_pop()
        return None


# Operator and Expression Type Analysis
# Validates that all operations are performed on types where those
# operations are valid according to C23:
#
# Unary prefix operators:
#   - Bitwise NOT (~) : integer operand required.
#   - Unary + / -     : arithmetic operand required.
#   - ++ / --         : arithmetic or pointer operand required.
#   - !               : scalar operand required.
#   - * (deref)       : pointer operand required.
#
# Binary operators:
#   - Bitwise (&, |, ^, <<, >>) and %: integer operands required.
#   - * and /         : arithmetic operands required (no pointer multiply).
#   - + and -         : arithmetic or valid pointer arithmetic only.
#   - Compound +=/-=  : arithmetic rhs, or integer rhs for pointer lhs.
#   - &&, ||          : scalar operands required.
#   - = (assignment)  : rhs must be implicitly convertible to lhs type
#                       under C23 §6.5.16.1 simple-assignment rules.
#
# Subscript expressions (a[i]):
#   - One operand must be a pointer or array; the other must be integer.
#
# Member access:
#   - .  requires the base to be a struct or union type.
#   - -> requires the base to be a pointer to struct or union.
#
# Function calls:
#   - Argument count must match for non-variadic functions.
#   - Each argument must be implicitly convertible to the parameter type.
#
# Conditional expressions (?:):
#   - Both branches must have mutually compatible types.
#
# C23 specifics:
#   - nullptr (NullPtrType) may not be used in arithmetic operations.
#   - bool, char, _BitInt, and enum are treated as integer types for
#     operator constraint purposes.
class Analysis14(_TypeCheckBase):
    def __init__(self) -> None:
        super().__init__()
        self.error: None | Error = None

    # Resolve the FunType of a call expression's callee so that argument
    # count and types can be verified.
    def callee_fun_type(self, node: CallExpr) -> FunType | None:
        callee_t = self.type_of(node.callee_expr)
        if callee_t is None:
            return None

        callee_t = self.unqual(callee_t)

        if isinstance(callee_t, FunType):
            return callee_t

        if isinstance(callee_t, PtrType):
            inner = self.unqual(callee_t.pointee)
            if isinstance(inner, FunType):
                return inner

        return None

    # --- Expression-level type checkers ---

    def check_unary_prefix(self, node: OpExpr) -> bool:
        op = node.op
        assert isinstance(op, UnaPrefOpTag)
        operand = node.exprs[0]

        if not self.check_expr(operand):
            return False

        t = self.type_of(operand)
        if t is None or self.is_unresolved(t):
            return True

        if op == UnaPrefOpTag.bit_neg:
            if not self.is_integer(t):
                self.error = Error()
                return False

        elif op in (UnaPrefOpTag.plus, UnaPrefOpTag.neg):
            if not self.is_arithmetic(t):
                self.error = Error()
                return False

        elif op in (UnaPrefOpTag.prefix_inc, UnaPrefOpTag.prefix_dec):
            if not (self.is_arithmetic(t) or self.is_pointer(t)):
                self.error = Error()
                return False

        elif op == UnaPrefOpTag.bool_neg:
            if not self.is_scalar(t):
                self.error = Error()
                return False

        elif op == UnaPrefOpTag.deref:
            if not isinstance(self.unqual(t), (PtrType, ArrayType)):
                self.error = Error()
                return False

        # addr_of: any lvalue is valid — no type constraint.

        return True

    def check_unary_postfix(self, node: OpExpr) -> bool:
        op = node.op
        assert isinstance(op, UnaPostOpTag)
        operand = node.exprs[0]

        if not self.check_expr(operand):
            return False

        t = self.type_of(operand)
        if t is None or self.is_unresolved(t):
            return True

        if op in (UnaPostOpTag.postfix_inc, UnaPostOpTag.postfix_dec):
            if not (self.is_arithmetic(t) or self.is_pointer(t)):
                self.error = Error()
                return False

        return True

    def check_binary(self, node: OpExpr) -> bool:
        op = node.op
        assert isinstance(op, BinOpTag)
        lhs_expr, rhs_expr = node.exprs[0], node.exprs[1]

        if not self.check_expr(lhs_expr) or not self.check_expr(rhs_expr):
            return False

        lt = self.type_of(lhs_expr)
        rt = self.type_of(rhs_expr)

        if lt is None or rt is None:
            return True

        if self.is_unresolved(lt) or self.is_unresolved(rt):
            return True

        lt_base = self.unqual(lt)
        rt_base = self.unqual(rt)

        # Bitwise operators: both operands must be integer.
        if op in (BinOpTag.bit_and, BinOpTag.bit_or, BinOpTag.bit_xor,
                  BinOpTag.shl, BinOpTag.shr):
            if not self.is_integer(lt) or not self.is_integer(rt):
                self.error = Error()
                return False

        # Compound bitwise assignments: both operands must be integer.
        elif op in (BinOpTag.shl_assign, BinOpTag.shr_assign,
                    BinOpTag.bit_and_assign, BinOpTag.bit_xor_assign,
                    BinOpTag.bit_or_assign):
            if not self.is_integer(lt) or not self.is_integer(rt):
                self.error = Error()
                return False

        # Modulo and modulo-assign: integer only.
        elif op in (BinOpTag.mod, BinOpTag.mod_assign):
            if not self.is_integer(lt) or not self.is_integer(rt):
                self.error = Error()
                return False

        # Multiplication and division: arithmetic only (pointer not allowed).
        elif op in (BinOpTag.mul, BinOpTag.div):
            if not self.is_arithmetic(lt) or not self.is_arithmetic(rt):
                self.error = Error()
                return False

        # Compound multiply/divide: rhs must be arithmetic.
        elif op in (BinOpTag.mul_assign, BinOpTag.div_assign):
            if not self.is_arithmetic(lt) or not self.is_arithmetic(rt):
                self.error = Error()
                return False

        # Addition: arithmetic+arithmetic, or pointer±integer (§6.5.6).
        elif op == BinOpTag.add:
            lhs_is_ptr = isinstance(lt_base, PtrType)
            rhs_is_ptr = isinstance(rt_base, PtrType)
            if lhs_is_ptr:
                if not self.is_integer(rt):
                    self.error = Error()
                    return False
            elif rhs_is_ptr:
                if not self.is_integer(lt):
                    self.error = Error()
                    return False
            elif not (self.is_arithmetic(lt) and self.is_arithmetic(rt)):
                self.error = Error()
                return False

        # Compound add-assign: pointer += integer, or arithmetic += arithmetic.
        elif op == BinOpTag.add_assign:
            if isinstance(lt_base, PtrType):
                if not self.is_integer(rt):
                    self.error = Error()
                    return False
            elif not self.is_arithmetic(rt):
                self.error = Error()
                return False

        # Subtraction: arithmetic-arithmetic, pointer-integer, or
        # pointer-pointer of the same type (§6.5.6).
        elif op == BinOpTag.sub:
            lhs_is_ptr = isinstance(lt_base, PtrType)
            rhs_is_ptr = isinstance(rt_base, PtrType)
            if lhs_is_ptr:
                if not (self.is_integer(rt) or rhs_is_ptr):
                    self.error = Error()
                    return False
            elif not (self.is_arithmetic(lt) and self.is_arithmetic(rt)):
                self.error = Error()
                return False

        # Compound sub-assign: pointer -= integer, or arithmetic -= arithmetic.
        elif op == BinOpTag.sub_assign:
            if isinstance(lt_base, PtrType):
                if not self.is_integer(rt):
                    self.error = Error()
                    return False
            elif not self.is_arithmetic(rt):
                self.error = Error()
                return False

        # Logical operators: both operands must be scalar.
        elif op in (BinOpTag.bool_and, BinOpTag.bool_or):
            if not self.is_scalar(lt) or not self.is_scalar(rt):
                self.error = Error()
                return False

        # Simple assignment: rhs must be convertible to lhs (§6.5.16.1).
        elif op == BinOpTag.assign:
            if not self.is_convertible(rt, lt):
                self.error = Error()
                return False

        return True

    def check_array_sub_expr(self, node: ArraySubExpr) -> bool:
        if not self.check_expr(node.base_expr) or not self.check_expr(node.idx_expr):
            return False

        base_t = self.type_of(node.base_expr)
        idx_t  = self.type_of(node.idx_expr)

        if base_t is None or idx_t is None:
            return True

        if self.is_unresolved(base_t) or self.is_unresolved(idx_t):
            return True

        base_base = self.unqual(base_t)
        idx_base  = self.unqual(idx_t)

        # One operand must be a pointer/array; the other must be integer (§6.5.2.1).
        if isinstance(base_base, (PtrType, ArrayType)):
            if not self.is_integer(idx_t):
                self.error = Error()
                return False
        elif isinstance(idx_base, (PtrType, ArrayType)):
            if not self.is_integer(base_t):
                self.error = Error()
                return False
        else:
            self.error = Error()
            return False

        return True

    def check_member_expr(self, node: MemberExpr) -> bool:
        if not self.check_expr(node.base_expr):
            return False

        base_t = self.type_of(node.base_expr)
        if base_t is None:
            return True

        if self.is_unresolved(base_t):
            return True

        base_base = self.unqual(base_t)

        if node.is_arrow:
            # -> requires pointer to struct or union (§6.5.2.3).
            if not isinstance(base_base, PtrType):
                self.error = Error()
                return False
            pointee = self.unqual(base_base.pointee)
            if not isinstance(pointee, (StructType, UnionType,
                                        TypeDefType, TypeOfType,
                                        TypeOfUnqualType, AtomicType)):
                self.error = Error()
                return False
        else:
            # . requires struct or union directly (§6.5.2.3).
            if not isinstance(base_base, (StructType, UnionType,
                                          TypeDefType, TypeOfType,
                                          TypeOfUnqualType, AtomicType)):
                self.error = Error()
                return False

        return True

    def check_call_expr(self, node: CallExpr) -> bool:
        if not self.check_expr(node.callee_expr):
            return False

        for arg in node.arg_exprs:
            if not self.check_expr(arg):
                return False

        fun_t = self.callee_fun_type(node)
        if fun_t is None:
            return True

        # Argument count: exact match for non-variadic, at-least for variadic.
        if not fun_t.is_variadic:
            if len(node.arg_exprs) != len(fun_t.params):
                self.error = Error()
                return False
        else:
            if len(node.arg_exprs) < len(fun_t.params):
                self.error = Error()
                return False

        # Argument type compatibility (§6.5.2.2).
        for arg, param in zip(node.arg_exprs, fun_t.params):
            arg_t = self.type_of(arg)
            if arg_t is None:
                continue
            if self.is_unresolved(arg_t) or self.is_unresolved(param.param_type):
                continue
            if not self.is_convertible(arg_t, param.param_type):
                self.error = Error()
                return False

        return True

    def check_cond_expr(self, node: CondExpr) -> bool:
        if not self.check_expr(node.cond_expr):
            return False
        if not self.check_expr(node.true_expr):
            return False
        if not self.check_expr(node.false_expr):
            return False

        # Condition must be scalar (§6.5.15).
        cond_t = self.type_of(node.cond_expr)
        if cond_t is not None and not self.is_unresolved(cond_t):
            if not self.is_scalar(cond_t):
                self.error = Error()
                return False

        true_t  = self.type_of(node.true_expr)
        false_t = self.type_of(node.false_expr)

        if true_t is None or false_t is None:
            return True

        if self.is_unresolved(true_t) or self.is_unresolved(false_t):
            return True

        true_base  = self.unqual(true_t)
        false_base = self.unqual(false_t)

        # Both void — valid (expression has type void).
        if isinstance(true_base, VoidType) and isinstance(false_base, VoidType):
            return True

        # Both branches must produce mutually compatible types (§6.5.15).
        if not (self.is_convertible(true_t, false_t) or
                self.is_convertible(false_t, true_t)):
            self.error = Error()
            return False

        return True

    def check_init_list(self, node: InitList) -> bool:
        for elem in node.init_elems:
            if isinstance(elem, ExprNode):
                if not self.check_expr(elem):
                    return False
            else:
                if not self.check_init_node(elem):
                    return False
        return True

    def check_init_node(self, node: InitNode) -> bool:
        if isinstance(node, InitList):
            return self.check_init_list(node)

        if isinstance(node, InitMember):
            if node.rec_init is not None:
                return self.check_init_node(node.rec_init)
            if node.expr_or_init is not None:
                if isinstance(node.expr_or_init, ExprNode):
                    return self.check_expr(node.expr_or_init)
                return self.check_init_node(node.expr_or_init)
            return True

        if isinstance(node, InitIndex):
            if not self.check_expr(node.idx_expr):
                return False
            if node.rec_init is not None:
                return self.check_init_node(node.rec_init)
            if node.expr_or_init is not None:
                if isinstance(node.expr_or_init, ExprNode):
                    return self.check_expr(node.expr_or_init)
                return self.check_init_node(node.expr_or_init)
            return True

        assert False

    def check_expr(self, node: ExprNode) -> bool:
        if isinstance(node, LITERAL_EXPRS):
            return True

        if isinstance(node, IdenExpr):
            return True

        if isinstance(node, AlignOfExpr):
            return True

        if isinstance(node, SizeOfExpr):
            if isinstance(node.expr_or_type, ExprNode):
                return self.check_expr(node.expr_or_type)
            return True

        if isinstance(node, GenericSelExpr):
            if not self.check_expr(node.ctrl_expr):
                return False
            for case_expr in node.assoc_table.values():
                if not self.check_expr(case_expr):
                    return False
            return True

        if isinstance(node, ArraySubExpr):
            return self.check_array_sub_expr(node)

        if isinstance(node, CallExpr):
            return self.check_call_expr(node)

        if isinstance(node, MemberExpr):
            return self.check_member_expr(node)

        if isinstance(node, CompoundLitExpr):
            return self.check_init_list(node.init)

        if isinstance(node, CastExpr):
            return self.check_expr(node.expr)

        if isinstance(node, OpExpr):
            if isinstance(node.op, UnaPrefOpTag):
                return self.check_unary_prefix(node)
            if isinstance(node.op, UnaPostOpTag):
                return self.check_unary_postfix(node)
            if isinstance(node.op, BinOpTag):
                return self.check_binary(node)
            assert False

        if isinstance(node, CondExpr):
            return self.check_cond_expr(node)

        if isinstance(node, CommaExpr):
            fst, snd = node.exprs
            return self.check_expr(fst) and self.check_expr(snd)

        assert False

    # --- Scope maintenance ---

    def var_decl(self, node: VarDecl) -> None:
        self.declare(node.iden, node.var_type)

    def enum_decl(self, node: EnumDecl) -> None:
        base = _unwrap_enum(node)
        if base is None or base.members is None:
            return
        for member in base.members:
            self.declare(member.iden, node.enum_type)

    # --- Statement traversal ---

    def stmt(self, node: StmtNode) -> bool:
        if isinstance(node, ExprStmt):
            return self.check_expr(node.expr)

        if isinstance(node, DeclStmt):
            return self.decl_stmt(node)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, CaseLabelStmt):
            if node.cond_expr is not None:
                return self.check_expr(node.cond_expr)
            return True

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, ReturnStmt):
            if node.ret_expr is not None:
                return self.check_expr(node.ret_expr)
            return True

        if isinstance(node, AssertStmt):
            return self.assert_stmt(node)

        if isinstance(node, PrintLnStmt):
            return self.println_stmt(node)

        if isinstance(node, (GotoStmt, LabelStmt, BreakStmt, ContinueStmt)):
            return True

        assert False

    def decl_stmt(self, node: DeclStmt) -> bool:
        if isinstance(node.decl, VarDecl):
            decl = node.decl
            if decl.init is not None:
                init = decl.init
                if isinstance(init, ExprNode):
                    if not self.check_expr(init):
                        return False
                else:
                    if not self.check_init_list(init):
                        return False
            self.var_decl(decl)

        elif isinstance(node.decl, EnumDecl):
            self.enum_decl(node.decl)

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        self.scope_push()

        for stmt_node in node.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.check_expr(node.cond_expr):
            return False

        if not self.stmt(node.then_stmt):
            return False

        if node.else_stmt is not None:
            if not self.stmt(node.else_stmt):
                return False

        return True

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.check_expr(node.cond_expr) and self.stmt(node.then_stmt)

    def for_stmt(self, node: ForStmt) -> bool:
        self.scope_push()

        if isinstance(node.init_clause, ExprNode):
            if not self.check_expr(node.init_clause):
                return False

        elif isinstance(node.init_clause, VarDecl):
            decl = node.init_clause
            if decl.init is not None:
                init = decl.init
                if isinstance(init, ExprNode):
                    if not self.check_expr(init):
                        return False
                else:
                    if not self.check_init_list(init):
                        return False
            self.var_decl(decl)

        if node.cond_expr is not None:
            if not self.check_expr(node.cond_expr):
                return False

        if node.inc_expr is not None:
            if not self.check_expr(node.inc_expr):
                return False

        if not self.stmt(node.then_stmt):
            return False

        self.scope_pop()
        return True

    def while_stmt(self, node: WhileStmt) -> bool:
        return self.check_expr(node.cond_expr) and self.stmt(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.stmt(node.do_stmt) and self.check_expr(node.cond_expr)

    def assert_stmt(self, node: AssertStmt) -> bool:
        if not self.check_expr(node.cond_expr):
            return False

        for arg in node.arg_exprs:
            if not self.check_expr(arg):
                return False

        return True

    def println_stmt(self, node: PrintLnStmt) -> bool:
        for arg in node.arg_exprs:
            if not self.check_expr(arg):
                return False

        return True

    def fun_decl(self, node: FunDecl) -> bool:
        if node.body is None:
            return True

        self.scope_push()

        for param in node.fun_type.params:
            if param.iden is not None:
                self.declare(param.iden, param.param_type)

        for stmt_node in node.body.stmts:
            if not self.stmt(stmt_node):
                return False

        self.scope_pop()
        return True

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        self.scope_push()

        # First pass: register all file-scope names so that function bodies
        # can reference globals and each other freely.
        for decl in ast.root.decls:
            if isinstance(decl, VarDecl):
                self.declare(decl.iden, decl.var_type)

            elif isinstance(decl, FunDecl):
                self.declare(decl.iden, decl.fun_type)

            elif isinstance(decl, EnumDecl):
                self.enum_decl(decl)

        # Second pass: check all function bodies.
        for decl in ast.root.decls:
            if isinstance(decl, FunDecl):
                if not self.fun_decl(decl):
                    assert self.error is not None
                    return self.error

        self.scope_pop()
        return None

####


# Goals of Static Analysis
# 1. Verify that each typedef has already declared type.
# 2. Verify that each identifier in expression has declaration
#    before-hand in the given scope.
# 3. Verify that each function have proper type when returning, that
#    means type that can be implicitly converted to the right type.
# 4. Verify that each constexpr is made only from compile time
#    expressions.
# 5. Verify that there are no invalid void declaration.
# 6. Verify that each initialization is proper to it's type.
# 7. Verify that each assignment is with it's proper type or something
#    that can be converted.
# 8. Verify that CondExpr is resulting the same type in both expression
#    branches.
# 9. Verify that there is no assignment to const unless initialization.

# 10. Dots and arrows are only under pointers that are structs or unions.
# 11. bit int has const expr, case has const expr
# something something maybe implicit casts


def test() -> None:
    pass


if __name__ == "__main__":
    test()
