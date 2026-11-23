#!/usr/bin/env python3
"""Reprocesa imagenes lanzando de nuevo la maquina de estados.

Ejemplos:
  # Reprocesar una imagen concreta (ya subida a uploads/)
  python scripts/reprocess.py --key uploads/12345.jpg

  # Reprocesar todas las ejecuciones FAILED
  python scripts/reprocess.py --failed

El procesamiento es idempotente: los resultados se escriben en rutas
deterministas (processed/<imageId>/..., reports/<imageId>.json) y se sobrescriben.
"""
import argparse
import json

import boto3


def stack_outputs(region, stack_name):
    cf = boto3.client("cloudformation", region_name=region)
    outputs = cf.describe_stacks(StackName=stack_name)["Stacks"][0]["Outputs"]
    return {o["OutputKey"]: o["OutputValue"] for o in outputs}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stack-name", default="image-fanout-fanin")
    parser.add_argument("--region", default="us-east-2")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--key", help="Clave S3 de la imagen, por ejemplo uploads/12345.jpg")
    group.add_argument("--failed", action="store_true", help="Reprocesar ejecuciones FAILED")
    parser.add_argument("--max", type=int, default=50, help="Maximo de ejecuciones a reprocesar con --failed")
    args = parser.parse_args()

    out = stack_outputs(args.region, args.stack_name)
    machine_arn = out["StateMachineArn"]
    bucket = out["ImagesBucketName"]
    sfn = boto3.client("stepfunctions", region_name=args.region)

    if args.key:
        payload = {"bucket": {"name": bucket}, "object": {"key": args.key}}
        resp = sfn.start_execution(stateMachineArn=machine_arn, input=json.dumps(payload))
        print(f"Ejecucion iniciada: {resp['executionArn']}")
        return

    count = 0
    paginator = sfn.get_paginator("list_executions")
    for page in paginator.paginate(stateMachineArn=machine_arn, statusFilter="FAILED"):
        for ex in page["executions"]:
            if count >= args.max:
                print(f"Limite alcanzado ({args.max}).")
                return
            original = sfn.describe_execution(executionArn=ex["executionArn"])
            resp = sfn.start_execution(stateMachineArn=machine_arn, input=original["input"])
            print(f"Reprocesando {ex['name']} -> {resp['executionArn']}")
            count += 1
    print(f"Total reprocesadas: {count}")


if __name__ == "__main__":
    main()
