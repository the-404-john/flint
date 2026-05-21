import sys

try:
    import readline
    _HAS_READLINE = True
except ImportError:
    _HAS_READLINE = False

from error import Error
from flint_ast import (
    AST, FunDecl, VarDecl, TransUnitDecl,
    ExprStmt, DeclStmt,
    ExprNode, StmtNode,
)
from memory import Memory, MemoryType
from eval import Evaluator
from scope import ScopeVar
from value_objects import (
    ValueObject,
    BoolValue, IntValue, FloatValue, DecValue,
    PtrValue, ArrayValue, EnumValue, StructValue, UnionValue,
)

# Read-Eval-Print Loop
# Provides an interactive C23 session backed by the same memory model
# and evaluator that powers the batch interpreter.  A single Evaluator
# (and its associated Memory and Scope) lives for the entire session so
# that variables, functions, and type definitions declared in one input
# are visible in every subsequent input.

_PRIMARY  = ">> "
_CONTINUE = ".. "
_INDENT   = "    "   # 4 spaces per brace level

_MEM_DATA  = 1 << 20   # 1 MB  global / static data
_MEM_STACK = 1 << 20   # 1 MB  automatic storage (globals live here too)
_MEM_HEAP  = 4 << 20   # 4 MB  malloc / heap

# Keywords that unambiguously begin a statement, not an expression.
_STMT_STARTS = frozenset({
    "if", "for", "while", "do", "switch",
    "return", "break", "continue", "goto",
    "assert", "println",
})

# Binary-operator endings that mean the expression continues on the next line.
_CONT_ENDINGS = (
    ",", "||", "&&",
    "+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "&=", "|=", "^=",
    "<<", ">>", "->",
    "+", "-", "*", "/", "%",
    "&", "|", "^", "?", ":", "=",
)


# ── Utility helpers ──────────────────────────────────────────────────────────

def _brace_depth(text: str) -> int:
    """
    Net count of unclosed '{' in *text*.  Skips characters inside string
    literals, character literals, and both flavours of comment so that
    brace-like characters in those positions are not counted.
    """
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]

        if c == '/' and i + 1 < n:
            if text[i + 1] == '/':
                while i < n and text[i] != '\n':
                    i += 1
                continue
            if text[i + 1] == '*':
                i += 2
                while i + 1 < n and not (text[i] == '*' and text[i + 1] == '/'):
                    i += 1
                i += 2
                continue

        if c == '"':
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                i += 1
            i += 1
            continue

        if c == "'":
            i += 1
            while i < n and text[i] != "'":
                if text[i] == '\\':
                    i += 1
                i += 1
            i += 1
            continue

        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1

        i += 1

    return depth


def _read_line(prompt: str, pre_fill: str = "") -> str:
    """
    Read one line from stdin with the given *prompt*.  When readline is
    available and *pre_fill* is non-empty, insert it as editable text
    before the user starts typing (so they can backspace over it for
    closing braces that belong at a shallower level).
    """
    if _HAS_READLINE and pre_fill:
        def _hook() -> None:
            readline.insert_text(pre_fill)
            readline.redisplay()
        readline.set_pre_input_hook(_hook)

    try:
        return input(prompt)
    finally:
        if _HAS_READLINE:
            readline.set_pre_input_hook(None)


def _format_value(val: ValueObject) -> str:
    """Human-readable representation of a ValueObject, mirroring C notation."""
    if isinstance(val, BoolValue):
        return "true" if val.value else "false"

    if isinstance(val, IntValue):
        return str(val.value)

    if isinstance(val, FloatValue):
        return repr(val.value)

    if isinstance(val, DecValue):
        return str(val.value)

    if isinstance(val, PtrValue):
        if val.block_id == 0 and val.offset == 0:
            return "NULL"
        return f"(ptr){val.block_id:#06x}+{val.offset}"

    if isinstance(val, EnumValue):
        return str(val.value.value)

    if isinstance(val, ArrayValue):
        preview = val.elems[:8]
        parts   = [_format_value(e) for e in preview]
        if len(val.elems) > 8:
            parts.append("...")
        return "[" + ", ".join(parts) + "]"

    if isinstance(val, StructValue):
        fields = ", ".join(
            f".{k} = {_format_value(v)}" for k, v in val.elems.items()
        )
        return "{" + fields + "}"

    if isinstance(val, UnionValue):
        return "{" + f".{val.active_member} = {_format_value(val.value)}" + "}"

    return repr(val)


# ── REPL class ───────────────────────────────────────────────────────────────

class REPL:
    def __init__(self) -> None:
        self.mem = Memory(_MEM_DATA, _MEM_STACK, _MEM_HEAP)
        self.ev  = Evaluator(self.mem, sys.maxsize, sys.maxsize)
        self.exit_code: int = 0

    # ── Output ────────────────────────────────────────────────────────────────

    def _write(self, msg: str) -> None:
        print(msg, file=sys.stdout, flush=True)

    def _error(self, msg: str) -> None:
        print(f"error: {msg}", file=sys.stderr, flush=True)

    # ── Input collection ──────────────────────────────────────────────────────

    def read_input(self) -> str | None:
        """
        Collect one logical unit of input, which may span multiple lines.

        Brace depth drives two behaviours:
          - While depth > 0 the prompt switches to _CONTINUE and the
            pre-filled text is _INDENT × depth, making the cursor land at
            the correct column.  The user can backspace over the pre-fill
            to type a closing brace at the shallower column.
          - When depth returns to 0 the buffer is submitted.

        Ctrl-C cancels the current multi-line buffer (returns to primary
        prompt).  Ctrl-D / EOF returns None to end the session.
        """
        lines: list[str] = []
        depth: int = 0

        while True:
            if not lines:
                # Primary prompt — no pre-fill.
                try:
                    line = input(_PRIMARY)
                except EOFError:
                    return None
                except KeyboardInterrupt:
                    print()
                    continue
            else:
                # Continuation prompt — pre-fill with depth-worth of spaces.
                indent = _INDENT * depth
                try:
                    line = _read_line(_CONTINUE, indent)
                except EOFError:
                    # Submit whatever we have collected so far.
                    return "\n".join(lines)
                except KeyboardInterrupt:
                    # Discard the current buffer and restart.
                    print()
                    lines = []
                    depth = 0
                    continue

            depth += _brace_depth(line)
            lines.append(line)
            stripped = line.strip()

            # Keep collecting while braces are unclosed.
            if depth > 0:
                continue

            # Keep collecting when a line ends with a binary operator,
            # indicating the expression/initialiser continues.
            if stripped.endswith(_CONT_ENDINGS):
                continue

            break

        return "\n".join(lines)

    # ── Redefinition support ──────────────────────────────────────────────────

    def _drop_existing(self, decl: VarDecl | FunDecl) -> None:
        """
        Remove a prior definition of *decl* from the live interpreter state
        so that the incoming declaration can replace it without a conflict.

        - Functions: removed from ev.functions (the new body replaces it).
        - Variables: removed from scope.frames[0] and their simulated-stack
          allocation is released so the memory budget is reclaimed.

        Structs, unions, enums, and typedefs are not handled here because
        their resolve_* methods in eval.py already overwrite the type
        registry unconditionally.
        """
        if isinstance(decl, FunDecl):
            if decl.body is not None and decl.iden in self.ev.functions:
                self.ev.functions.pop(decl.iden)

        elif isinstance(decl, VarDecl):
            frame = self.ev.scope.frames[0]
            if decl.iden in frame.vars:
                var: ScopeVar = frame.vars.pop(decl.iden)
                self.ev.scope.pop_var(var)

    def _allow_redef(self, ast: AST) -> None:
        """
        Walk the top-level decls of *ast* and purge any definitions that
        already exist in the REPL environment.  Called immediately before
        _exec_top_level so that the evaluator sees a clean slate for each
        name being redefined.

        Handles TransUnitDecl (multi-declarator: int a = 1, b = 2;) by
        recursing into its children.
        """
        assert ast.root is not None
        for decl in ast.root.decls:
            if isinstance(decl, TransUnitDecl):
                for sub in decl.decls:
                    if isinstance(sub, (FunDecl, VarDecl)):
                        self._drop_existing(sub)
            elif isinstance(decl, (FunDecl, VarDecl)):
                self._drop_existing(decl)

    # ── Parsing helpers ───────────────────────────────────────────────────────

    def _parse(self, source: str) -> AST | Error:
        ast = AST(source)
        result = ast.build(save_comments=False)
        if isinstance(result, Error):
            return result
        return ast

    def _parse_wrapped(self, source: str) -> AST | Error:
        """
        Wrap *source* inside a dummy function body so the parser sees a
        valid statement context.  A trailing semicolon is appended when the
        source is not already terminated.
        """
        s = source.rstrip()
        if not (s.endswith(";") or s.endswith("}")):
            s = s + ";"
        return self._parse(f"void __repl__(void) {{\n{s}\n}}")

    # ── Execution helpers ─────────────────────────────────────────────────────

    def _exec_top_level(self, ast: AST) -> None | Error:
        """
        Execute a parsed top-level translation unit.  Redefine-safe: existing
        functions and variables are purged first so the new definitions
        replace them without triggering a duplicate-declaration error.
        """
        self._allow_redef(ast)
        assert ast.root is not None
        return self.ev.trans_unit_decl(ast.root)

    def _exec_stmts(self, ast: AST) -> None | Error:
        """
        Run the body of the __repl__ wrapper directly in the evaluator's
        current (global) scope — no extra frame is pushed — so that any
        declarations made here persist for the rest of the session.
        """
        assert ast.root is not None
        fun: FunDecl = ast.root.decls[0]  # type: ignore
        assert fun.body is not None

        for stmt_node in fun.body.stmts:
            result = self.ev.stmt(stmt_node)
            if isinstance(result, Error):
                return result

        return None

    def _eval_expr(self, ast: AST) -> ValueObject | Error:
        """
        Extract and evaluate the single expression from the wrapper body.
        Succeeds only when the body contains exactly one ExprStmt.
        """
        fun: FunDecl = ast.root.decls[0]  # type: ignore
        if fun.body is None or len(fun.body.stmts) != 1:
            return Error()

        node = fun.body.stmts[0]
        if not isinstance(node, ExprStmt):
            return Error()

        result = self.ev.expr(node.expr)
        return self.ev.load(result)

    # ── Meta-commands ─────────────────────────────────────────────────────────

    def _handle_meta(self, line: str) -> bool:
        """
        Process a dot-command.  Returns True if the line was consumed.
        Raises EOFError to signal a clean exit.
        """
        cmd = line.strip()

        if cmd in (".exit", ".quit", "exit", "quit"):
            raise EOFError

        if cmd == ".help":
            self._write(
                "Flint C23 REPL\n"
                "\n"
                "  .exit / .quit  exit the session\n"
                "  .help          show this message\n"
                "  .mem           show memory budget remaining\n"
                "  .vars          list declared global variables\n"
                "  .fns           list declared functions\n"
                "\n"
                "Input rules:\n"
                "  Declarations and function definitions are evaluated\n"
                "  as top-level C.  Re-defining a name replaces the\n"
                "  previous definition without an error.\n"
                "  Statements execute in the global scope.\n"
                "  Expressions without a trailing ';' print their value.\n"
                "  Multi-line input is accepted when braces are unclosed\n"
                "  (prompt changes to '.. ' with auto-indentation).\n"
                "  Backspace over the pre-filled spaces to type a '}'\n"
                "  at a shallower level.  Ctrl-C cancels the buffer.\n"
                "  Ctrl-D (EOF) ends the session."
            )
            return True

        if cmd == ".mem":
            lims = self.mem.mem_limits
            self._write(
                f"  data:  {lims[MemoryType.data]:>10,} bytes free\n"
                f"  stack: {lims[MemoryType.stack]:>10,} bytes free\n"
                f"  heap:  {lims[MemoryType.heap]:>10,} bytes free"
            )
            return True

        if cmd == ".vars":
            frame = self.ev.scope.frames[0]
            if not frame.vars:
                self._write("  (no globals declared)")
            else:
                for name in sorted(frame.vars):
                    v = self.ev.scope.read(name)
                    vstr = _format_value(v) if isinstance(v, ValueObject) else "<unreadable>"
                    self._write(f"  {name} = {vstr}")
            return True

        if cmd == ".fns":
            if not self.ev.functions:
                self._write("  (no functions declared)")
            else:
                for name in sorted(self.ev.functions):
                    self._write(f"  {name}()")
            return True

        return False

    # ── Evaluate-dispatch ─────────────────────────────────────────────────────

    def eval_input(self, source: str) -> None:
        """
        Attempt to evaluate *source* using three strategies, in order:

        1. Top-level declaration  — int x = 5;  void f() { ... }
           Existing definitions for the same name are replaced silently.
        2. Statement in global scope — x = 5;  if (...) { ... }
        3. Bare expression (prints result) — x + 3  fib(7)

        For strategies 2 and 3 the source is wrapped inside a dummy
        function so the parser sees a valid statement context; statements
        are then executed directly against the evaluator's global scope
        so their side-effects persist.
        """
        stripped = source.strip()

        first_token = stripped.split()[0] if stripped else ""
        wants_print = not (
            stripped.endswith(";")
            or stripped.endswith("}")
            or first_token in _STMT_STARTS
        )

        # Strategy 1 — top-level parse (declarations, function definitions).
        ast = self._parse(source)
        if not isinstance(ast, Error):
            result = self._exec_top_level(ast)
            if isinstance(result, Error):
                self._error("runtime error")
            return

        # Strategy 2 — statement in the global scope.
        ast_w = self._parse_wrapped(source)
        if not isinstance(ast_w, Error):
            if wants_print:
                val = self._eval_expr(ast_w)
                if isinstance(val, ValueObject):
                    self._write(_format_value(val))
                    return
            result = self._exec_stmts(ast_w)
            if isinstance(result, Error):
                self._error("runtime error")
            return

        # Strategy 3 — retry bare expression with explicit semicolon.
        if wants_print:
            ast_e = self._parse_wrapped(source + ";")
            if not isinstance(ast_e, Error):
                val = self._eval_expr(ast_e)
                if isinstance(val, ValueObject):
                    self._write(_format_value(val))
                    return

        self._error("parse error")

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        while True:
            try:
                source = self.read_input()
            except EOFError:
                break

            if source is None:
                break

            stripped = source.strip()
            if not stripped:
                continue

            try:
                if self._handle_meta(stripped):
                    continue
                self.eval_input(source)
            except EOFError:
                break
            except Exception as exc:
                self._error(f"internal error: {exc}")


def test() -> None:
    pass


if __name__ == "__main__":
    test()
