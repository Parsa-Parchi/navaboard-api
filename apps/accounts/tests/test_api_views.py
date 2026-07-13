from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from apps.accounts.services.tokens import issue_auth_token_pair
from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import check_otp_code, create_otp_challenge
from django.test import TestCase, override_settings
from apps.accounts.models import EmailVerificationChallenge, OTPChallenge


from django.contrib.auth import get_user_model


User = get_user_model()

class OTPRequestAPIViewTests(APITestCase):

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_requests_otp_code(self):
        url = reverse("accounts-api:otp-request")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["detail"], "OTP code has been generated.")
        self.assertIn("expires_at", response.data)
        self.assertIn("development_otp_code", response.data)

        challenge = OTPChallenge.objects.get()

        self.assertEqual(challenge.phone_number, "+989121234567")
        self.assertEqual(challenge.purpose, OTPChallenge.Purpose.LOGIN)
        self.assertTrue(
            check_otp_code(
                response.data["development_otp_code"],
                challenge.code_hash,
            )
        )

    def test_rejects_invalid_phone_number(self):
        url = reverse("accounts-api:otp-request")

        response = self.client.post(
            url,
            data={
                "phone_number": "02112345678",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("phone_number", response.data)

    def test_revokes_previous_active_challenge(self):
        url = reverse("accounts-api:otp-request")

        first_response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
            },
            format="json",
        )
        second_response = self.client.post(
            url,
            data={
                "phone_number": "+989121234567",
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)

        challenges = OTPChallenge.objects.order_by("created_at")
        self.assertEqual(challenges.count(), 2)
        self.assertIsNotNone(challenges[0].revoked_at)
        self.assertIsNone(challenges[1].revoked_at)


    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=False)
    def test_does_not_expose_development_otp_code_when_disabled(self):
        url = reverse("accounts-api:otp-request")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("expires_at", response.data)
        self.assertNotIn("development_otp_code", response.data)


class OTPVerificationAPIViewTests(APITestCase):
    def test_verifies_otp_and_returns_tokens_for_new_user(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        url = reverse("accounts-api:otp-verify")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertTrue(response.data["user_created"])
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user_data = response.data["user"]
        self.assertEqual(user_data["phone_number"], "+989121234567")
        self.assertTrue(user_data["is_phone_verified"])

        request_result.challenge.refresh_from_db()
        self.assertIsNotNone(request_result.challenge.used_at)

    def test_verifies_otp_and_returns_existing_user(self):
        first_request_result = create_otp_challenge(phone_number="09121234567")
        url = reverse("accounts-api:otp-verify")

        first_response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
                "code": first_request_result.plain_code,
            },
            format="json",
        )

        second_request_result = create_otp_challenge(phone_number="09121234567")

        second_response = self.client.post(
            url,
            data={
                "phone_number": "+989121234567",
                "code": second_request_result.plain_code,
            },
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertTrue(first_response.data["user_created"])
        self.assertFalse(second_response.data["user_created"])
        self.assertEqual(
            first_response.data["user"]["id"],
            second_response.data["user"]["id"],
        )

    def test_rejects_invalid_otp_code(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        invalid_code = (
            "000000"
            if request_result.plain_code != "000000"
            else "111111"
        )
        url = reverse("accounts-api:otp-verify")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
                "code": invalid_code,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_missing_active_challenge(self):
        url = reverse("accounts-api:otp-verify")

        response = self.client.post(
            url,
            data={
                "phone_number": "09121234567",
                "code": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class AuthSessionAPIViewTests(APITestCase):
    def test_refreshes_auth_tokens(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        refresh_url = reverse("accounts-api:token-refresh")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        response = self.client.post(
            refresh_url,
            data={
                "refresh": verify_response.data["refresh"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertNotEqual(
            response.data["refresh"],
            verify_response.data["refresh"],
        )

    def test_rejects_invalid_refresh_token(self):
        url = reverse("accounts-api:token-refresh")

        response = self.client.post(
            url,
            data={
                "refresh": "invalid-refresh-token",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logs_out_by_blacklisting_refresh_token(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        logout_url = reverse("accounts-api:logout")
        refresh_url = reverse("accounts-api:token-refresh")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        logout_response = self.client.post(
            logout_url,
            data={
                "refresh": verify_response.data["refresh"],
            },
            format="json",
        )

        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            logout_response.data["detail"],
            "Logged out successfully.",
        )

        refresh_response = self.client.post(
            refresh_url,
            data={
                "refresh": verify_response.data["refresh"],
            },
            format="json",
        )

        self.assertEqual(refresh_response.status_code, status.HTTP_400_BAD_REQUEST)

class CurrentUserProfileAPIViewTests(APITestCase):
    def test_rejects_unauthenticated_request(self):
        url = reverse("accounts-api:me")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_current_user_profile(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        me_url = reverse("accounts-api:me")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        response = self.client.get(me_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], "+989121234567")
        self.assertTrue(response.data["is_phone_verified"])
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)

    def test_updates_current_user_full_name(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        me_url = reverse("accounts-api:me")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        response = self.client.patch(
            me_url,
            data={
                "full_name": "  Ali Test  ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["full_name"], "Ali Test")

    def test_does_not_update_read_only_identity_fields(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        me_url = reverse("accounts-api:me")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        response = self.client.patch(
            me_url,
            data={
                "phone_number": "+989991234567",
                "email": "new@example.com",
                "is_phone_verified": False,
                "full_name": "Ali Updated",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["phone_number"], "+989121234567")
        self.assertIsNone(response.data["email"])
        self.assertTrue(response.data["is_phone_verified"])
        self.assertEqual(response.data["full_name"], "Ali Updated")
class EmailPasswordLoginAPIViewTests(APITestCase):
    def test_logs_in_verified_user_with_email_and_password(self):
        user = User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )
        url = reverse("accounts-api:email-login")

        response = self.client.post(
            url,
            data={
                "email": "ALI@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["token_type"], "Bearer")
        self.assertFalse(response.data["user_created"])
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(str(response.data["user"]["id"]), str(user.id))
        self.assertEqual(response.data["user"]["email"], "ali@example.com")

    def test_rejects_wrong_password(self):
        User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=True,
        )
        url = reverse("accounts-api:email-login")

        response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_unverified_email(self):
        User.objects.create_user(
            email="ali@example.com",
            password="StrongPassword123!",
            is_email_verified=False,
        )
        url = reverse("accounts-api:email-login")

        response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_account_without_password_login_enabled(self):
        User.objects.create_user(
            email="ali@example.com",
            is_email_verified=True,
        )
        url = reverse("accounts-api:email-login")

        response = self.client.post(
            url,
            data={
                "email": "ali@example.com",
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class SetInitialPasswordAPIViewTests(APITestCase):
    def test_sets_initial_password_for_authenticated_user(self):
        request_result = create_otp_challenge(phone_number="09121234567")
        verify_url = reverse("accounts-api:otp-verify")
        set_password_url = reverse("accounts-api:set-password")

        verify_response = self.client.post(
            verify_url,
            data={
                "phone_number": "09121234567",
                "code": request_result.plain_code,
            },
            format="json",
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {verify_response.data['access']}",
        )

        response = self.client.post(
            set_password_url,
            data={
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Password has been set successfully.",
        )

        user = User.objects.get(phone_number="+989121234567")
        self.assertTrue(user.check_password("StrongPassword123!"))

    def test_rejects_unauthenticated_request(self):
        url = reverse("accounts-api:set-password")

        response = self.client.post(
            url,
            data={
                "password": "StrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_setting_password_when_password_already_exists(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="StrongPassword123!",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        url = reverse("accounts-api:set-password")

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        response = self.client.post(
            url,
            data={
                "password": "AnotherStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class ChangePasswordAPIViewTests(APITestCase):
    def test_changes_password_for_authenticated_user(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        url = reverse("accounts-api:change-password")

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        response = self.client.post(
            url,
            data={
                "current_password": "OldStrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Password has been changed successfully.",
        )

        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPassword123!"))
        self.assertFalse(user.check_password("OldStrongPassword123!"))

    def test_rejects_unauthenticated_request(self):
        url = reverse("accounts-api:change-password")

        response = self.client.post(
            url,
            data={
                "current_password": "OldStrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejects_wrong_current_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        url = reverse("accounts-api:change-password")

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        response = self.client.post(
            url,
            data={
                "current_password": "WrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_user_without_existing_password(self):
        user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )
        token_pair = issue_auth_token_pair(user)
        url = reverse("accounts-api:change-password")

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token_pair.access}",
        )

        response = self.client.post(
            url,
            data={
                "current_password": "OldStrongPassword123!",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class EmailVerificationAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121234567",
            is_phone_verified=True,
        )

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_authenticated_user_can_request_email_verification_code(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "  Ali@Example.COM  ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["detail"],
            "Email verification code has been created.",
        )
        self.assertIn("expires_at", response.data)
        self.assertIn("development_verification_code", response.data)

        challenge = EmailVerificationChallenge.objects.get(user=self.user)

        self.assertEqual(challenge.email, "ali@example.com")
        self.assertEqual(len(response.data["development_verification_code"]), 6)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=False)
    def test_request_response_hides_development_code_when_disabled(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "ali@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("development_verification_code", response.data)

    def test_anonymous_user_cannot_request_email_verification_code(self):
        response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "ali@example.com",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_authenticated_user_can_confirm_email_verification_code(self):
        self.client.force_authenticate(user=self.user)

        request_response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "Ali@Example.COM",
            },
            format="json",
        )

        response = self.client.post(
            reverse("accounts-api:email-verification-confirm"),
            {
                "email": "ali@example.com",
                "code": request_response.data["development_verification_code"],
            },
            format="json",
        )

        self.user.refresh_from_db()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Email address has been verified successfully.",
        )
        self.assertEqual(response.data["email"], "ali@example.com")
        self.assertTrue(response.data["is_email_verified"])
        self.assertEqual(self.user.email, "ali@example.com")
        self.assertTrue(self.user.is_email_verified)

    @override_settings(EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_confirm_rejects_invalid_code(self):
        self.client.force_authenticate(user=self.user)

        request_response = self.client.post(
            reverse("accounts-api:email-verification-request"),
            {
                "email": "ali@example.com",
            },
            format="json",
        )

        valid_code = request_response.data["development_verification_code"]
        invalid_code = "000000" if valid_code != "000000" else "111111"

        response = self.client.post(
            reverse("accounts-api:email-verification-confirm"),
            {
                "email": "ali@example.com",
                "code": invalid_code,
            },
            format="json",
        )

        challenge = EmailVerificationChallenge.objects.get(user=self.user)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(challenge.attempts_count, 1)
        self.assertIsNone(challenge.used_at)

    def test_anonymous_user_cannot_confirm_email_verification_code(self):
        response = self.client.post(
            reverse("accounts-api:email-verification-confirm"),
            {
                "email": "ali@example.com",
                "code": "123456",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

class PasswordResetAPIViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            phone_number="+989121234567",
            password="OldStrongPassword123!",
            is_phone_verified=True,
        )

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_user_can_request_password_reset_code(self):
        response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "0912 123 4567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            response.data["detail"],
            "Password reset code has been created.",
        )
        self.assertIn("expires_at", response.data)
        self.assertIn("development_otp_code", response.data)

        challenge = OTPChallenge.objects.get(
            phone_number="+989121234567",
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
        )

        self.assertEqual(challenge.phone_number, self.user.phone_number)
        self.assertEqual(len(response.data["development_otp_code"]), 6)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=False)
    def test_request_response_hides_development_code_when_disabled(self):
        response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "+989121234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertNotIn("development_otp_code", response.data)

    def test_rejects_password_reset_request_for_unknown_phone_number(self):
        response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "+989991234567",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_user_can_confirm_password_reset_code(self):
        request_response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "+989121234567",
            },
            format="json",
        )

        response = self.client.post(
            reverse("accounts-api:password-reset-confirm"),
            {
                "phone_number": "0912 123 4567",
                "code": request_response.data["development_otp_code"],
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.user.refresh_from_db()
        challenge = OTPChallenge.objects.get(
            phone_number="+989121234567",
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"],
            "Password has been reset successfully.",
        )
        self.assertTrue(self.user.check_password("NewStrongPassword123!"))
        self.assertIsNotNone(challenge.used_at)

    @override_settings(OTP_DEVELOPMENT_CODE_IN_RESPONSE=True)
    def test_confirm_rejects_invalid_code(self):
        request_response = self.client.post(
            reverse("accounts-api:password-reset-request"),
            {
                "phone_number": "+989121234567",
            },
            format="json",
        )

        valid_code = request_response.data["development_otp_code"]
        invalid_code = "000000" if valid_code != "000000" else "111111"

        response = self.client.post(
            reverse("accounts-api:password-reset-confirm"),
            {
                "phone_number": "+989121234567",
                "code": invalid_code,
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        challenge = OTPChallenge.objects.get(
            phone_number="+989121234567",
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(challenge.attempts_count, 1)
        self.assertIsNone(challenge.used_at)

    def test_confirm_rejects_when_no_active_challenge_exists(self):
        response = self.client.post(
            reverse("accounts-api:password-reset-confirm"),
            {
                "phone_number": "+989121234567",
                "code": "123456",
                "new_password": "NewStrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)