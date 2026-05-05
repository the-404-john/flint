
# Static verification
# 1. Control flow statements `break` and `continue` are only present
#    inside iteration statements.
#
# 2. Labels `case` and `default` are only present in switch statement.
#


# Labels `case` contain only compile time integer constants.
#
# const
# . Identifiers must not contain with prefix:
#    - underscore + uppercase
#    - underscore + underscore + lowercase
#    -
#
# .
#

# x. are used identifiers in expressions are defined within the scope
# .
# x. Function calls are correctly called
# x. initializer lists are in proper form, to their type
# x. operators are defined on expression types
# x. if casts are valid on the given type


# Dynamic verification
# index out of bounds
# invalid pointer arithmetic
# nullptr dereference
# no return
# reading uninitialized variable
# type overflow
# division by zero




#
# 1. Implicit conversions.
#

# verify, that
# - break and continue is only in loops
# - case and default are only in switch

# - types are correct to their operator

# -
