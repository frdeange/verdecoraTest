# MCP Business Central — Guía de Permisos y Capacidades

> **Fecha de descubrimiento:** 3-4 Mayo 2026  
> **Entorno:** Business Central API v2.0 vía MCP (Model Context Protocol)  
> **Caso de uso probado:** Procesamiento de albarán de entrega (Herstera Garden S.L.)

---

## 1. Resumen Ejecutivo

Se realizó una prueba de concepto para evaluar la viabilidad de un **flujo agéntico** que procese albaranes de entrega y los registre automáticamente en Business Central. El flujo completo requiere:

1. Leer un PDF de albarán
2. Dar de alta productos (Items) en el catálogo
3. Registrar la entrada de mercancía (stock)

Se logró automatizar los pasos 1 y 2. El paso 3 quedó parcialmente completado (se creó el Purchase Order con sus 59 líneas, pero no se pudo registrar la recepción por limitaciones de la API).

---

## 2. Endpoints Utilizados y Permisos Necesarios

### 2.1 Items (PAG30008) — Catálogo de Productos

| Permiso | Necesario | Para qué |
|---------|:---------:|----------|
| **Allow Read** | ✅ | Consultar inventario, buscar items existentes, obtener posting groups de referencia |
| **Allow Create** | ✅ | Dar de alta nuevos productos desde el albarán |
| **Allow Modify** | ✅ | Asignar `generalProductPostingGroupCode` e `inventoryPostingGroupCode` a los items (obligatorio para poder usarlos en documentos) |
| Allow Delete | ⬜ | No necesario para este flujo |
| Allow Bound Actions | ⬜ | No aplica |

**Funciones utilizadas:**

| Función | Descripción |
|---------|-------------|
| `List_Items_PAG30008` | Lista items con filtros OData. Permite filtrar por tipo, número, categoría, y campos vacíos. Usado para verificar items existentes y obtener IDs/etags para modificación. |
| `Create_Item_PAG30008` | Crea una ficha de producto. Campos clave: `number` (código), `displayName` (nombre), `type` (Inventory/Service/Non-Inventory), `unitCost`, `unitPrice`, `generalProductPostingGroupCode`, `inventoryPostingGroupCode`. |
| `Modify_Item_PAG30008` | Modifica un item existente. Requiere `id` y `If-Match` (etag para control de concurrencia). Usado para asignar posting groups en lote. |

**⚠️ Hallazgo importante:** Al crear items, es **imprescindible** asignar `generalProductPostingGroupCode` e `inventoryPostingGroupCode`. Sin estos campos, los items no pueden usarse en documentos (Purchase Orders, Sales Orders, etc.) y BC devuelve error de validación.

**💡 Recomendación:** Al crear items, siempre incluir los posting groups en la misma llamada de creación para evitar un paso adicional de modificación. Ejemplo:

```json
{
  "number": "14101014",
  "displayName": "Anillo Para Balcon 14cm Antracita",
  "type": "'Inventory'",
  "unitCost": 1.49,
  "generalProductPostingGroupCode": "RETAIL",
  "inventoryPostingGroupCode": "RESALE"
}
```

---

### 2.2 Purchase Orders (PAG30066) — Pedidos de Compra

| Permiso | Necesario | Para qué |
|---------|:---------:|----------|
| **Allow Read** | ✅ | Consultar pedidos existentes, obtener etags |
| **Allow Create** | ✅ | Crear el pedido de compra vinculado al proveedor |
| **Allow Modify** | ✅ | Actualizar campos del pedido (fechas, etc.) |
| Allow Delete | ⬜ | No necesario para este flujo |
| **Allow Bound Actions** | ✅ | Para ejecutar `ReceiveAndInvoice` (registrar recepción + factura) |

**Funciones utilizadas:**

| Función | Descripción |
|---------|-------------|
| `List_PurchaseOrders_PAG30066` | Lista pedidos de compra. Filtrable por número, proveedor, estado, etc. |
| `Create_PurchaseOrder_PAG30066` | Crea un pedido de compra. Campos clave: `vendorNumber`, `orderDate`, `postingDate`. |
| `Modify_PurchaseOrder_PAG30066` | Modifica un pedido existente. Requiere `id` y `If-Match`. |
| `ReceiveAndInvoice_PurchaseOrders_PAG30066` | **Bound Action** que registra la recepción de mercancía Y crea la factura de compra. Actualiza el stock de todos los items del pedido. Requiere `id` del pedido. |

---

### 2.3 Purchase Order Lines (PAG30067) — Líneas de Pedido de Compra

| Permiso | Necesario | Para qué |
|---------|:---------:|----------|
| **Allow Read** | ✅ | Consultar líneas existentes |
| **Allow Create** | ✅ | Añadir líneas al pedido con item, cantidad y coste |
| Allow Modify | ⬜ | No necesario si las líneas se crean correctamente |
| Allow Delete | ⬜ | No necesario para este flujo |
| Allow Bound Actions | ⬜ | No aplica |

**Funciones utilizadas:**

| Función | Descripción |
|---------|-------------|
| `Create_PurchaseOrderLinesOfPurchaseOrder_PAG30067` | Crea una línea dentro de un pedido de compra. Requiere `PurchaseOrder_id` (ID del pedido padre). Campos clave: `lineType` ('Item'), `lineObjectNumber` (código del item), `quantity`, `directUnitCost`. |

---

### 2.4 Vendors (PAG30010) — Proveedores

| Permiso | Necesario | Para qué |
|---------|:---------:|----------|
| **Allow Read** | ✅ | Buscar si el proveedor ya existe |
| **Allow Create** | ✅ | Dar de alta nuevos proveedores desde el albarán |
| Allow Modify | ⬜ | No necesario para este flujo |
| Allow Delete | ⬜ | No aplica |
| Allow Bound Actions | ⬜ | No aplica |

**Funciones utilizadas:**

| Función | Descripción |
|---------|-------------|
| `List_Vendors_PAG30010` | Lista proveedores con filtros. Usado para verificar si un proveedor ya existe. |
| `Create_Vendor_PAG30010` | Crea un proveedor. Campos clave: `number`, `displayName`. |

**⚠️ Hallazgo importante:** Al crear un proveedor, es obligatorio que tenga un **Vendor Posting Group** asignado para poder usarlo en Purchase Orders. La API no expone este campo directamente, por lo que los proveedores creados vía API pueden necesitar configuración adicional en BC.

**💡 Recomendación:** Usar proveedores ya existentes en BC (que ya tengan posting groups configurados) o configurar el proveedor manualmente en BC tras crearlo por API.

---

### 2.5 Journals / JournalLines (PAG30016 / PAG30049) — Diarios Generales

| Permiso | Necesario | Para qué |
|---------|:---------:|----------|
| **Allow Read** | ✅ | Consultar diarios existentes |
| **Allow Create** | ✅ | Crear diarios y líneas de diario |
| **Allow Modify** | ✅ | Modificar diarios |
| **Allow Bound Actions** | ✅ | Para ejecutar `Post` (registrar el diario) |

**⚠️ Hallazgo importante:** Los Journals de la API v2 son **Diarios Generales (General Journals)**, NO Diarios de Productos (Item Journals). Los tipos de cuenta disponibles son: G/L Account, Customer, Vendor, Bank Account, Fixed Asset, IC Partner, Employee, Allocation Account. **No incluyen tipo "Item"**, por lo que **no sirven para ajustar stock directamente**.

---

## 3. Endpoints de Solo Lectura (No requieren escritura)

Estos endpoints son útiles para consultas pero no necesitan permisos de escritura:

| Page ID | Nombre | Uso |
|---------|--------|-----|
| 30009 | Customers | Consultar clientes |
| 30011 | Company Information | Datos de la empresa |
| 30014 | Accounts | Plan de cuentas |
| 30018 | G/L Entries | Movimientos contables |
| 30033 | Balance Sheet | Balance de situación |
| 30034 | Trial Balance | Balance de sumas y saldos |
| 30048 | Cust Financial Details | Detalle financiero de clientes |
| 30052 | Item Variants | Variantes de producto |
| 30064 | Purchase Receipts | Albaranes de recepción (solo lectura) |
| 30069 | Item Ledger Entries | Movimientos de inventario (entradas, salidas, ajustes) |
| 30076 | Locations | Almacenes/ubicaciones |
| 30079 | Gen. Prod. Post. Group | Grupos contables de producto |
| 30096 | Inventory Post. Group | Grupos contables de inventario |

---

## 4. Limitaciones Descubiertas en la API v2

### 4.1 ❌ No existe endpoint de Item Journal (Diario de Productos)

**Problema:** La API v2 de Business Central **no expone el Item Journal** como endpoint. El endpoint `Journals/JournalLines` (PAG30016/PAG30049) corresponde al **General Journal**, que solo maneja cuentas contables (G/L, clientes, proveedores, bancos, etc.) pero no items/productos.

**Impacto:** No es posible hacer ajustes de inventario (Positive/Negative Adjustment) directamente por API. La única vía para mover stock es a través de Purchase Orders con `ReceiveAndInvoice`.

**Solución propuesta:** Crear una **Custom API Page** en BC que exponga el Item Journal con operaciones CRUD y una bound action `Post`. Esto permitiría un flujo más simple:
1. Crear línea de diario con tipo "Positive Adjmt." + item + cantidad
2. Registrar (Post) → stock actualizado

---

### 4.2 ❌ `Vendor Invoice No.` no expuesto en la API

**Problema:** El campo `Vendor Invoice No.` (Nº de factura del proveedor) es **obligatorio** para ejecutar `ReceiveAndInvoice`, pero **no está expuesto** en el esquema de la API v2 de Purchase Orders (ni en Create ni en Modify).

**Impacto:** No es posible completar el flujo de recepción de mercancía de forma 100% automatizada. Requiere intervención manual para establecer este campo en BC.

**Solución propuesta:** 
- Opción A: Personalizar la API Page 30066 para exponer el campo `Vendor Invoice No.`
- Opción B: Crear una bound action `Receive` (solo recepción, sin factura) que no requiera este campo
- Opción C: Establecer un valor por defecto para el campo en BC vía Event Subscriber

---

### 4.3 ❌ `Vendor Posting Group` no expuesto al crear proveedores

**Problema:** Al crear un proveedor vía API, el campo `Vendor Posting Group` no se puede establecer. Sin embargo, es obligatorio para que el proveedor pueda usarse en documentos.

**Impacto:** Los proveedores creados por API necesitan configuración adicional manual en BC.

**Solución propuesta:** Personalizar la API Page 30010 para exponer este campo, o usar un Event Subscriber que asigne un valor por defecto.

---

## 5. Tabla Resumen de Permisos Necesarios

### Permisos mínimos para flujo completo (albarán → stock):

| Page ID | Endpoint | Read | Create | Modify | Delete | Bound Actions |
|---------|----------|:----:|:------:|:------:|:------:|:-------------:|
| **30008** | Items | ✅ | ✅ | ✅ | ⬜ | ⬜ |
| **30010** | Vendors | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| **30066** | Purchase Orders | ✅ | ✅ | ✅ | ⬜ | ✅ |
| **30067** | Purchase Order Lines | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

### Permisos mínimos solo para dar de alta items (sin stock):

| Page ID | Endpoint | Read | Create | Modify | Delete | Bound Actions |
|---------|----------|:----:|:------:|:------:|:------:|:-------------:|
| **30008** | Items | ✅ | ✅ | ✅* | ⬜ | ⬜ |

*\* Modify solo necesario si no se incluyen posting groups en la creación.*

---

## 6. Flujo Agéntico Completo — Diagrama

```
┌─────────────────────────────────────────────────────────┐
│                    ALBARÁN (PDF)                         │
│  Proveedor: Herstera Garden S.L.                        │
│  59 líneas con código, descripción, cantidad, precio    │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  PASO 1: Lectura del PDF                                │
│  • Extraer datos del albarán (OCR / parsing)            │
│  • Identificar: código, descripción, cantidad, precio   │
│  Estado: ✅ AUTOMATIZADO                                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  PASO 2: Verificar/Crear Items                          │
│  • List_Items → ¿existe el item?                        │
│  • Create_Item → crear con posting groups               │
│  Estado: ✅ AUTOMATIZADO                                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  PASO 3: Verificar/Crear Proveedor                      │
│  • List_Vendors → ¿existe?                              │
│  • Create_Vendor → crear (⚠️ posting group manual)      │
│  Estado: ⚠️ PARCIALMENTE AUTOMATIZADO                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  PASO 4: Crear Purchase Order + Líneas                  │
│  • Create_PurchaseOrder → con proveedor y fechas        │
│  • Create_PurchaseOrderLines → 59 líneas con qty/cost   │
│  Estado: ✅ AUTOMATIZADO                                │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────┐
│  PASO 5: Registrar Recepción                            │
│  • Modify_PurchaseOrder → Vendor Invoice No.            │
│  • ReceiveAndInvoice → Post                             │
│  Estado: ❌ BLOQUEADO (Vendor Invoice No. no en API)    │
└──────────────────────────────────────────────────────────┘
```

---

## 7. Herramientas del MCP

El MCP de Business Central expone 3 herramientas base:

| Herramienta | Función |
|-------------|---------|
| `bc_actions_search` | Busca acciones disponibles por tipo (List, Create, Modify, Delete, BoundAction) y texto. Soporta búsqueda por keyword o semántica. |
| `bc_actions_describe` | Devuelve el esquema JSON completo de una acción: campos disponibles, tipos, enums, campos requeridos, y relaciones padre-hijo. |
| `bc_actions_invoke` | Ejecuta una acción pasando los parámetros según el esquema. Soporta filtros OData v4, paginación (top/skip), selección de campos (select) y ordenación (orderby). |

---

## 8. Próximos Pasos Recomendados

1. **Personalizar API Page 30066** para exponer `Vendor Invoice No.` → desbloquea el flujo completo
2. **Crear Custom API Page para Item Journal** → alternativa más simple al flujo de Purchase Orders
3. **Configurar proveedores con posting groups por defecto** → via Event Subscriber en BC
4. **Evaluar flujo de envío de correo** → WorkIQ (M365 Copilot) solo crea borradores; para envío automático usar Microsoft Graph API con permisos `Mail.Send`
