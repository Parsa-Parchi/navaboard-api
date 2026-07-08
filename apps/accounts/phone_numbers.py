import re

from django.core.exceptions import ValidationError


IRANIAN_MOBILE_ERROR_MESSAGE = (
    "Phone number must be an Iranian mobile number in E.164 format. "
    "Example: +989121234567"
)

_PERSIAN_AND_ARABIC_DIGITS_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def normalize_iranian_mobile_number(phone_number: str | None) -> str | None:
    if phone_number is None:
        return None

    normalized_phone_number = str(phone_number).strip()
    normalized_phone_number = normalized_phone_number.translate(
        _PERSIAN_AND_ARABIC_DIGITS_TRANSLATION
    )
    normalized_phone_number = re.sub(r"[\s\-\(\)]", "", normalized_phone_number)

    if not normalized_phone_number:
        return None

    if normalized_phone_number.startswith("0098"):
        normalized_phone_number = f"+98{normalized_phone_number[4:]}"
    elif normalized_phone_number.startswith("98"):
        normalized_phone_number = f"+{normalized_phone_number}"
    elif normalized_phone_number.startswith("09"):
        normalized_phone_number = f"+98{normalized_phone_number[1:]}"
    elif normalized_phone_number.startswith("9"):
        normalized_phone_number = f"+98{normalized_phone_number}"
    elif not normalized_phone_number.startswith("+98"):
        raise ValidationError(IRANIAN_MOBILE_ERROR_MESSAGE)

    if not re.fullmatch(r"\+989\d{9}", normalized_phone_number):
        raise ValidationError(IRANIAN_MOBILE_ERROR_MESSAGE)

    return normalized_phone_number