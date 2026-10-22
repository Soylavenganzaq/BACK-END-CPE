# Contratos de la API

Prefijo actual: raíz (`/`). Las respuestas de éxito usan JSON. Errores de validación responden `400`, autenticación `401`, autorización `403`, registro inexistente `404`, MAC/estado en conflicto `409`, y persistencia no conectada `503`.

## Autenticación y autorización

| Método | Ruta | Entrada | Permiso |
| --- | --- | --- | --- |
| `POST` | `/login` | `{ "username": "...", "password": "..." }` | Público |
| `POST` | `/logout` | Ninguna | Público; el cliente elimina el JWT, que es stateless |

El login devuelve `access_token` y datos públicos de usuario. El adaptador futuro debe autenticar contra la tabla real, comprobar el hash y devolver el rol real para incluirlo como claim firmado. No hay revocación de token implementada.

## Usuarios y técnicos

| Método | Ruta | Entrada | Permiso |
| --- | --- | --- | --- |
| `GET` | `/users` | Ninguna | `users:read` |
| `GET` | `/users/{user_id}` | Ninguna | `users:read` |
| `POST` | `/registry` | `{ "username": "...", "password": "mínimo 12 caracteres", "role": "Super Admin\|Admin\|Usuario" }` | `users:manage` |
| `PUT` | `/users/{user_id}` | `username`, `password` y/o `role` | `users:manage` |
| `DELETE` | `/users/{user_id}` | Ninguna | `users:manage` |
| `GET` | `/technicians` | Ninguna | `technicians:read` |
| `GET` | `/technicians/{technician_id}` | Ninguna | `technicians:read` |
| `POST` | `/technicians` | Objeto JSON pendiente de confirmar con DDL | `technicians:write` |
| `PUT` | `/technicians/{technician_id}` | Objeto JSON pendiente de confirmar con DDL | `technicians:write` |
| `DELETE` | `/technicians/{technician_id}` | Ninguna | `technicians:write` |

## Inventario y operaciones

| Método | Ruta | Entrada | Permiso |
| --- | --- | --- | --- |
| `POST` | `/inventory/entries` | `{ "macs": ["AA:BB:CC:DD:EE:FF"], "technician_id": 1, "equipment_type_id": 1, "condition_id": 1, "observations": "..." }` | `operations:write` |
| `POST` | `/inventory/deliveries` | `{ "macs": ["AA:BB:CC:DD:EE:FF"], "condition_id": 1, "observations": "..." }` | `operations:write` |
| `GET` | `/inventory/mac/{mac}` | MAC en la ruta | `inventory:read` |
| `GET` | `/inventory/available` | `mac`, `equipment_type_id`, `date_from`, `date_to` como query params | `inventory:read` |

Las operaciones de lote usan la identidad del usuario responsable tomada del JWT. Las MAC se aceptan con `:`, `-`, `.`, o sin separadores; se normalizan a mayúsculas `AA:BB:CC:DD:EE:FF`. El tamaño máximo es 500 por lote, no se permiten duplicados dentro del mismo request y las fechas usan `YYYY-MM-DD`.

## Reportes y estado

| Método | Ruta | Entrada | Permiso |
| --- | --- | --- | --- |
| `GET` | `/reports/operations` | `date_from`, `date_to`, `user_id` | `reports:read` |
| `GET` | `/reports/daily-volume` | `date_from`, `date_to`, `user_id` | `reports:read` |
| `GET` | `/health/database` | Ninguna | Público; informa configuración, no prueba conectividad |

Los endpoints de inventario y reportes no confirman escrituras ni lecturas mientras no exista un repositorio PostgreSQL conectado. El adaptador futuro debe delegar estados, historial y auditoría a las funciones/vistas SQL, comprobar MAC activas de forma transaccional y convertir errores de restricciones en conflictos `409`.

## Matriz de permisos provisional

| Rol | Permisos |
| --- | --- |
| `Super Admin` | Usuarios (lectura/gestión), técnicos (lectura/escritura), inventario, operaciones y reportes |
| `Admin` | Usuarios (lectura), técnicos (lectura/escritura), inventario, operaciones y reportes |
| `Usuario` | Inventario y operaciones |

Esta matriz es una propuesta técnica para el scaffold, no una regla confirmada del proyecto. Debe validarse con el responsable funcional antes de producción. Los nombres del esquema, tablas, columnas, constraints, vistas, `inventario.fn_historial_por_mac` y funciones para lotes permanecen pendientes de recibir y revisar el SQL oficial.

## Ejemplos

```sh
curl -X POST http://localhost:4729/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"usuario","password":"contraseña"}'
```

```sh
curl 'http://localhost:4729/inventory/available?mac=AA:BB:CC:DD:EE:FF&date_from=2026-10-01' \
  -H 'Authorization: Bearer TOKEN'
```

Al no estar configurado el adaptador SQL, un request válido a una ruta persistente debe devolver `503`; eso es deliberado y no representa una operación guardada.