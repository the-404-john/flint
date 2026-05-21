import sys
from contextlib import contextmanager
from typing import IO, Any, Generator

from error import Error
from value_objects import (
    ValueObject, BoolValue, IntValue, FloatValue, DecValue,
    PtrValue, ArrayValue, StructValue, UnionValue, EnumValue,
    TypeObject, VoidType, BoolType, IntType, FloatType, DecType,
    PtrType, ArrayType, StructType, UnionType, EnumType,
)
from flint_ast import (
    ASTNode, IdenExpr, IntLitExpr, BoolLitExpr, RealFloatLitExpr,
    DecFloatLitExpr, CharLitExpr, StrLitExpr, OpExpr, CallExpr,
    MemberExpr, VarDecl, FunDecl, LabelStmt, GotoStmt, CaseLabelStmt,
)


# Execution Tracer
# Provides indented entry/exit tracing for AST node evaluation.
# Kept separate from eval.py so the evaluator contains no print calls.


def format_value(val: ValueObject) -> str:
    if isinstance(val, BoolValue):
        return "true" if val.value else "false"
    if isinstance(val, IntValue):
        sign = "i" if val.value_type.is_signed else "u"
        bits = val.value_type.size * 8
        return f"{val.value}:{sign}{bits}"
    if isinstance(val, FloatValue):
        bits = val.value_type.size * 8
        return f"{repr(val.value)}:f{bits}"
    if isinstance(val, DecValue):
        bits = val.value_type.size * 8
        return f"{val.value}:d{bits}"
    if isinstance(val, PtrValue):
        if val.block_id == 0:
            return "nullptr"
        return f"ptr(blk#{val.block_id}+{val.offset})"
    if isinstance(val, ArrayValue):
        elems = ", ".join(format_value(e) for e in val.elems[:4])
        suffix = ", …" if len(val.elems) > 4 else ""
        return f"[{elems}{suffix}]"
    if isinstance(val, StructValue):
        name = val.struct_type.iden or "<anon>"
        fields = ", ".join(
            f".{k}={format_value(v)}"
            for k, v in list(val.elems.items())[:3]
        )
        return f"{name}{{{fields}}}"
    if isinstance(val, UnionValue):
        name = val.union_type.iden or "<anon>"
        return f"{name}{{.{val.active_member}={format_value(val.value)}}}"
    if isinstance(val, EnumValue):
        name = val.enum_type.iden or "<enum>"
        return f"{name}({format_value(val.value)})"
    return "?"


def format_type(t: TypeObject) -> str:
    if isinstance(t, VoidType):
        return "void"
    if isinstance(t, BoolType):
        return "bool"
    if isinstance(t, IntType):
        sign = "i" if t.is_signed else "u"
        return f"{sign}{t.size * 8}"
    if isinstance(t, FloatType):
        return f"f{t.size * 8}"
    if isinstance(t, DecType):
        return f"d{t.size * 8}"
    if isinstance(t, PtrType):
        inner = format_type(t.target_type) if t.target_type else "void"
        return f"*{inner}"
    if isinstance(t, ArrayType):
        return f"{format_type(t.elem_type)}[{t.length}]"
    if isinstance(t, StructType):
        return f"struct {t.iden or '<anon>'}"
    if isinstance(t, UnionType):
        return f"union {t.iden or '<anon>'}"
    if isinstance(t, EnumType):
        return f"enum {t.iden or '<anon>'}"
    return "?"


class _TraceRecord:
    __slots__ = ("result",)

    def __init__(self) -> None:
        self.result: Any = None


class Tracer:
    def __init__(self,
                 enabled: bool = False,
                 out: IO[str] | None = None) -> None:
        self.enabled = enabled
        self._depth = 0
        self._out: IO[str] = out if out is not None else sys.stderr

    def _write(self, text: str) -> None:
        self._out.write("  " * self._depth + text + "\n")

    def node_detail(self, node: ASTNode) -> str:
        if isinstance(node, IdenExpr):
            return f" iden='{node.iden}'"
        if isinstance(node, IntLitExpr):
            return f" value={node.int_expr}"
        if isinstance(node, BoolLitExpr):
            return f" value={'true' if node.bool_expr else 'false'}"
        if isinstance(node, (RealFloatLitExpr, DecFloatLitExpr)):
            return f" value={node.float_expr}"
        if isinstance(node, CharLitExpr):
            return f" char='{node.char_expr}'"
        if isinstance(node, StrLitExpr):
            return f" str={node.str_expr[:32]!r}"
        if isinstance(node, OpExpr):
            return f" op='{node.op.value}'"
        if isinstance(node, CallExpr):
            if isinstance(node.callee_expr, IdenExpr):
                return f" callee='{node.callee_expr.iden}'"
        if isinstance(node, MemberExpr):
            arrow = "->" if node.is_arrow else "."
            return f" member='{arrow}{node.member_iden}'"
        if isinstance(node, VarDecl):
            return f" name='{node.iden}'"
        if isinstance(node, FunDecl):
            return f" name='{node.iden}'"
        if isinstance(node, LabelStmt):
            return f" label='{node.iden}'"
        if isinstance(node, GotoStmt):
            return f" label='{node.label_iden}'"
        if isinstance(node, CaseLabelStmt):
            return " default" if node.cond_expr is None else ""
        return ""

    def format_result(self, result: Any) -> str:
        if result is None:
            return ""
        if isinstance(result, Error):
            return f"Error({result.msg!r})" if result.msg else "Error"
        if isinstance(result, ValueObject):
            return format_value(result)
        # Duck-type control-flow signals to avoid a circular import from eval.py.
        if type(result).__name__ == "ReturnSignal":
            val = getattr(result, "value", None)
            inner = format_value(val) if isinstance(val, ValueObject) else ""
            return f"return({inner})" if inner else "return"
        if type(result).__name__ == "BreakSignal":
            return "break"
        if type(result).__name__ == "ContinueSignal":
            return "continue"
        if type(result).__name__ == "GotoSignal":
            return f"goto({result.label!r})"
        # Duck-type LValue variants.
        if hasattr(result, "iden") and not isinstance(result, ASTNode):
            return f"lval(scope:'{result.iden}')"
        if hasattr(result, "block_id") and hasattr(result, "obj_type"):
            return f"lval(mem:blk#{result.block_id}+{result.offset})"
        return str(result)

    @contextmanager
    def enter(self,
              label: str,
              detail: str = "") -> Generator[_TraceRecord, None, None]:
        """Context manager that brackets a single AST node's evaluation."""
        rec = _TraceRecord()
        if not self.enabled:
            yield rec
            return

        self._write(f">> {label}{detail}")
        self._depth += 1
        try:
            yield rec
        finally:
            self._depth -= 1
            suffix = (
                f" → {self.format_result(rec.result)}"
                if rec.result is not None else ""
            )
            self._write(f"<< {label}{suffix}")

    @contextmanager
    def call_frame(self, fun_name: str) -> Generator[None, None, None]:
        """Context manager that marks a user-defined function call boundary."""
        if not self.enabled:
            yield
            return

        self._write(f"## call {fun_name}()")
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1
            self._write(f"## end  {fun_name}()")
