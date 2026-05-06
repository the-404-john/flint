<div align="center">
  <picture>
    <img alt="The "
         src="https://github.com/the-404-john/flint/flint_logo.png"
         width="50%">
  </picture>
</div>

This is the main source code repository for project [Flint].

[Flint]:  https://github.com/the-404-john/flint

## What is Flint?
Programming in languages like C is challenging for beginners because
many errors are difficult to detect, trace, or debug — even
experienced programmers can spend hours diagnosing them.

[Flint] is an interpreter that explicitly models a subset of [C23] and
converts certain undefined behaviors into raised exceptions. Designed
primarily for educational purposes, [Flint] is written in [Python] in
a straightforward manner so that students can also learn by reading
the source code.

> [!WARNING] Development Status
> Flint is still a work in progress! A significant amount of
development is required before the project reaches its **official Beta
release**.

[C23]: https://en.cppreference.com/w/c/23.html
[Python]: https://docs.python.org/3.14/
[Flint]: https://github.com/the-404-john/flint

## Why Flint?
- **Reliability:** Detecting undefined, unspecified, and
implementation-defined behaviours, alongside identifying memory leaks
and invalid memory usage.

- **Productivity:** Extensive documentation, robust diagnostics and
sophisticated toolchain that includes a build system and auto-formatter.

## Quick Start
If you want to install from source (though this is not recommended),
see [INSTALL.md].

[INSTALL.md]: (INSTALL.md)

## License
This project is licensed under the MIT License - see the [LICENSE-MIT]
file for details.

[LICENSE-MIT]: (LICENSE-MIT)

## Design Philosophy
The interpreter was built for teachers and students, by a teacher
and a student. Every line of code in this project is intentional. If
you encounter a section that seems unoptimized or unconventional
by modern Python standards, know that it was written that way
for a specific reason.

One of the primary goals of this project isn't just to execute [C23]
code — it’s also to ensure that a student can open the interpreter's
source code and actually understand how it works.

To maintain this level of transparency, the project follows a strict
set of constraints:
- Zero to Minimal Dependencies.
- Restricted Python Subset.
    - No Magic Methods.
    - No Complex Control Flow.
    - Manual Error Handling.

We adhere strictly to these principles, departing from them only when
necessary for system interaction. In such cases, we maintain
the smallest possible footprint to preserve educational clarity.

## Project Layout

```bash
flint/
├── flint.py          # Main entry point; bootstraps the interpreter
├── cli.py            # CLI logic and argument parsing
├── cli_msgs.py       # CLI help text and user-facing messages
├── tokenizer.py      # Lexical analysis; converts source to tokens
├── parser.py         # Syntactic analysis; builds the AST
├── flint_ast.py      # AST node structures and definitions
├── eval.py           # Tree-walking interpreter and execution
├── analysis.py       # Semantic analysis and type checking
├── format.py         # Source code auto-formatter
├── error.py          # Error handling and diagnostic reporting
├── colors.py         # ANSI terminal styling and output formatting
├── common.py         # Shared constants and utility functions
├── repl.py           # Interactive Read-Eval-Print Loop
├── build.py          # Build and packaging scripts
├── tests/            # Test suite
├── README.md
├── INSTALL.md
└── LICENSE-MIT
```
