def str_to_int(string: str) -> int | Error:
    num: int = 0

    if len(string) == 0:
        return Error()

    for chr in string:
        if not chr.isdigit():
            return Error()

        num *= 10
        num += ord(chr) - ord('0')

    return num


def is_bin_digit(char: str) -> bool:
    return '0' <= char <= '1'


def is_oct_digit(char: str) -> bool:
    return '0' <= char <= '7'


def is_dec_digit(char: str) -> bool:
    return '0' <= char <= '9'


def is_hex_digit(char: str) -> bool:
    char = char.lower()
    return '0' <= char <= '9' or 'a' <= char <= 'f'


def is_letter_or_num(char: str) -> bool:
    return char.isalnum() and char.isascii()
