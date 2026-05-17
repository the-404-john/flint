from error import *
from limits import *

from flint_ast import *

# NOTE: The whole file has to be reworked, because it's all garbage.
# Also I have type convertor in convert.py, but it's handling
# the runtime objects, so maybe it's fine, but there has to be some
# duplicity. I should just burn it all and start again \o/.

SIZE_T = IntType(IntKind.long_long, SignKind.unsigned)

FLOAT_RANK: dict[RealFloatKind, int] = {
    RealFloatKind.float: 1,
    RealFloatKind.double: 2,
    RealFloatKind.long_double: 3,
}

DEC_RANK: dict[DecimalFloatKind, int] = {
    DecimalFloatKind.decimal32: 1,
    DecimalFloatKind.decimal64: 2,
    DecimalFloatKind.decimal128: 3,
}

INT_RANK: dict[IntKind, int] = {
    IntKind.int: 1,
    IntKind.long: 2,
    IntKind.long_long: 3,
}

ASSIGN_OPS: set[BinOpTag] = {
    BinOpTag.assign, BinOpTag.mul_assign, BinOpTag.div_assign,
    BinOpTag.mod_assign, BinOpTag.add_assign, BinOpTag.sub_assign,
    BinOpTag.shl_assign, BinOpTag.shr_assign, BinOpTag.bit_and_assign,
    BinOpTag.bit_xor_assign, BinOpTag.bit_or_assign,
}

CMP_OPS: set[BinOpTag] = {
    BinOpTag.lt, BinOpTag.gt, BinOpTag.le, BinOpTag.ge,
    BinOpTag.eq, BinOpTag.ne, BinOpTag.bool_and, BinOpTag.bool_or,
}


class TypeScope:
    def __init__(self) -> None:
        self.frames: list[dict[str, TypeNode]] = [{}]

    def push(self) -> None:
        self.frames.append({})

    def pop(self) -> None:
        self.frames.pop()

    def define(self, name: str, node: TypeNode) -> None:
        self.frames[-1][name] = node

    def lookup(self, name: str) -> TypeNode | None:
        for i in range(len(self.frames) - 1, -1, -1):
            frame = self.frames[i]

            if name in frame:
                return frame[name]

        return None


class TagScope:
    def __init__(self) -> None:
        self.structs: dict[str, StructType] = {}
        self.unions: dict[str, UnionType] = {}

    def define_struct(self, iden: str, struct_type: StructType) -> None:
        self.structs[iden] = struct_type

    def define_union(self, iden: str, union_type: UnionType) -> None:
        self.unions[iden] = union_type

    def lookup_struct(self, iden: str) -> StructType | None:
        return self.structs.get(iden)

    def lookup_union(self, iden: str) -> UnionType | None:
        return self.unions.get(iden)


class Normalize01:
    def __init__(self) -> None:
        self.typedefs = TypeScope()
        self.type_scope = TypeScope()
        self.tags = TagScope()

    def push_scope(self) -> None:
        self.typedefs.push()
        self.type_scope.push()

    def pop_scope(self) -> None:
        self.type_scope.pop()
        self.typedefs.pop()

    def size_of_bit_int(self, bin_int_type: BitIntType) -> int | Error:
        if isinstance(bin_int_type.width_expr, IntLitExpr):
            return (t.width_expr.int_expr + CHAR_BIT_SIZE - 1) // CHAR_BIT_SIZE

        return Error()

    def _size_of_array(self, t: ArrayType) -> int | Error:
        if t.is_unspec_vla or t.elem_count is None or not isinstance(t.elem_count, IntLitExpr):
            return Error()
        elem_sz = self._size_of(t.elem_type)
        if isinstance(elem_sz, Error):
            return elem_sz
        return elem_sz * t.elem_count.int_expr

    def _size_of_struct(self, t: StructType) -> int | Error:
        if t.members is None:
            if t.iden is not None:
                full = self.tags.lookup_struct(t.iden)
                if full is not None:
                    return self._size_of(full)
            return Error()
        total = 0
        for m in t.members:
            if isinstance(m, VarDecl):
                s = self._size_of(m.var_type)
                if isinstance(s, Error):
                    return s
                total += s
        return total

    def _size_of_union(self, t: UnionType) -> int | Error:
        if t.members is None:
            if t.iden is not None:
                full = self.tags.lookup_union(t.iden)
                if full is not None:
                    return self._size_of(full)
            return Error()
        largest = 0
        for m in t.members:
            if isinstance(m, VarDecl):
                s = self._size_of(m.var_type)
                if isinstance(s, Error):
                    return s
                largest = max(largest, s)
        return largest

    def _size_of(self, t: TypeNode) -> int | Error:
        if isinstance(t, QualifiedType):    return self._size_of(t.base_type)
        if isinstance(t, AtomicType):       return self._size_of(t.base_type)
        if isinstance(t, VoidType):         return Error()
        if isinstance(t, BoolType):         return 1
        if isinstance(t, NullPtrType):      return PTR_SIZE
        if isinstance(t, CharType):         return CHAR_KIND_SIZE[t.kind]
        if isinstance(t, IntType):          return INT_KIND_SIZE[t.kind]
        if isinstance(t, BitIntType):       return self._size_of_bit_int(t)
        if isinstance(t, RealFloatType):    return REAL_FLOAT_KIND_SIZE[t.kind]
        if isinstance(t, DecimalFloatType): return DECIMAL_FLOAT_KIND_SIZE[t.kind]
        if isinstance(t, ComplexType):      return REAL_FLOAT_KIND_SIZE[t.kind] * 2
        if isinstance(t, ImaginaryType):    return REAL_FLOAT_KIND_SIZE[t.kind]
        if isinstance(t, PtrType):          return PTR_SIZE
        if isinstance(t, FunType):          return Error()
        if isinstance(t, ArrayType):        return self._size_of_array(t)
        if isinstance(t, StructType):       return self._size_of_struct(t)
        if isinstance(t, UnionType):        return self._size_of_union(t)
        if isinstance(t, EnumType):
            return self._size_of(t.member_type) if t.member_type is not None else INT_KIND_SIZE[IntKind.int]
        if isinstance(t, TypeDefType):
            resolved = self.typedefs.lookup(t.iden)
            return Error() if resolved is None else self._size_of(resolved)
        if isinstance(t, (TypeOfType, TypeOfUnqualType)):
            inner = self.resolve_typeof(t)
            return Error() if isinstance(inner, Error) else self._size_of(inner)
        return Error()

    def _align_of_tag(self, t: StructType | UnionType) -> int | Error:
        if t.members is None:
            if t.iden is not None:
                full = (self.tags.lookup_struct(t.iden) if isinstance(t, StructType)
                        else self.tags.lookup_union(t.iden))
                if full is not None:
                    return self._align_of(full)
            return Error()
        result = 1
        for m in t.members:
            if isinstance(m, VarDecl):
                a = self._align_of(m.var_type)
                if isinstance(a, Error):
                    return a
                result = max(result, a)
        return result

    def _align_of(self, t: TypeNode) -> int | Error:
        if isinstance(t, QualifiedType):           return self._align_of(t.base_type)
        if isinstance(t, AtomicType):              return self._align_of(t.base_type)
        if isinstance(t, ArrayType):               return self._align_of(t.elem_type)
        if isinstance(t, (StructType, UnionType)): return self._align_of_tag(t)
        if isinstance(t, TypeDefType):
            resolved = self.typedefs.lookup(t.iden)
            return Error() if resolved is None else self._align_of(resolved)
        if isinstance(t, (TypeOfType, TypeOfUnqualType)):
            inner = self.resolve_typeof(t)
            return Error() if isinstance(inner, Error) else self._align_of(inner)
        return self._size_of(t)

    def infer_iden_type(self, node: IdenExpr) -> TypeNode | Error:
        var_type: TypeNode | Error = self.type_scope.lookup(node.iden)

        if var_type is None:
            return Error()

        return var_type

    def infer_nullptr_lit_type(self,
                               node: NullPtrLitExpr) -> TypeNode | Error:
        return NullPtrType()

    def infer_bool_lit_type(self, node: BoolType) -> TypeNode | Error:
        return BoolType()

    def infer_int_lit_type(self, node: IntLitExpr) -> TypeNode | Error:
        return node.int_type

    def infer_float_lit_type(self,
                             node: RealFloatType) -> TypeNode | Error:
        return node.float_type

    def infer_dec_lit_type(self,
                           node: DecimalFloatType) -> TypeNode | Error:
        return node.float_type

    def infer_char_lit_type(self,
                            node: CharLitExpr) -> TypeNode | Error:
        return node.char_type

    def infer_str_lit_type(self,
                           node: StrLitExpr) -> TypeNode | Error:
        return PtrType(node.char_type, set())

    def infer_array_sub_expr_type(self, node: ArraySubExpr) -> TypeNode | Error:
        base_type: TypeNode | Error = self.infer_expr_type(node.base_expr)
        if isinstance(base_type, Error):
            return Error()

        base_base_type = self.base_type(base_type)

        if isinstance(base_base_type, ArrayType):
            return base_base_type.elem_type

        if isinstance(base_base_type, PtrType):
            return base.pointee

        return Error()

    def infer_call_expr_type(self, node: CallExpr) -> TypeNode | Error:
        callee_type: TypeNode | Error = self.infer_expr_type(node.callee_expr)
        if isinstance(callee_t, Error):
            return Error()

        base_type = self.base_type(callee_type)
        if isinstance(base_type, PtrType):
            base_type = self.base_type(base_type.pointee)

        if isinstance(base_type, FunType):
            return base_type.ret_type

        return Error()

    def infer_member_expr_type(self, node: MemberExpr) -> TypeNode | Error:
        base_t = self.infer_expr_type(node.base_expr)
        if isinstance(base_t, Error):
            return Error()
        base = self.base_type(base_t)
        if node.is_arrow:
            if not isinstance(base, PtrType):
                return Error()
            base = self.base_type(base.pointee)
        if isinstance(base, (StructType, UnionType)):
            return self._member_type(base, node.member_iden)
        return Error()

    def infer_expr_type(self, node: ExprNode) -> TypeNode | Error:
        if isinstance(node, IdenExpr):
            return self.infer_iden_type(node)

        if isinstance(node, NullPtrLitExpr):
            return self.infer_nullptr_expr_type(node)

        if isinstance(node, BoolLitExpr):
            return self.infer_bool_lit_type(node)

        if isinstance(node, IntLitExpr):
            return self.infer_int_lit_type(node)

        if isinstance(node, RealFloatLitExpr):
            return self.infer_float_lit_type(node)

        if isinstance(node, DecFloatLitExpr):
            return self.infer_dec_lit_type(node)

        if isinstance(node, CharLitExpr):
            return self.infer_char_lit_type(node)

        if isinstance(node, StrLitExpr):
            return self.infer_str_lit_type(node)

        if isinstance(node, ArraySubExpr):
            return self.infer_array_sub_expr_type(node)

        if isinstance(node, CallExpr):
            return self.infer_call_expr_type(node)

        if isinstance(node, MemberExpr):
            return self.infer_member_expr_type(node)

        if isinstance(node, CompoundLitExpr):
            return node.expr_type

        if isinstance(node, CastExpr):
            return node.expr_type

        if isinstance(node, (SizeOfExpr, AlignOfExpr)):
            return SIZE_T

        if isinstance(node, OpExpr):       return self._infer_op_type(node)
        if isinstance(node, CondExpr):     return self.infer_expr_type(node.true_expr)
        if isinstance(node, CommaExpr):    return self.infer_expr_type(node.exprs[1])

        return Error()

    def expr_or_type(self, node: ExprNode | TypeNode) -> ExprNode | TypeNode:
        if isinstance(node, TypeNode):
            return self.type(node)
        else:
            return self.infer_expr_type(node)

    def resolve_typeof(self, node: TypeOfType | TypeOfUnqualType) -> TypeNode:
        if isinstance(node.expr_or_type, TypeNode):
            resolved = self.type(node.expr_or_type)
        else:
            resolved = self.infer_expr_type(self.expr(node.expr_or_type))
        if isinstance(node, TypeOfUnqualType) and isinstance(resolved, QualifiedType):
            return resolved.base_type
        return resolved

    def base_type(self, node: TypeNode) -> TypeNode:
        if isinstance(node, QualifiedType): return self.base_type(node.base_type)
        if isinstance(node, AtomicType):    return self.base_type(node.base_type)
        if isinstance(node, TypeDefType):
            resolved = self.typedefs.lookup(node.iden)
            if resolved is not None:
                return self.base_type(resolved)
        return node

    def _member_type(self,
                     t: StructType | UnionType,
                     member_iden: str) -> TypeNode | Error:
        if t.members is None:
            if t.iden is not None:
                full = (self.tags.lookup_struct(t.iden)
                        if isinstance(t, StructType)
                        else self.tags.lookup_union(t.iden))
                if full is not None:
                    return self._member_type(full, member_iden)
            return Error()
        for m in t.members:
            if isinstance(m, VarDecl) and m.iden == member_iden:
                return m.var_type
        return Error()

    def integer_promote(self, node: TypeNode) -> TypeNode:
        if isinstance(node, (BoolType, CharType)):
            return IntType(IntKind.int, SignKind.signed)

        if isinstance(node, IntType) and node.kind == IntKind.short:
            return IntType(IntKind.int, node.sign_kind)

        return node

    # def _usual_arith_conv_int(self, a: IntType, b: IntType) -> TypeNode:
    #     ra, rb = _INT_RANK.get(a.kind, 0), _INT_RANK.get(b.kind, 0)
    #     if ra != rb:
    #         return a if ra > rb else b
    #     sign = (SignKind.unsigned
    #             if a.sign_kind == SignKind.unsigned or b.sign_kind == SignKind.unsigned
    #             else SignKind.signed)
    #     return IntType(a.kind, sign)
    #
    # def _usual_arith_conv(self, a: TypeNode, b: TypeNode) -> TypeNode:
    #     if isinstance(a, RealFloatType) or isinstance(b, RealFloatType):
    #         ra = _REAL_RANK.get(a.kind, 0) if isinstance(a, RealFloatType) else 0
    #         rb = _REAL_RANK.get(b.kind, 0) if isinstance(b, RealFloatType) else 0
    #         return a if ra >= rb else b
    #     if isinstance(a, DecimalFloatType) or isinstance(b, DecimalFloatType):
    #         ra = _DEC_RANK.get(a.kind, 0) if isinstance(a, DecimalFloatType) else 0
    #         rb = _DEC_RANK.get(b.kind, 0) if isinstance(b, DecimalFloatType) else 0
    #         return a if ra >= rb else b
    #     if isinstance(a, ComplexType) or isinstance(b, ComplexType):
    #         ra = _REAL_RANK.get(a.kind, 0) if isinstance(a, ComplexType) else 0
    #         rb = _REAL_RANK.get(b.kind, 0) if isinstance(b, ComplexType) else 0
    #         return a if ra >= rb else b
    #     a, b = self._integer_promote(a), self._integer_promote(b)
    #     if isinstance(a, IntType) and isinstance(b, IntType):
    #         return self._usual_arith_conv_int(a, b)
    #     return a

    def infer_una_op_type(self, node: OpExpr) -> TypeNode | Error:
        val_type = self.infer_expr_type(node.exprs[0])
        if isinstance(val_type, Error):
            return Error()

        base_type = self.base_type(val_type)

        if node.op == UnaPrefOpTag.addr_of:
            return PtrType(val_type, set())

        if op == UnaPrefOpTag.deref:
            if isinstance(base_type, PtrType):
                return base_type.pointee

            if isinstance(base_type, ArrayType):
                return base_type.elem_type

            return Error()

        if op == UnaPrefOpTag.bool_neg:
            return BoolType()

        return self.integer_promote(base_type)

    def infer_bin_op_type(self, node: OpExpr) -> TypeNode | Error:
        fst, snd = node.exprs[0], node.exprs[1]

        left = self.infer_expr_type(fst)
        if isinstance(left, Error):
            return Error()

        right = self.infer_expr_type(snd)
        if isinstance(right, Error):
            return right

        left_type = self.base_type(left)
        right_type = self.base_type(right)

        if node.op in ASSIGN_OPS:
            return left_type

        if node.op in CMP_OPS:
            return BoolType()

        if op in (BinOpTag.shl, BinOpTag.shr):
            return self.integer_promote(left_type)

        # TODO:
        if isinstance(lhs_b, PtrType) and not isinstance(rhs_b, PtrType):
            return left_type

        if isinstance(rhs_b, PtrType) and not isinstance(lhs_b, PtrType):
            return right_type

        if isinstance(lhs_b, PtrType) and isinstance(rhs_b, PtrType) and op == BinOpTag.sub:
            return IntType(IntKind.long, SignKind.signed)
        return self._usual_arith_conv(lhs_b, rhs_b)

    def infer_op_type(self, node: OpExpr) -> TypeNode | Error:
        if isinstance(node.op, (UnaPrefOpTag, UnaPostOpTag)):
            return self.infer_una_op_type(node)

        else:
            assert isinstance(node.op, BinOpTag)
            return self.infer_bin_op_type(node)

    def bit_int_type(self, node: BitIntType) -> BitIntType:
        node.width_expr = self.expr(node.width_expr)
        return node

    def ptr_type(self, node: PtrType) -> PtrType:
        node.pointee = self.type(node.pointee)
        return node

    def array_type(self, node: ArrayType) -> ArrayType:
        node.elem_type = self.type(node.elem_type)

        if node.elem_count is not None:
            node.elem_count = self.expr(node.elem_count)

        return node

    def fun_type(self, node: FunType) -> FunType:
        node.ret_type = self.type(node.ret_type)

        for param in node.params:
            param.param_type = self.type(param.param_type)

        return node

    def enum_type(self, node: EnumType) -> EnumType:
        if node.member_type is not None:
            node.member_type = self.type(node.member_type)

        if node.members is None:
            return node

        member_type: TypeNode | None = node.member_type

        if member_type is None:
            member_type = IntType(IntKind.int, SignKind.signed)

        for member in node.members:
            if member.expr is not None:
                member.expr = self.expr(member.expr)

            self.type_scope.define(member.iden, member_type)

        return node

    TagType = StructType | UnionType

    def struct_or_union_type(self, node: TagType) -> TagType:
        if node.members is None:
            return node

        new_members: list[DeclNode] = []

        for member in node.members:
            new_members.append(self.decl(member))

        node.members = new_members

        if node.iden is not None:
            if isinstance(node, StructType):
                self.tags.define_struct(node.iden, node)
            else:
                self.tags.define_union(node.iden, node)

        return node

    def atomic_type(self, node: AtomicType) -> AtomicType:
        node.base_type = self.type(node.base_type)
        return node

    TypeOfLike = TypeOfType | TypeOfUnqualType

    def typeof_or_unqual_type(self, node: TypeOfLike) -> TypeNode:
        resolved: TypeNode = self.resolve_typeof(node)
        return resolved

    def typedef_type(self, node: TypeDefType) -> TypeNode:
        resolved: TypeNode | None = self.typedefs.lookup(node.iden)
        assert resolved is not None

        return self.type(resolved)

    def qualified_type(self, node: QualifiedType) -> QualifiedType:
        resolved_base = self.type(node.base_type)

        if not isinstance(resolved_base, QualifiedType):
            node.base_type = resolved_base
        else:
            # FIX:
            node.qualifiers = resolved_base.qualifiers | node.qualifiers
            node.storage = node.storage if node.storage is not None else resolved_base.storage
            node.alignment = node.alignment if node.alignment is not None else resolved_base.alignment
            node.fun_spec = node.fun_spec if node.fun_spec is not None else resolved_base.fun_spec
            node.base_type = resolved_base.base_type

        if node.alignment is not None:
            node.alignment = self.expr_or_type(node.alignment)

        return node

    def type(self, node: TypeNode) -> TypeNode:
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

        return node

    def generic_sel_expr(self, node: GenericSelExpr) -> GenericSelExpr:
        node.ctrl_expr = self.expr(node.ctrl_expr)

        new_assoc_table: AssocTable = {}

        for case_type, case_expr in node.assoc_table.items():
            new_case_type: TypeNode | None = None

            if case_type is not None:
                new_case_type = self.type(case_type)

            new_assoc_table[new_case_type] = self.expr(case_expr)

        node.assoc_table = new_assoc_table
        return node

    def array_sub_expr(self, node: ArraySubExpr) -> ArraySubExpr:
        node.base_expr = self.expr(node.base_expr)
        node.idx_expr = self.expr(node.idx_expr)

        return node

    def call_expr(self, node: CallExpr) -> CallExpr:
        node.callee_expr = self.expr(node.callee_expr)
        node.arg_exprs = self.arg_exprs(node.arg_exprs)

        return node

    def member_expr(self, node: MemberExpr) -> MemberExpr:
        node.base_expr = self.expr(node.base_expr)
        return node

    def compound_lit_expr(self, node: CompoundLitExpr) -> CompoundLitExpr:
        node.expr_type = self.type(node.expr_type)
        node.init = self.init(node.init)

        return node

    def cast_expr(self, node: CastExpr) -> CastExpr:
        node.expr_type = self.type(node.expr_type)
        node.expr = self.expr(node.expr)

        return node

    def op_expr(self, node: OpExpr) -> OpExpr:
        node.exprs = [self.expr(expr_node) for expr_node in node.exprs]
        return node

    def cond_expr(self, node: CondExpr) -> CondExpr:
        node.cond_expr = self.expr(node.cond_expr)
        node.true_expr = self.expr(node.true_expr)
        node.false_expr = self.expr(node.false_expr)

        return node

    def comma_expr(self, node: CommaExpr) -> CommaExpr:
        fst_expr, snd_expr = node.exprs[0], node.exprs[1]

        node.exprs = (self.expr(fst_expr), self.expr(snd_expr))
        return node

    ###
    def sizeof_expr(self, node: SizeOfExpr) -> ExprNode:
        if isinstance(node.expr_or_type, TypeNode):
            t = self.type(node.expr_or_type)
            size = self._size_of(t)
            if isinstance(size, Error):
                node.expr_or_type = t
                return node  # leave non-constant sizeof for runtime
        else:
            operand = self.expr(node.expr_or_type)
            inferred = self.infer_expr_type(operand)
            if isinstance(inferred, Error):
                node.expr_or_type = operand
                return node  # HOOK: need symbol table to resolve
            # VLA: array with a non-literal element count
            if (isinstance(inferred, ArrayType)
                    and inferred.elem_count is not None
                    and not isinstance(inferred.elem_count, IntLitExpr)):
                node.expr_or_type = operand
                return node  # VLA — runtime sizeof
            size = self._size_of(inferred)
            if isinstance(size, Error):
                node.expr_or_type = operand
                return node

        return IntLitExpr(size, SIZE_T)

    def alignof_expr(self, node: AlignOfExpr) -> ExprNode:
        t = self.type(node.align_type)
        align = self._align_of(t)
        if isinstance(align, Error):
            node.align_type = t
            return node
        return IntLitExpr(align, SIZE_T)
    ###

    def expr(self, node: ExprNode) -> ExprNode:
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
            return self.alignof_expr(node)

        return node

    def expr_or_init(self,
                     node: ExprNode | InitNode) -> ExprNode | InitNode:
        if isinstance(node, ExprNode):
            return self.expr(node)
        else:
            return self.init(node)

    def init_member(self, node: InitMember) -> InitMember:
        if node.rec_init is not None:
            node.rec_init = self.init(node.rec_init)

        if node.expr_or_init is not None:
            node.expr_or_init = self.expr_or_init(node.expr_or_init)

        return node

    def init_index(self, node: InitIndex) -> InitIndex:
        node.idx_expr = self.expr(node.idx_expr)

        if node.rec_init is not None:
            node.rec_init = self.init(node.rec_init)

        if node.expr_or_init is not None:
            node.expr_or_init = self.expr_or_init(node.expr_or_init)

        return node

    def init_list(self, node: InitList) -> InitList:
        new_init_elems: list[ExprNode | InitNode] = []

        for elem in node.init_elems:
            new_init_elems.append(self.expr_or_init(elem))

        node.init_elems = new_init_elems
        return node

    def init(self, node: InitNode) -> InitNode:
        if isinstance(node, InitMember):
            return self.init_member(node)

        if isinstance(node, InitIndex):
            return self.init_index(node)

        if isinstance(node, InitList):
            return self.init_list(node)

        assert False

    def trans_unit_decl(self, node: TransUnitDecl) -> TransUnitDecl:
        node.decls = [self.decl(decl_node) for decl_node in node.decls]
        return node

    def var_decl(self, node: VarDecl) -> VarDecl:
        node.var_type = self.type(node.var_type)

        if node.init is not None:
            node.init = self.expr_or_init(node.init)

        self.type_scope.define(node.iden, node.var_type)
        return node

    def fun_decl(self, node: FunDecl) -> FunDecl:
        node.fun_type = self.type(node.fun_type)

        self.type_scope.define(node.iden, node.fun_type)

        if node.body is None:
            return node

        self.push_scope()

        for param in node.fun_type.params:
            if param.iden is not None:
                self.type_scope.define(param.iden, param.param_type)

        node.body = self.stmt(node.body)
        self.pop_scope()

        return node

    def enum_decl(self, node: EnumDecl) -> EnumDecl:
        node.enum_type = self.type(node.enum_type)
        return node

    def struct_decl(self, node: StructDecl) -> StructDecl:
        node.struct_type = self.type(node.struct_type)
        return node

    def union_decl(self, node: UnionDecl) -> UnionDecl:
        node.union_type = self.type(node.union_type)
        return node

    def static_assert_decl(self,
                           node: StaticAssertDecl) -> StaticAssertDecl:
        node.cond_expr = self.expr(node.cond_expr)
        return node

    ###
    def typedef_decl(self, node: TypedefDecl) -> TypedefDecl:
        visited = self.type(node.base_type)
        # Register canonical type: strip typedef storage, keep other qualifiers.
        qt = visited
        if isinstance(qt, QualifiedType):
            if qt.qualifiers or qt.alignment or qt.fun_spec:
                canonical: TypeNode = QualifiedType(
                    qt.base_type, qt.qualifiers, None, qt.alignment, qt.fun_spec
                )
            else:
                canonical = qt.base_type
        else:
            canonical = qt
        self.typedefs.define(node.alias_iden, canonical)
        return node

    ###

    def decl(self, node: DeclNode) -> DeclNode:
        if isinstance(node, TransUnitDecl):
            return self.trans_unit_decl(node)

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
            return self.static_assert_decl(node)

        if isinstance(node, TypedefDecl):
            return self.typedef_decl(node)

        return node

    def arg_exprs(self, args: list[ExprNode]) -> list[ExprNode]:
        new_args: list[ExprNode] = []

        for arg_expr in args:
            new_args.append(self.expr(arg_expr))

        return new_args

    def assert_stmt(self, node: AssertStmt) -> AssertStmt:
        node.cond_expr = self.expr(node.cond_expr)
        node.arg_exprs = self.arg_exprs(node.arg_exprs)

        return node

    def println_stmt(self, node: PrintLnStmt) -> PrintLnStmt:
        node.arg_exprs = self.arg_exprs(node.arg_exprs)
        return node

    def compound_stmt(self, node: CompoundStmt) -> CompoundStmt:
        self.push_scope()
        node.stmts = [self.stmt(stmt_node) for stmt_node in node.stmts]
        self.pop_scope()

        return node

    def decl_stmt(self, node: DeclStmt) -> DeclStmt:
        node.decl = self.decl(node.decl)
        return node

    def expr_stmt(self, node: ExprStmt) -> ExprStmt:
        node.expr = self.expr(node.expr)
        return node

    def if_stmt(self, node: IfStmt) -> IfStmt:
        node.cond_expr = self.expr(node.cond_expr)
        node.then_stmt = self.stmt(node.then_stmt)

        if node.else_stmt is not None:
            node.else_stmt = self.stmt(node.else_stmt)

        return node

    def case_label_stmt(self, node: CaseLabelStmt) -> CaseLabelStmt:
        if node.cond_expr is not None:
            node.cond_expr = self.expr(node.cond_expr)

        return node

    def switch_stmt(self, node: SwitchStmt) -> SwitchStmt:
        node.cond_expr = self.expr(node.cond_expr)
        node.then_stmt = self.stmt(node.then_stmt)

        return node

    def expr_or_decl(self,
                     node: ExprNode | DeclStmt) -> ExprNode | DeclStmt:
        if isinstance(node, ExprNode):
            return self.expr(node)
        else:
            return self.decl(node)

    def for_stmt(self, node: ForStmt) -> ForStmt:
        if node.init_clause is not None:
            node.init_clause = self.expr_or_decl(node.init_clause)

        if node.cond_expr is not None:
            node.cond_expr = self.expr(node.cond_expr)

        if node.inc_expr is not None:
            node.inc_expr = self.expr(node.inc_expr)

        node.then_stmt = self.stmt(node.then_stmt)

        return node

    def while_stmt(self, node: WhileStmt) -> WhileStmt:
        node.cond_expr = self.expr(node.cond_expr)
        node.then_stmt = self.stmt(node.then_stmt)

        return node

    def do_while_stmt(self, node: DoWhileStmt) -> DoWhileStmt:
        node.do_stmt = self.stmt(node.do_stmt)
        node.cond_expr = self.expr(node.cond_expr)

        return node

    def return_stmt(self, node: ReturnStmt) -> ReturnStmt:
        if node.ret_expr is not None:
            node.ret_expr = self.expr(node.ret_expr)

        return node

    def stmt(self, node: StmtNode) -> StmtNode:
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
            return self.switch_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, ReturnStmt):
            return self.return_stmt(node)

        return node

    def normalize(self, root: TransUnitDecl) -> TransUnitDecl:
        return self.decl(root)


# Implicit-cast injection (C23 §6.3)
#
# Runs after Normalize01. Walks every expression in every function body
# and wraps operands of OpExpr nodes in CastExpr wherever C23 mandates an
# implicit conversion:
#   • Integer promotions   (§6.3.1.1) – unary +, -, ~
#   • Usual arithmetic conversions (§6.3.1.8) – binary arithmetic, bitwise,
#     comparison, and shift operators
#   • Assignment conversions – RHS is cast to the declared LHS type
#   • Function-argument conversions – each argument is cast to its
#     declared parameter type (§6.5.2.2)
#   • Return-value conversions – the returned expression is cast to the
#     function's declared return type (§6.8.6.4)
#
# After this pass every binary operator that the interpreter evaluates will
# have both operands of exactly the same AST type, satisfying the
# interpreter's internal types_match assertions.
class Normalize02:

    def __init__(self) -> None:
        self.scopes: list[dict[str, TypeNode]] = []
        self._fun_ret_type: TypeNode | None = None

    # --- Scope helpers ---

    def _push(self) -> None:
        self.scopes.append({})

    def _pop(self) -> None:
        self.scopes.pop()

    def _define(self, name: str, t: TypeNode) -> None:
        self.scopes[-1][name] = t

    def _lookup(self, name: str) -> TypeNode | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    # --- Type helpers ---

    def _unqual(self, t: TypeNode) -> TypeNode:
        if isinstance(t, QualifiedType):
            return t.base_type
        return t

    def _is_arithmetic(self, t: TypeNode) -> bool:
        return isinstance(t, (BoolType, IntType, BitIntType, CharType,
                               RealFloatType, DecimalFloatType,
                               ComplexType, ImaginaryType, EnumType))

    def _is_integer(self, t: TypeNode) -> bool:
        return isinstance(t, (BoolType, IntType, BitIntType, CharType, EnumType))

    def _is_unresolved(self, t: TypeNode) -> bool:
        return isinstance(t, (TypeDefType, TypeOfType, TypeOfUnqualType, AtomicType))

    # --- Type inference ---

    def _type_of(self, node: ExprNode) -> TypeNode | None:
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
            return self._lookup(node.iden)
        if isinstance(node, CastExpr):
            return node.expr_type
        if isinstance(node, CompoundLitExpr):
            return node.expr_type
        if isinstance(node, (SizeOfExpr, AlignOfExpr)):
            return SIZE_T
        if isinstance(node, CallExpr):
            return self._type_of_call(node)
        if isinstance(node, OpExpr):
            return self._type_of_op(node)
        if isinstance(node, CondExpr):
            return self._type_of(node.true_expr)
        if isinstance(node, CommaExpr):
            return self._type_of(node.exprs[1])
        return None

    def _type_of_call(self, node: CallExpr) -> TypeNode | None:
        callee_t = self._type_of(node.callee_expr)
        if callee_t is None:
            return None
        callee_t = self._unqual(callee_t)
        if isinstance(callee_t, FunType):
            return callee_t.ret_type
        if isinstance(callee_t, PtrType):
            inner = self._unqual(callee_t.pointee)
            if isinstance(inner, FunType):
                return inner.ret_type
        return None

    def _type_of_op(self, node: OpExpr) -> TypeNode | None:
        op = node.op

        if isinstance(op, UnaPrefOpTag):
            if op == UnaPrefOpTag.addr_of:
                t = self._type_of(node.exprs[0])
                return PtrType(t, set()) if t is not None else None
            if op == UnaPrefOpTag.deref:
                t = self._type_of(node.exprs[0])
                if t is None:
                    return None
                t = self._unqual(t)
                if isinstance(t, PtrType):
                    return t.pointee
                return None
            if op == UnaPrefOpTag.bool_neg:
                return IntType(IntKind.int, SignKind.signed)
            t = self._type_of(node.exprs[0])
            if t is None:
                return None
            return self._integer_promote(self._unqual(t))

        if isinstance(op, UnaPostOpTag):
            return self._type_of(node.exprs[0])

        if isinstance(op, BinOpTag):
            lt = self._type_of(node.exprs[0])
            rt = self._type_of(node.exprs[1])
            if lt is None or rt is None:
                return None
            lt_b = self._unqual(lt)
            rt_b = self._unqual(rt)

            if op in CMP_OPS:
                return IntType(IntKind.int, SignKind.signed)
            if op in ASSIGN_OPS:
                return lt_b
            if op in (BinOpTag.shl, BinOpTag.shr,
                      BinOpTag.shl_assign, BinOpTag.shr_assign):
                return self._integer_promote(lt_b)

            if isinstance(lt_b, PtrType) and not isinstance(rt_b, PtrType):
                return lt_b
            if isinstance(rt_b, PtrType) and not isinstance(lt_b, PtrType):
                return rt_b
            if isinstance(lt_b, PtrType) and isinstance(rt_b, PtrType):
                return IntType(IntKind.long, SignKind.signed)

            if self._is_arithmetic(lt_b) and self._is_arithmetic(rt_b):
                return self._usual_arith_conv(lt_b, rt_b)

        return None

    # --- Integer promotion (C23 §6.3.1.1) ---

    def _effective_sign(self, s: SignKind) -> SignKind:
        return SignKind.signed if s == SignKind.default else s

    def _integer_promote(self, t: TypeNode) -> TypeNode:
        if isinstance(t, (BoolType, CharType)):
            return IntType(IntKind.int, SignKind.signed)
        if isinstance(t, IntType) and t.kind == IntKind.short:
            return IntType(IntKind.int,
                           self._effective_sign(t.sign_kind))
        if isinstance(t, EnumType):
            base = t.member_type
            if base is not None:
                return self._integer_promote(self._unqual(base))
            return IntType(IntKind.int, SignKind.signed)
        return t

    # --- Usual arithmetic conversions (C23 §6.3.1.8) ---

    def _usual_arith_conv_int(self, a: IntType, b: IntType) -> IntType:
        ra = INT_RANK.get(a.kind, 0)
        rb = INT_RANK.get(b.kind, 0)
        a_sign = self._effective_sign(a.sign_kind)
        b_sign = self._effective_sign(b.sign_kind)
        if ra != rb:
            winner = a if ra > rb else b
            # preserve effective signedness of the higher-rank type
            w_sign = self._effective_sign(winner.sign_kind)
            if a_sign == SignKind.unsigned or b_sign == SignKind.unsigned:
                w_sign = SignKind.unsigned
            return IntType(winner.kind, w_sign)
        if a_sign == SignKind.unsigned or b_sign == SignKind.unsigned:
            return IntType(a.kind, SignKind.unsigned)
        return IntType(a.kind, SignKind.signed)

    def _usual_arith_conv(self, a: TypeNode, b: TypeNode) -> TypeNode:
        # Decimal float dominates; no mixing with binary float in C23.
        if isinstance(a, DecimalFloatType) or isinstance(b, DecimalFloatType):
            ra = DEC_RANK.get(a.kind, 0) if isinstance(a, DecimalFloatType) else 0
            rb = DEC_RANK.get(b.kind, 0) if isinstance(b, DecimalFloatType) else 0
            return a if ra >= rb else b

        # Complex float.
        if isinstance(a, ComplexType) or isinstance(b, ComplexType):
            ra = FLOAT_RANK.get(a.kind, 0) if isinstance(a, ComplexType) else 0
            rb = FLOAT_RANK.get(b.kind, 0) if isinstance(b, ComplexType) else 0
            return a if ra >= rb else b

        # Real float.
        if isinstance(a, RealFloatType) or isinstance(b, RealFloatType):
            ra = FLOAT_RANK.get(a.kind, 0) if isinstance(a, RealFloatType) else 0
            rb = FLOAT_RANK.get(b.kind, 0) if isinstance(b, RealFloatType) else 0
            return a if ra >= rb else b

        # Both integer: apply promotions, then compare.
        a = self._integer_promote(a)
        b = self._integer_promote(b)
        if isinstance(a, IntType) and isinstance(b, IntType):
            return self._usual_arith_conv_int(a, b)

        # BitInt or other integer-like: return whichever has higher declared width.
        # (Analysis already verified the combination is valid.)
        return a

    # --- Structural type equality ---
    # Two types are equal when the interpreter's resolve_type would produce
    # identical TypeObject values (same size, same is_signed).

    def _types_eq(self, a: TypeNode, b: TypeNode) -> bool:
        if type(a) is not type(b):
            return False
        if isinstance(a, (BoolType, NullPtrType, VoidType)):
            return True
        if isinstance(a, IntType) and isinstance(b, IntType):
            return (a.kind == b.kind and
                    self._effective_sign(a.sign_kind) ==
                    self._effective_sign(b.sign_kind))
        if isinstance(a, CharType) and isinstance(b, CharType):
            return (a.kind == b.kind and
                    self._effective_sign(a.sign_kind) ==
                    self._effective_sign(b.sign_kind))
        if isinstance(a, RealFloatType) and isinstance(b, RealFloatType):
            return a.kind == b.kind
        if isinstance(a, DecimalFloatType) and isinstance(b, DecimalFloatType):
            return a.kind == b.kind
        if isinstance(a, ComplexType) and isinstance(b, ComplexType):
            return a.kind == b.kind
        return False

    def _maybe_cast(self,
                    expr: ExprNode,
                    from_t: TypeNode,
                    to_t: TypeNode) -> ExprNode:
        if self._types_eq(from_t, to_t):
            return expr
        return CastExpr(to_t, expr)

    # --- Cast injection for operators ---

    def _inject_op_expr(self, node: OpExpr) -> ExprNode:
        # Recurse into children first so sub-expression types are settled.
        node.exprs = [self._expr(e) for e in node.exprs]

        op = node.op

        # Unary: integer-promote the operand of +, -, ~ (§6.5.3.3).
        if isinstance(op, UnaPrefOpTag):
            if op in (UnaPrefOpTag.plus, UnaPrefOpTag.neg, UnaPrefOpTag.bit_neg):
                operand = node.exprs[0]
                t = self._type_of(operand)
                if t is not None:
                    base = self._unqual(t)
                    if not self._is_unresolved(base):
                        promoted = self._integer_promote(base)
                        node.exprs[0] = self._maybe_cast(operand, base, promoted)
            return node

        if isinstance(op, UnaPostOpTag):
            return node

        assert isinstance(op, BinOpTag)

        lhs, rhs = node.exprs[0], node.exprs[1]
        lt = self._type_of(lhs)
        rt = self._type_of(rhs)

        if lt is None or rt is None:
            return node

        lt_b = self._unqual(lt)
        rt_b = self._unqual(rt)

        if self._is_unresolved(lt_b) or self._is_unresolved(rt_b):
            return node

        # Shift assignments: promote RHS to the promoted LHS type so that
        # both sides share the same type for the shift operation (§6.5.7 p3).
        if op in (BinOpTag.shl_assign, BinOpTag.shr_assign):
            pl = self._integer_promote(lt_b)
            node.exprs[1] = self._maybe_cast(rhs, rt_b, pl)
            return node

        # All other assignment operators: cast RHS to the LHS type (§6.5.16).
        if op in ASSIGN_OPS:
            node.exprs[1] = self._maybe_cast(rhs, rt_b, lt_b)
            return node

        # Shift: promote each operand independently; cast RHS to promoted
        # LHS type so both operands match (§6.5.7 p3).
        if op in (BinOpTag.shl, BinOpTag.shr):
            pl = self._integer_promote(lt_b)
            node.exprs[0] = self._maybe_cast(lhs, lt_b, pl)
            node.exprs[1] = self._maybe_cast(rhs, rt_b, pl)
            return node

        # Logical operators: no operand conversion required (§6.5.13/14).
        if op in (BinOpTag.bool_and, BinOpTag.bool_or):
            return node

        # Pointer arithmetic: the pointer side stays as-is; the integer
        # side may independently need promotion, but the pointer type and
        # ptrdiff_t type differ so we leave both untouched (§6.5.6).
        if isinstance(lt_b, PtrType) or isinstance(rt_b, PtrType):
            return node

        # All remaining arithmetic, bitwise, and comparison operators:
        # apply the usual arithmetic conversions (§6.3.1.8).
        if not (self._is_arithmetic(lt_b) and self._is_arithmetic(rt_b)):
            return node

        common = self._usual_arith_conv(lt_b, rt_b)
        node.exprs[0] = self._maybe_cast(lhs, lt_b, common)
        node.exprs[1] = self._maybe_cast(rhs, rt_b, common)
        return node

    # --- Expression walker ---

    def _expr(self, node: ExprNode) -> ExprNode:
        if isinstance(node, (NullPtrLitExpr, BoolLitExpr, IntLitExpr,
                              RealFloatLitExpr, DecFloatLitExpr,
                              CharLitExpr, StrLitExpr, IdenExpr, AlignOfExpr)):
            return node

        if isinstance(node, SizeOfExpr):
            if isinstance(node.expr_or_type, ExprNode):
                node.expr_or_type = self._expr(node.expr_or_type)
            return node

        if isinstance(node, CastExpr):
            node.expr = self._expr(node.expr)
            return node

        if isinstance(node, CompoundLitExpr):
            node.init = self._init(node.init)
            return node

        if isinstance(node, GenericSelExpr):
            node.ctrl_expr = self._expr(node.ctrl_expr)
            node.assoc_table = {
                t: self._expr(e) for t, e in node.assoc_table.items()
            }
            return node

        if isinstance(node, ArraySubExpr):
            node.base_expr = self._expr(node.base_expr)
            node.idx_expr = self._expr(node.idx_expr)
            return node

        if isinstance(node, MemberExpr):
            node.base_expr = self._expr(node.base_expr)
            return node

        if isinstance(node, CallExpr):
            node.callee_expr = self._expr(node.callee_expr)
            node.arg_exprs = self._arg_exprs(node)
            return node

        if isinstance(node, OpExpr):
            return self._inject_op_expr(node)

        if isinstance(node, CondExpr):
            node.cond_expr = self._expr(node.cond_expr)
            # Sample types before recursing so we work with original types.
            true_t = self._type_of(node.true_expr)
            false_t = self._type_of(node.false_expr)
            node.true_expr = self._expr(node.true_expr)
            node.false_expr = self._expr(node.false_expr)
            # Align both branches to the common arithmetic type (§6.5.15).
            if true_t is not None and false_t is not None:
                true_b = self._unqual(true_t)
                false_b = self._unqual(false_t)
                if (self._is_arithmetic(true_b) and self._is_arithmetic(false_b)
                        and not self._is_unresolved(true_b)
                        and not self._is_unresolved(false_b)):
                    common = self._usual_arith_conv(true_b, false_b)
                    node.true_expr = self._maybe_cast(node.true_expr, true_b, common)
                    node.false_expr = self._maybe_cast(node.false_expr, false_b, common)
            return node

        if isinstance(node, CommaExpr):
            fst, snd = node.exprs
            node.exprs = (self._expr(fst), self._expr(snd))
            return node

        return node

    def _arg_exprs(self, node: CallExpr) -> list[ExprNode]:
        callee_t = self._type_of(node.callee_expr)
        fun_t: FunType | None = None
        if callee_t is not None:
            callee_t = self._unqual(callee_t)
            if isinstance(callee_t, FunType):
                fun_t = callee_t
            elif isinstance(callee_t, PtrType):
                inner = self._unqual(callee_t.pointee)
                if isinstance(inner, FunType):
                    fun_t = inner

        result: list[ExprNode] = []
        for i, arg in enumerate(node.arg_exprs):
            arg = self._expr(arg)
            if fun_t is not None and i < len(fun_t.params):
                param_b = self._unqual(fun_t.params[i].param_type)
                arg_t = self._type_of(arg)
                if arg_t is not None:
                    arg_b = self._unqual(arg_t)
                    if (not self._is_unresolved(arg_b) and
                            not self._is_unresolved(param_b) and
                            self._is_arithmetic(arg_b) and
                            self._is_arithmetic(param_b)):
                        arg = self._maybe_cast(arg, arg_b, param_b)
            result.append(arg)
        return result

    def _init_elem(self, node: ExprNode | InitNode) -> ExprNode | InitNode:
        if isinstance(node, ExprNode):
            return self._expr(node)
        return self._init(node)

    def _init(self, node: InitNode) -> InitNode:
        if isinstance(node, InitList):
            node.init_elems = [self._init_elem(e) for e in node.init_elems]
        elif isinstance(node, InitMember):
            if node.rec_init is not None:
                node.rec_init = self._init(node.rec_init)
            if node.expr_or_init is not None:
                node.expr_or_init = self._init_elem(node.expr_or_init)
        elif isinstance(node, InitIndex):
            node.idx_expr = self._expr(node.idx_expr)
            if node.rec_init is not None:
                node.rec_init = self._init(node.rec_init)
            if node.expr_or_init is not None:
                node.expr_or_init = self._init_elem(node.expr_or_init)
        return node

    # --- Statement walker ---

    def _stmt(self, node: StmtNode) -> None:
        if isinstance(node, ExprStmt):
            node.expr = self._expr(node.expr)

        elif isinstance(node, DeclStmt):
            self._decl_stmt(node)

        elif isinstance(node, CompoundStmt):
            self._push()
            for s in node.stmts:
                self._stmt(s)
            self._pop()

        elif isinstance(node, IfStmt):
            node.cond_expr = self._expr(node.cond_expr)
            self._stmt(node.then_stmt)
            if node.else_stmt is not None:
                self._stmt(node.else_stmt)

        elif isinstance(node, SwitchStmt):
            node.cond_expr = self._expr(node.cond_expr)
            self._stmt(node.then_stmt)

        elif isinstance(node, CaseLabelStmt):
            if node.cond_expr is not None:
                node.cond_expr = self._expr(node.cond_expr)

        elif isinstance(node, ForStmt):
            self._push()
            if isinstance(node.init_clause, ExprNode):
                node.init_clause = self._expr(node.init_clause)
            elif isinstance(node.init_clause, DeclNode):
                self._decl_stmt(DeclStmt(node.init_clause))
            if node.cond_expr is not None:
                node.cond_expr = self._expr(node.cond_expr)
            if node.inc_expr is not None:
                node.inc_expr = self._expr(node.inc_expr)
            self._stmt(node.then_stmt)
            self._pop()

        elif isinstance(node, WhileStmt):
            node.cond_expr = self._expr(node.cond_expr)
            self._stmt(node.then_stmt)

        elif isinstance(node, DoWhileStmt):
            self._stmt(node.do_stmt)
            node.cond_expr = self._expr(node.cond_expr)

        elif isinstance(node, ReturnStmt):
            if node.ret_expr is not None:
                ret = self._expr(node.ret_expr)
                if self._fun_ret_type is not None:
                    ret_t = self._type_of(ret)
                    if ret_t is not None:
                        ret_b = self._unqual(ret_t)
                        fun_b = self._unqual(self._fun_ret_type)
                        if (not self._is_unresolved(ret_b) and
                                not self._is_unresolved(fun_b) and
                                self._is_arithmetic(ret_b) and
                                self._is_arithmetic(fun_b)):
                            ret = self._maybe_cast(ret, ret_b, fun_b)
                node.ret_expr = ret

        elif isinstance(node, AssertStmt):
            node.cond_expr = self._expr(node.cond_expr)
            node.arg_exprs = [self._expr(e) for e in node.arg_exprs]

        elif isinstance(node, PrintLnStmt):
            node.arg_exprs = [self._expr(e) for e in node.arg_exprs]

    def _decl_stmt(self, node: DeclStmt) -> None:
        if isinstance(node.decl, VarDecl):
            decl = node.decl
            if decl.init is not None:
                if isinstance(decl.init, ExprNode):
                    init_expr = self._expr(decl.init)
                    var_b = self._unqual(decl.var_type)
                    init_t = self._type_of(init_expr)
                    if init_t is not None:
                        init_b = self._unqual(init_t)
                        if (not self._is_unresolved(init_b) and
                                not self._is_unresolved(var_b) and
                                self._is_arithmetic(init_b) and
                                self._is_arithmetic(var_b)):
                            init_expr = self._maybe_cast(init_expr, init_b, var_b)
                    decl.init = init_expr
                else:
                    decl.init = self._init(decl.init)
            self._define(decl.iden, decl.var_type)

        elif isinstance(node.decl, EnumDecl):
            self._register_enum(node.decl)

    def _register_enum(self, node: EnumDecl) -> None:
        enum_t = node.enum_type
        if isinstance(enum_t, QualifiedType):
            enum_t = enum_t.base_type
        if not isinstance(enum_t, EnumType) or enum_t.members is None:
            return
        member_t: TypeNode = (enum_t.member_type
                              if enum_t.member_type is not None
                              else IntType(IntKind.int, SignKind.signed))
        for member in enum_t.members:
            self._define(member.iden, member_t)

    # --- Entry point ---

    def normalize(self, root: TransUnitDecl) -> TransUnitDecl:
        self._push()

        # First pass: register all file-scope names so function bodies can
        # freely reference globals and each other (mirrors Analysis14).
        for decl in root.decls:
            if isinstance(decl, VarDecl):
                self._define(decl.iden, decl.var_type)
            elif isinstance(decl, FunDecl):
                self._define(decl.iden, decl.fun_type)
            elif isinstance(decl, EnumDecl):
                self._register_enum(decl)

        # Second pass: inject casts inside every function body.
        for decl in root.decls:
            if not isinstance(decl, FunDecl) or decl.body is None:
                continue

            self._push()
            prev_ret = self._fun_ret_type
            self._fun_ret_type = decl.fun_type.ret_type

            for param in decl.fun_type.params:
                if param.iden is not None:
                    self._define(param.iden, param.param_type)

            for s in decl.body.stmts:
                self._stmt(s)

            self._fun_ret_type = prev_ret
            self._pop()

        self._pop()
        return root
