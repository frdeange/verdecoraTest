# Checklist de Pruebas de Aceptación de Usuario (UAT)

## Información general

| Campo | Valor |
|---|---|
| **Aplicación** | Upload Web — Portal de subida de albaranes |
| **Tiendas piloto** | Tienda A (Madrid) · Tienda B (Valencia) |
| **Periodo de pruebas** | 2 semanas desde el inicio del piloto |
| **Responsable** | Coordinador de operaciones + responsable de tienda |

---

## Escenarios de prueba

### 1. Subir un albarán PDF de una sola página

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Iniciar sesión con la cuenta de tienda | Página principal cargada correctamente |
| 2 | Pulsar "Subir albarán" | Se abre la pantalla de subida |
| 3 | Arrastrar o seleccionar un PDF de 1 página | Barra de progreso visible, carga completa |
| 4 | Pulsar "Verificar" (preflight) | Se muestra proveedor, fecha y número detectados |
| 5 | Pulsar "Confirmar y enviar" | Mensaje de confirmación con resumen |

**Resultado**: ☐ Correcto · ☐ Incorrecto  
**Observaciones**: _______________________________________________

---

### 2. Subir fotografías de albarán (JPEG/PNG)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Seleccionar 2-3 fotos JPEG/PNG del albarán | Cada imagen aparece como miniatura |
| 2 | Agrupar las imágenes como un único albarán | Indicador de grupo visible |
| 3 | Verificar (preflight) | Proveedor y datos detectados con confianza media-alta |
| 4 | Confirmar y enviar | Sesión marcada como "confirmada" |

**Resultado**: ☐ Correcto · ☐ Incorrecto  
**Observaciones**: _______________________________________________

---

### 3. Subir albarán multipágina (PDF de varias páginas)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Seleccionar un PDF con 3+ páginas | Todas las páginas se cargan |
| 2 | Verificar qué páginas corresponden al albarán | Preflight muestra datos coherentes |
| 3 | Confirmar | Sesión enviada sin errores |

**Resultado**: ☐ Correcto · ☐ Incorrecto  
**Observaciones**: _______________________________________________

---

### 4. Subir un archivo con tipo incorrecto (DOCX, XLS, etc.)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Intentar subir un archivo .docx o .xls | Error claro: "Tipo de archivo no permitido" |
| 2 | Verificar que la sesión sigue activa | Se puede reintentar con un archivo válido |

**Resultado**: ☐ Correcto · ☐ Incorrecto  
**Observaciones**: _______________________________________________

---

### 5. Archivo demasiado grande (> 50 MB)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Intentar subir un archivo mayor de 50 MB | Error: "El archivo supera el tamaño máximo" |
| 2 | La sesión no se rompe | Puede seguir subiendo otros archivos |

**Resultado**: ☐ Correcto · ☐ Incorrecto  
**Observaciones**: _______________________________________________

---

### 6. Sesión inactiva (timeout)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Iniciar sesión y no interactuar durante 30 min | Redirigido a login con aviso de inactividad |
| 2 | Volver a iniciar sesión | Los datos anteriores no confirmados no se pierden |

**Resultado**: ☐ Correcto · ☐ Incorrecto  
**Observaciones**: _______________________________________________

---

### 7. Acceso denegado (usuario sin permisos)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Acceder con una cuenta sin grupo "uploaders" | Mensaje: "No tiene permisos para acceder" |

**Resultado**: ☐ Correcto · ☐ Incorrecto  
**Observaciones**: _______________________________________________

---

## Formulario de feedback

Al finalizar las pruebas, cada tienda piloto debe completar este formulario:

| Pregunta | Respuesta |
|---|---|
| ¿El proceso de subida fue intuitivo? (1-5) | ___ |
| ¿Los mensajes de error fueron claros? (1-5) | ___ |
| ¿El tiempo de carga fue aceptable? (1-5) | ___ |
| ¿El preflight detectó correctamente el proveedor? | Sí / No / Parcialmente |
| ¿Encontró algún error no listado arriba? | ___ |
| ¿Qué mejoraría del proceso? | ___ |
| Puntuación general (1-10) | ___ |

---

## Criterios de aceptación

- ✅ Todos los escenarios 1-5 pasan sin errores.
- ✅ Los mensajes de error son comprensibles para el personal de tienda.
- ✅ Puntuación media ≥ 7/10 en ambas tiendas piloto.
- ✅ No se detectan bloqueos críticos.
- ⚠️ Incidencias menores se documentan y se resuelven antes de la Fase 2.
