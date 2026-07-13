from unittest.mock import patch

from django.core import mail
from django.test import SimpleTestCase, override_settings

from apps.accounts.services.notifications import (
    NotificationDeliveryError,
    send_email_verification_code,
    send_login_otp_code,
)


class NotificationServiceTests(SimpleTestCase):
    @override_settings(SMS_PROVIDER="console")
    def test_console_sms_provider_returns_success_result(self):
        result = send_login_otp_code(
            phone_number="+989121234567",
            code="123456",
        )

        self.assertEqual(result.provider, "console")

    @override_settings(SMS_PROVIDER="unsupported")
    def test_rejects_unsupported_sms_provider(self):
        with self.assertRaises(NotificationDeliveryError):
            send_login_otp_code(
                phone_number="+989121234567",
                code="123456",
            )

    @override_settings(
        SMS_PROVIDER="smsir",
        SMSIR_API_KEY="test-api-key",
        SMSIR_VERIFY_TEMPLATE_ID=12345,
        SMSIR_CODE_PARAMETER_NAME="CODE",
        SMSIR_API_URL="https://api.sms.ir/v1/send/verify",
        SMSIR_TIMEOUT_SECONDS=10,
    )
    @patch("apps.accounts.services.notifications.urlopen")
    def test_smsir_provider_sends_verify_request(self, mocked_urlopen):
        mocked_urlopen.return_value.__enter__.return_value.read.return_value = b"{}"

        result = send_login_otp_code(
            phone_number="+989121234567",
            code="123456",
        )

        request = mocked_urlopen.call_args.args[0]

        self.assertEqual(result.provider, "smsir")
        self.assertEqual(request.full_url, "https://api.sms.ir/v1/send/verify")
        self.assertEqual(request.headers["X-api-key"], "test-api-key")
        self.assertIn(b'"mobile": "09121234567"', request.data)
        self.assertIn(b'"templateId": 12345', request.data)
        self.assertIn(b'"name": "CODE"', request.data)
        self.assertIn(b'"value": "123456"', request.data)

    @override_settings(
        SMS_PROVIDER="smsir",
        SMSIR_API_KEY="",
        SMSIR_VERIFY_TEMPLATE_ID=12345,
    )
    def test_smsir_provider_requires_api_key(self):
        with self.assertRaises(NotificationDeliveryError):
            send_login_otp_code(
                phone_number="+989121234567",
                code="123456",
            )

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="NavaBoard <no-reply@example.com>",
    )
    def test_sends_email_verification_code(self):
        result = send_email_verification_code(
            email="ali@example.com",
            code="123456",
        )

        self.assertEqual(result.backend, "django.core.mail.backends.locmem.EmailBackend")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ali@example.com"])
        self.assertEqual(mail.outbox[0].from_email, "NavaBoard <no-reply@example.com>")
        self.assertIn("123456", mail.outbox[0].body)