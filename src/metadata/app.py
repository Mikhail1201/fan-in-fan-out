"""Extrae informacion tecnica de la imagen original."""
import io
import logging

import boto3
from PIL import ExifTags, Image, UnidentifiedImageError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

EXIF_FIELDS = {"Make", "Model", "DateTime", "Orientation", "Software"}


class InvalidImageError(Exception):
    """Error permanente: el archivo no es una imagen valida."""


def _read_exif(img):
    exif = {}
    try:
        for tag_id, value in img.getexif().items():
            name = ExifTags.TAGS.get(tag_id, str(tag_id))
            if name in EXIF_FIELDS:
                exif[name] = str(value)
    except Exception:  # EXIF corrupto no debe tumbar el proceso
        logger.warning("No se pudo leer EXIF")
    return exif


def handler(event, context):
    image_id = event["imageId"]
    bucket = event["bucket"]
    key = event["key"]

    logger.info("Extrayendo metadata", extra={"imageId": image_id, "key": key})

    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read()

    try:
        img = Image.open(io.BytesIO(body))
        img.verify()
        img = Image.open(io.BytesIO(body))  # verify() invalida el objeto
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError(f"No se pudo leer la imagen: {exc}") from exc

    result = {
        "type": "metadata",
        "width": img.width,
        "height": img.height,
        "format": img.format,
        "mode": img.mode,
        "sizeBytes": len(body),
        "contentType": obj.get("ContentType"),
        "exif": _read_exif(img),
    }
    logger.info("Metadata extraida", extra={"imageId": image_id, **result})
    return result
