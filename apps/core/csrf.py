from django.http import JsonResponse


def failure(request, reason=""):
    return JsonResponse({"detail": "CSRF verification failed. Initialize /api/auth/csrf/ and send X-CSRFToken with cookies."}, status=403)
