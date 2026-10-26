from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request: HttpRequest) -> JsonResponse:
    """Liveness probe. It does not touch the database."""
    return JsonResponse({"status": "ok"})
