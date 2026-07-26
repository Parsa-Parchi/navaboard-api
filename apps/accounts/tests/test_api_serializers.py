from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from apps.accounts.api.serializers import (
    PhoneChangeConfirmResponseSerializer,
    PhoneChangeConfirmSerializer,
    PhoneChangeRequestResponseSerializer,
    PhoneChangeRequestSerializer,
    PasswordResetConfirmResponseSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestResponseSerializer,
    PasswordResetRequestSerializer,
    EmailVerificationConfirmResponseSerializer,
    EmailVerificationConfirmSerializer,
    EmailVerificationRequestResponseSerializer,
    EmailVerificationRequestSerializer,
    ChangePasswordSerializer,
    CurrentUserProfileSerializer,
    EmailPasswordLoginSerializer,
    LogoutResponseSerializer,
    OTPRequestSerializer,
    OTPVerificationSerializer,
    SetInitialPasswordSerializer,
    TokenRefreshResponseSerializer,
    EmailSignupConfirmRequestSerializer,
    EmailSignupConfirmResponseSerializer,
    EmailSignupRequestResponseSerializer,
    EmailSignupRequestSerializer,
)
User = get_user_model()

class OTPRequestSerializerTests(SimpleTestCase):
    def test_validates_and_normalizes_phone_number(self):
        serializer = OTPRequestSerializer(
            data={
                "phone_number": "09121234567",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["phone_number"],
            "+989121234567",
        )
        self.assertNotIn("purpose", serializer.validated_data)

    def test_rejects_supported_purpose_from_public_request(self):
        serializer = OTPRequestSerializer(
            data={
                "phone_number": "۰۹۱۲۱۲۳۴۵۶۷",
                "purpose": "login",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("purpose", serializer.errors)

    def test_rejects_invalid_phone_number(self):
        serializer = OTPRequestSerializer(
            data={
                "phone_number": "02112345678",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)

    def test_rejects_missing_phone_number(self):
        serializer = OTPRequestSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)

    def test_rejects_invalid_purpose(self):
        serializer = OTPRequestSerializer(
            data={
                "phone_number": "09121234567",
                "purpose": "invalid-purpose",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("purpose", serializer.errors)

class OTPVerificationSerializerTests(SimpleTestCase):
    def test_validates_and_normalizes_phone_number_and_code(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
                "code": "123456",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["phone_number"],
            "+989121234567",
        )
        self.assertEqual(serializer.validated_data["code"], "123456")
        self.assertNotIn("purpose", serializer.validated_data)

    def test_rejects_supported_purpose_from_public_verification(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "۰۹۱۲۱۲۳۴۵۶۷",
                "code": "123456",
                "purpose": "login",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("purpose", serializer.errors)

    def test_rejects_invalid_phone_number(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "02112345678",
                "code": "123456",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)

    def test_rejects_missing_code(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_non_numeric_code(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
                "code": "abcdef",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_short_code(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
                "code": "12345",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_invalid_purpose(self):
        serializer = OTPVerificationSerializer(
            data={
                "phone_number": "09121234567",
                "code": "123456",
                "purpose": "invalid-purpose",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("purpose", serializer.errors)


class AuthSessionSerializerTests(SimpleTestCase):
    def test_token_refresh_response_is_valid(self):
        serializer = TokenRefreshResponseSerializer(
            data={
                "access": "access-token-value",
                "token_type": "Bearer",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_logout_response_is_valid(self):
        serializer = LogoutResponseSerializer(
            data={
                "detail": "Logged out successfully.",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

class CurrentUserProfileSerializerTests(TestCase):
    def test_serializes_current_user_profile(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            email="ali@example.com",
            full_name="Ali Test",
            is_phone_verified=True,
        )

        serializer = CurrentUserProfileSerializer(user)

        self.assertEqual(serializer.data["phone_number"], "+989121234567")
        self.assertEqual(serializer.data["email"], "ali@example.com")
        self.assertEqual(serializer.data["full_name"], "Ali Test")
        self.assertTrue(serializer.data["is_phone_verified"])

    def test_updates_full_name_and_trims_whitespace(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            full_name="Old Name",
        )

        serializer = CurrentUserProfileSerializer(
            instance=user,
            data={
                "full_name": "  New Name  ",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_user = serializer.save()

        self.assertEqual(updated_user.full_name, "New Name")

    def test_ignores_read_only_identity_fields_when_updating(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            email="old@example.com",
            full_name="Old Name",
            is_phone_verified=True,
        )

        serializer = CurrentUserProfileSerializer(
            instance=user,
            data={
                "phone_number": "+989991234567",
                "email": "new@example.com",
                "is_phone_verified": False,
                "full_name": "New Name",
            },
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_user = serializer.save()

        self.assertEqual(updated_user.phone_number, "+989121234567")
        self.assertEqual(updated_user.email, "old@example.com")
        self.assertTrue(updated_user.is_phone_verified)
        self.assertEqual(updated_user.full_name, "New Name")

class EmailPasswordLoginSerializerTests(SimpleTestCase):
    def test_validates_and_normalizes_email(self):
        serializer = EmailPasswordLoginSerializer(
            data={
                "email": "  Ali@Example.COM  ",
                "password": "StrongPassword123!",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["email"], "ali@example.com")
        self.assertEqual(
            serializer.validated_data["password"],
            "StrongPassword123!",
        )

    def test_preserves_password_whitespace(self):
        serializer = EmailPasswordLoginSerializer(
            data={
                "email": "ali@example.com",
                "password": "  StrongPassword123!  ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["password"],
            "  StrongPassword123!  ",
        )

    def test_rejects_invalid_email(self):
        serializer = EmailPasswordLoginSerializer(
            data={
                "email": "not-an-email",
                "password": "StrongPassword123!",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_rejects_missing_password(self):
        serializer = EmailPasswordLoginSerializer(
            data={
                "email": "ali@example.com",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)


class EmailSignupSerializerTests(SimpleTestCase):
    def test_request_validates_email_password_and_full_name(self):
        serializer = EmailSignupRequestSerializer(
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
                "full_name": "Ali Test",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["email"], "ali@example.com")
        self.assertEqual(
            serializer.validated_data["password"],
            "StrongPassword123!",
        )
        self.assertEqual(serializer.validated_data["full_name"], "Ali Test")

    def test_request_allows_blank_full_name(self):
        serializer = EmailSignupRequestSerializer(
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
                "full_name": "",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["full_name"], "")

    def test_request_rejects_invalid_email(self):
        serializer = EmailSignupRequestSerializer(
            data={
                "email": "not-an-email",
                "password": "StrongPassword123!",
                "full_name": "Ali Test",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_request_rejects_missing_password(self):
        serializer = EmailSignupRequestSerializer(
            data={
                "email": "ali@example.com",
                "full_name": "Ali Test",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_confirm_accepts_email_and_code(self):
        serializer = EmailSignupConfirmRequestSerializer(
            data={
                "email": "ali@example.com",
                "code": "123456",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["email"], "ali@example.com")
        self.assertEqual(serializer.validated_data["code"], "123456")

    def test_confirm_rejects_invalid_email(self):
        serializer = EmailSignupConfirmRequestSerializer(
            data={
                "email": "not-an-email",
                "code": "123456",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("email", serializer.errors)

    def test_request_response_is_valid(self):
        serializer = EmailSignupRequestResponseSerializer(
            data={
                "detail": "Email signup verification code has been generated.",
                "user_created": True,
                "development_email_verification_code": "123456",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_confirm_response_is_valid(self):
        serializer = EmailSignupConfirmResponseSerializer(
            data={
                "access": "access-token-value",
                "token_type": "Bearer",
                "user": {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "phone_number": None,
                    "email": "ali@example.com",
                    "full_name": "Ali Test",
                    "is_phone_verified": False,
                },
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

class SetInitialPasswordSerializerTests(SimpleTestCase):
    def test_accepts_password(self):
        serializer = SetInitialPasswordSerializer(
            data={
                "password": "StrongPassword123!",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["password"],
            "StrongPassword123!",
        )

    def test_preserves_password_whitespace(self):
        serializer = SetInitialPasswordSerializer(
            data={
                "password": "  StrongPassword123!  ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["password"],
            "  StrongPassword123!  ",
        )

    def test_rejects_missing_password(self):
        serializer = SetInitialPasswordSerializer(data={})

        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

class ChangePasswordSerializerTests(SimpleTestCase):
    def test_accepts_current_and_new_password(self):
        serializer = ChangePasswordSerializer(
            data={
                "current_password": "OldStrongPassword123!",
                "new_password": "NewStrongPassword123!",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["current_password"],
            "OldStrongPassword123!",
        )
        self.assertEqual(
            serializer.validated_data["new_password"],
            "NewStrongPassword123!",
        )

    def test_preserves_password_whitespace(self):
        serializer = ChangePasswordSerializer(
            data={
                "current_password": "  OldStrongPassword123!  ",
                "new_password": "  NewStrongPassword123!  ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(
            serializer.validated_data["current_password"],
            "  OldStrongPassword123!  ",
        )
        self.assertEqual(
            serializer.validated_data["new_password"],
            "  NewStrongPassword123!  ",
        )

    def test_rejects_missing_current_password(self):
        serializer = ChangePasswordSerializer(
            data={
                "new_password": "NewStrongPassword123!",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("current_password", serializer.errors)

    def test_rejects_missing_new_password(self):
        serializer = ChangePasswordSerializer(
            data={
                "current_password": "OldStrongPassword123!",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("new_password", serializer.errors)

class EmailVerificationRequestSerializerTests(SimpleTestCase):
    def test_normalizes_email(self):
        serializer = EmailVerificationRequestSerializer(
            data={
                "email": "  Ali@Example.COM  ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["email"], "ali@example.com")


class EmailVerificationConfirmSerializerTests(SimpleTestCase):
    def test_normalizes_email_and_code(self):
        serializer = EmailVerificationConfirmSerializer(
            data={
                "email": "  Ali@Example.COM  ",
                "code": " 123456 ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["email"], "ali@example.com")
        self.assertEqual(serializer.validated_data["code"], "123456")

    def test_rejects_non_numeric_code(self):
        serializer = EmailVerificationConfirmSerializer(
            data={
                "email": "ali@example.com",
                "code": "abc123",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_code_with_invalid_length(self):
        serializer = EmailVerificationConfirmSerializer(
            data={
                "email": "ali@example.com",
                "code": "12345",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)


class EmailVerificationResponseSerializerTests(SimpleTestCase):
    def test_request_response_accepts_optional_development_code(self):
        serializer = EmailVerificationRequestResponseSerializer(
            data={
                "detail": "Email verification code has been created.",
                "expires_at": "2026-01-01T12:00:00Z",
                "development_verification_code": "123456",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_confirm_response_is_valid(self):
        serializer = EmailVerificationConfirmResponseSerializer(
            data={
                "detail": "Email address has been verified successfully.",
                "email": "ali@example.com",
                "is_email_verified": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

class PasswordResetRequestSerializerTests(SimpleTestCase):
    def test_normalizes_phone_number(self):
        serializer = PasswordResetRequestSerializer(
            data={
                "phone_number": "0912 123 4567",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["phone_number"], "+989121234567")

    def test_rejects_invalid_phone_number(self):
        serializer = PasswordResetRequestSerializer(
            data={
                "phone_number": "12345",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)


class PasswordResetConfirmSerializerTests(SimpleTestCase):
    def test_normalizes_phone_number_and_code(self):
        serializer = PasswordResetConfirmSerializer(
            data={
                "phone_number": "0912 123 4567",
                "code": " 123456 ",
                "new_password": "NewStrongPassword123!",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["phone_number"], "+989121234567")
        self.assertEqual(serializer.validated_data["code"], "123456")
        self.assertEqual(
            serializer.validated_data["new_password"],
            "NewStrongPassword123!",
        )

    def test_rejects_non_numeric_code(self):
        serializer = PasswordResetConfirmSerializer(
            data={
                "phone_number": "+989121234567",
                "code": "abc123",
                "new_password": "NewStrongPassword123!",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_code_with_invalid_length(self):
        serializer = PasswordResetConfirmSerializer(
            data={
                "phone_number": "+989121234567",
                "code": "12345",
                "new_password": "NewStrongPassword123!",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)


class PasswordResetResponseSerializerTests(SimpleTestCase):
    def test_request_response_accepts_optional_development_code(self):
        serializer = PasswordResetRequestResponseSerializer(
            data={
                "detail": "Password reset code has been created.",
                "expires_at": "2026-01-01T12:00:00Z",
                "development_otp_code": "123456",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_confirm_response_is_valid(self):
        serializer = PasswordResetConfirmResponseSerializer(
            data={
                "detail": "Password has been reset successfully.",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

class PhoneChangeRequestSerializerTests(SimpleTestCase):
    def test_normalizes_phone_number(self):
        serializer = PhoneChangeRequestSerializer(
            data={
                "phone_number": "0912 444 5566",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["phone_number"], "+989124445566")

    def test_rejects_invalid_phone_number(self):
        serializer = PhoneChangeRequestSerializer(
            data={
                "phone_number": "12345",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("phone_number", serializer.errors)


class PhoneChangeConfirmSerializerTests(SimpleTestCase):
    def test_normalizes_phone_number_and_code(self):
        serializer = PhoneChangeConfirmSerializer(
            data={
                "phone_number": "0912 444 5566",
                "code": " 123456 ",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["phone_number"], "+989124445566")
        self.assertEqual(serializer.validated_data["code"], "123456")

    def test_rejects_non_numeric_code(self):
        serializer = PhoneChangeConfirmSerializer(
            data={
                "phone_number": "+989124445566",
                "code": "abc123",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)

    def test_rejects_code_with_invalid_length(self):
        serializer = PhoneChangeConfirmSerializer(
            data={
                "phone_number": "+989124445566",
                "code": "12345",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("code", serializer.errors)


class PhoneChangeResponseSerializerTests(SimpleTestCase):
    def test_request_response_accepts_optional_development_code(self):
        serializer = PhoneChangeRequestResponseSerializer(
            data={
                "detail": "Phone change code has been created.",
                "expires_at": "2026-01-01T12:00:00Z",
                "development_otp_code": "123456",
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_confirm_response_is_valid(self):
        serializer = PhoneChangeConfirmResponseSerializer(
            data={
                "detail": "Phone number has been changed successfully.",
                "phone_number": "+989124445566",
                "is_phone_verified": True,
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
