# APPI1.5 Backend

API Flask para autenticación, usuarios, técnicos e inventario de equipos de red. Conserva la organización existente por controladores, servicios y repositorios. La capa de inventario ya tiene contratos HTTP y validaciones, pero su persistencia PostgreSQL permanece pendiente del SQL oficial del proyecto.

## Estado actual

- La aplicación puede arrancar sin `DATABASE_URL` y sin conectarse a PostgreSQL.
- No se crean tablas, no se ejecutan migraciones y no se utiliza SQLite como alternativa.
- Los repositorios predeterminados de usuarios, técnicos e inventario son marcadores no configurados. Las operaciones que los necesitan responden `503`; no simulan lecturas ni escrituras.
- La configuración `DATABASE_URL` por sí sola no conecta los endpoints de inventario. Todavía hace falta implementar y registrar el adaptador SQL descrito más adelante.
- Los endpoints antiguos de `/computadores` se conservan como funcionalidad heredada y no representan inventario de equipos de red.
- La matriz de roles incluida es provisional. Debe confirmarse con los responsables funcionales antes de producción.

## Tecnologías

- Python 3.10 o posterior.
- Flask y Flask-JWT-Extended para HTTP y tokens de acceso.
- SQLAlchemy como infraestructura prevista para sesiones y acceso futuro a PostgreSQL.
- Psycopg 3 como driver de PostgreSQL.
- Werkzeug para el hash y la comprobación de contraseñas.
- `unittest` para pruebas sin PostgreSQL.

Las versiones instalables están declaradas en [requirements.txt](requirements.txt).

## Estructura y responsabilidades

```text
config/
	authorization.py          Matriz de permisos y decorador JWT
	database.py               Configuración perezosa del engine y sesiones PostgreSQL
	jwt.py                    Lectura de parámetros JWT desde el entorno
controllers/
	component_controller.py   Rutas heredadas de computadores
	inventory_controller.py   Rutas de ingresos, entregas, MAC, disponibles y reportes
	user_controllers.py       Login, usuarios y técnicos
models/
	inventory.py              Comandos, filtros y errores del dominio; no son tablas ORM
repositories/
	inventory_repository.py   Contrato Protocol para persistencia de inventario
	pending_repositories.py   Adaptadores que informan persistencia pendiente
	componente_repository.py  Repositorio heredado de computadores
	user_repository.py       Repositorio heredado de usuarios
services/
	auth_service.py           Verificación de credenciales desacoplada del almacenamiento
	inventory_service.py      Normalización y validación de solicitudes de inventario
	user_services.py          Servicio heredado de usuarios
tests/
	test_api_contracts.py     Pruebas de endpoints, login y permisos con dobles
	test_inventory_service.py Pruebas de validaciones y comandos de lote
docs/API.md                 Contratos HTTP completos y matriz provisional
main.py                     Factory Flask, registro de blueprints y manejadores de error
```

### Flujo de una solicitud

1. `main.create_app()` crea la aplicación, configura JWT/CORS y registra los blueprints. Acepta repositorios por parámetro para facilitar pruebas.
2. El controlador valida la forma general de la petición y aplica `requires_permission` a las rutas protegidas.
3. El servicio aplica reglas que no dependen del esquema: normalización de MAC, IDs positivos, tamaño y duplicados dentro del request, fechas ISO y orden del rango.
4. El servicio llama a un contrato de repositorio. El repositorio PostgreSQL todavía no existe; el predeterminado lanza `PersistenceNotConfigured`, que se convierte en `503`.

Esto permite probar reglas y contratos sin fingir que una operación se guardó. La detección de un equipo ya activo, la actualización del estado y condición, las transacciones de lotes, la auditoría y el historial completo deben delegarse al SQL confirmado.

## Configuración y ejecución

Requisitos: Python 3.10 o posterior. Desde la raíz del repositorio:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Antes de usar autenticación, reemplaza el valor de ejemplo de `JWT_SECRET_KEY` por una clave aleatoria privada de al menos 32 bytes. No guardes el secreto real en Git ni lo compartas en logs. `DATABASE_URL` debe reemplazarse por una URL válida solo cuando se vaya a preparar la etapa de conexión. El `.env` está excluido por `.gitignore`.

Variables disponibles:

| Variable | Uso |
| --- | --- |
| `JWT_SECRET_KEY` | Firma y validación de tokens. Sin ella, el login y las rutas JWT responden que JWT no está configurado. |
| `DATABASE_URL` | URL PostgreSQL, por ejemplo `postgresql+psycopg://USUARIO:CLAVE@localhost:5432/preconfiguracion_db`. El driver puede inferirse desde `postgresql://`. |
| `PORT` | Puerto HTTP; por defecto `4729`. |
| `FLASK_DEBUG` | Activa el modo debug solamente si vale `true`; debe permanecer desactivado en producción. |

El archivo [.env.example](.env.example) contiene valores ilustrativos, no credenciales utilizables. En Codespaces, inicia con:

```sh
python main.py
```

La app escucha en `0.0.0.0` y usa el puerto `4729`, salvo que `PORT` indique otro.

### Health check actual

`GET /health/database` **no abre una conexión**. Devuelve `database: configured` y `connection_checked: false` si `DATABASE_URL` existe al importar la aplicación; si no existe, devuelve `503`, `database: not_configured` y `connection_checked: false`. Una URL configurada no garantiza que el servidor esté disponible, que las credenciales sean válidas ni que exista el esquema.

## Funcionalidad preparada

Las rutas y cuerpos completos están en [docs/API.md](docs/API.md). Resumen:

| Área | Rutas principales | Estado |
| --- | --- | --- |
| Autenticación | `POST /login`, `POST /logout` | Login desacoplado; requiere repositorio real para autenticar. Logout informa que el cliente debe eliminar el token; no hay revocación server-side. |
| Usuarios | `GET /users`, `GET/PUT/DELETE /users/{id}`, `POST /registry` | Permisos, validación básica y hash preparados; persistencia pendiente. |
| Técnicos | `GET/POST /technicians`, `GET/PUT/DELETE /technicians/{id}` | Rutas protegidas; el cuerpo de técnico debe definirse con el DDL real. |
| Ingresos por lote | `POST /inventory/entries` | Valida y forma un comando; no escribe hasta conectar el repositorio SQL. |
| Entregas por lote | `POST /inventory/deliveries` | Valida y forma un comando; no cambia estado hasta conectar el repositorio SQL. |
| Consulta por MAC | `GET /inventory/mac/{mac}` | Ruta preparada; debe delegar en la función SQL de historial que confirme el DDL. |
| Disponibles | `GET /inventory/available` | Acepta filtros MAC, tipo y fechas; consulta SQL pendiente. |
| Reportes | `GET /reports/operations`, `GET /reports/daily-volume` | Filtros preparados; vistas y funciones SQL pendientes. |

Las MAC admiten `:`, `-`, `.`, o ningún separador y se normalizan a `AA:BB:CC:DD:EE:FF`. Cada lote acepta entre 1 y 500 MAC y rechaza repeticiones dentro de la misma solicitud. Esto **no** detecta duplicados activos concurrentes: esa garantía requiere una transacción y la restricción o función definida por PostgreSQL.

Roles y permisos propuestos:

| Rol | Acceso propuesto |
| --- | --- |
| `Super Admin` | Lectura y gestión de usuarios; lectura/escritura de técnicos; inventario, operaciones y reportes. |
| `Admin` | Lectura de usuarios; gestión de técnicos; inventario, operaciones y reportes. |
| `Usuario` | Lectura de inventario e historial; registro de operaciones. |

Esta tabla está aplicada en `config/authorization.py`, pero es una propuesta, no una especificación validada. Confirma también si los usuarios pueden hacer entregas, gestionar técnicos o consultar reportes antes de producción.

## Pruebas sin PostgreSQL

Las pruebas usan repositorios falsos en memoria para comprobar llamadas y validaciones; no crean base de datos ni prueban persistencia real:

```sh
python -m unittest discover -s tests -v
```

Cobertura actual: emisión/rechazo de login, ausencia de token, autorización por rol, respuesta `503` cuando falta persistencia, indicador de health check sin conexión, normalización de MAC, lotes de ingreso/entrega, repetición dentro del lote y filtros de fechas.

## Integración PostgreSQL pendiente

No hay en este repositorio un script DDL que confirme tablas, columnas, relaciones, constraints, vistas o funciones. Por eso no se crean modelos ORM para inventario ni consultas SQL basadas en supuestos. Para integrar PostgreSQL de forma segura:

1. **Incorporar y revisar el SQL oficial.** Confirmar el esquema (`inventario`), tablas de usuarios/roles/técnicos/equipos/operaciones/detalle/auditoría, columnas, tipos, claves, estados válidos, restricciones e índices. Localizar las funciones y vistas para ingresos, entregas, historial y reportes.
2. **Confirmar los contratos funcionales.** Validar la matriz de roles, el algoritmo/formato de hash almacenado, los campos requeridos de técnicos y la semántica de entrega/condición. Verificar especialmente `inventario.fn_historial_por_mac` y su resultado.
3. **Implementar repositorios concretos.** Implementar `InventoryRepository` y los contratos de autenticación/administración con consultas parametrizadas, preferentemente llamando las funciones y vistas que ya encapsulan la lógica. No duplicar en Python las transiciones de estado resueltas por SQL.
4. **Definir unidad transaccional por lote.** Ingreso y entrega deben ser atómicos según las reglas del proyecto, validar que todos los equipos correspondan al estado permitido y manejar concurrencia. La restricción/función PostgreSQL debe ser la autoridad para impedir dos ingresos activos de la misma MAC.
5. **Mapear errores de PostgreSQL.** Traducir conflictos de unicidad/estado a `409`, referencias inválidas a `400` o `404` según el contrato y fallos de conexión a `503`; no devolver detalles, SQL o credenciales al cliente. Conservar la auditoría generada por el sistema.
6. **Conectar dependencias en la factory.** Crear el engine mediante `config.database.get_engine()`, administrar el ciclo de vida de sesiones por request/unidad de trabajo y pasar los repositorios concretos a `create_app()`. Cerrar/rollback de sesiones ante error. Actualmente `create_app()` usa adaptadores “no configurados” por defecto.
7. **Verificar con la base de integración autorizada.** Solo después de disponer del DDL, URL y ambiente acordado: ejecutar pruebas de conexión y de los contratos reales para login/roles, lote de ingreso, entrega, historial con varios ciclos, equipos disponibles, reportes y auditoría. Este README no afirma que esos flujos ya estén integrados.

La configuración en `config/database.py` valida que la URL sea PostgreSQL y crea el engine de forma perezosa; `get_db_session()` ofrece el punto de entrada de sesiones. Hoy las rutas de inventario no usan esa sesión porque falta el adaptador de repositorio. No se ejecuta `create_all()`, no hay migraciones automáticas y no existe fallback a SQLite.

## Respuestas de error

| Estado | Significado general |
| --- | --- |
| `400` | Cuerpo o filtros inválidos. |
| `401` | Falta autenticación o las credenciales son inválidas. |
| `403` | El rol autenticado no tiene el permiso requerido. |
| `404` | Recurso no encontrado por el adaptador configurado. |
| `409` | Conflicto de MAC/estado que el adaptador deberá mapear desde PostgreSQL. |
| `503` | JWT o persistencia requerida no configurados; no implica operación completada. |

## Seguridad y despliegue

- No uses `FLASK_DEBUG=true` en despliegues públicos.
- Restringe CORS a los orígenes reales del frontend antes de producción; ahora la configuración es permisiva para desarrollo.
- `JWT_SECRET_KEY` debe ser secreta, aleatoria, estable entre réplicas y rotarse siguiendo un procedimiento que contemple tokens emitidos.
- Los JWT son stateless: `/logout` no revoca tokens robados o previamente emitidos.
- Añade límites de frecuencia al login y auditoría de accesos fallidos al integrar la persistencia.
- Evita registrar credenciales, tokens, contraseñas o el contenido sensible de las operaciones en logs.
