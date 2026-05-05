# step limit
# trace
# rosahy v tokenoch, aby pri chybach ked mam viacero riadkov, aby issue
# tak toto je problem

from error import ErrorCode
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

    def inc_step_count(self, node: ASTNode) -> None:
        pass

    def trace(self, node: ASTNode) -> None:
        pass

    def iden_expr(self, node: IdenExpr):
        pass

    def comound_stmt(self, node: CompoundStmt) -> ErrorCode | None:
        pass

    def expr_stmt(self, node: ExprStmt) -> ErrorCode | None:
        pass

    def if_stmt(self, node: IfStmt) -> ErrorCode | None:
        result = self.eval_expr(node.cond_expr)

        if XXXX:
            return eval_stmt(node.then_stmt)
        elif else_stmt is not None:
            return eval_stmt(node.else_stmt)

        return None

    def switch_stmt(self, node: SwitchStmt) -> ErrorCode | None:
        pass

    def cycle_stmt(self, node: CycleStmt) -> ErrorCode | None:
        pass

    def do_while_stmt(self, node: DoWhileStmt) -> ErrorCode | None:
        pass

    def goto_stmt(self, node: GotoStmt) -> ErrorCode | None:
        pass

    def label_stmt(self, node: LabelStmt) -> ErrorCode | None:
        pass

    def eval(self, node: ASTNode):
        pass

    def run(self):
        pass


def test() -> None:
    pass


if __name__ == "__main__":
    pass
