from error import *
from flint_ast import *


class Scope:
    def __init__(self) -> None:
        pass


class Evaluator:
    def __init__(self, ) -> None:
        self.scope = Scope()

        self.step_count = 0
        self.step_limit = 0
        self.trace_flag = trace_flag

    # Expressions.
    def ident_expr(self, node: IdenExpr) -> None | Error:
        pass

    def int_lit_expr(self, node: IntLitExpr) -> None | Error:
        pass

    def float_lit_expr(self, node: FloatLitExpr) -> None | Error:
        pass

    def char_lit_expr(self, node: CharLitExpr) -> None | Error:
        pass

    def str_lit_expr(self, node: StrLitExpr) -> None | Error:
        pass

    def generic_sel_expr(self, node: GenericSelExpr) -> None | Error:
        pass

    def array_sub_expr(self, node: ArraySubExpr) -> None | Error:
        pass

    def call_expr(self, node: CallExpr) -> None | Error:
        pass

    def member_expr(self, node: MemberExpr) -> None | Error:
        pass

    def compound_lit_expr(self, node: CompoundLitExpr) -> None | Error:
        pass

    def cast_expr(self, node: CastExpr) -> None | Error:
        pass

    def una_expr(self, node: OpExpr) -> None | Error:
        assert len(node.exprs)
        assert isinstance(node.op, UnaOpTag)

        expr = self.eval(expr_arg)

        if node.op == UnaPrefOpTag.prefix_inc:

        if node.op == UnaPrefOpTag.prefix_dec:

        if node.op == UnaPrefOpTag.addr_of:

        if node.op == UnaPrefOpTag.deref:

        if node.op == UnaPrefOpTag.neg:

        if node.op == UnaPrefOpTag.bit_neg:

        if node.op == UnaPrefOpTag.bool_neg:

        if node.op == UnaPostOpTag.postfix_inc:

        if node.op == UnaPostOpTag.postfix_dec:


        pass

    def bin_expr(self, node: OpExpr) -> None | Error:
        pass

    def op_expr(self, node: OpExpr) -> None | Error:
        if len(node.exprs) == 1:
            return self.una_expr(node)
        else:
            assert len(node.exprs) == 2
            return self.bin_expr(node)

    def cond_expr(self, node: CondExpr) -> None | Error:
        pass

    def assignment_expr(self, node: AssignmentExpr) -> None | Error:
        pass

    def comma_expr(self, node: CommaExpr) -> None | Error:
        pass

    def sizeof_expr(self, node: SizeOfExpr) -> None | Error:
        pass

    def alignof_expr(self, node: AlignOfExpr) -> None | Error:
        pass

    # Statements.
    def println_stmt(self, node: PrintLnStmt) -> None | Error:
        pass

    def assert_stmt(self, node: AssertStmt) -> None | Error:
        pass

    def compound_stmt(self, node: CompoundStmt) -> None | Error:
        pass

    def decl_stmt(self, node: DeclStmt) -> None | Error:
        pass

    def expr_stmt(self, node: ExprStmt) -> None | Error:
        pass

    def if_stmt(self, node: IfStmt) -> None | Error:
        pass

    def case_label_stmt(self, node: CaseLabelStmt) -> None | Error:
        pass

    def switch_stmt(self, node: SwitchStmt) -> None | Error:
        pass

    def cycle_stmt(self, node: CycleStmt) -> None | Error:
        pass

    def do_while_stmt(self, node: DoWhileStmt) -> None | Error:
        pass

    def goto_stmt(self, node: GotoStmt) -> None | Error:
        pass

    def label_stmt(self, ) -> None | Error:
        pass

    def eval(self, node: ASTNode) -> None | Error:
        self.trace(node)

        if isinstance(node, IdenExpr):
            pass

        if isinstance(node, IntLitExpr):
            pass

        if isinstance(node, FloatLitExpr):
            pass

        if isinstance(node, CharLitExpr):
            pass

        if isinstance(node, StrLitExpr):
            pass

        if isinstance(node, GenericSelExpr):
            pass

        if isinstance(node, ArraySubExpr):
            pass

        if isinstance(node, CallExpr):
            pass

        if isinstance(node, MemberExpr):
            pass

        if isinstance(node, CompoundLitExpr):
            pass

        if isinstance(node, CastExpr):
            pass

        if isinstance(node, OpExpr):
            pass

        if isinstance(node, CondExpr):
            pass

        if isinstance(node, AssignmentExpr):
            pass

        if isinstance(node, CommaExpr):
            pass

        if isinstance(node, SizeOfExpr):
            pass

        if isinstance(node, AlignOfExpr):
            pass

        # Declarations.


        # Statements.
        if isinstance(node, PrintLnStmt):
            return self.println_stmt(node)

        if isinstance(node, AssertStmt):
            return self.assert_stmt(node)

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

        if isinstance(node, CycleStmt):
            return self.cycle_stmt(node)

        if isinstance(node, DoWhileStmt):
            return self.do_while_stmt(node)

        if isinstance(node, GotoStmt):
            return self.goto_stmt(node)

        if isinstance(node, LabelStmt):
            pass

        if isinstance(node, BreakStmt):
            pass

        if isinstance(node, ContinueStmt):
            pass

        return None

    def run(self):
        pass


def test() -> None:
    pass


if __name__ == "__main__":
    pass
