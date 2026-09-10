from django.conf import settings
from django.core.checks import Error, Warning, register


@register(deploy=True)
def deployment_configuration(app_configs, **kwargs):
    issues = []
    if settings.OTP_DEVELOPMENT_CODE_IN_RESPONSE or settings.EMAIL_VERIFICATION_DEVELOPMENT_CODE_IN_RESPONSE:
        issues.append(Error("Development verification codes must not be returned in production.", id="navaboard.E001"))
    if settings.SMS_PROVIDER == "console":
        issues.append(Warning("SMS delivery is disabled. Configure SMS_PROVIDER=smsir before enabling public phone login.", id="navaboard.W001"))
    if "locmem" in settings.CACHES["default"]["BACKEND"].lower():
        issues.append(Warning("Use a shared Redis cache for multi-worker authentication throttles.", id="navaboard.W002"))
    if not settings.AUTH_REFRESH_COOKIE_SECURE:
        issues.append(Error("Production refresh cookies must be Secure.", id="navaboard.E002"))
    return issues
