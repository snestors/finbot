# Backend Spec: Controls API (para sincronización NSPanel ↔ Web)

> Dale este documento a tu agente backend para implementar los endpoints de controles.

## Objetivo

Agregar un sistema de "Controles" al backend de FinBot para manejar dispositivos IoT (luces, enchufes, etc.) desde el NSPanel Flutter y la web, sincronizados en tiempo real via WebSocket.

## Modelo de datos

Crear tabla `controls` en SQLite:

```sql
CREATE TABLE IF NOT EXISTS controls (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    icon_name TEXT NOT NULL DEFAULT 'lightbulb',
    color_hex TEXT NOT NULL DEFAULT '#F59E0B',
    is_active INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Datos iniciales

```sql
INSERT INTO controls (id, name, icon_name, color_hex, is_active, sort_order) VALUES
('sala', 'Sala', 'sofa', '#FFFFFF', 0, 0),
('cocina', 'Cocina', 'soup', '#22C55E', 0, 1),
('frente', 'Frente', 'palmtree', '#06B6D4', 0, 2);
```

## Endpoints REST (todos requieren auth)

| Método | Ruta | Body | Respuesta |
|--------|------|------|-----------|
| GET | `/api/controls` | — | `[{ id, name, icon_name, color_hex, is_active, sort_order }]` |
| POST | `/api/controls` | `{ name, icon_name, color_hex }` | `{ id, name, icon_name, color_hex, is_active, sort_order }` |
| PUT | `/api/controls/:id` | `{ name?, icon_name?, color_hex?, sort_order? }` | `{ ok: true }` |
| DELETE | `/api/controls/:id` | — | `{ ok: true }` |
| POST | `/api/controls/:id/toggle` | — | `{ id, is_active }` |
| PUT | `/api/controls/reorder` | `{ order: ["id1", "id2", ...] }` | `{ ok: true }` |

## WebSocket broadcasts

Enviar a TODOS los clientes conectados cuando ocurra un cambio:

### Toggle de un control
```json
{ "type": "control_toggle", "id": "abc123", "is_active": true }
```

### Cambio en configuración (add/edit/delete/reorder)
```json
{
  "type": "controls_changed",
  "controls": [
    { "id": "...", "name": "...", "icon_name": "...", "color_hex": "...", "is_active": false, "sort_order": 0 }
  ]
}
```

## Flujo de sincronización

1. Cliente abre app → `GET /api/controls` → muestra botones
2. Usuario toca "Sala" → `POST /api/controls/sala/toggle`
3. Backend cambia `is_active` en DB → responde `{ id: "sala", is_active: true }`
4. Backend broadcast WS: `{ type: "control_toggle", id: "sala", is_active: true }`
5. Todos los demás clientes (web, otro panel) reciben el WS y actualizan el botón

## Valores válidos

### icon_name
`sofa`, `lamp`, `sun`, `moon`, `zap`, `plug`, `fan`, `thermometer`, `droplets`, `flame`, `tv`, `monitor`, `speaker`, `wifi`, `lock`, `unlock`, `camera`, `bell`, `home`, `door_open`, `car`, `palmtree`, `flower`, `soup`, `coffee`, `bath`, `bed`, `baby`, `dog`, `power`, `lightbulb`, `blinds`, `air_vent`, `refrigerator`, `gauge`, `shield`

### color_hex
`#FFFFFF`, `#3B82F6`, `#06B6D4`, `#22C55E`, `#F59E0B`, `#EF4444`, `#9CA3AF`, `#A855F7`, `#EC4899`

## Web UI

Agregar una sección en la interfaz web de FinBot donde se puedan:
- Ver y controlar los mismos dispositivos (grid de botones)
- Configurar: agregar, editar, eliminar controles
- Los cambios se sincronizan en tiempo real con el panel Flutter
