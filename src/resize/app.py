"""Genera una version redimensionada de la imagen (thumbnail, web o mobile).

El mismo codigo atiende las tres Lambdas; lo que cambia es la configuracion
por variables de entorno (VARIANT, MAX_SIZE, QUALITY).
"""
import io
import logging
import os

import boto3
from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

VARIANT = os.environ["VARIANT"]
MAX_SIZE = int(os.environ["MAX_SIZE"])
QUALITY = int(os.environ["QUALITY"])


class InvalidImageError(Exception):
    """Error permanente: el archivo no es una imagen valida."""


def _to_rgb(img):
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def handler(event, context):
    image_id = event["imageId"]
    bucket = event["bucket"]
    key = event["key"]

    logger.info(
        "Inicio de procesamiento",
        extra={"imageId": image_id, "variant": VARIANT, "key": key},
    )

    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()

    try:
        img = Image.open(io.BytesIO(body))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError(f"No se pudo leer la imagen: {exc}") from exc

    img = ImageOps.exif_transpose(img)
    img = _to_rgb(img)
    # thumbnail() conserva la proporcion y nunca agranda la imagen
    img.thumbnail((MAX_SIZE, MAX_SIZE), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, "JPEG", quality=QUALITY, optimize=True, progressive=True)
    data = buffer.getvalue()

    out_key = f"processed/{image_id}/{VARIANT}.jpg"
    s3.put_object(
        Bucket=bucket,
        Key=out_key,
        Body=data,
        ContentType="image/jpeg",
    )

    result = {
        "type": VARIANT,
        "uri": f"s3://{bucket}/{out_key}",
        "width": img.width,
        "height": img.height,
        "sizeBytes": len(data),
    }
    logger.info("Version generada", extra={"imageId": image_id, **result})
    return result
