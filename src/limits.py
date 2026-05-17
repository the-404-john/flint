from flint_ast import IntKind, CharKind, RealFloatKind, DecimalFloatKind

# Limits
# Maps standard data types to their byte size.


CHAR_BIT_SIZE: int = 8

PTR_SIZE: int = 16

INT_KIND_SIZE: dict[IntKind, int] = {
    IntKind.short:     2,
    IntKind.int:       4,
    IntKind.long:      8,
    IntKind.long_long: 8,
}

CHAR_KIND_SIZE: dict[CharKind, int] = {
    CharKind.char:    1,
    CharKind.char8:   1,
    CharKind.char16:  2,
    CharKind.char32:  4,
    CharKind.wchar:   4,
}

REAL_FLOAT_KIND_SIZE: dict[RealFloatKind, int] = {
    RealFloatKind.float:       8,
    RealFloatKind.double:      8,
    RealFloatKind.long_double: 8,
}

DECIMAL_FLOAT_KIND_SIZE: dict[DecimalFloatKind, int] = {
    DecimalFloatKind.decimal32:  4,
    DecimalFloatKind.decimal64:  8,
    DecimalFloatKind.decimal128: 16,
}


def test_limits() -> None:
    pass


if __name__ == "__main__":
    test_limits()
