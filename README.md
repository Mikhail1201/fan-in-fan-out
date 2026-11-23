# Procesamiento de imagenes serverless: Fan-Out / Fan-In en AWS

Cuando se sube una imagen a S3, se ejecutan **4 procesos en paralelo** (thumbnail, version web,
version mobile y metadata). Al terminar todos, una Lambda consolida los resultados en un unico
reporte JSON.

```
            +-----------+   Object Created   +-------------+
 imagen --> |    S3     | -----------------> | EventBridge |
 uploads/   +-----------+                    +------+------+
                                                    | StartExecution
                                             +------v-------+
                                             | Step Functions|
                                             +------+-------+
                                                    |
                                              [Prepare Lambda]
                                                    |
                          +-----------+-------------+-------------+
          FAN-OUT         |           |             |             |
        (Parallel)   Thumbnail      Web          Mobile        Metadata
                       Lambda      Lambda        Lambda         Lambda
                          |           |             |             |
                          +-----------+------+------+-------------+
                                             |
                                     FAN-IN: Consolidate Lambda
                                             |
                                  s3://bucket/reports/<imageId>.json
```

## Servicios usados
S3, EventBridge, Step Functions (Standard), Lambda (Python 3.12), CloudWatch Logs, IAM.
Sin EC2. Todo escala automaticamente.

## Estructura
```
template.yaml                         Infraestructura (AWS SAM)
statemachine/image_processing.asl.json  Definicion de Step Functions
src/prepare/        Valida el evento y calcula imageId
src/resize/         Thumbnail / Web / Mobile (mismo codigo, distinta config)
src/metadata/       Extrae metadata tecnica
src/consolidate/    Fan-In: genera el reporte final (COMPLETED o FAILED)
layer/              Layer de Pillow (se construye sin Docker)
scripts/            build_layer.ps1, reprocess.py
```

## Despliegue (PowerShell, region us-east-2)
```powershell
cd image-fanout-fanin
.\scripts\build_layer.ps1      # descarga Pillow para Linux (sin Docker)
sam build
sam deploy                     # usa samconfig.toml
```

## Probar
```powershell
$BUCKET = aws cloudformation describe-stacks --stack-name image-fanout-fanin --region us-east-2 `
  --query "Stacks[0].Outputs[?OutputKey=='ImagesBucketName'].OutputValue" --output text

aws s3 cp .\foto.jpg s3://$BUCKET/uploads/12345.jpg --region us-east-2

# Esperar ~10 s y descargar el reporte
aws s3 cp s3://$BUCKET/reports/12345.json - --region us-east-2
aws s3 ls s3://$BUCKET/processed/12345/ --region us-east-2
```

Resultado esperado:
```json
{
  "imageId": "12345",
  "status": "COMPLETED",
  "thumbnail": "s3://<bucket>/processed/12345/thumbnail.jpg",
  "web": "s3://<bucket>/processed/12345/web.jpg",
  "mobile": "s3://<bucket>/processed/12345/mobile.jpg",
  "metadata": { "width": 1920, "height": 1080, "format": "JPEG", "...": "..." }
}
```

## Manejo de errores
- **Retry** con backoff exponencial y jitter en cada rama ante errores transitorios de Lambda.
- Errores permanentes (`InvalidImageError`, imagen corrupta) **no se reintentan**.
- **Catch** en el `Parallel`: si una rama falla, se escribe un reporte `FAILED` y la ejecucion termina en `Fail`.
- Entrada invalida (extension o prefijo) termina en el estado `InvalidInput`.
- EventBridge reintenta la entrega al target hasta 5 veces / 1 hora.

## Reprocesamiento
```powershell
python scripts\reprocess.py --key uploads/12345.jpg   # una imagen
python scripts\reprocess.py --failed                  # todas las ejecuciones FAILED
```
Tambien se puede usar **Redrive** desde la consola de Step Functions en una ejecucion fallida.
Las salidas usan rutas deterministas, asi que reprocesar solo sobrescribe.

## Observabilidad
- Logs JSON estructurados por Lambda: `/aws/lambda/image-fanout-fanin-<funcion>`
- Logs de la maquina de estados (nivel ALL): `/aws/vendedlogs/states/image-fanout-fanin-image-processing`
- Grafo de ejecucion visual en la consola de Step Functions.

## Limpieza
```powershell
aws s3 rm s3://$BUCKET --recursive --region us-east-2
sam delete --stack-name image-fanout-fanin --region us-east-2
```
