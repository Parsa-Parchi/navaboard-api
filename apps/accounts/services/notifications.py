from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


class NotificationDeliveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmsDeliveryResult:
    provider: str


@dataclass(frozen=True)
class EmailDeliveryResult:
    backend: str


def _to_local_iranian_mobile_number(phone_number: str) -> str:
    normalized_phone_number = phone_number.strip()

    if normalized_phone_number.startswith("+98"):
        return f"0{normalized_phone_number[3:]}"

    return normalized_phone_number


def _send_smsir_verify_code(
    *,
    phone_number: str,
    code: str,
) -> SmsDeliveryResult:
    if not settings.SMSIR_API_KEY:
        raise NotificationDeliveryError("SMS.ir API key is not configured.")

    if not settings.SMSIR_VERIFY_TEMPLATE_ID:
        raise NotificationDeliveryError("SMS.ir verify template ID is not configured.")

    payload = {
        "mobile": _to_local_iranian_mobile_number(phone_number),
        "templateId": settings.SMSIR_VERIFY_TEMPLATE_ID,
        "parameters": [
            {
                "name": settings.SMSIR_CODE_PARAMETER_NAME,
                "value": code,
            }
        ],
    }

    request = Request(
        settings.SMSIR_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-API-KEY": settings.SMSIR_API_KEY,
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=settings.SMSIR_TIMEOUT_SECONDS) as response:
            response.read()
    except HTTPError as exc:
        raise NotificationDeliveryError(
            f"SMS.ir request failed with status {exc.code}."
        ) from exc
    except URLError as exc:
        raise NotificationDeliveryError("SMS.ir request failed.") from exc

    return SmsDeliveryResult(provider="smsir")


def send_sms_verification_code(
    *,
    phone_number: str,
    code: str,
    purpose: str,
) -> SmsDeliveryResult:
    sms_provider = settings.SMS_PROVIDER.strip().lower()

    if sms_provider == "console":
        logger.info(
            "SMS verification code generated for %s with purpose %s.",
            phone_number,
            purpose,
        )
        return SmsDeliveryResult(provider="console")

    if sms_provider == "smsir":
        return _send_smsir_verify_code(
            phone_number=phone_number,
            code=code,
        )

    raise NotificationDeliveryError("Unsupported SMS provider configured.")


def send_login_otp_code(
    *,
    phone_number: str,
    code: str,
) -> SmsDeliveryResult:
    return send_sms_verification_code(
        phone_number=phone_number,
        code=code,
        purpose="login",
    )


def send_password_reset_code(
    *,
    phone_number: str,
    code: str,
) -> SmsDeliveryResult:
    return send_sms_verification_code(
        phone_number=phone_number,
        code=code,
        purpose="password_reset",
    )


def send_phone_change_code(
    *,
    phone_number: str,
    code: str,
) -> SmsDeliveryResult:
    return send_sms_verification_code(
        phone_number=phone_number,
        code=code,
        purpose="change_phone",
    )


def send_email_verification_code(
    *,
    email: str,
    code: str,
) -> EmailDeliveryResult:
    send_mail(
        subject="NavaBoard email verification code",
        message=(
            f"Your NavaBoard verification code is: {code}\n\n"
            "Do not share this code with anyone."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )

    return EmailDeliveryResult(
        backend=settings.EMAIL_BACKEND,
    )