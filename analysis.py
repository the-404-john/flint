from error import *
from flint_ast import *


# NOTE: mornfall I know there is duplicity of the code and some the
# tree I could cut or optimize, but we can do that later ig

def is_int_expr(expr: ExprNode) -> bool:
    pass


def is_int_constant_expr(expr: ExprNode) -> bool:
    pass


def eval_int_constant_expr(expr: ExprNode) -> int:
    pass



# Function Signature Analysis
# Verifies the following constraints:
# - `function` declarations and definitions have matching return types,
#   parameter counts, and parameter types.
# - `function` definitions are not duplicated.
class AnalysisXX:
    def __init__(self) -> None:
        self.decls: dict[str, FunDecl] = {}
        self.error: None | Error = None

    def match_types(self, fst: TypeNode, snd: TypeNode) -> bool:
        pass

    def match_params(self,
                     fst_params: ParamSpec,
                     snd_params: ParamSpec) -> bool:
        if len(fst_params) != len(snd_params):
            return False

        for i in range(len(fst_params)):
            fst_type, _ = fst_params[i]
            snd_type, _ = snd_params[i]

            if not self.match_types(fst_type, snd_type):
                return False

        return True

    def fun_decl(self, node: FunDecl) -> bool:
        prev_decl = self.decls.get(node.iden)

        if prev_decl is None:
            self.decls[node.iden] = node
            return True

        if not self.match_types(prev_decl.ret_type, node.ret_type):
            self.error = Error()
            return False

        if not self.match_params(prev_decl.params, node.params):
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


# Loop Context Analysis
# Verifies that `continue` and `break` statements occur exclusively
# inside valid contexts:
#   - `break`    : inside a loop OR a switch statement
#   - `continue` : inside a loop only
class AnalysisXX:
    def __init__(self) -> None:
        self.in_loop: bool = False
        self.in_switch: bool = False

        self.error: None | Error = None

    def visit(self, node: StmtNode) -> bool:
        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, LoopStmt):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, BreakStmt):
            return self.break_stmt(node)

        if isinstance(node, ContinueStmt):
            return self.continue_stmt(node)

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        for stmt_node in node.block_items:
            if not self.visit(stmt_node):
                return False

        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.visit(node.then_stmt):
            return False

        return node.else_stmt is None or self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> bool:
        prev_swtich_flag, self.in_switch = self.in_switch, True

        if not self.visit(node.then_stmt):
            return False

        self.in_switch = prev_switch_flag
        return True

    def loop_stmt(self, node: LoopStmt) -> bool:
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

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        for decl in ast.root.decls:
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return self.error

        return None


# Switch Context Analysis
# Verifies the following constraints:
# - `case` and `default` labels appear exclusively within `switch`
#   statements.
# - `case` and `default` labels are unique within one `swtich`
#   statement scope.
# - `switch` statements utilize integer constant expressions.
# - `case` labels contain only constant expressions.
class AnalysisXX:
    def __init__(self) -> None:
        self.in_switch: bool = False
        self.labels: set[int | None] = set()

        self.error: None | Error = None

    def visit(self, node: StmtNode) -> bool:
        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, CaseLabelStmt):
            return self.case_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, LoopStmt):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        for stmt_node in node.block_items:
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
        prev_swtich_flag, self.in_switch = self.in_switch, True

        if not is_int_expr(node.cond_expr):
            self.error = Error()
            return False

        if not self.visit(node.then_stmt):
            return False

        self.in_switch = prev_swtich_flag
        return True

    def loop_stmt(self, node: LoopStmt) -> bool:
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


# Goto Label Analysis
# Verifies the following constraints:
# - `goto` statements have associated destination `label` statements.
# - `label` statements are not duplicated within the same function
#   declaration.
class AnalysisXX:
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

        if isinstance(node, LoopStmt):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, GotoStmt):
            return self.goto_stmt(node)

        if isinstance(node, LabelStmt):
            return self.label_stmt(node)

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        for stmt_node in node.block_items:
            if not self.visit(stmt_node):
                return False

        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.visit(node.then_stmt):
            return False

        return node.else_stmt is None or self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.visit(node.then_stmt)

    def loop_stmt(self, node: LoopStmt) -> bool:
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
        self.idens.add(node.name)

    def generic_sel_expr(self, node: GenericSelExpr) -> None:
        self.collect_from_expr(node.expr)

        for expr_node in table.values():
            self.collect_from_expr(node.expr_node)

    def array_sub_expr(self, node: ArraySubExpr) -> None:
        self.collect_from_expr(node.base_expr)
        self.collect_from_expr(node.idx_expr)

    def call_expr(self, node: CallExpr) -> None:
        self.collect_from_expr(node.callee_expr)

        for arg_node in node.arg_expr_list:
            self.collect_from_expr(arg_node)

    def member_expr(self, node: MemberExpr) -> None:
        self.collect_from_expr(node.base_expr)

    def comound_lit_expr(self, node: CompoundLitExpr) -> None:
        pass

    def cast_expr(self, node: CastExpr) -> None:
        self.collect_from_expr(node.val_expr)

    def op_expr(self, node: OpExpr) -> None:
        for child_expr in node.exprs:
            self.collect_from_expr(child)

    def cond_expr(self, node: CondExpr) -> None:
        self.collect_from_expr(node.cond_expr)
        self.collect_from_expr(node.true_expr)
        self.collect_from_expr(node.false_expr)

    def comma_expr(self, node: CommaExpr) -> None:
        fst, snd = node.expr

        self.collect_from_expr(fst)
        self.collect_from_expr(snd)

    def sizeof_expr(self, node: SizeOfExpr) -> None:
        if isinstance(node.expr_or_type, ExprNode):
            self.collect_from_expr(node.expr_or_type)

    def collect_from_expr(self, node: ExprNode):
        if isinstance(node, IdenExpr):
            return self.iden_expr(node)

        if isinstance(node, CallExpr):
            return self.call_expr(node)

        if isinstance(node, ArraySubExpr):
            return self.array_sub_expr(node)

        if isinstance(node, MemberExpr):
            return self.member_expr(node)

        if isinstance(node, CompoundLitExpr):
            return self.comound_lit_expr(node)

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



class AnalysisXX:
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

        if isinstance(node, LoopStmt):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, (GotoStmt, LabelStmt, DeclStmt)):
            self.flat.append((len(self.flat), node))

            if isinstance(node, LabelStmt):
                self.label_pos[node.iden] = len(self.flat) - 1  # BUG 2 (original): label_pos was never populated

    def compound_stmt(self, node: CompoundStmt) -> None:
        for stmt_node in node.block_items:
            self.visit(stmt_node)

    def if_stmt(self, node: IfStmt) -> None:
        self.visit(node.then_stmt)

        if node.else_stmt is not None:
            self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> None:
        self.visit(node.then_stmt)

    def loop_stmt(self, node: LoopStmt) -> None:
        if isinstance(node.init_clause, DeclNode):
            self.flat.append((len(self.flat), DeclStmt(node.init_clause)))

        self.visit(node.then_stmt)

    def do_while_stmt(self, node: DoWhileStmt) -> None:
        self.visit(node.do_stmt)

    def collect_idens_expr(self, node: ExprNode, out: set[str]) -> None:

    def _collect_idens_stmt(self, node: StmtNode, out: set[str]) -> None:
        """Recursively collect every identifier *used* (not declared) in a statement subtree."""
        if isinstance(node, ExprStmt) and node.expr is not None:
            self._collect_idens_expr(node.expr, out)
        elif isinstance(node, DeclStmt):
            if isinstance(node.decl, VarDecl) and node.decl.init is not None:
                # Only the initialiser counts as a *use*; the declared name is a def.
                if isinstance(node.decl.init, ExprNode):
                    self._collect_idens_expr(node.decl.init, out)
        elif isinstance(node, CompoundStmt):
            for child in node.block_items:
                self._collect_idens_stmt(child, out)
        elif isinstance(node, IfStmt):
            self._collect_idens_expr(node.cond_expr, out)
            self._collect_idens_stmt(node.then_stmt, out)
            if node.else_stmt is not None:
                self._collect_idens_stmt(node.else_stmt, out)
        elif isinstance(node, ReturnStmt):
            if node.ret_expr is not None:
                self._collect_idens_expr(node.ret_expr, out)
        elif isinstance(node, LoopStmt):
            if node.cond_expr is not None:
                self._collect_idens_expr(node.cond_expr, out)
            if node.inc_expr is not None:
                self._collect_idens_expr(node.inc_expr, out)
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

        if len(skipped_decls & used_idens) == 0:
            self.error = Error()
            return False

        return True

    # --- Entry points ---

    def fun_decl(self, node: FunDecl) -> bool:
        # BUG 8 (original): self.visit returns None but fun_decl tested
        # `not self.visit(node.body)` as if it returned bool.
        # BUG 9 (original): self.goto_labels / self.labels were never defined;
        # that undefined-label check belongs in a separate analysis pass.
        # BUG 10 (original): flat and label_pos were never reset between functions.
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


# Format String Analysis
# Verifies the following constraints:
# - `println` statements have a matching number of format specifiers
#   and arguments.
# - `assert` statements have a matching number of format specifiers
#   and arguments.
class AnalysisXX:
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

        if isinstance(node, LoopStmt):
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
        for stmt_node in node.block_items:
            if not self.visit(stmt_node):
                return False

        return True

    def if_stmt(self, node: IfStmt) -> bool:
        if not self.visit(node.then_stmt):
            return False

        return node.else_stmt is None or self.visit(node.else_stmt)

    def switch_stmt(self, node: SwitchStmt) -> bool:
        return self.visit(node.then_stmt)

    def loop_stmt(self, node: LoopStmt) -> bool:
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
class AnalysisXX:
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
            self.block_idens,
            self.tag_defs,
            self.tag_idens
        )

        self.block_idens = set()
        self.tag_defs = set()
        self.tag_idens = {}

    def scope_pop(self) -> None:
        self.block_idens, self.tag_defs, self.tag_idens = self.scope.pop()

    def visit(self, node: StmtNode) -> bool:
        if isinstance(node, DeclStmt):
            return self.decl_stmt(node)

        if isinstance(node, CompoundStmt):
            return self.compound_stmt(node)

        if isinstance(node, IfStmt):
            return self.if_stmt(node)

        if isinstance(node, SwitchStmt):
            return self.switch_stmt(node)

        if isinstance(node, LoopStmt):
            return self.loop_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        return True

    def decl_stmt(self, node: DeclStmt) -> bool:
        if isinstance(node.decl, VarDecl):
            return self.var_decl(node.decl)

        if isinstance(node.decl, (EnumDecl, StructDecl, UnionDecl)):
            return self.tag_decl(node.decl)

        return True

    def compound_stmt(self, node: CompoundStmt) -> bool:
        self.scope_push()

        for stmt_node in node.block_items:
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

    def loop_stmt(self, node: LoopStmt) -> bool:
        if not isinstance(init_clause, DeclNode):
            return self.visit(node.then_stmt)

        self.scope_push()

        if not isinstance(node.then_stmt, CompoundStmt):
            if not self.visit(node.then_stmt):
                return False
        else:
            for stmt_node in node.then_stmt.block_items:
                if not self.visit(stmt_node):
                    return False

        self.scope_pop()

        return True

    def do_while_stmt(self, node: DoWhileStmt) -> bool:
        return self.visit(node.do_stmt)

    def var_decl(self, node: VarDecl) -> bool:
        if node.iden in self.block_idens:
            self.error = Error()
            return False

        self.block_idens.add(node.iden)
        return True

    def tag_decl(self, node: EnumDecl | StructDecl | UnionDecl) -> bool:
        if node.iden is None:
            return True

        if tag_id(node) != self.tag_idens.get(node.iden, tag_id(node)):
            self.error = Error()
            return False

        self.tag_idens[node.iden] = tag_id(node)

        if node.members is None:
            return True

        if node.iden in self.tag_defs:
            self.error = Error()
            return False

        self.tag_defs.add(node.iden)

        return True

    def fun_decl(self, node: FunDecl) -> bool:
        self.scope_push()
        self.block_idens.add(node.iden)

        for param_type, param_name in node.params:
            if param_name is None:
                continue

            if param_name in self.block_idens:
                self.error = Error()
                return False

            self.block_idens.add(param_name)

        if node.body is None:
            return True

        for stmt_node in node.body.block_items:
            if not self.visit(stmt_node):
                return False

        self.scope_pop()

        return True

    def trans_unit_decl(self, node: TransUnitDecl) -> bool:
        for decl in node.decls:
            # something something, has to figure out, how does it work
            # with everything...
            if not isinstance(decl, FunDecl):
                continue

            if not self.fun_decl(decl):
                assert self.error is not None
                return self.error

    def analyze(self, ast: AST) -> None | Error:
        assert ast.root is not None

        if not self.trans_unit_decl(ast.root):
            return self.error

        return None

# verify that each exression have declaration if symbol
class AnalysisXX:
    def __init__(self) -> None:
        pass


# verify that each call of function have proper parameters and with
# proper types
# verify enum, struct and union, regard to their names, and assigning
# something something maybe implicit casts
# something verify if the function have proper types of arguments
# return of functions are valid

# if the conditional expr is right in types
# similar with other expressions, for example on assignment and that

# if all the identificators in expr are defined

# fix parser, because I renames the cyclestmt to loop stmt
# fix parser, because do while can have null statement like just ;

def test() -> None:
    pass


if __name__ == "__main__":
    test()
