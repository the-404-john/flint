<div align="center">
  <picture>
    <img
        alt="Flint Interpreter: An educational tool for C programming best practices"
        src="https://raw.githubusercontent.com/the-404-john/flint/main/flint_logo.png"
        width="50%">
  </picture>

  <p>This is the main source code repository for project
    <a href="https://github.com/the-404-john/flint">Flint</a>.
  </p>
</div>

## What is Flint?
Programming in languages like C is challenging for beginners because
many errors are difficult to detect, trace, or debug — even
experienced programmers can spend hours diagnosing them.

[Flint] is an interpreter that explicitly models a subset of [C23] and
provides defined semantics for undefined behaviors. Designed
primarily for educational purposes, [Flint] is written in [Python] in
a straightforward manner so that students can also learn by reading
the source code.

> [!WARNING]
> [Flint] is still a work in progress! A significant amount of
development is required before the project reaches its **official Beta
release**.

[C23]: https://en.cppreference.com/w/c/23
[Python]: https://docs.python.org/3/
[Flint]: https://github.com/the-404-john/flint

## Why Flint?
- **Reliability:** Detecting undefined, unspecified, and
implementation-defined behaviours, alongside identifying memory leaks
and invalid memory usage.

- **Productivity:** Extensive documentation, robust diagnostics and
sophisticated toolchain that includes a build system and auto-formatter.

## Quick Start
No installation is required. Run the interpreter directly with
[Python] 3.10 or later:

```bash
python3 src/flint.py
```

To build a high-performance standalone binary instead, see [INSTALL.md].

[INSTALL.md]: INSTALL.md

## License
This project is licensed under the MIT License — see the [LICENSE-MIT]
file for details.

[LICENSE-MIT]: LICENSE-MIT

## Design Philosophy
The interpreter was built for teachers and students, by a teacher
and a student. Every line of code in this project is intentional. If
you encounter a section that seems unoptimized or unconventional
by modern [Python] standards, know that it was written that way
for a specific reason.

One of the primary goals of this project isn't just to execute [C23]
code — it's also to ensure that a student can open the interpreter's
source code and actually understand how it works.

To maintain this level of transparency, the project follows a strict
set of constraints:
- Zero to minimal dependencies.
- Restricted [Python] subset.
    - No magic methods.
    - No complex control flow.
    - Manual error handling.

We adhere strictly to these principles, departing from them only when
necessary for system interaction. In such cases, we maintain
the smallest possible footprint to preserve educational clarity.

## Project Layout

```
flint/
├── src/
│   │
│   # ─── Entry Points & Interface ───────────────────────────────────
│   ├── flint.py            # Main entry point — bootstraps the CLI.
│   ├── cli.py              # Argument parsing and command dispatch.
│   ├── cli_messages.py     # Help text and user-facing messages.
│   ├── repl.py             # Interactive Read-Eval-Print Loop.
│   ├── build.py            # Orchestrates parse → analyze → optimize.
│   └── format.py           # Source code auto-formatter.
│   │
│   # ─── Lexing & Parsing ────────────────────────────────────────────
│   ├── tokenizer.py        # Lexical analysis — source text to tokens.
│   ├── parser.py           # Syntactic analysis — tokens to AST.
│   └── flint_ast.py        # AST node types and definitions.
│   │
│   # ─── Execution ───────────────────────────────────────────────────
│   ├── eval.py             # Tree-walking interpreter.
│   ├── memory.py           # Memory model (stack, heap, globals).
│   ├── scope.py            # Variable scope and lifetime management.
│   └── value_objects.py    # Runtime value and type representations.
│   │
│   # ─── Analysis & Utilities ────────────────────────────────────────
│   ├── analysis.py         # Static semantic analysis.
│   ├── norm.py             # Arithmetic and type normalization.
│   ├── convert.py          # Value and memory type converters.
│   ├── cycle_simulation.py # Deterministic processor-cycle estimator.
│   ├── limits.py           # C23 type size and range constants.
│   ├── error.py            # Error types and diagnostic reporting.
│   ├── colors.py           # ANSI terminal color helpers.
│   ├── common.py           # Shared constants and utility functions.
│   └── dump.py             # AST debug dumper (work in progress).
│
├── tests/
│   ├── simple/             # Hand-written behavioral test cases.
│   ├── gcc-torture-subset/ # Subset of the GCC torture test suite.
│   │   ├── compile/        # Compile-only tests.
│   │   └── execute/        # Execute-and-verify tests.
│   ├── ub-torture-subset/  # Undefined-behaviour torture tests.
│   └── hidden/             # Reserved for CI / grading (gitignored).
│
# ─── Identity ────────────────────────────────────────────────────────
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── INSTALL.md
├── LICENSE-MIT
├── README.md
└── flint_logo.png
```
