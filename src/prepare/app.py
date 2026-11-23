"""Valida el evento de S3 (via EventBridge) y calcula el imageId.

Entrada (campo "detail" del evento de EventBridge):
    {"bucket": {"name": "..."}, "object": {"key": "uploads/12345.jpg"}}

Salida:
    {"imageId": "12345", "bucket": "...", "key": "uploads/12345.jpg"}
"""
import logging
import os
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
UPLOAD_PREFIX = "uploads/"


class InvalidImageError(Exception):
    """Error permanente: la entrada no es valida y no tiene sentido reintentar."""


def handler(event, context):
    try:
        bucket = event["bucket"]["name"]
        key = event["object"]["key"]
    except (KeyError, TypeError) as exc:
        raise InvalidImageError(f"Evento con formato inesperado: {exc}") from exc

    if not key.startswith(UPLOAD_PREFIX):
        raise InvalidImageError(f"La clave '{key}' no esta bajo '{UPLOAD_PREFIX}'")

    name, ext = os.path.splitext(os.path.basename(key))
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise InvalidImageError(f"Extension no soportada: '{ext}'")

    image_id = re.sub(r"[^A-Za-z0-9._-]", "_", name)

    logger.info(
        "Imagen recibida",
        extra={"imageId": image_id, "bucket": bucket, "key": key},
    )
    return {"imageId": image_id, "bucket": bucket, "key": key}
