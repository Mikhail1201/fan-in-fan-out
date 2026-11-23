"""FAN-IN: consolida los resultados de las ramas paralelas en un unico JSON.

Dos modos (campo "mode"):
  - success: recibe "results" (arreglo con los 4 resultados) y escribe status COMPLETED.
  - failure: recibe "error" (de un Catch de Step Functions) y escribe status FAILED.

El reporte se guarda en s3://<bucket>/reports/<imageId>.json
"""
import json
import logging
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")

REQUIRED = ("thumbnail", "web", "mobile", "metadata")


class ConsolidationError(Exception):
    """Faltan resultados de alguna rama."""


def _build_success(event):
    by_type = {r["type"]: r for r in event["results"]}
    missing = [t for t in REQUIRED if t not in by_type]
    if missing:
        raise ConsolidationError(f"Faltan resultados de: {missing}")

    meta = by_type["metadata"]
    return {
        "imageId": event["imageId"],
        "status": "COMPLETED",
        "thumbnail": by_type["thumbnail"]["uri"],
        "web": by_type["web"]["uri"],
        "mobile": by_type["mobile"]["uri"],
        "metadata": {k: v for k, v in meta.items() if k != "type"},
    }


def _build_failure(event):
    error = event.get("error") or {}
    return {
        "imageId": event["imageId"],
        "status": "FAILED",
        "error": {
            "type": error.get("Error"),
            "cause": (error.get("Cause") or "")[:1000],
        },
    }


def handler(event, context):
    mode = event.get("mode", "success")
    bucket = event["bucket"]

    report = _build_failure(event) if mode == "failure" else _build_success(event)
    report["source"] = f"s3://{bucket}/{event['key']}"
    report["executionId"] = event.get("executionId")
    report["processedAt"] = datetime.now(timezone.utc).isoformat()

    out_key = f"reports/{event['imageId']}.json"
    s3.put_object(
        Bucket=bucket,
        Key=out_key,
        Body=json.dumps(report, indent=2).encode("utf-8"),
        ContentType="application/json",
    )

    log = logger.info if report["status"] == "COMPLETED" else logger.error
    log(
        "Reporte generado",
        extra={
            "imageId": event["imageId"],
            "status": report["status"],
            "reportUri": f"s3://{bucket}/{out_key}",
        },
    )
    return report
