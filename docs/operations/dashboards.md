# Observability dashboards

## Objetivo

`infra/dashboards/overview-workbook.json` despliega un Azure Workbook operativo para seguir el flujo de albaranes, la salud de los agentes A1-A6 y la carga pendiente de HITL.

El workbook está pensado para el entorno `rg-verdecoratest-dev` en `swedencentral`, usando Application Insights + Log Analytics ya definidos en `infra/modules/monitoring.bicep`.

## Qué incluye el workbook

- Volumen de procesamiento de albaranes por hora
- Volumen de procesamiento de albaranes por día
- Ratio de éxito, fallo y derivación a HITL
- Desglose de latencia por agente (A1-A6)
- Tipos de error más frecuentes
- Revisiones HITL pendientes activas

## Cómo desplegar el workbook

### Opción 1: despliegue con ARM

```powershell
$resourceGroup = 'rg-verdecoratest-dev'
$workspaceId = az monitor log-analytics workspace show `
  --resource-group $resourceGroup `
  --workspace-name log-albaranes-dev `
  --query id -o tsv

$appInsightsId = az monitor app-insights component show `
  --app appi-albaranes-dev `
  --resource-group $resourceGroup `
  --query id -o tsv

az deployment group create `
  --resource-group $resourceGroup `
  --template-file infra\dashboards\overview-workbook.json `
  --parameters workbookDisplayName='Verdecora - Observabilidad general' `
               workbookSourceId=$workspaceId `
               logAnalyticsWorkspaceId=$workspaceId `
               appInsightsComponentId=$appInsightsId
```

### Opción 2: importación manual desde Azure Portal

1. Azure Portal → **Monitor** → **Workbooks**.
2. Selecciona **+ New** → **Advanced Editor**.
3. Copia el bloque `serializedData` generado por el template o despliega primero el ARM.
4. Guarda el workbook con el nombre del entorno (`Verdecora - Observabilidad general`).

## Suposiciones de telemetría

Las consultas esperan dimensiones alineadas con la arquitectura actual:

- `albaran_id` o `albaranId` para correlación de documentos
- `result` / `routing_decision` para éxito, error o HITL
- `agent_name` / `agent_id` para A1-A6
- `error_type` para clasificar incidencias
- `review_status` para elementos HITL pendientes

Si la instrumentación usa otros nombres, ajusta las consultas KQL del workbook antes de publicarlo.

## KQL de referencia

### 1. Albarán processing timeline

```kusto
AppEvents
| where TimeGenerated >= ago(24h)
| extend dims = column_ifexists("Properties", dynamic({}))
| extend albaranId = coalesce(tostring(dims["albaran_id"]), tostring(dims["albaranId"]), OperationId)
| summarize Procesados = dcount(albaranId) by bin(TimeGenerated, 1h)
| order by TimeGenerated asc
```

### 2. Agent performance breakdown

```kusto
AppDependencies
| where TimeGenerated >= ago(24h)
| extend dims = column_ifexists("Properties", dynamic({}))
| extend agentName = coalesce(tostring(dims["agent_name"]), tostring(dims["agent_id"]), Name)
| where agentName has_any ("A1", "A2", "A3", "A4", "A5", "A6", "extractor", "triage", "coherence", "validator", "inventory", "communication")
| summarize P50_ms = percentile(DurationMs, 50), P95_ms = percentile(DurationMs, 95), Total = count() by agentName
| order by P95_ms desc
```

### 3. Error investigation

```kusto
AppTraces
| where TimeGenerated >= ago(6h)
| where SeverityLevel >= 3
| extend dims = column_ifexists("Properties", dynamic({}))
| extend errorType = coalesce(tostring(dims["error_type"]), tostring(dims["exception_type"]), Message)
| summarize Eventos = count() by errorType
| top 20 by Eventos desc
```

### 4. HITL backlog monitoring

```kusto
AppEvents
| where TimeGenerated >= ago(7d)
| extend dims = column_ifexists("Properties", dynamic({}))
| extend reviewStatus = coalesce(tostring(dims["review_status"]), tostring(dims["status"]), Name)
| extend createdAt = todatetime(coalesce(tostring(dims["created_at"]), tostring(dims["createdAt"]), TimeGenerated))
| where reviewStatus in ("pending", "reminded", "escalated")
| summarize Pendientes = count(), MasAntiguo = min(createdAt)
```

## Recomendaciones operativas

- Publica el workbook en cada entorno (`dev`, `test`, `prod`) con el prefijo del entorno.
- Revisa semanalmente si las dimensiones de telemetría siguen alineadas con los nombres usados por las apps.
- Usa este workbook junto con `infra/modules/alerts.bicep`: el dashboard sirve para diagnóstico, las alertas para reacción temprana.
