import sys
import os

# Enable ANSI escape codes only when the terminal can render them.
ANSI: bool = (
    (sys.stdout.isatty() or "FORCE_COLOR" in os.environ)
    and "NO_COLOR" not in os.environ
    and os.environ.get("TERM") != "dumb"
)

# Terminal colors.
BLACK   = "\033[30m" if ANSI else ""
RED     = "\033[31m" if ANSI else ""
GREEN   = "\033[32m" if ANSI else ""
YELLOW  = "\033[33m" if ANSI else ""
BLUE    = "\033[34m" if ANSI else ""
MAGENTA = "\033[35m" if ANSI else ""
CYAN    = "\033[36m" if ANSI else ""
WHITE   = "\033[37m" if ANSI else ""

# Terminal text style modifiers.
BOLD   = "\033[1m"  if ANSI else ""
NORMAL = "\033[22m" if ANSI else ""
DIM    = "\033[2m"  if ANSI else ""
RESET  = "\033[0m"  if ANSI else ""
