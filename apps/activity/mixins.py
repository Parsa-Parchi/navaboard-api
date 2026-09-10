from django.db import transaction

from .services import record_mutation, resolve_scope


class ActivityMutationMixin:
    """Commit each successful domain API mutation and its history together."""

    def dispatch(self, request, *args, **kwargs):
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return super().dispatch(request, *args, **kwargs)
        with transaction.atomic():
            scope = resolve_scope(kwargs)
            response = super().dispatch(request, *args, **kwargs)
            if 200 <= response.status_code < 300:
                record_mutation(request=self.request, response=response, scope=scope, kwargs=kwargs)
            else:
                transaction.set_rollback(True)
            return response
