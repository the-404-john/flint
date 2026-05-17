from error import *
from flint_ast import *


# Processor Cycle Simulator
# Simulates processor clock cycles to enable deterministic program
# cost comparison. This heuristic bypasses non-deterministic hardware
# time measurements by scoring the execution complexity of expressions,
# statements, and declarations.
#
# Constraints:
# - Does not differentiate between integer and floating-point
#   operations.
# - Assumes an idealized memory model where all accesses result in
#   an L1 cache hit.


ZERO: int = 0
SMALL: int = 1
MEDIUM: int = 10
LARGE: int = 50

OP_PENALTY: dict[OpTag, int] = {
    # Unary Prefix Operations.
    UnaPrefOpTag.addr_of: ZERO,
    UnaPrefOpTag.deref:   MEDIUM,

    # Binary Operations.
    BinOpTag.mul: MEDIUM,
    BinOpTag.div: LARGE,
    BinOpTag.mod: LARGE,

    BinOpTag.mul_assign: MEDIUM,
    BinOpTag.div_assign: LARGE,
    BinOpTag.mod_assign: LARGE,
}


class CycleSimulator:
    def __init__(self) -> None:
        pass

    # Expressions.
    def expr(self, node: ExprNode) -> int:
        if isinstance(node, ArraySubExpr):
            return MEDIUM

        if isinstance(node, CallExpr):
            return MEDIUM

        if isinstance(node, MemberExpr):
            return MEDIUM * (node.is_arrow)

        if isinstance(node, OpExpr):
            return OP_PENALTY.get(node.op, SMALL)

        if isinstance(node, CondExpr):
            return SMALL

        return ZERO

    # Initialisers.
    def init(self, node: InitNode) -> int:
        if isinstance(node, InitIndex):
            return SMALL

        if isinstance(node, InitMember):
            return SMALL

        return ZERO

    def cycle_cost(self, node: ASTNode) -> int:
        if isinstance(node, ExprNode):
            return self.expr(node)

        if isinstance(node, InitNode):
            return self.init(node)

        if isinstance(node, StmtNode):
            return SMALL

        return ZERO
