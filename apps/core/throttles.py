"""Application-level traffic budgets; share the cache across API workers."""
from rest_framework.permissions import SAFE_METHODS
from rest_framework.throttling import SimpleRateThrottle


class ReadRateThrottle(SimpleRateThrottle):
    scope = "api_read"

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated or request.method not in SAFE_METHODS:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class ActionRateThrottle(SimpleRateThrottle):
    scope = "api_action"

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated or request.method in SAFE_METHODS:
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class SearchRateThrottle(SimpleRateThrottle):
    scope = "api_search"

    def get_cache_key(self, request, view):
        if not request.user.is_authenticated or request.method not in SAFE_METHODS:
            return None
        if not getattr(view, "is_search_view", False) and not (
            getattr(view, "supports_search", False) and request.query_params
        ):
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}
