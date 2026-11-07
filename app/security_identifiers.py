"""Check digits establish identifier syntax, not provider coverage or ownership."""
from __future__ import annotations

import re


def valid_cusip(value: str) -> bool:
    if not re.fullmatch(r"[A-Z0-9*@#]{8}[0-9]", value):
        return False
    total = 0
    for index, character in enumerate(value[:8]):
        number = int(character) if character.isdigit() else {"*": 36, "@": 37, "#": 38}.get(character, ord(character) - 55)
        number *= 2 if index % 2 else 1
        total += number // 10 + number % 10
    return (10 - total % 10) % 10 == int(value[-1])


def valid_isin(value: str) -> bool:
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", value):
        return False
    digits = "".join(str(ord(character) - 55) if character.isalpha() else character for character in value)
    total = 0
    for index, character in enumerate(reversed(digits)):
        number = int(character) * (2 if index % 2 else 1)
        total += number // 10 + number % 10
    return total % 10 == 0
