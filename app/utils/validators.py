import re


GHANA_PHONE_PATTERN = re.compile(r"^(0[2459]\d{8})$")
GHANA_CARD_PATTERN = re.compile(r"^GHA\d{9,10}$")


def is_valid_ghana_phone(phone_number: str) -> bool:
    return bool(GHANA_PHONE_PATTERN.match(phone_number))


def is_valid_ghana_card(card_number: str) -> bool:
    normalized = re.sub(r"[\s-]", "", card_number.upper())
    return bool(GHANA_CARD_PATTERN.match(normalized))
