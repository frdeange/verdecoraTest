# Load test configuration

## Objetivo

Validar que la plataforma soporta el volumen objetivo de **750 albaranes por día** sin degradar la experiencia del formulario HITL ni generar una tasa de error operativa inaceptable.

## Escenarios incluidos

`locustfile.py` define tres perfiles de carga:

1. **OrchestratorUser**
   - Envía peticiones `POST /process`
   - Simula el ritmo diario objetivo de entrada de albaranes
2. **BlobUploadUser**
   - Simula subidas concurrentes de PDFs al contenedor `albaranes-raw`
   - Requiere un SAS temporal para el contenedor de pruebas
3. **HITLReviewerUser**
   - Abre revisiones pendientes y publica decisiones
   - Requiere un header `Authorization` válido del formulario HITL

## Variables de entorno necesarias

| Variable | Uso |
| --- | --- |
| `VERDECORA_ORCHESTRATOR_HOST` | URL base del orquestador |
| `VERDECORA_HITL_HOST` | URL base del webform HITL |
| `VERDECORA_BLOB_HOST` | URL base del endpoint Blob |
| `VERDECORA_BLOB_CONTAINER` | Contenedor objetivo (por defecto `albaranes-raw`) |
| `VERDECORA_BLOB_SAS_QUERY` | SAS temporal para las subidas de prueba |
| `VERDECORA_HITL_AUTH_HEADER` | Bearer token para acceder al formulario HITL |

## Ejecución recomendada

```powershell
$env:VERDECORA_ORCHESTRATOR_HOST = 'https://orchestrator.contoso.internal'
$env:VERDECORA_HITL_HOST = 'https://hitl.contoso.internal'
$env:VERDECORA_BLOB_HOST = 'https://stverdecora.blob.core.windows.net'
$env:VERDECORA_BLOB_SAS_QUERY = '<sas-de-pruebas>'
$env:VERDECORA_HITL_AUTH_HEADER = 'Bearer <jwt>'

locust -f tests\load\locustfile.py --headless --users 25 --spawn-rate 5 --run-time 30m
```

## Umbrales esperados

| Métrica | Umbral objetivo |
| --- | --- |
| `POST /process` p95 | < 15 s |
| `GET /review/{id}` p95 | < 5 s |
| `POST /review/{id}/decide` p95 | < 8 s |
| Blob upload p95 | < 3 s para PDFs de prueba pequeños |
| Error rate global | < 1% |
| Throughput sostenido | >= 750 albaranes/día equivalente |

## Lectura de resultados

- Si el p95 del orquestador supera 15 s, revisar colas de Service Bus, saturación de OCR y latencia A1/A4.
- Si el formulario HITL supera 5 s, revisar Cosmos, autenticación Entra y el backlog de revisiones.
- Si falla Blob upload, validar SAS, conectividad privada y límites del storage account.
- Cruza siempre los resultados con los dashboards y alertas definidos en el sprint de observabilidad.
