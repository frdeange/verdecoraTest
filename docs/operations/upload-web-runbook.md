# Upload Web — Runbook de Operaciones

## Resumen

Este runbook cubre la respuesta a incidentes, diagnóstico y escalado del
componente **Upload Web** (portal de subida de albaranes desplegado en
Azure Container Apps).

---

## 1. Respuesta a incidentes

### 1.1 Tasa alta de errores 5xx

**Síntomas**: dashboard muestra error rate > 5 %, alerta `upload-web-5xx-rate` disparada.

```text
Severidad: Crítica
Tiempo de respuesta: < 15 min
```

**Pasos de diagnóstico**:

1. Verificar salud básica:
   ```bash
   curl https://upload.verdecora.es/healthz
   curl https://upload.verdecora.es/readyz
   ```

2. Consultar logs en App Insights:
   ```kql
   AppExceptions
   | where TimeGenerated >= ago(30m)
   | where AppRoleName has 'upload-web'
   | summarize count() by type, outerMessage
   | order by count_ desc
   ```

3. Verificar estado de Container Apps:
   ```bash
   az containerapp show -n ca-upload-web -g rg-verdecora-prod --query "properties.runningStatus"
   ```

**Remediación**:
- Reiniciar Container App:
  ```bash
  az containerapp revision restart -n ca-upload-web -g rg-verdecora-prod --revision <revision-name>
  ```
- Si el error persiste, verificar dependencias (Storage, Cosmos, Service Bus).

---

### 1.2 Fallo en generación de SAS

**Síntomas**: usuarios no pueden subir archivos, error "No se pudo generar URL de subida".

**Pasos de diagnóstico**:

1. Verificar permisos de Managed Identity en Storage:
   ```bash
   az role assignment list \
     --assignee <managed-identity-object-id> \
     --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account> \
     --output table
   ```
   Debe tener `Storage Blob Data Contributor`.

2. Verificar conectividad al Storage Account:
   ```kql
   AppDependencies
   | where TimeGenerated >= ago(30m)
   | where Target has 'blob.core.windows.net'
   | where Success == false
   | summarize count() by ResultCode, DependencyTypeName
   ```

**Remediación**:
- Si faltan permisos:
  ```bash
  az role assignment create \
    --assignee <managed-identity-object-id> \
    --role "Storage Blob Data Contributor" \
    --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>
  ```
- Si hay problemas de red, verificar Private Endpoints y NSG.

---

### 1.3 Timeouts en preflight (Document Intelligence)

**Síntomas**: preflight tarda más de 30 s o falla con timeout.

**Pasos de diagnóstico**:

1. Verificar salud del endpoint de Document Intelligence:
   ```bash
   az cognitiveservices account show -n <di-account> -g <rg> --query "properties.provisioningState"
   ```

2. Revisar latencia en logs:
   ```kql
   AppDependencies
   | where TimeGenerated >= ago(1h)
   | where Target has 'cognitiveservices'
   | summarize avg(DurationMs), percentile(DurationMs, 95), count() by bin(TimeGenerated, 5m)
   ```

3. Verificar rate limits de Document Intelligence:
   ```kql
   AppDependencies
   | where TimeGenerated >= ago(1h)
   | where Target has 'cognitiveservices'
   | where ResultCode == '429'
   | summarize count() by bin(TimeGenerated, 5m)
   ```

**Remediación**:
- Si hay throttling (429), reducir concurrencia o escalar el tier de DI.
- Si hay timeout de red, verificar Private Endpoints.
- El preflight cae a heurístico si DI falla; los usuarios pueden seguir subiendo.

---

### 1.4 Sesión atascada en "processing"

**Síntomas**: albarán confirmado pero nunca pasa a "completado".

**Pasos de diagnóstico**:

1. Verificar que el mensaje se publicó en Service Bus:
   ```kql
   AppTraces
   | where TimeGenerated >= ago(2h)
   | where Message has 'Published session'
   | where Message has '<session-id>'
   ```

2. Verificar profundidad de cola:
   ```bash
   az servicebus topic subscription show \
     --namespace-name <sb-namespace> \
     --topic-name albaran-processing \
     --name <subscription> \
     --query "countDetails"
   ```

3. Verificar logs del orquestador (Flow 0):
   ```kql
   AppTraces
   | where TimeGenerated >= ago(2h)
   | where AppRoleName has 'orchestrator'
   | where Message has '<session-id>'
   | order by TimeGenerated asc
   ```

**Remediación**:
- Si el mensaje no se publicó, reenviar manualmente o confirmar de nuevo la sesión.
- Si está en la cola pero no se procesa, verificar el orquestador y los agentes.

---

### 1.5 Fallos de autenticación

**Síntomas**: usuarios no pueden iniciar sesión, alerta `upload-web-auth-failures` disparada.

**Pasos de diagnóstico**:

1. Verificar configuración de Easy Auth en Container Apps:
   ```bash
   az containerapp auth show -n ca-upload-web -g rg-verdecora-prod
   ```

2. Verificar App Registration en Entra ID:
   ```bash
   az ad app show --id <app-id> --query "{redirectUris:web.redirectUris, status:disabledByMicrosoftStatus}"
   ```

3. Revisar logs de autenticación:
   ```kql
   AppTraces
   | where TimeGenerated >= ago(1h)
   | where Message has_any ('auth', 'login', '401', '403')
   | where AppRoleName has 'upload-web'
   | summarize count() by Message
   | order by count_ desc
   ```

**Remediación**:
- Verificar que `AZURE_TENANT_ID` y `SESSION_SIGNING_KEY` están correctamente configurados.
- Si es un posible ataque de fuerza bruta (> 10 intentos en 5 min desde misma IP), considerar bloqueo temporal.
- Verificar que el grupo `verdecora-store-uploaders` tiene los usuarios correctos.

---

## 2. Escalado

### 2.1 Escalado manual

```bash
# Escalar a 3 réplicas
az containerapp update -n ca-upload-web -g rg-verdecora-prod \
  --min-replicas 2 --max-replicas 5

# Verificar réplicas
az containerapp revision list -n ca-upload-web -g rg-verdecora-prod \
  --query "[].{name:name, replicas:properties.replicas, active:properties.active}" -o table
```

### 2.2 Escalado con KEDA

La app soporta auto-scaling basado en peticiones HTTP concurrentes:

```yaml
# Configuración KEDA (ya definida en Bicep)
scale:
  minReplicas: 1
  maxReplicas: 10
  rules:
    - name: http-scaling
      http:
        metadata:
          concurrentRequests: "50"
```

- **Regla**: 1 réplica adicional por cada 50 peticiones concurrentes.
- **Mínimo**: 1 réplica (2 en producción para HA).
- **Máximo**: 10 réplicas.

---

## 3. Consultas KQL útiles

### Sesiones creadas vs confirmadas (última hora)

```kql
customMetrics
| where TimeGenerated >= ago(1h)
| where name in ('upload_sessions_created', 'upload_session_abandoned')
| summarize Total = sum(valueCount) by name
```

### Errores por tipo

```kql
customMetrics
| where TimeGenerated >= ago(1h)
| where name == 'upload_errors'
| extend error_type = tostring(customDimensions['error_type'])
| summarize count() by error_type
| order by count_ desc
```

### Latencia de preflight (percentiles)

```kql
customMetrics
| where TimeGenerated >= ago(1h)
| where name == 'upload_preflight_duration_seconds'
| summarize P50 = percentile(value, 50), P95 = percentile(value, 95), P99 = percentile(value, 99)
```

### Top usuarios por volumen

```kql
customMetrics
| where TimeGenerated >= ago(24h)
| where name == 'upload_files_processed'
| extend supplier = tostring(customDimensions['supplier'])
| summarize Files = sum(valueCount) by supplier
| top 10 by Files desc
```

### Requests 5xx en la última hora

```kql
AppRequests
| where TimeGenerated >= ago(1h)
| where AppRoleName has 'upload-web'
| where toint(ResultCode) >= 500
| summarize count() by ResultCode, Name, bin(TimeGenerated, 5m)
| order by TimeGenerated desc
```

---

## 4. Contactos de escalado

| Nivel | Contacto | Tiempo de respuesta |
|---|---|---|
| L1 — Operaciones | ops@verdecora.example.com | < 15 min |
| L2 — Desarrollo | dev-team@verdecora.example.com | < 1 h |
| L3 — Infraestructura | infra@verdecora.example.com | < 2 h |

---

*Última actualización: 2025*
