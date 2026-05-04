# Operations runbook

## Incident response

### 1. Triage inicial

1. Confirma el alcance: orquestador, agentes, cola, OCR, HITL o integración BC.
2. Revisa Azure Monitor / Application Insights para identificar el primer síntoma.
3. Valida salud básica:
   - `GET /health` del orquestador
   - `GET /health` del webform HITL
   - profundidad de `extraccion-queue`, `extraccion-in` y cola HITL
4. Abre incidencia operativa si el impacto supera 15 minutos o afecta aprobaciones de albaranes en tienda.

### 2. Clasificación rápida

- **Sev1**: flujo de albaranes detenido, BC caído, webform HITL inaccesible, colas bloqueadas
- **Sev2**: degradación fuerte de latencia, backlog creciente, OCR con errores repetidos
- **Sev3**: error funcional acotado, proveedor concreto, warning operativo sin impacto inmediato

### 3. Comunicación

- Avisar a operaciones y responsables de tienda si existe riesgo de retraso en recepciones.
- Si el incidente afecta HITL, activar el flujo alternativo por correo.
- Registrar la línea temporal: inicio, mitigación aplicada, estado actual, siguiente revisión.

## Failure scenarios and remediation

### BC MCP connection lost

**Síntomas**
- Errores de conexión repetidos contra Business Central MCP
- Validaciones A3/A4 fallando por timeout o dependencia no disponible

**Acción inmediata**
1. Reintentar automáticamente (backoff exponencial).
2. Verificar conectividad saliente, credencial y tenant configurado.
3. Revisar si la incidencia es puntual o sostenida > 5 minutos.

**Remediación**
- Si persiste, escalar a integración BC y pausar aprobaciones automáticas.
- Mantener los albaranes en `hitl_review` o cola operativa hasta recuperación.

### Document Intelligence rate limiting

**Síntomas**
- Respuestas 429/408/504 desde OCR
- Aumento del tiempo de extracción A1

**Acción inmediata**
1. Aplicar backpressure desde el orquestador.
2. Reducir concurrencia temporal del procesamiento.
3. Desviar proveedores estables al modelo/flujo alternativo si existe feature flag.

**Remediación**
- Ajustar volumen de entrada y revisar cuota/SKU del recurso.
- Confirmar si el patrón coincide con horas punta o lotes masivos.

### Service Bus dead letters

**Síntomas**
- Mensajes en DLQ de `extraccion-in` o suscripciones relacionadas
- Reintentos agotados (`maxDeliveryCount`)

**Acción inmediata**
1. Inspeccionar el payload y la excepción original.
2. Clasificar: dato corrupto, dependencia externa, bug de procesamiento, permiso.
3. Corregir la causa raíz antes de reinyectar.

**Remediación**
- Reprocesar manualmente solo los mensajes validados.
- Si el error se repite, desactivar el feature implicado o poner el proveedor en tratamiento manual.

### HITL webform down

**Síntomas**
- `/health` falla
- Usuarios no pueden abrir o enviar decisiones HITL

**Acción inmediata**
1. Confirmar si falla la app, Entra ID o Cosmos.
2. Activar **email-only flow**: enviar incidencia y enlace alternativo/manual a operaciones.
3. Evitar que el backlog siga creciendo sin seguimiento humano.

**Remediación**
- Reiniciar revisión de despliegue, escalado, secretos/config y autenticación.
- Una vez restaurado, priorizar los albaranes caducados o más antiguos.

### Agent hallucination detected

**Síntomas**
- Identificadores BC inventados
- Razonamientos no soportados por OCR/PO
- Decisiones automáticas incoherentes

**Acción inmediata**
1. Deshabilitar el feature flag o ruta automática afectada.
2. Forzar revisión manual / HITL para el tramo impactado.
3. Capturar ejemplos con `albaran_id`, proveedor y salida del agente.

**Remediación**
- Revisar prompt, validaciones estructuradas y datos de entrada sanitizados.
- Reentrenar criterios operativos antes de reactivar la automatización.

## Scaling procedures

### Manual scaling

- **Orchestrator ACA**: subir `maxReplicas` si hay cola sostenida y OCR/BC están sanos.
- **HITL webform ACA**: subir `maxReplicas` si la apertura/envío de revisiones se degrada.
- **Flow 0 dedup job**: aumentar `maxExecutions` solo si el cuello está antes del orquestador.

### KEDA-guided scaling

- Revisar profundidad de Service Bus y edad del mensaje más antiguo.
- No escalar si el cuello está en Document Intelligence o BC; primero aplicar backpressure.
- Tras el incidente, devolver límites a valores operativos para controlar coste y ruido.

## Deployment rollback process

1. Identifica el último despliegue sano (imagen, commit o PR).
2. Confirma que no existe migración incompatible o cambio de configuración irreversible.
3. Ejecuta rollback de la revisión/container image anterior.
4. Verifica:
   - `/health`
   - cola procesándose
   - logs sin errores críticos
   - decisiones HITL funcionando
5. Documenta motivo del rollback y evidencia.

## Health check verification

### Orchestrator

- `GET /health`
- capacidad de conectar con Cosmos, Service Bus y OCR
- mensajes avanzando en `extraccion-in`

### HITL webform

- `GET /health`
- acceso autenticado a `/review/{id}`
- escritura de decisión + publicación a Service Bus

### MCP servers

- Business Central MCP responde
- Cosmos MCP puede leer y escribir
- Document Intelligence MCP procesa una muestra controlada
- ACS Email MCP puede enviar una notificación de prueba

## Log investigation guide

### BC MCP failures

```kusto
AppTraces
| where TimeGenerated >= ago(30m)
| where SeverityLevel >= 3
| where Message has_any ("BC MCP", "Business Central MCP", "connection failed", "connection lost")
| order by TimeGenerated desc
```

### Document Intelligence throttling / timeout

```kusto
AppDependencies
| where TimeGenerated >= ago(30m)
| where Name has "Document Intelligence" or Target has "cognitiveservices"
| where ResultCode in ("408", "429", "504") or Success == false
| project TimeGenerated, Name, Target, ResultCode, DurationMs, Success
| order by TimeGenerated desc
```

### Service Bus backlog pattern

```kusto
AppTraces
| where TimeGenerated >= ago(1h)
| where Message has_any ("queue", "Service Bus", "received", "processed")
| summarize Eventos = count() by bin(TimeGenerated, 5m)
| order by TimeGenerated asc
```

### HITL backlog older than 24h

```kusto
AppEvents
| where TimeGenerated >= ago(7d)
| extend dims = column_ifexists("Properties", dynamic({}))
| extend reviewStatus = coalesce(tostring(dims["review_status"]), tostring(dims["status"]), Name)
| extend createdAt = todatetime(coalesce(tostring(dims["created_at"]), tostring(dims["createdAt"]), TimeGenerated))
| where reviewStatus in ("pending", "reminded", "escalated")
| where createdAt <= ago(24h)
| summarize Pendientes = count(), MasAntiguo = min(createdAt)
```
