# Plan de Rollout — Upload Web (25 tiendas)

## Resumen

Despliegue progresivo del portal de subida de albaranes (Upload Web) en
tres fases, desde 2 tiendas piloto hasta 25 tiendas en producción completa.

---

## Fases de despliegue

### Fase 1 — Piloto (2 tiendas)

| Parámetro | Valor |
|---|---|
| **Tiendas** | Tienda A (Madrid) · Tienda B (Valencia) |
| **Duración** | 2 semanas |
| **Feature flag** | `upload_web_enabled: pilot` |
| **Réplicas ACA** | 1 (mínimo) |

**Checklist de monitorización**:
- [ ] Error rate < 1 % durante 48 h continuas
- [ ] Tasa de abandono < 15 %
- [ ] Preflight detecta proveedor en > 80 % de sesiones
- [ ] Latencia p95 < 2 s para preflight
- [ ] Cero incidentes Sev1 o Sev2
- [ ] Feedback UAT ≥ 7/10 en ambas tiendas

**Criterios de rollback**:
- Error rate > 5 % durante 30 min
- Bloqueo total del flujo de subida
- Feedback negativo consistente de ambas tiendas

**Acciones de rollback**:
```bash
# Desactivar feature flag
az containerapp update -n ca-upload-web -g rg-verdecora-prod \
  --set-env-vars "UPLOAD_WEB_FEATURE_FLAG=disabled"

# Redirigir a página de mantenimiento
az containerapp ingress update -n ca-upload-web -g rg-verdecora-prod \
  --target-port 8000
```

---

### Fase 2 — Rollout controlado (10 tiendas)

| Parámetro | Valor |
|---|---|
| **Tiendas** | 8 tiendas adicionales (mix de tamaños y regiones) |
| **Duración** | 2 semanas |
| **Feature flag** | `upload_web_enabled: controlled` |
| **Réplicas ACA** | 2-3 (auto-scaling activado) |

**Pre-requisitos**:
- ✅ Fase 1 completada con éxito
- ✅ Todas las incidencias de UAT resueltas
- ✅ Formación completada para las 8 nuevas tiendas

**Checklist de monitorización**:
- [ ] Error rate < 2 % durante 72 h continuas
- [ ] Tasa de abandono < 20 %
- [ ] RPS < 60 % de capacidad máxima
- [ ] No hay degradación de latencia vs. Fase 1
- [ ] Service Bus queue depth < 50 mensajes
- [ ] Zero incidentes de seguridad

**Criterios de rollback**:
- Error rate > 5 % durante 15 min
- Latencia p95 > 5 s durante 30 min
- Queue depth > 200 mensajes durante 15 min

---

### Fase 3 — Rollout completo (25 tiendas)

| Parámetro | Valor |
|---|---|
| **Tiendas** | 15 tiendas adicionales |
| **Duración** | Indefinida (producción) |
| **Feature flag** | `upload_web_enabled: all` |
| **Réplicas ACA** | 2-5 (KEDA auto-scaling) |

**Pre-requisitos**:
- ✅ Fase 2 completada con éxito (2 semanas sin Sev1/Sev2)
- ✅ Load test de 30 RPS / 30 min superado
- ✅ Runbook de operaciones revisado y actualizado
- ✅ Formación completada para todas las tiendas

**Checklist de monitorización**:
- [ ] Error rate < 1 % en régimen estable
- [ ] Auto-scaling funciona correctamente bajo carga pico
- [ ] Alertas configuradas y probadas
- [ ] Dashboard operativo revisado diariamente (primera semana)
- [ ] Sin degradación en el pipeline de procesamiento (orquestador, agentes)

---

## Configuración de Feature Flags

```bash
# Fase 1: solo tiendas piloto
az containerapp update -n ca-upload-web -g rg-verdecora-prod \
  --set-env-vars "UPLOAD_WEB_FEATURE_FLAG=pilot" \
                 "UPLOAD_WEB_ALLOWED_STORES=STORE-A,STORE-B"

# Fase 2: 10 tiendas
az containerapp update -n ca-upload-web -g rg-verdecora-prod \
  --set-env-vars "UPLOAD_WEB_FEATURE_FLAG=controlled" \
                 "UPLOAD_WEB_ALLOWED_STORES=STORE-A,STORE-B,STORE-C,STORE-D,STORE-E,STORE-F,STORE-G,STORE-H,STORE-I,STORE-J"

# Fase 3: todas las tiendas
az containerapp update -n ca-upload-web -g rg-verdecora-prod \
  --set-env-vars "UPLOAD_WEB_FEATURE_FLAG=all" \
  --remove-env-vars "UPLOAD_WEB_ALLOWED_STORES"
```

---

## Plan de comunicación

### Antes de cada fase

| Acción | Responsable | Plazo |
|---|---|---|
| Enviar email informativo a responsables de tienda | Coordinador de operaciones | 1 semana antes |
| Compartir manual de usuario (docs/user/upload-web-manual.md) | Coordinador de operaciones | 1 semana antes |
| Sesión de formación por videollamada (30 min) | Equipo técnico | 3 días antes |
| Confirmar acceso de usuarios en Entra ID | Administrador IT | 1 día antes |

### Durante cada fase

| Acción | Responsable | Frecuencia |
|---|---|---|
| Revisar dashboard de Upload Web | Operaciones | Diario |
| Recoger feedback de tiendas | Coordinador | Semanal |
| Revisar alertas y incidencias | DevOps | Diario |
| Reunión de seguimiento con tiendas piloto | Coordinador | Semanal (Fase 1) |

### Después de cada fase

| Acción | Responsable | Plazo |
|---|---|---|
| Compilar informe de métricas | DevOps | 2 días después |
| Decidir Go/No-Go para siguiente fase | Comité de operaciones | 3 días después |
| Documentar lecciones aprendidas | Equipo técnico | 1 semana después |

---

## Métricas de éxito global

| Métrica | Objetivo |
|---|---|
| Adopción | ≥ 80 % de tiendas usando Upload Web activamente |
| Error rate | < 1 % en régimen estable |
| Tiempo medio de subida | < 3 minutos por albarán |
| Satisfacción de usuario | ≥ 7/10 |
| Reducción de errores manuales | ≥ 50 % vs. proceso anterior |

---

*Última actualización: 2025*
