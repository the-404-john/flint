import sys
import decimal
from decimal import Decimal
from enum import Enum

from error import *
from limits import *

import flint_ast
from flint_ast import *
from value_objects import *

from memory import Memory, MemoryType, MemoryBlock
from scope import Scope, ScopeFrame, ScopeVar
from convert import TypeConverter, MemConverter
from cycle_simulation import CycleSimulator


# Evaluator
# Interprets the abstract syntax tree (AST) using a tree-walking
# evaluation.
#
# Manages execution scopes, maintains the runtime environment, and
# dynamically detects instances of undefined behavior.


# Predefined integer type shortcuts used throughout the evaluator.
I8   = IntType(1, 1, True)
U8   = IntType(1, 1, False)
I16  = IntType(2, 2, True)
U16  = IntType(2, 2, False)
I32  = IntType(4, 4, True)
U32  = IntType(4, 4, False)
I64  = IntType(8, 8, True)
U64  = IntType(8, 8, False)
# size_t: same width as a pointer half (PTR_SIZE // 2 bytes, unsigned).
SIZE_T = IntType(PTR_SIZE // 2, PTR_SIZE // 2, False)


# Order of Computation.
class Direction(Enum):
    left_to_right = "left_to_right"
    right_to_left = "right_to_left"


# LValues
class LValue:
    pass


class ScopeLValue(LValue):
    def __init__(self, iden: str) -> None:
        self.iden = iden


class MemoryLValue(LValue):
    def __init__(self,
                 obj_type: TypeObject,
                 block_id: int,
                 offset: int) -> None:
        self.obj_type = obj_type
        self.block_id = block_id
        self.offset = offset


# Signals.
class BreakSignal:
    pass


class ContinueSignal:
    pass


class ReturnSignal:
    def __init__(self, value: ValueObject | None) -> None:
        self.value = value


class GotoSignal:
    def __init__(self, label: str) -> None:
        self.label = label


# Result Types.
ExprResult = ValueObject | LValue

StmtResult = BreakSignal | ContinueSignal | ReturnSignal | \
             GotoSignal | None


class TypeRegistry:
    def __init__(self) -> None:
        self.structs: dict[str, StructType] = {}
        self.unions: dict[str, UnionType] = {}
        self.enums: dict[str, EnumType] = {}
        self.typedefs: dict[str, TypeObject] = {}


class Evaluator:
    def __init__(self,
                 mem: Memory,
                 step_limit: int,
                 cycle_limit: int,
                 trace_flag: bool) -> None:
        self.mem = mem
        self.scope = Scope(mem)

        self.type_registry = TypeRegistry()
        self.functions: dict[str, FunDecl] = {}

        self.step_count: int = 0
        self.cycle_count: int = 0

        self.step_limit = step_limit
        self.cycle_limit = cycle_limit

        self.trace_flag = trace_flag
        self.direction = Direction.left_to_right
        self.cycle_sim = CycleSimulator()

    def eval_args(self,
                  arg_exprs: list[ExprNode]) -> list[ValueObject] | Error:
        args: list[ValueObject] = []

        for arg_expr in arg_exprs:
            val_obj: ValueObject | Error = self.load(self.expr(arg_expr))

            if isinstance(val_obj, Error):
                return val_obj

            args.append(val_obj)

        return args

    def eval_cond(self, node: ExprNode) -> bool | Error:
        cond = self.load(self.expr(node))
        if isinstance(cond, Error):
            return cond

        result = TypeConverter().cast(cond, BoolType())
        if isinstance(result, Error):
            return result

        assert isinstance(result, BoolValue)
        return result.value

    def eval_body(self, node: StmtNode, have_scope: bool) -> StmtResult:
        if not have_scope:
            self.scope.push()

        result: StmtResult = None

        if isinstance(node, CompoundStmt):
            for stmt_node in node.stmts:
                result = self.stmt(stmt_node)

                if result is not None:
                    break
        else:
            result = self.stmt(node)

        if not have_scope:
            self.scope.pop()

        return result

    def step_inc(self) -> None | Error:
        self.step_count += 1

        if self.step_count > self.step_limit:
            return Error()

    def cycle_inc(self, node: ASTNode) -> None | Error:
        self.cycle_count += self.cycle_sim.cycle_cost(node)

        if self.cycle_count > self.cycle_limit:
            return Error()

    def trace(self, node: ASTNode) -> None:
        if self.trace_flag:
            print(f"[trace] {type(node).__name__}", file=sys.stderr)

    def load_scope_lvalue(self, val: ScopeLValue) -> ValueObject | Error:
        return self.scope.read(val.iden)

    def load_mem_lvalue(self,
                        mem_val: MemoryLValue) -> ValueObject | Error:
        mem_block: MemoryBlock | Error = self.mem.get(mem_val.block_id)
        if isinstance(mem_block, Error):
            return mem_block

        sub_mem_block: MemoryBlock | Error = mem_block.read_block(
            mem_val.offset,
            mem_val.obj_type.size
        )

        if isinstance(sub_mem_block, Error):
            return sub_mem_block

        return MemConverter().from_mem_block(
            mem_val.obj_type,
            sub_mem_block
        )

    def load(self, val: ExprResult | Error) -> ValueObject | Error:
        if isinstance(val, Error):
            return val

        if isinstance(val, ValueObject):
            return val

        if isinstance(val, ScopeLValue):
            return self.load_scope_lvalue(val)

        if isinstance(val, MemoryLValue):
            return self.load_mem_lvalue(val)

        assert False

    def store_scope_lvalue(self,
                           val: ScopeLValue,
                           val_obj: ValueObject) -> None | Error:
        return self.scope.write(val.iden, val_obj)

    def store_mem_lvalue(self,
                         val: MemoryLValue,
                         val_obj: ValueObject) -> None | Error:
        mem_block: MemoryBlock | Error = self.mem.get(val.block_id)

        if isinstance(mem_block, Error):
            return mem_block

        val_mem_block: MemoryBlock = MemConverter().to_mem_block(val_obj)
        return mem_block.write_block(val.offset, val_mem_block)

    def store(self, val: ExprResult, val_obj: ValueObject) -> None | Error:
        if isinstance(val, ScopeLValue):
            return self.store_scope_lvalue(val, val_obj)

        if isinstance(val, MemoryLValue):
            return self.store_mem_lvalue(val, val_obj)

        return Error()

    def val_obj_type(self, val: ValueObject) -> TypeObject | None:
        if isinstance(val, BoolValue):
            return val.value_type

        if isinstance(val, IntValue):
            return val.value_type

        if isinstance(val, FloatValue):
            return val.value_type

        if isinstance(val, DecValue):
            return val.value_type

        if isinstance(val, PtrValue):
            return val.ptr_type

        if isinstance(val, ArrayValue):
            return val.array_type

        if isinstance(val, StructValue):
            return val.struct_type

        if isinstance(val, UnionValue):
            return val.union_type

        if isinstance(val, EnumValue):
            return val.enum_type

        assert False

    def types_match(self, fst: TypeObject, snd: TypeObject) -> bool:
        if isinstance(fst, BoolType) and isinstance(snd, BoolType):
            return True

        if isinstance(fst, IntType) and isinstance(snd, IntType):
            return fst.size == snd.size and \
                   fst.is_signed == snd.is_signed

        if isinstance(fst, FloatType) and isinstance(snd, FloatType):
            return fst.size == snd.size

        if isinstance(fst, DecType) and isinstance(snd, DecType):
            return fst.size == snd.size

        if isinstance(fst, PtrType) and isinstance(snd, PtrType):
            if (fst.target_type is None) != (snd.target_type is None):
                return False

            if fst.target_type is None and snd.target_type is None:
                return True
            else:
                return self.types_match(fst.target_type, snd.target_type)

        if isinstance(fst, EnumType) and isinstance(snd, EnumType):
            return fst.iden == snd.iden

        if isinstance(fst, StructType) and isinstance(snd, StructType):
            return fst.iden == snd.iden

        if isinstance(fst, UnionType) and isinstance(snd, UnionType):
            return fst.iden == snd.iden

        return False

    ###
    def format_value(self, val_obj: ValueObject) -> str:
        if isinstance(val_obj, BoolValue):
            return "true" if val_obj.value else "false"

        if isinstance(val_obj, IntValue):
            return str(val_obj.value)

        if isinstance(val_obj, FloatValue):
            return repr(val_obj.value)

        if isinstance(val_obj, DecValue):
            return str(val_obj.value)

        if isinstance(val_obj, PtrValue):
            return f"0x{val_obj.block_id:x}:{val_obj.offset:x}"

        if isinstance(val_obj, ArrayValue):
            elems = ", ".join(self.format_value(e) for e in val_obj.elems)
            return f"{{{elems}}}"

        if isinstance(val_obj, StructValue):
            fields = ", ".join(
                f".{k}={self.format_value(v)}"
                for k, v in val_obj.elems.items()
            )
            return f"{{{fields}}}"

        if isinstance(val_obj, EnumValue):
            return self.format_value(val_obj.value)

        return "?"

    def fmt_sub(self,
                string: StrLitExpr | None,
                arg_exprs: list[ExprNode]) -> str | Error:
        args: list[ValueObject] | Error = self.eval_args(arg_exprs)
        if isinstance(args, Error):
            return args

        if string is None:
            return " ".join(self.format_value(v) for v in args)

        fmt_str = string.str_expr
        result = fmt_str
        for val_obj in args:
            result = result.replace(FORMAT_SPEC, self.format_value(val_obj), 1)

        return result

    def apply_init_list(self,
                        block_id: int,
                        base_offset: int,
                        t: TypeObject,
                        init: InitList) -> None | Error:
        block = self.mem.get(block_id)
        if isinstance(block, Error):
            return Error()

        if isinstance(t, StructType):
            member_names = list(t.members.keys())
            seq_idx = 0

            for elem in init.init_elems:
                if isinstance(elem, InitMember):
                    member = t.members.get(elem.member_iden)
                    if member is None:
                        return Error()
                    target = elem.expr_or_init
                    if target is None:
                        continue
                    off = base_offset + member.offset
                    if isinstance(target, ExprNode):
                        val = self.load(self.expr(target))
                        if isinstance(val, Error):
                            return Error()
                        raw = MemConverter().to_mem_block(val)
                        result = block.write_block(off, raw)
                        if isinstance(result, Error):
                            return Error()
                    elif isinstance(target, InitList):
                        result = self.apply_init_list(block_id, off, member.member_type, target)
                        if isinstance(result, Error):
                            return Error()

                elif isinstance(elem, ExprNode):
                    if seq_idx >= len(member_names):
                        return Error()
                    member = t.members[member_names[seq_idx]]
                    off = base_offset + member.offset
                    val = self.load(self.expr(elem))
                    if isinstance(val, Error):
                        return Error()
                    raw = MemConverter().to_mem_block(val)
                    result = block.write_block(off, raw)
                    if isinstance(result, Error):
                        return Error()
                    seq_idx += 1

                elif isinstance(elem, InitList):
                    if seq_idx >= len(member_names):
                        return Error()
                    member = t.members[member_names[seq_idx]]
                    off = base_offset + member.offset
                    result = self.apply_init_list(block_id, off, member.member_type, elem)
                    if isinstance(result, Error):
                        return Error()
                    seq_idx += 1

        elif isinstance(t, ArrayType):
            elem_size = t.elem_type.size
            seq_idx = 0

            for elem in init.init_elems:
                if isinstance(elem, InitIndex):
                    idx_val = self.load(self.expr(elem.idx_expr))
                    if isinstance(idx_val, Error):
                        return Error()
                    if not isinstance(idx_val, IntValue):
                        return Error()
                    seq_idx = idx_val.value
                    target = elem.expr_or_init
                    if target is None:
                        seq_idx += 1
                        continue
                    off = base_offset + seq_idx * elem_size
                    if isinstance(target, ExprNode):
                        val = self.load(self.expr(target))
                        if isinstance(val, Error):
                            return Error()
                        raw = MemConverter().to_mem_block(val)
                        result = block.write_block(off, raw)
                        if isinstance(result, Error):
                            return Error()
                    elif isinstance(target, InitList):
                        result = self.apply_init_list(block_id, off, t.elem_type, target)
                        if isinstance(result, Error):
                            return Error()
                    seq_idx += 1

                elif isinstance(elem, ExprNode):
                    if seq_idx >= t.length:
                        return Error()
                    off = base_offset + seq_idx * elem_size
                    val = self.load(self.expr(elem))
                    if isinstance(val, Error):
                        return Error()
                    raw = MemConverter().to_mem_block(val)
                    result = block.write_block(off, raw)
                    if isinstance(result, Error):
                        return Error()
                    seq_idx += 1

                elif isinstance(elem, InitList):
                    if seq_idx >= t.length:
                        return Error()
                    off = base_offset + seq_idx * elem_size
                    result = self.apply_init_list(block_id, off, t.elem_type, elem)
                    if isinstance(result, Error):
                        return Error()
                    seq_idx += 1

        elif isinstance(t, UnionType):
            if not init.init_elems:
                return None
            elem = init.init_elems[0]
            first_name = next(iter(t.members))
            first_type = t.members[first_name]

            if isinstance(elem, InitMember):
                member_type = t.members.get(elem.member_iden)
                if member_type is None:
                    return Error()
                target = elem.expr_or_init
                if target is not None and isinstance(target, ExprNode):
                    val = self.load(self.expr(target))
                    if isinstance(val, Error):
                        return Error()
                    raw = MemConverter().to_mem_block(val)
                    return block.write_block(base_offset, raw)
            elif isinstance(elem, ExprNode):
                val = self.load(self.expr(elem))
                if isinstance(val, Error):
                    return Error()
                raw = MemConverter().to_mem_block(val)
                return block.write_block(base_offset, raw)

        return None

    ###
    def call_fun(self,
                 node: FunDecl,
                 args: list[ValueObject]) -> ExprResult | Error:
        assert node.body is not None

        saved_frames = self.scope.frames
        self.scope.frames = [ScopeFrame()]

        for i, param in enumerate(node.fun_type.params):
            if param.iden is None:
                continue
            if i >= len(args):
                self.scope.frames = saved_frames
                return Error()
            pt = self.resolve_type(param.param_type)
            if isinstance(pt, Error):
                self.scope.frames = saved_frames
                return Error()

            # Implicit conversion of argument to parameter type.
            arg = args[i]
            arg_type = self.val_obj_type(arg)
            if arg_type is not None and not self.types_match(arg_type, pt):
                converted = TypeConverter().cast(arg, pt)
                if not isinstance(converted, Error):
                    arg = converted

            result = self.scope.declare(param.iden, pt, arg)
            if isinstance(result, Error):
                self.scope.frames = saved_frames
                return Error()

        signal = self.stmt(node.body)

        self.scope.pop_all()
        self.scope.frames = saved_frames

        if isinstance(signal, ReturnSignal):
            return signal.value if signal.value is not None else IntValue(I32, 0)
        if isinstance(signal, Error):
            return Error()
        return IntValue(I32, 0)

    ###

    # Types.
    def resolve_void_type(self,
                          node: flint_ast.VoidType) -> TypeObject | Error:
        return Error()

    def resolve_nullptr_type(self,
                             node: flint_ast.NullPtrType) -> TypeObject | Error:
        return PtrType(None)

    def resolve_bool_type(self,
                          node: flint_ast.BoolType) -> TypeObject | Error:
        return BoolType()

    def resolve_char_type(self,
                          node: flint_ast.CharType) -> TypeObject | Error:
        size = CHAR_KIND_SIZE[node.kind]
        is_signed = node.sign_kind == SignKind.signed if node.sign_kind else True

        return IntType(size, size, is_signed)

    def resolve_int_type(self,
                         node: flint_ast.IntType) -> TypeObject | Error:
        size = INT_KIND_SIZE[node.kind]
        is_signed = node.sign_kind != SignKind.unsigned

        return IntType(size, size, is_signed)

    def resolve_bit_int_type(self,
                             node: flint_ast.BitIntType) -> TypeObject | Error:
        width_val: ValueObject | Error = self.load(self.expr(node.width_expr))
        if isinstance(width_val, Error):
            return width_val

        assert isinstance(width_val, IntValue)

        bits = width_val.value
        if bits <= 0:
            return Error()
        byte_size = (bits + 7) // 8
        is_signed = node.sign_kind != SignKind.unsigned
        return IntType(byte_size, byte_size, is_signed)

    def resolve_real_float_type(self,
                                node: flint_ast.RealFloatType) -> TypeObject | Error:
        size = REAL_FLOAT_KIND_SIZE[node.kind]
        return FloatType(size, size)

    def resolve_dec_float_type(self,
                               node: flint_ast.DecimalFloatType) -> TypeObject | Error:
        size = DECIMAL_FLOAT_KIND_SIZE[node.kind]
        return DecType(size, size)

    def resolve_complex_type(self,
                             node: flint_ast.ComplexType) -> TypeObject | Error:
        return Error()

    def resolve_imaginary_type(self,
                               node: flint_ast.ImaginaryType) -> TypeObject | Error:
        return Error()

    def resolve_ptr_type(self,
                         node: flint_ast.PtrType) -> TypeObject | Error:
        if isinstance(node.pointee, flint_ast.VoidType):
            return PtrType(None)

        pointee_type: TypeObject | Error = self.resolve_type(node.pointee)
        if isinstance(pointee_type, Error):
            return pointee_type

        return PtrType(pointee_type)

    def resolve_array_type(self,
                           node: flint_ast.ArrayType) -> TypeObject | Error:
        elem_type: TypeObject | Error = self.resolve_type(node.elem_type)
        if isinstance(elem_type, Error):
            return elem_type

        if node.is_unspec_vla or node.elem_count is None:
            return Error()

        count_val: ValueObject | Error = self.load(self.expr(node.elem_count))
        if isinstance(count_val, Error):
            return count_val

        if not isinstance(count_val, IntValue):
            return Error()

        if count_val.value <= 0:
            return Error()

        return ArrayType(elem_type, count_val.value)

    def resolve_enum_type(self,
                          node: flint_ast.EnumType) -> TypeObject | Error:
        if node.members is None:
            if node.iden is None:
                return Error()
            enum_type: EnumType | None = self.type_registry.enums.get(node.iden)
            if enum_type is None:
                return Error()
            return enum_type

        elem_type: IntType = I32
        if node.member_type is not None:
            resolved: TypeObject | Error = self.resolve_type(node.member_type)
            if isinstance(resolved, Error):
                return resolved
            if not isinstance(resolved, IntType):
                return Error()
            elem_type = resolved

        elems: dict[str, int] = {}
        next_val: int = 0

        for member in node.members:
            if member.expr is not None:
                val: ValueObject | Error = self.load(self.expr(member.expr))
                if isinstance(val, Error):
                    return val
                if not isinstance(val, IntValue):
                    return Error()
                next_val = val.value
            elems[member.iden] = next_val
            next_val += 1

        enum_type = EnumType(node.iden, elem_type, elems)

        if node.iden is not None:
            self.type_registry.enums[node.iden] = enum_type

        return enum_type

    def resolve_struct_type(self,
                            node: flint_ast.StructType) -> TypeObject | Error:
        if node.members is None:
            if node.iden is None:
                return Error()
            struct_type: StructType | None = self.type_registry.structs.get(node.iden)
            if struct_type is None:
                return Error()
            return struct_type

        members: dict[str, TypeObject] = {}
        for member_decl in node.members:
            if not isinstance(member_decl, VarDecl):
                continue
            member_type: TypeObject | Error = self.resolve_type(member_decl.var_type)
            if isinstance(member_type, Error):
                return member_type
            members[member_decl.iden] = member_type

        struct_type = StructType(node.iden, members)

        if node.iden is not None:
            self.type_registry.structs[node.iden] = struct_type

        return struct_type

    def resolve_union_type(self,
                           node: flint_ast.UnionType) -> TypeObject | Error:
        if node.members is None:
            if node.iden is None:
                return Error()
            union_type: UnionType | None = self.type_registry.unions.get(node.iden)
            if union_type is None:
                return Error()
            return union_type

        members: dict[str, TypeObject] = {}
        for member_decl in node.members:
            if not isinstance(member_decl, VarDecl):
                continue
            member_type: TypeObject | Error = self.resolve_type(member_decl.var_type)
            if isinstance(member_type, Error):
                return member_type
            members[member_decl.iden] = member_type

        union_type = UnionType(node.iden, members)

        if node.iden is not None:
            self.type_registry.unions[node.iden] = union_type

        return union_type

    def resolve_atomic_type(self,
                            node: flint_ast.AtomicType) -> TypeObject | Error:
        return self.resolve_type(node.base_type)

    def resolve_typeof_type(self,
                            node: flint_ast.TypeOfType) -> TypeObject | Error:
        if isinstance(node.expr_or_type, TypeNode):
            return self.resolve_type(node.expr_or_type)

        val: ValueObject | Error = self.load(self.expr(node.expr_or_type))
        if isinstance(val, Error):
            return val

        t: TypeObject | None = self.val_obj_type(val)
        if t is None:
            return Error()

        return t

    def resolve_typeof_unqual_type(self,
                                   node: flint_ast.TypeOfUnqualType) -> TypeObject | Error:
        return self.resolve_typeof_type(flint_ast.TypeOfType(node.expr_or_type))

    def resolve_typedef_type(self,
                             node: flint_ast.TypeDefType) -> TypeObject | Error:
        type_obj: TypeObject | None = self.type_registry.typedefs.get(node.iden)

        if type_obj is None:
            return Error()

        return type_obj

    def resolve_qualified_type(self,
                               node: flint_ast.QualifiedType) -> TypeObject | Error:
        return self.resolve_type(node.base_type)

    ###
    def resolve_type(self, node: TypeNode) -> TypeObject | Error:
        if isinstance(node, flint_ast.VoidType):
            return self.resolve_void_type(node)

        if isinstance(node, flint_ast.NullPtrType):
            return self.resolve_nullptr_type(node)

        if isinstance(node, flint_ast.BoolType):
            return self.resolve_bool_type(node)

        if isinstance(node, flint_ast.CharType):
            return self.resolve_char_type(node)

        if isinstance(node, flint_ast.IntType):
            return self.resolve_int_type(node)

        if isinstance(node, flint_ast.BitIntType):
            return self.resolve_bit_int_type(node)

        if isinstance(node, flint_ast.RealFloatType):
            return self.resolve_real_float_type(node)

        if isinstance(node, flint_ast.DecimalFloatType):
            return self.resolve_dec_float_type(node)

        if isinstance(node, flint_ast.ComplexType):
            return self.resolve_complex_type(node)

        if isinstance(node, flint_ast.ImaginaryType):
            return self.resolve_imaginary_type(node)

        if isinstance(node, flint_ast.PtrType):
            return self.resolve_ptr_type(node)

        if isinstance(node, flint_ast.ArrayType):
            return self.resolve_array_type(node)

        if isinstance(node, flint_ast.EnumType):
            return self.resolve_enum_type(node)

        if isinstance(node, flint_ast.StructType):
            return self.resolve_struct_type(node)

        if isinstance(node, flint_ast.UnionType):
            return self.resolve_union_type(node)

        if isinstance(node, flint_ast.AtomicType):
            return self.resolve_atomic_type(node)

        if isinstance(node, flint_ast.TypeOfType):
            return self.resolve_typeof_type(node)

        if isinstance(node, flint_ast.TypeOfUnqualType):
            return self.resolve_typeof_unqual_type(node)

        if isinstance(node, flint_ast.TypeDefType):
            return self.resolve_typedef_type(node)

        if isinstance(node, flint_ast.QualifiedType):
            return self.resolve_qualified_type(node)

        assert False

    # Expressions.
    def iden_expr(self, node: IdenExpr) -> ExprResult | Error:
        var: ScopeVar | Error = self.scope.lookup(node.iden)
        if not isinstance(var, Error):
            return ScopeLValue(node.iden)

        for enum_type in self.type_registry.enums.values():
            if node.iden in enum_type.elems:
                return EnumValue(
                    enum_type,
                    IntValue(enum_type.elem_type, enum_type.elems[node.iden])
                )

        # Function identifiers used as direct call targets are resolved
        # in call_expr before this path is reached; return Error for any
        # other use (function pointers are not supported).
        return Error()

    def nullptr_lit_expr(self, node: NullPtrLitExpr) -> ExprResult | Error:
        return PtrValue(PtrType(None), 0, 0)

    def bool_lit_expr(self, node: BoolLitExpr) -> ExprResult | Error:
        return BoolValue(node.bool_expr)

    def int_lit_expr(self, node: IntLitExpr) -> ExprResult | Error:
        int_type = self.resolve_type(node.int_type)
        if isinstance(int_type, Error):
            return int_type

        if not isinstance(int_type, IntType):
            return Error()

        return IntValue(int_type, node.int_expr)

    def real_float_lit_expr(self, node: RealFloatLitExpr) -> ExprResult | Error:
        float_type = self.resolve_type(node.float_type)
        if isinstance(float_type, Error):
            return float_type
        if not isinstance(float_type, FloatType):
            return Error()
        return FloatValue(float_type, node.float_expr)

    def dec_float_lit_expr(self, node: DecFloatLitExpr) -> ExprResult | Error:
        dec_type = self.resolve_type(node.float_type)
        if isinstance(dec_type, Error):
            return dec_type
        if not isinstance(dec_type, DecType):
            return Error()
        return DecValue(dec_type, node.float_expr)

    def char_lit_expr(self, node: CharLitExpr) -> ExprResult | Error:
        char_type: IntType = I8
        kind: CharKind = node.char_type.kind

        if kind == CharKind.char8:
            char_type = U8

        elif kind == CharKind.char16:
            char_type = U16

        elif kind == CharKind.char32 or kind == CharKind.wchar:
            char_type = U32

        return IntValue(char_type, ord(node.char_expr))

    def str_lit_expr(self, node: StrLitExpr) -> ExprResult | Error:
        encoded = node.str_expr.encode('utf-8') + b'\x00'

        block_id = self.mem.alloc(MemoryType.data, len(encoded))
        if isinstance(block_id, Error):
            return block_id

        mem_block_ref = self.mem.get(block_id)
        if isinstance(mem_block_ref, Error):
            return mem_block_ref

        for i, byte in enumerate(encoded):
            result = mem_block_ref.write(i, byte)
            if isinstance(result, Error):
                return result

        size = CHAR_KIND_SIZE[node.char_type.kind]
        is_signed = (node.char_type.sign_kind == SignKind.signed
                     if node.char_type.sign_kind else True)
        elem_type = IntType(size, size, is_signed)
        ptr_type = PtrType(elem_type)
        return PtrValue(ptr_type, block_id, 0)

    def generic_sel_expr(self, node: GenericSelExpr) -> ExprResult | Error:
        ctrl: ValueObject | Error = self.load(self.expr(node.ctrl_expr))
        if isinstance(ctrl, Error):
            return ctrl

        ctrl_type: TypeObject | None = self.val_obj_type(ctrl)
        default_expr: ExprNode | None = node.assoc_table.get(None)

        for assoc_node_type, assoc_expr in node.assoc_table.items():
            if assoc_node_type is None:
                continue

            node_type: TypeObject | Error = self.resolve_type(assoc_node_type)
            if isinstance(node_type, Error):
                continue

            if ctrl_type is not None and self.types_match(node_type, ctrl_type):
                return self.expr(assoc_expr)

        if default_expr is not None:
            return self.expr(default_expr)

        return Error()

    def array_sub_expr(self, node: ArraySubExpr) -> ExprResult | Error:
        base: ValueObject | Error = self.load(self.expr(node.base_expr))
        if isinstance(base, Error):
            return base

        idx: ValueObject | Error = self.load(self.expr(node.idx_expr))
        if isinstance(idx, Error):
            return idx

        # Support both ptr[i] and i[ptr].
        if isinstance(idx, PtrValue) and isinstance(base, IntValue):
            base, idx = idx, base

        if not isinstance(base, PtrValue) or not isinstance(idx, IntValue):
            return Error()

        if base.ptr_type is None or base.ptr_type.target_type is None:
            return Error()

        target_type = base.ptr_type.target_type
        new_offset = base.offset + idx.value * target_type.size

        if base.block_id == 0:
            return Error()

        return MemoryLValue(target_type, base.block_id, new_offset)

    def call_expr(self, node: CallExpr) -> ExprResult | Error:
        callee_iden = None

        if isinstance(node.callee_expr, IdenExpr):
            callee_iden = node.callee_expr.iden

        args: list[ValueObject] | Error = self.eval_args(node.arg_exprs)
        if isinstance(args, Error):
            return args

        if callee_iden is not None:
            fun = self.functions.get(callee_iden)
            if fun is not None:
                return self.call_fun(fun, args)

        return Error()

    def member_arrow_expr(self, node: MemberExpr) -> ExprResult | Error:
        assert node.is_arrow

        ptr: ValueObject | Error = self.load(self.expr(node.base_expr))
        if isinstance(ptr, Error):
            return ptr

        if not isinstance(ptr, PtrValue):
            return Error()

        if ptr.ptr_type is None or ptr.ptr_type.target_type is None:
            return Error()

        target_type: TypeObject = ptr.ptr_type.target_type

        offset: int = ptr.offset
        member_type: TypeObject | None = None

        if isinstance(target_type, StructType):
            member = target_type.members.get(node.member_iden)
            if member is None:
                return Error()

            offset += member.offset
            member_type = member.member_type

        elif isinstance(target_type, UnionType):
            member_type = target_type.members.get(node.member_iden)
            if member_type is None:
                return Error()

        else:
            return Error()

        if member_type is None:
            return Error()

        if ptr.block_id == 0:
            return Error()

        return MemoryLValue(member_type, ptr.block_id, offset)

    def member_dot_mem_lvalue(self,
                              node: MemberExpr,
                              base: MemoryLValue) -> ExprResult | Error:
        obj_type = base.obj_type

        offset: int = base.offset
        member_type: TypeObject | None = None

        if isinstance(obj_type, StructType):
            member = obj_type.members.get(node.member_iden)
            if member is None:
                return Error()

            offset += member.offset
            member_type = member.member_type

        elif isinstance(obj_type, UnionType):
            member_type = obj_type.members.get(node.member_iden)
            if member_type is None:
                return Error()

        else:
            return Error()

        if member_type is None:
            return Error()

        return MemoryLValue(member_type, base.block_id, offset)

    def member_dot_scope_lvalue(self,
                                node: MemberExpr,
                                base: ScopeLValue) -> ExprResult | Error:
        var: ScopeVar | Error = self.scope.lookup(base.iden)
        if isinstance(var, Error):
            return var

        var_type = var.var_type

        member_type: TypeObject | None = None
        offset: int = 0

        if isinstance(var_type, StructType):
            member = var_type.members.get(node.member_iden)
            if member is None:
                return Error()

            offset += member.offset
            member_type = member.member_type

        elif isinstance(var_type, UnionType):
            member_type = var_type.members.get(node.member_iden)
            if member_type is None:
                return Error()

        else:
            return Error()

        if member_type is None:
            return Error()

        if var.block_id is not None:
            block_id = var.block_id
        else:
            block_id = self.scope.promote(base.iden)

            if isinstance(block_id, Error):
                return block_id

        return MemoryLValue(member_type, block_id, offset)

    def member_dot_expr(self, node: MemberExpr) -> ExprResult | Error:
        assert not node.is_arrow

        base: ExprResult | Error = self.expr(node.base_expr)
        if isinstance(base, Error):
            return base

        if isinstance(base, MemoryLValue):
            return self.member_dot_mem_lvalue(node, base)

        if isinstance(base, ScopeLValue):
            return self.member_dot_scope_lvalue(node, base)

        # base is a value (e.g. compound literal): not an lvalue, error.
        return Error()

    def member_expr(self, node: MemberExpr) -> ExprResult | Error:
        if node.is_arrow:
            return self.member_arrow_expr(node)
        else:
            return self.member_dot_expr(node)

    def compound_lit_expr(self, node: CompoundLitExpr) -> ExprResult | Error:
        lit_type: TypeObject | Error = self.resolve_type(node.expr_type)
        if isinstance(lit_type, Error):
            return lit_type

        if lit_type.size == 0:
            return Error()

        block_id: int | Error = self.mem.alloc(
            MemoryType.stack,
            lit_type.size
        )

        if isinstance(block_id, Error):
            return block_id

        result = self.apply_init_list(block_id, 0, lit_type, node.init)
        if isinstance(result, Error):
            return result

        return MemoryLValue(lit_type, block_id, 0)

    def cast_expr(self, node: CastExpr) -> ExprResult | Error:
        val_obj: ValueObject | Error = self.load(self.expr(node.expr))
        if isinstance(val_obj, Error):
            return val_obj

        new_type: TypeObject | Error = self.resolve_type(node.expr_type)
        if isinstance(new_type, Error):
            return new_type

        return TypeConverter().cast(val_obj, new_type)

    def sizeof_expr(self, node: SizeOfExpr) -> ExprResult | Error:
        if isinstance(node.expr_or_type, TypeNode):
            type_obj = self.resolve_type(node.expr_or_type)
            if isinstance(type_obj, Error):
                return type_obj
            return IntValue(SIZE_T, type_obj.size)

        # sizeof(expr) — evaluate only for type, ignore side effects is
        # the C standard, but we evaluate fully here for simplicity.
        val = self.load(self.expr(node.expr_or_type))
        if isinstance(val, Error):
            return val
        type_obj = self.val_obj_type(val)
        if type_obj is None:
            return Error()
        return IntValue(SIZE_T, type_obj.size)

    def alignof_expr(self, node: AlignOfExpr) -> ExprResult | Error:
        type_obj = self.resolve_type(node.align_type)
        if isinstance(type_obj, Error):
            return type_obj
        return IntValue(SIZE_T, type_obj.alignment)

    def una_inc(self, val_obj: ValueObject) -> ValueObject | Error:
        if isinstance(val_obj, IntValue):
            int_type: IntType = val_obj.value_type
            return self.bin_add(val_obj, IntValue(int_type, 1))

        if isinstance(val_obj, PtrValue):
            return self.bin_add(val_obj, IntValue(U64, 1))

        if isinstance(val_obj, FloatValue):
            return FloatValue(val_obj.value_type, val_obj.value + 1.0)

        return Error()

    def una_dec(self, val_obj: ValueObject) -> ValueObject | Error:
        if isinstance(val_obj, IntValue):
            int_type: IntType = val_obj.value_type
            return self.bin_sub(val_obj, IntValue(int_type, 1))

        if isinstance(val_obj, PtrValue):
            return self.bin_sub(val_obj, IntValue(U64, 1))

        if isinstance(val_obj, FloatValue):
            return FloatValue(val_obj.value_type, val_obj.value - 1.0)

        return Error()

    def una_prefix_inc(self,
                       lvalue: ExprResult,
                       val_obj: ValueObject) -> ExprResult | Error:
        new_val_obj: ValueObject | Error = self.una_inc(val_obj)
        if isinstance(new_val_obj, Error):
            return new_val_obj

        result: None | Error = self.store(lvalue, new_val_obj)
        if isinstance(result, Error):
            return result

        return new_val_obj

    def una_prefix_dec(self,
                       lvalue: ExprResult,
                       val_obj: ValueObject) -> ExprResult | Error:
        new_val_obj: ValueObject | Error = self.una_dec(val_obj)
        if isinstance(new_val_obj, Error):
            return new_val_obj

        result: None | Error = self.store(lvalue, new_val_obj)
        if isinstance(result, Error):
            return result

        return new_val_obj

    def una_addr_of(self, operand: ExprResult) -> ExprResult | Error:
        if isinstance(operand, MemoryLValue):
            ptr_type = PtrType(operand.obj_type)
            return PtrValue(ptr_type, operand.block_id, operand.offset)

        if isinstance(operand, ScopeLValue):
            block_id: int | Error = self.scope.promote(operand.iden)

            if isinstance(block_id, Error):
                return block_id

            var = self.scope.lookup(operand.iden)
            if isinstance(var, Error):
                return var

            ptr_type = PtrType(var.var_type)
            return PtrValue(ptr_type, block_id, 0)

        return Error()

    def una_deref(self, val_obj: ValueObject) -> ExprResult | Error:
        if not isinstance(val_obj, PtrValue):
            return Error()

        if val_obj.ptr_type is None or val_obj.ptr_type.target_type is None:
            return Error()

        if val_obj.block_id == 0:
            return Error()

        target_type = val_obj.ptr_type.target_type

        return MemoryLValue(
            target_type,
            val_obj.block_id,
            val_obj.offset
        )

    def una_plus(self, val_obj: ValueObject) -> ExprResult | Error:
        promoted = TypeConverter().promote(val_obj)
        if isinstance(promoted, Error):
            return promoted
        return promoted

    def una_neg(self, val_obj: ValueObject) -> ExprResult | Error:
        if isinstance(val_obj, IntValue):
            return self.int_norm(val_obj.value_type, -val_obj.value)

        if isinstance(val_obj, FloatValue):
            return FloatValue(val_obj.value_type, -val_obj.value)

        if isinstance(val_obj, DecValue):
            ctx = TypeConverter().dec_context(val_obj.value_type)
            return DecValue(val_obj.value_type, ctx.minus(val_obj.value))

        return Error()

    def una_bit_neg(self, val_obj: ValueObject) -> ExprResult | Error:
        # Integer promotions first.
        promoted = TypeConverter().promote(val_obj)
        if isinstance(promoted, Error):
            return promoted
        if not isinstance(promoted, IntValue):
            return Error()
        return self.int_norm(promoted.value_type, ~promoted.value)

    def una_bool_neg(self, val_obj: ValueObject) -> ExprResult | Error:
        result = TypeConverter().cast(val_obj, BoolType())
        if isinstance(result, Error):
            return result
        assert isinstance(result, BoolValue)
        return BoolValue(not result.value)

    def una_postfix_inc(self,
                        lvalue: ExprResult,
                        val_obj: ValueObject) -> ExprResult | Error:
        new_val_obj: ValueObject | Error = self.una_inc(val_obj)
        if isinstance(new_val_obj, Error):
            return new_val_obj

        result: None | Error = self.store(lvalue, new_val_obj)
        if isinstance(result, Error):
            return result

        # C semantics: postfix returns the value BEFORE increment.
        return val_obj

    def una_postfix_dec(self,
                        lvalue: ExprResult,
                        val_obj: ValueObject) -> ExprResult | Error:
        new_val_obj: ValueObject | Error = self.una_dec(val_obj)
        if isinstance(new_val_obj, Error):
            return new_val_obj

        result: None | Error = self.store(lvalue, new_val_obj)
        if isinstance(result, Error):
            return result

        # C semantics: postfix returns the value BEFORE decrement.
        return val_obj

    def una_expr(self, node: OpExpr) -> ExprResult | Error:
        assert len(node.exprs) == 1

        expr_res: ExprResult | Error = self.expr(node.exprs[0])
        if isinstance(expr_res, Error):
            return expr_res

        if node.op == UnaPrefOpTag.addr_of:
            return self.una_addr_of(expr_res)

        val_obj: ValueObject | Error = self.load(expr_res)
        if isinstance(val_obj, Error):
            return val_obj

        if node.op == UnaPrefOpTag.prefix_inc:
            return self.una_prefix_inc(expr_res, val_obj)

        if node.op == UnaPrefOpTag.prefix_dec:
            return self.una_prefix_dec(expr_res, val_obj)

        if node.op == UnaPrefOpTag.plus:
            return self.una_plus(val_obj)

        if node.op == UnaPrefOpTag.neg:
            return self.una_neg(val_obj)

        if node.op == UnaPrefOpTag.bit_neg:
            return self.una_bit_neg(val_obj)

        if node.op == UnaPrefOpTag.bool_neg:
            return self.una_bool_neg(val_obj)

        if node.op == UnaPrefOpTag.deref:
            return self.una_deref(val_obj)

        if node.op == UnaPostOpTag.postfix_inc:
            return self.una_postfix_inc(expr_res, val_obj)

        if node.op == UnaPostOpTag.postfix_dec:
            return self.una_postfix_dec(expr_res, val_obj)

        assert False

    BinOperands = tuple[ValueObject, ValueObject]

    def bool_neg(self, left: BoolValue) -> BoolValue:
        return BoolValue(not left.value)

    def int_norm(self,
                 int_type: IntType,
                 int_value: int) -> IntValue:
        bits = int_type.size * CHAR_BIT_SIZE
        # Wrap into the unsigned bit range, then reinterpret as signed.
        int_value %= (1 << bits)
        if int_type.is_signed and int_value >= (1 << (bits - 1)):
            int_value -= (1 << bits)
        return IntValue(int_type, int_value)

    def int_add(self, left: IntValue, right: IntValue) -> IntValue:
        return self.int_norm(left.value_type, left.value + right.value)

    def int_sub(self, left: IntValue, right: IntValue) -> IntValue:
        return self.int_norm(left.value_type, left.value - right.value)

    def int_mul(self, left: IntValue, right: IntValue) -> IntValue:
        return self.int_norm(left.value_type, left.value * right.value)

    def int_div(self, left: IntValue, right: IntValue) -> IntValue | Error:
        if right.value == 0:
            return Error()
        # C truncates toward zero.
        result = int(left.value / right.value)
        return self.int_norm(left.value_type, result)

    def int_mod(self, left: IntValue, right: IntValue) -> IntValue | Error:
        if right.value == 0:
            return Error()
        # C remainder: result has the sign of the dividend.
        int_value = left.value - int(left.value / right.value) * right.value
        return self.int_norm(left.value_type, int_value)

    def int_bit_and(self, left: IntValue, right: IntValue) -> IntValue:
        return self.int_norm(left.value_type, left.value & right.value)

    def int_bit_or(self, left: IntValue, right: IntValue) -> IntValue:
        return self.int_norm(left.value_type, left.value | right.value)

    def int_bit_xor(self, left: IntValue, right: IntValue) -> IntValue:
        return self.int_norm(left.value_type, left.value ^ right.value)

    def int_bit_neg(self, val: IntValue) -> IntValue:
        return self.int_norm(val.value_type, ~val.value)

    def int_shl(self, left: IntValue, shift: int) -> IntValue | Error:
        bits = left.value_type.size * CHAR_BIT_SIZE
        if shift < 0 or shift >= bits:
            return Error()
        return self.int_norm(left.value_type, left.value << shift)

    def int_shr(self, left: IntValue, shift: int) -> IntValue | Error:
        bits = left.value_type.size * CHAR_BIT_SIZE
        if shift < 0 or shift >= bits:
            return Error()
        return self.int_norm(left.value_type, left.value >> shift)

    def int_eq(self, left: IntValue, right: IntValue) -> BoolValue:
        return BoolValue(left.value == right.value)

    def int_ne(self, left: IntValue, right: IntValue) -> BoolValue:
        return BoolValue(left.value != right.value)

    def int_lt(self, left: IntValue, right: IntValue) -> BoolValue:
        return BoolValue(left.value < right.value)

    def int_le(self, left: IntValue, right: IntValue) -> BoolValue:
        return BoolValue(left.value <= right.value)

    def int_gt(self, left: IntValue, right: IntValue) -> BoolValue:
        return BoolValue(left.value > right.value)

    def int_ge(self, left: IntValue, right: IntValue) -> BoolValue:
        return BoolValue(left.value >= right.value)

    def float_add(self, left: FloatValue, right: FloatValue) -> FloatValue:
        return FloatValue(left.value_type, left.value + right.value)

    def float_sub(self, left: FloatValue, right: FloatValue) -> FloatValue:
        return FloatValue(left.value_type, left.value - right.value)

    def float_mul(self, left: FloatValue, right: FloatValue) -> FloatValue:
        return FloatValue(left.value_type, left.value * right.value)

    def float_div(self, left: FloatValue, right: FloatValue) -> FloatValue | Error:
        if right.value == 0.0:
            return Error()
        return FloatValue(left.value_type, left.value / right.value)

    def float_eq(self, left: FloatValue, right: FloatValue) -> BoolValue:
        return BoolValue(left.value == right.value)

    def float_ne(self, left: FloatValue, right: FloatValue) -> BoolValue:
        return BoolValue(left.value != right.value)

    def float_lt(self, left: FloatValue, right: FloatValue) -> BoolValue:
        return BoolValue(left.value < right.value)

    def float_le(self, left: FloatValue, right: FloatValue) -> BoolValue:
        return BoolValue(left.value <= right.value)

    def float_gt(self, left: FloatValue, right: FloatValue) -> BoolValue:
        return BoolValue(left.value > right.value)

    def float_ge(self, left: FloatValue, right: FloatValue) -> BoolValue:
        return BoolValue(left.value >= right.value)

    def dec_context(self, val_type: DecType) -> decimal.Context:
        if val_type.size == DECIMAL_FLOAT_KIND_SIZE[DecimalFloatKind.decimal32]:
            return ctx32

        if val_type.size == DECIMAL_FLOAT_KIND_SIZE[DecimalFloatKind.decimal64]:
            return ctx64

        if val_type.size == DECIMAL_FLOAT_KIND_SIZE[DecimalFloatKind.decimal128]:
            return ctx128

        assert False

    def dec_add(self, left: DecValue, right: DecValue) -> DecValue | Error:
        val_type: DecType = left.value_type
        ctx: decimal.Context = self.dec_context(val_type)

        try:
            val: Decimal = ctx.add(left.value, right.value)

        except decimal.Overflow:
            return Error()

        except decimal.Underflow:
            return Error()

        except decimal.InvalidOperation:
            return Error()

        return DecValue(val_type, val)

    def dec_sub(self, left: DecValue, right: DecValue) -> DecValue | Error:
        val_type: DecType = left.value_type
        ctx: decimal.Context = self.dec_context(val_type)

        try:
            val: Decimal = ctx.subtract(left.value, right.value)

        except decimal.Overflow:
            return Error()

        except decimal.Underflow:
            return Error()

        except decimal.InvalidOperation:
            return Error()

        return DecValue(val_type, val)

    def dec_mul(self, left: DecValue, right: DecValue) -> DecValue | Error:
        val_type: DecType = left.value_type
        ctx: decimal.Context = self.dec_context(val_type)

        try:
            val: Decimal = ctx.multiply(left.value, right.value)

        except decimal.Overflow:
            return Error()

        except decimal.Underflow:
            return Error()

        except decimal.InvalidOperation:
            return Error()

        return DecValue(val_type, val)

    def dec_div(self, left: DecValue, right: DecValue) -> DecValue | Error:
        if right.value == Decimal(0):
            return Error()

        val_type: DecType = left.value_type
        ctx: decimal.Context = self.dec_context(val_type)

        try:
            val: Decimal = ctx.divide(left.value, right.value)

        except decimal.Overflow:
            return Error()

        except decimal.Underflow:
            return Error()

        except decimal.InvalidOperation:
            return Error()

        return DecValue(val_type, val)

    def dec_eq(self, left: DecValue, right: DecValue) -> BoolValue:
        return BoolValue(left.value == right.value)

    def dec_ne(self, left: DecValue, right: DecValue) -> BoolValue:
        return BoolValue(left.value != right.value)

    def dec_lt(self, left: DecValue, right: DecValue) -> BoolValue:
        return BoolValue(left.value < right.value)

    def dec_le(self, left: DecValue, right: DecValue) -> BoolValue:
        return BoolValue(left.value <= right.value)

    def dec_gt(self, left: DecValue, right: DecValue) -> BoolValue:
        return BoolValue(left.value > right.value)

    def dec_ge(self, left: DecValue, right: DecValue) -> BoolValue:
        return BoolValue(left.value >= right.value)

    def ptr_verify_bounds(self, ptr: PtrValue) -> None | Error:
        if ptr.block_id == 0:
            # Null pointer; let the caller decide whether this is fatal.
            return None

        mem_block: MemoryBlock | Error = self.mem.get(ptr.block_id)
        if isinstance(mem_block, Error):
            return mem_block

        # Offset may equal size (one-past-the-end is allowed for
        # pointer arithmetic, though not for dereferencing).
        if not (-1 < ptr.offset <= mem_block.size()):
            return Error()

        return None

    def ptr_verify_bounds_both(self,
                               left: PtrValue,
                               right: PtrValue) -> None | Error:
        result: None | Error = self.ptr_verify_bounds(left)
        if isinstance(result, Error):
            return result

        return self.ptr_verify_bounds(right)

    def ptr_add(self,
                left: PtrValue,
                right: IntValue) -> PtrValue | Error:
        result: None | Error = self.ptr_verify_bounds(left)
        if isinstance(result, Error):
            return result

        if left.ptr_type is None or left.ptr_type.target_type is None:
            return Error()

        elem_size = left.ptr_type.target_type.size
        new_ptr: PtrValue = PtrValue(
            left.ptr_type,
            left.block_id,
            left.offset + right.value * elem_size
        )

        result = self.ptr_verify_bounds(new_ptr)
        if isinstance(result, Error):
            return result

        return new_ptr

    def ptr_sub(self,
                left: PtrValue,
                right: PtrValue | IntValue) -> PtrValue | IntValue | Error:
        result: None | Error = self.ptr_verify_bounds(left)
        if isinstance(result, Error):
            return result

        if isinstance(right, IntValue):
            if left.ptr_type is None or left.ptr_type.target_type is None:
                return Error()

            elem_size = left.ptr_type.target_type.size
            new_ptr: PtrValue = PtrValue(
                left.ptr_type,
                left.block_id,
                left.offset - right.value * elem_size
            )

            result = self.ptr_verify_bounds(new_ptr)
            if isinstance(result, Error):
                return result

            return new_ptr

        # Pointer minus pointer: yields ptrdiff_t (signed 64-bit).
        result = self.ptr_verify_bounds(right)
        if isinstance(result, Error):
            return result

        if left.block_id != right.block_id:
            return Error()

        if left.ptr_type is None or left.ptr_type.target_type is None:
            return Error()

        elem_size = left.ptr_type.target_type.size

        return self.int_sub(
            IntValue(I64, left.offset // elem_size),
            IntValue(I64, right.offset // elem_size)
        )

    def ptr_eq(self, left: PtrValue, right: PtrValue) -> BoolValue | Error:
        cond: bool = left.block_id == right.block_id and \
                     left.offset == right.offset

        return BoolValue(cond)

    def ptr_ne(self, left: PtrValue, right: PtrValue) -> BoolValue | Error:
        val_obj: BoolValue | Error = self.ptr_eq(left, right)
        if isinstance(val_obj, Error):
            return val_obj

        return self.bool_neg(val_obj)

    def ptr_lt(self, left: PtrValue, right: PtrValue) -> BoolValue | Error:
        if left.block_id != right.block_id:
            return Error()
        return BoolValue(left.offset < right.offset)

    def ptr_le(self, left: PtrValue, right: PtrValue) -> BoolValue | Error:
        if left.block_id != right.block_id:
            return Error()
        return BoolValue(left.offset <= right.offset)

    def ptr_gt(self, left: PtrValue, right: PtrValue) -> BoolValue | Error:
        if left.block_id != right.block_id:
            return Error()
        return BoolValue(left.offset > right.offset)

    def ptr_ge(self, left: PtrValue, right: PtrValue) -> BoolValue | Error:
        if left.block_id != right.block_id:
            return Error()
        return BoolValue(left.offset >= right.offset)

    # Binary operation helpers.
    # Callers are expected to have applied usual arithmetic conversions
    # (UAC) already so both operands share the same type.

    def bin_bit_and(self,
                    left: ValueObject,
                    right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_bit_and(left, right)
        return Error()

    def bin_mul(self,
                left: ValueObject,
                right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_mul(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_mul(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_mul(left, right)

        return Error()

    def bin_add(self,
                left: ValueObject,
                right: ValueObject) -> ExprResult | Error:
        if isinstance(left, PtrValue) and isinstance(right, IntValue):
            return self.ptr_add(left, right)

        if isinstance(left, IntValue) and isinstance(right, PtrValue):
            return self.ptr_add(right, left)

        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_add(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_add(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_add(left, right)

        return Error()

    def bin_sub(self,
                left: ValueObject,
                right: ValueObject) -> ExprResult | Error:
        if isinstance(left, PtrValue):
            return self.ptr_sub(left, right)

        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_sub(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_sub(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_sub(left, right)

        return Error()

    def bin_div(self,
                left: ValueObject,
                right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_div(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_div(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_div(left, right)

        return Error()

    def bin_mod(self,
                left: ValueObject,
                right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_mod(left, right)

        return Error()

    def bin_shl(self,
                left: ValueObject,
                right: ValueObject) -> ExprResult | Error:
        # For shifts, only the left operand's type matters for the result.
        # Right operand is the shift count and may have a different type.
        if not isinstance(left, IntValue) or not isinstance(right, IntValue):
            return Error()
        promoted_left = TypeConverter().promote(left)
        if isinstance(promoted_left, Error):
            return promoted_left
        assert isinstance(promoted_left, IntValue)
        return self.int_shl(promoted_left, right.value)

    def bin_shr(self,
                left: ValueObject,
                right: ValueObject) -> ExprResult | Error:
        if not isinstance(left, IntValue) or not isinstance(right, IntValue):
            return Error()
        promoted_left = TypeConverter().promote(left)
        if isinstance(promoted_left, Error):
            return promoted_left
        assert isinstance(promoted_left, IntValue)
        return self.int_shr(promoted_left, right.value)

    def bin_lt(self,
               left: ValueObject,
               right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_lt(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_lt(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_lt(left, right)

        if isinstance(left, PtrValue) and isinstance(right, PtrValue):
            return self.ptr_lt(left, right)

        return Error()

    def bin_gt(self,
               left: ValueObject,
               right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_gt(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_gt(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_gt(left, right)

        if isinstance(left, PtrValue) and isinstance(right, PtrValue):
            return self.ptr_gt(left, right)

        return Error()

    def bin_le(self,
               left: ValueObject,
               right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_le(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_le(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_le(left, right)

        if isinstance(left, PtrValue) and isinstance(right, PtrValue):
            return self.ptr_le(left, right)

        return Error()

    def bin_ge(self,
               left: ValueObject,
               right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_ge(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_ge(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_ge(left, right)

        if isinstance(left, PtrValue) and isinstance(right, PtrValue):
            return self.ptr_ge(left, right)

        return Error()

    def bin_eq(self,
               left: ValueObject,
               right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_eq(left, right)

        if isinstance(left, FloatValue) and isinstance(right, FloatValue):
            return self.float_eq(left, right)

        if isinstance(left, DecValue) and isinstance(right, DecValue):
            return self.dec_eq(left, right)

        if isinstance(left, PtrValue) and isinstance(right, PtrValue):
            return self.ptr_eq(left, right)

        # nullptr == nullptr
        if isinstance(left, PtrValue) and isinstance(right, IntValue):
            return BoolValue(left.block_id == 0 and right.value == 0)

        if isinstance(left, IntValue) and isinstance(right, PtrValue):
            return BoolValue(right.block_id == 0 and left.value == 0)

        return Error()

    def bin_ne(self,
               left: ValueObject,
               right: ValueObject) -> ExprResult | Error:
        eq = self.bin_eq(left, right)
        if isinstance(eq, Error):
            return eq
        assert isinstance(eq, BoolValue)
        return self.bool_neg(eq)

    def bin_bit_xor(self,
                    left: ValueObject,
                    right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_bit_xor(left, right)
        return Error()

    def bin_bit_or(self,
                   left: ValueObject,
                   right: ValueObject) -> ExprResult | Error:
        if isinstance(left, IntValue) and isinstance(right, IntValue):
            return self.int_bit_or(left, right)
        return Error()

    def bin_op_assign(self,
                      op: BinOpTag,
                      lvalue: ExprResult,
                      left: ValueObject,
                      right: ValueObject) -> ExprResult | Error:
        new_val: ValueObject | Error = None

        if op == BinOpTag.mul_assign:
            new_val = self.bin_mul(left, right)

        elif op == BinOpTag.div_assign:
            new_val = self.bin_div(left, right)

        elif op == BinOpTag.mod_assign:
            new_val = self.bin_mod(left, right)

        elif op == BinOpTag.add_assign:
            new_val = self.bin_add(left, right)

        elif op == BinOpTag.sub_assign:
            new_val = self.bin_sub(left, right)

        elif op == BinOpTag.shl_assign:
            new_val = self.bin_shl(left, right)

        elif op == BinOpTag.shr_assign:
            new_val = self.bin_shr(left, right)

        elif op == BinOpTag.bit_and_assign:
            new_val = self.bin_bit_and(left, right)

        elif op == BinOpTag.bit_xor_assign:
            new_val = self.bin_bit_xor(left, right)

        elif op == BinOpTag.bit_or_assign:
            new_val = self.bin_bit_or(left, right)

        else:
            assert False

        if isinstance(new_val, Error):
            return new_val

        assert isinstance(new_val, ValueObject)

        # Cast result back to the lvalue's declared type.
        lval_type = None
        if isinstance(lvalue, ScopeLValue):
            var = self.scope.lookup(lvalue.iden)
            if not isinstance(var, Error):
                lval_type = var.var_type
        elif isinstance(lvalue, MemoryLValue):
            lval_type = lvalue.obj_type

        if lval_type is not None:
            cast_result = TypeConverter().cast(new_val, lval_type)
            if not isinstance(cast_result, Error):
                new_val = cast_result

        result = self.store(lvalue, new_val)
        if isinstance(result, Error):
            return result

        return new_val

    # Short-circuit boolean operators.
    def bin_bool_and_expr(self, node: OpExpr) -> ExprResult | Error:
        assert len(node.exprs) == 2
        assert node.op == BinOpTag.bool_and

        left_expr, right_expr = node.exprs[0], node.exprs[1]

        left_cond: bool | Error = self.eval_cond(left_expr)
        if isinstance(left_cond, Error):
            return left_cond

        if not left_cond:
            return BoolValue(False)

        right_cond: bool | Error = self.eval_cond(right_expr)
        if isinstance(right_cond, Error):
            return right_cond

        return BoolValue(right_cond)

    def bin_bool_or_expr(self, node: OpExpr) -> ExprResult | Error:
        assert len(node.exprs) == 2
        assert node.op == BinOpTag.bool_or

        left_expr, right_expr = node.exprs[0], node.exprs[1]

        left_cond: bool | Error = self.eval_cond(left_expr)
        if isinstance(left_cond, Error):
            return left_cond

        if left_cond:
            return BoolValue(True)

        right_cond: bool | Error = self.eval_cond(right_expr)
        if isinstance(right_cond, Error):
            return right_cond

        return BoolValue(right_cond)

    def bin_assign_expr(self, node: OpExpr) -> ExprResult | Error:
        assert len(node.exprs) == 2
        assert node.op == BinOpTag.assign

        left_expr, right_expr = node.exprs[0], node.exprs[1]

        lvalue: ExprResult | Error = self.expr(left_expr)
        if isinstance(lvalue, Error):
            return lvalue

        rvalue: ValueObject | Error = self.load(self.expr(right_expr))
        if isinstance(rvalue, Error):
            return rvalue

        # Implicit conversion of rvalue to the lvalue's declared type.
        lval_type = None
        if isinstance(lvalue, ScopeLValue):
            var = self.scope.lookup(lvalue.iden)
            if not isinstance(var, Error):
                lval_type = var.var_type
        elif isinstance(lvalue, MemoryLValue):
            lval_type = lvalue.obj_type

        if lval_type is not None:
            cast_result = TypeConverter().cast(rvalue, lval_type)
            if not isinstance(cast_result, Error):
                rvalue = cast_result

        result = self.store(lvalue, rvalue)
        if isinstance(result, Error):
            return result

        return rvalue

    # Arithmetic operators that require usual arithmetic conversions (UAC).
    _UAC_OPS: frozenset = frozenset({
        BinOpTag.mul, BinOpTag.div, BinOpTag.mod,
        BinOpTag.add, BinOpTag.sub,
        BinOpTag.lt,  BinOpTag.gt,  BinOpTag.le,  BinOpTag.ge,
        BinOpTag.eq,  BinOpTag.ne,
        BinOpTag.bit_and, BinOpTag.bit_xor, BinOpTag.bit_or,
        BinOpTag.mul_assign, BinOpTag.div_assign, BinOpTag.mod_assign,
        BinOpTag.add_assign, BinOpTag.sub_assign,
        BinOpTag.bit_and_assign, BinOpTag.bit_xor_assign,
        BinOpTag.bit_or_assign,
    })

    def bin_expr(self, node: OpExpr) -> ExprResult | Error:
        assert len(node.exprs) == 2

        if node.op == BinOpTag.bool_and:
            return self.bin_bool_and_expr(node)

        if node.op == BinOpTag.bool_or:
            return self.bin_bool_or_expr(node)

        if node.op == BinOpTag.assign:
            return self.bin_assign_expr(node)

        left_expr, right_expr = node.exprs[0], node.exprs[1]

        if self.direction == Direction.left_to_right:
            left_res: ExprResult | Error = self.expr(left_expr)
            if isinstance(left_res, Error):
                return left_res

            right_res: ExprResult | Error = self.expr(right_expr)
            if isinstance(right_res, Error):
                return right_res

        else:
            right_res = self.expr(right_expr)
            if isinstance(right_res, Error):
                return right_res

            left_res = self.expr(left_expr)
            if isinstance(left_res, Error):
                return left_res

        lvalue = left_res

        left: ValueObject | Error = self.load(left_res)
        if isinstance(left, Error):
            return left

        right: ValueObject | Error = self.load(right_res)
        if isinstance(right, Error):
            return right

        # Apply usual arithmetic conversions for non-pointer arithmetic.
        if node.op in self._UAC_OPS:
            if not (isinstance(left, PtrValue) or isinstance(right, PtrValue)):
                conv = TypeConverter().usual_arith_convert(left, right)
                if not isinstance(conv, Error):
                    left, right = conv

        if node.op == BinOpTag.bit_and:
            return self.bin_bit_and(left, right)

        if node.op == BinOpTag.mul:
            return self.bin_mul(left, right)

        if node.op == BinOpTag.add:
            return self.bin_add(left, right)

        if node.op == BinOpTag.sub:
            return self.bin_sub(left, right)

        if node.op == BinOpTag.div:
            return self.bin_div(left, right)

        if node.op == BinOpTag.mod:
            return self.bin_mod(left, right)

        if node.op == BinOpTag.shl:
            return self.bin_shl(left, right)

        if node.op == BinOpTag.shr:
            return self.bin_shr(left, right)

        if node.op == BinOpTag.lt:
            return self.bin_lt(left, right)

        if node.op == BinOpTag.gt:
            return self.bin_gt(left, right)

        if node.op == BinOpTag.le:
            return self.bin_le(left, right)

        if node.op == BinOpTag.ge:
            return self.bin_ge(left, right)

        if node.op == BinOpTag.eq:
            return self.bin_eq(left, right)

        if node.op == BinOpTag.ne:
            return self.bin_ne(left, right)

        if node.op == BinOpTag.bit_xor:
            return self.bin_bit_xor(left, right)

        if node.op == BinOpTag.bit_or:
            return self.bin_bit_or(left, right)

        return self.bin_op_assign(node.op, lvalue, left, right)

    def op_expr(self, node: OpExpr) -> ExprResult | Error:
        if len(node.exprs) == 1:
            return self.una_expr(node)
        else:
            assert len(node.exprs) == 2
            return self.bin_expr(node)

    def cond_expr(self, node: CondExpr) -> ExprResult | Error:
        cond: bool | Error = self.eval_cond(node.cond_expr)
        if isinstance(cond, Error):
            return cond

        if cond:
            return self.expr(node.true_expr)
        else:
            return self.expr(node.false_expr)

    def comma_expr(self, node: CommaExpr) -> ExprResult | Error:
        fst_expr, snd_expr = node.exprs

        if self.direction == Direction.right_to_left:
            fst_expr, snd_expr = snd_expr, fst_expr

        result: ExprResult | Error = self.expr(fst_expr)
        if isinstance(result, Error):
            return result

        return self.expr(snd_expr)

    def expr(self, node: ExprNode) -> ExprResult | Error:
        self.cycle_inc(node)

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

        if isinstance(node, SizeOfExpr):
            return self.sizeof_expr(node)

        if isinstance(node, AlignOfExpr):
            return self.alignof_expr(node)

        if isinstance(node, OpExpr):
            return self.op_expr(node)

        if isinstance(node, CondExpr):
            return self.cond_expr(node)

        if isinstance(node, CommaExpr):
            return self.comma_expr(node)

        assert False

    # Declarations.
    def trans_unit_decl(self, node: TransUnitDecl) -> None | Error:
        for decl_node in node.decls:
            result = self.decl(decl_node)

            if isinstance(result, Error):
                return result

        return None

    def empty_decl(self, node: EmptyDecl) -> None | Error:
        return None

    def var_decl(self, node: VarDecl) -> None | Error:
        storage: StorageSpec | None = node.var_type.storage
        if storage == StorageSpec.extern:
            return None

        var_type: TypeObject | Error = self.resolve_type(node.var_type)
        if isinstance(var_type, Error):
            return var_type

        mem_type: MemoryType = MemoryType.stack
        if storage in (StorageSpec.static, StorageSpec.constexpr):
            mem_type = MemoryType.data

        if node.init is None:
            block_id: int | Error = self.mem.alloc(mem_type, var_type.size)
            if isinstance(block_id, Error):
                return block_id

            return self.scope.declare(node.iden, var_type, None, block_id)

        if isinstance(node.init, InitList):
            block_id = self.mem.alloc(mem_type, var_type.size)
            if isinstance(block_id, Error):
                return block_id

            result: None | Error = self.apply_init_list(block_id, 0, var_type, node.init)
            if isinstance(result, Error):
                self.mem.dealloc(mem_type, block_id)
                return result

            return self.scope.declare(node.iden, var_type, None, block_id)

        # Scalar expression initializer.
        init_val: ValueObject | Error = self.load(self.expr(node.init))
        if isinstance(init_val, Error):
            return init_val

        init_type: TypeObject | None = self.val_obj_type(init_val)
        if init_type is None or not self.types_match(init_type, var_type):
            converted = TypeConverter().cast(init_val, var_type)
            if not isinstance(converted, Error):
                init_val = converted

        return self.scope.declare(node.iden, var_type, init_val, None)

    def fun_decl(self, node: FunDecl) -> None | Error:
        if node.body is None:
            return None

        if node.iden in self.functions:
            # Re-declaration of a function with a body is an error.
            return Error()

        self.functions[node.iden] = node
        return None

    def enum_decl(self, node: EnumDecl) -> None | Error:
        result: TypeObject | Error = self.resolve_type(node.enum_type)
        if isinstance(result, Error):
            return result

        return None

    def struct_decl(self, node: StructDecl) -> None | Error:
        result: TypeObject | Error = self.resolve_type(node.struct_type)
        if isinstance(result, Error):
            return result

        return None

    def union_decl(self, node: UnionDecl) -> None | Error:
        result: TypeObject | Error = self.resolve_type(node.union_type)
        if isinstance(result, Error):
            return result

        return None

    def typedef_decl(self, node: TypedefDecl) -> None | Error:
        base_type: TypeObject | Error = self.resolve_type(node.base_type)
        if isinstance(base_type, Error):
            return base_type

        self.type_registry.typedefs[node.alias_iden] = base_type
        return None

    def static_assert_decl(self, node: StaticAssertDecl) -> None | Error:
        return None

    def decl(self, node: DeclNode) -> None | Error:
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
    def println_stmt(self, node: PrintLnStmt) -> StmtResult | Error:
        msg = self.fmt_sub(node.str_expr, node.arg_exprs)
        if isinstance(msg, Error):
            return Error()

        print(msg)
        return None

    def assert_stmt(self, node: AssertStmt) -> StmtResult | Error:
        cond: bool | Error = self.eval_cond(node.cond_expr)
        if isinstance(cond, Error):
            return cond

        if cond:
            return None

        msg = self.fmt_sub(node.str_expr, node.arg_exprs)
        if not isinstance(msg, Error) and msg:
            print(f"Assertion failed: {msg}", file=sys.stderr)
        else:
            print("Assertion failed", file=sys.stderr)

        return Error()

    def compound_stmt(self, node: CompoundStmt) -> StmtResult | Error:
        self.scope.push()

        signal: StmtResult = None

        for stmt_node in node.stmts:
            signal = self.stmt(stmt_node)

            if signal is not None:
                break

        self.scope.pop()
        return signal

    def decl_stmt(self, node: DeclStmt) -> StmtResult | Error:
        result = self.decl(node.decl)
        if isinstance(result, Error):
            return result
        return None

    def expr_stmt(self, node: ExprStmt) -> StmtResult | Error:
        result = self.expr(node.expr)
        if isinstance(result, Error):
            return result
        return None

    def if_stmt(self, node: IfStmt) -> StmtResult | Error:
        cond: bool | Error = self.eval_cond(node.cond_expr)
        if isinstance(cond, Error):
            return cond

        if cond:
            return self.stmt(node.then_stmt)

        if node.else_stmt is not None:
            return self.stmt(node.else_stmt)

        return None

    def switch_stmt(self, node: SwitchStmt) -> StmtResult | Error:
        # Switch is not fully implemented; stub evaluates the condition
        # but does not execute any case arm.
        cond = self.load(self.expr(node.cond_expr))
        if isinstance(cond, Error):
            return cond

        return None

    def for_stmt_init(self,
                      init_clause: ExprNode | DeclNode | None) -> None | Error:
        if init_clause is None:
            return None

        result = self.eval(init_clause)
        if isinstance(result, Error):
            return result

        return None

    def for_stmt_guard(self, node: ForStmt) -> StmtResult | Error:
        init_result: None | Error = self.for_stmt_init(node.init_clause)
        if isinstance(init_result, Error):
            return init_result

        while True:
            # A missing condition means loop forever (e.g. for(;;)).
            if node.cond_expr is not None:
                cond: bool | Error = self.eval_cond(node.cond_expr)
                if isinstance(cond, Error):
                    return cond

                if not cond:
                    break

            signal: StmtResult = self.eval_body(node.then_stmt, False)

            if isinstance(signal, Error):
                return signal

            if isinstance(signal, BreakSignal):
                break

            if isinstance(signal, ReturnSignal):
                return signal

            # ContinueSignal: execute increment, then re-check condition.

            if node.inc_expr is not None:
                result = self.expr(node.inc_expr)
                if isinstance(result, Error):
                    return result

        return None

    def for_stmt(self, node: ForStmt) -> StmtResult | Error:
        # The for-loop scope covers init-clause declarations as well as
        # all iterations of the body.
        self.scope.push()
        result: StmtResult = self.for_stmt_guard(node)
        self.scope.pop()
        return result

    def while_stmt(self, node: WhileStmt) -> StmtResult | Error:
        while True:
            cond: bool | Error = self.eval_cond(node.cond_expr)
            if isinstance(cond, Error):
                return cond

            if not cond:
                break

            signal: StmtResult = self.eval_body(node.then_stmt, False)
            if isinstance(signal, Error):
                return signal

            if isinstance(signal, BreakSignal):
                break

            if isinstance(signal, ReturnSignal):
                return signal

            # ContinueSignal: re-evaluate condition (fall through).

        return None

    def do_while_stmt(self, node: DoWhileStmt) -> StmtResult | Error:
        while True:
            signal: StmtResult = self.eval_body(node.do_stmt, False)
            if isinstance(signal, Error):
                return signal

            if isinstance(signal, BreakSignal):
                break

            if isinstance(signal, ReturnSignal):
                return signal

            # ContinueSignal: evaluate condition and decide whether to loop.

            cond: bool | Error = self.eval_cond(node.cond_expr)
            if isinstance(cond, Error):
                return cond

            if not cond:
                break

        return None

    def goto_stmt(self, node: GotoStmt) -> StmtResult | Error:
        return GotoSignal(node.label_iden)

    def break_stmt(self) -> StmtResult | Error:
        return BreakSignal()

    def continue_stmt(self) -> StmtResult | Error:
        return ContinueSignal()

    def return_stmt(self, node: ReturnStmt) -> StmtResult | Error:
        if node.ret_expr is None:
            return ReturnSignal(None)

        val: ValueObject | Error = self.load(self.expr(node.ret_expr))
        if isinstance(val, Error):
            return val

        return ReturnSignal(val)

    def stmt(self, node: StmtNode) -> StmtResult | Error:
        self.trace(node)

        step_result = self.step_inc()
        if isinstance(step_result, Error):
            return step_result

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

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, ForStmt):
            return self.for_stmt(node)

        if isinstance(node, WhileStmt):
            return self.while_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, GotoStmt):
            return self.goto_stmt(node)

        if isinstance(node, LabelStmt):
            return None

        if isinstance(node, CaseLabelStmt):
            return None

        if isinstance(node, BreakStmt):
            return self.break_stmt()

        if isinstance(node, ContinueStmt):
            return self.continue_stmt()

        if isinstance(node, ReturnStmt):
            return self.return_stmt(node)

        return None

    def eval(self, node: ASTNode) -> ExprResult | StmtResult | Error:
        if isinstance(node, ExprNode):
            return self.expr(node)

        if isinstance(node, DeclNode):
            return self.decl(node)

        if isinstance(node, StmtNode):
            return self.stmt(node)

        assert False

    def run(self, ast: AST) -> int | Error:
        assert ast.root is not None

        result = self.trans_unit_decl(ast.root)
        if isinstance(result, Error):
            return result

        main = self.functions.get("main")
        if main is None:
            return Error()

        ret_val = self.call_fun(main, [])
        if isinstance(ret_val, Error):
            return ret_val

        if isinstance(ret_val, IntValue):
            return ret_val.value

        return 0
