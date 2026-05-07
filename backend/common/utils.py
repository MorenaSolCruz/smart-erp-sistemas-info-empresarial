from decimal import Decimal


def decimal_to_float(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def normalize_text(value):
    return (value or "").strip()

