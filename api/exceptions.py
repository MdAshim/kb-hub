"""Custom DRF exception handler: unhandled exceptions in api/ views never
leak a traceback to the client. API.md's error table documents
500 -> {"detail": "Internal error."}; the real exception is still logged
server-side."""

from __future__ import annotations

import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None:
        # DRF already turned this into a proper response (ValidationError,
        # NotFound, PermissionDenied, ...) -- nothing more to do.
        return response

    request = context.get("request")
    path = request.path if request is not None else "?"
    logger.exception("Unhandled exception in API view %s", path)
    return Response({"detail": "Internal error."}, status=500)
