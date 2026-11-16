from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, DataError, IntegrityError, OperationalError

from config.database import DatabaseNotConfigured, get_db_session
from models.inventory import DuplicateActiveEquipment, PersistenceNotConfigured, ValidationError


def _normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    return value.strip()


def _translate_db_error(error: Exception, default_message: str):
    message = str(error).lower()
    if isinstance(error, IntegrityError):
        if 'mac' in message or 'indice_mac_activa_unica' in message:
            raise DuplicateActiveEquipment('Ya existe un equipo activo con esta MAC.') from error
        if 'correo' in message or 'unique' in message or 'duplicate key' in message:
            raise ValidationError('El registro ya existe.') from error
        raise ValidationError(default_message) from error
    if isinstance(error, DataError):
        raise ValidationError(default_message) from error
    if isinstance(error, (OperationalError, DBAPIError)):
        raise PersistenceNotConfigured('La base de datos PostgreSQL no está disponible o no responde.') from error
    raise PersistenceNotConfigured(default_message) from error


class PostgresInventoryRepository:
    def __init__(self, session=None):
        self.session = session or get_db_session()

    def register_entries(self, batch):
        try:
            result = self.session.execute(
                text(
                    """
                    SELECT inventario.registro_ingreso_lote(
                        :identificacion_tecnico,
                        :id_usuario,
                        :observaciones,
                        :macs,
                        :id_tipo,
                        :id_condicion
                    ) AS id_operacion
                    """
                ),
                {
                    'identificacion_tecnico': str(batch.technician_id),
                    'id_usuario': batch.responsible_user_id,
                    'observaciones': batch.observations,
                    'macs': list(batch.macs),
                    'id_tipo': batch.equipment_type_id,
                    'id_condicion': batch.condition_id,
                },
            )
            self.session.commit()
            operation_id = result.scalar_one()
            return {'id_operacion': operation_id, 'macs': list(batch.macs), 'tipo_operacion': 'INGRESO'}
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (DuplicateActiveEquipment, ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible registrar el ingreso por lote.')

    def register_deliveries(self, batch):
        try:
            result = self.session.execute(
                text(
                    """
                    SELECT inventario.registro_entrega_lote(
                        :identificacion_tecnico,
                        :id_usuario,
                        :observaciones,
                        :macs,
                        :id_condicion
                    ) AS id_operacion
                    """
                ),
                {
                    'identificacion_tecnico': None,
                    'id_usuario': batch.responsible_user_id,
                    'observaciones': batch.observations,
                    'macs': list(batch.macs),
                    'id_condicion': batch.condition_id,
                },
            )
            self.session.commit()
            operation_id = result.scalar_one()
            return {'id_operacion': operation_id, 'macs': list(batch.macs), 'tipo_operacion': 'ENTREGA'}
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (DuplicateActiveEquipment, ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible registrar la entrega por lote.')

    def get_history_by_mac(self, mac: str):
        try:
            rows = self.session.execute(
                text("SELECT * FROM inventario.fn_historial_por_mac(:mac) ORDER BY fecha ASC, hora ASC, id_operacion ASC"),
                {'mac': mac},
            )
            return [dict(row._mapping) for row in rows]
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible consultar el historial por MAC.')

    def list_available(self, filters):
        try:
            query = text(
                """
                SELECT
                    e.id_equipo,
                    e.mac,
                    te.nombre AS tipo_equipo,
                    ce.nombre AS condicion_ingreso,
                    e.estado,
                    e.fecha_ingreso,
                    e.observaciones
                FROM inventario.equipos e
                INNER JOIN inventario.tipos_equipo te ON e.id_tipo = te.id_tipo
                INNER JOIN inventario.condiciones_equipo ce ON e.id_condicion_ingreso = ce.id_condicion
                WHERE e.estado = 'INGRESADO'
                  AND (:mac IS NULL OR e.mac = :mac)
                  AND (:equipment_type_id IS NULL OR e.id_tipo = :equipment_type_id)
                  AND (:date_from IS NULL OR e.fecha_ingreso::DATE >= :date_from)
                  AND (:date_to IS NULL OR e.fecha_ingreso::DATE <= :date_to)
                ORDER BY e.fecha_ingreso DESC
                """
            )
            rows = self.session.execute(
                query,
                {
                    'mac': filters.mac,
                    'equipment_type_id': filters.equipment_type_id,
                    'date_from': filters.date_from,
                    'date_to': filters.date_to,
                },
            )
            return [dict(row._mapping) for row in rows]
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible consultar el inventario disponible.')

    def list_operations(self, filters):
        try:
            query = text(
                """
                SELECT
                    o.id_operacion,
                    o.tipo_operacion,
                    o.identificacion_tecnico,
                    o.id_usuario,
                    o.fecha,
                    o.hora,
                    o.observaciones
                FROM inventario.operaciones o
                WHERE (:date_from IS NULL OR o.fecha >= :date_from)
                  AND (:date_to IS NULL OR o.fecha <= :date_to)
                  AND (:user_id IS NULL OR o.id_usuario = :user_id)
                ORDER BY o.fecha DESC, o.hora DESC
                """
            )
            rows = self.session.execute(
                query,
                {
                    'date_from': filters.date_from,
                    'date_to': filters.date_to,
                    'user_id': filters.user_id,
                },
            )
            return [dict(row._mapping) for row in rows]
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible consultar los reportes de operaciones.')

    def daily_volume(self, filters):
        try:
            query = text(
                """
                SELECT
                    o.fecha AS fecha,
                    COUNT(*) AS total_operaciones
                FROM inventario.operaciones o
                WHERE (:date_from IS NULL OR o.fecha >= :date_from)
                  AND (:date_to IS NULL OR o.fecha <= :date_to)
                  AND (:user_id IS NULL OR o.id_usuario = :user_id)
                GROUP BY o.fecha
                ORDER BY o.fecha DESC
                """
            )
            rows = self.session.execute(
                query,
                {
                    'date_from': filters.date_from,
                    'date_to': filters.date_to,
                    'user_id': filters.user_id,
                },
            )
            return [dict(row._mapping) for row in rows]
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible consultar el volumen diario.')


class PostgresUserRepository:
    def __init__(self, session=None):
        self.session = session or get_db_session()

    def authenticate(self, username: str):
        try:
            row = self.session.execute(
                text(
                    """
                    SELECT
                        u.id_usuario AS id,
                        u.correo AS username,
                        u.contrasena AS password_hash,
                        r.nombre AS role
                    FROM inventario.usuarios u
                    INNER JOIN inventario.roles r ON r.id_rol = u.id_rol
                    WHERE LOWER(u.correo) = LOWER(:username)
                    LIMIT 1
                    """
                ),
                {'username': _normalize_string(username) or ''},
            ).mappings().first()
            if row is None:
                return None
            return dict(row)
        except Exception as error:
            self.session.rollback()
            _translate_db_error(error, 'No fue posible autenticar al usuario.')

    def list_users(self):
        try:
            rows = self.session.execute(
                text(
                    """
                    SELECT
                        u.id_usuario AS id,
                        u.correo AS username,
                        r.nombre AS role,
                        u.activo
                    FROM inventario.usuarios u
                    INNER JOIN inventario.roles r ON r.id_rol = u.id_rol
                    ORDER BY u.id_usuario
                    """
                )
            ).mappings().all()
            return [dict(row) for row in rows]
        except Exception as error:
            self.session.rollback()
            _translate_db_error(error, 'No fue posible consultar los usuarios.')

    def get_user(self, user_id: int):
        try:
            row = self.session.execute(
                text(
                    """
                    SELECT
                        u.id_usuario AS id,
                        u.correo AS username,
                        r.nombre AS role,
                        u.activo
                    FROM inventario.usuarios u
                    INNER JOIN inventario.roles r ON r.id_rol = u.id_rol
                    WHERE u.id_usuario = :user_id
                    LIMIT 1
                    """
                ),
                {'user_id': user_id},
            ).mappings().first()
            return dict(row) if row is not None else None
        except Exception as error:
            self.session.rollback()
            _translate_db_error(error, 'No fue posible consultar el usuario.')

    def create_user(self, payload):
        username = _normalize_string(payload.get('username'))
        password_hash = payload.get('password_hash')
        role_name = payload.get('role')
        if not username or not password_hash or not role_name:
            raise ValidationError('Faltan datos requeridos para crear el usuario.')
        try:
            role_row = self.session.execute(
                text('SELECT id_rol FROM inventario.roles WHERE nombre = :role_name LIMIT 1'),
                {'role_name': role_name},
            ).scalar_one_or_none()
            if role_row is None:
                raise ValidationError('El rol indicado no existe.')
            result = self.session.execute(
                text(
                    """
                    INSERT INTO inventario.usuarios (id_rol, correo, contrasena, activo)
                    VALUES (:id_rol, :correo, :contrasena, TRUE)
                    RETURNING id_usuario
                    """
                ),
                {'id_rol': role_row, 'correo': username, 'contrasena': password_hash},
            )
            self.session.commit()
            user_id = result.scalar_one()
            return {'id': user_id, 'username': username, 'role': role_name}
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible crear el usuario.')

    def update_user(self, user_id: int, payload):
        values = {}
        if 'username' in payload:
            values['correo'] = _normalize_string(payload['username'])
        if 'password_hash' in payload:
            values['contrasena'] = payload['password_hash']
        if 'role' in payload:
            role_row = self.session.execute(
                text('SELECT id_rol FROM inventario.roles WHERE nombre = :role_name LIMIT 1'),
                {'role_name': payload['role']},
            ).scalar_one_or_none()
            if role_row is None:
                raise ValidationError('El rol indicado no existe.')
            values['id_rol'] = role_row
        if not values:
            return self.get_user(user_id)
        assignments = ', '.join(f'{key} = :{key}' for key in values.keys())
        try:
            self.session.execute(
                text(f'UPDATE inventario.usuarios SET {assignments} WHERE id_usuario = :user_id'),
                {**values, 'user_id': user_id},
            )
            self.session.commit()
            return self.get_user(user_id)
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible actualizar el usuario.')

    def delete_user(self, user_id: int):
        try:
            row = self.get_user(user_id)
            if row is None:
                return None
            self.session.execute(text('DELETE FROM inventario.usuarios WHERE id_usuario = :user_id'), {'user_id': user_id})
            self.session.commit()
            return row
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible eliminar el usuario.')

    def list_technicians(self):
        try:
            rows = self.session.execute(
                text(
                    """
                    SELECT
                        t.identificacion AS id,
                        t.identificacion AS identificacion,
                        t.nombres,
                        t.apellidos,
                        t.ciudad,
                        t.sede,
                        t.activo
                    FROM inventario.tecnicos t
                    ORDER BY t.identificacion
                    """
                )
            ).mappings().all()
            return [dict(row) for row in rows]
        except Exception as error:
            self.session.rollback()
            _translate_db_error(error, 'No fue posible consultar los técnicos.')

    def create_technician(self, payload):
        required = ['identificacion', 'nombres', 'apellidos', 'ciudad', 'sede']
        missing = [field for field in required if field not in payload or payload.get(field) in (None, '')]
        if missing:
            raise ValidationError(f'Faltan datos requeridos: {", ".join(missing)}')
        try:
            result = self.session.execute(
                text(
                    """
                    INSERT INTO inventario.tecnicos (
                        identificacion, nombres, apellidos, ciudad, sede, activo
                    ) VALUES (
                        :identificacion, :nombres, :apellidos, :ciudad, :sede, TRUE
                    )
                    RETURNING identificacion
                    """
                ),
                {
                    'identificacion': str(payload['identificacion']),
                    'nombres': payload['nombres'],
                    'apellidos': payload['apellidos'],
                    'ciudad': payload['ciudad'],
                    'sede': payload['sede'],
                },
            )
            self.session.commit()
            identificacion = result.scalar_one()
            return {'id': identificacion, 'identificacion': identificacion, **{k: payload[k] for k in ['nombres','apellidos','ciudad','sede']}}
        except Exception as error:
            self.session.rollback()
            if isinstance(error, (ValidationError, PersistenceNotConfigured)):
                raise
            _translate_db_error(error, 'No fue posible crear el técnico.')

    def get_technician(self, technician_id):
        try:
            row = self.session.execute(
                text(
                    """
                    SELECT
                        t.identificacion AS id,
                        t.identificacion,
                        t.nombres,
                        t.apellidos,
                        t.ciudad,
                        t.sede,
                        t.activo
                    FROM inventario.tecnicos t
                    WHERE t.identificacion = :identificacion
                    LIMIT 1
                    """
                ),
                {'identificacion': str(technician_id)},
            ).mappings().first()
            return dict(row) if row is not None else None
        except Exception as error:
            self.session.rollback()
            _translate_db_error(error, 'No fue posible consultar el técnico.')

    def update_technician(self, technician_id, payload):
        if not payload:
            return self.get_technician(technician_id)
        assignments = []
        params = {'identificacion': str(technician_id)}
        for field in ['nombres', 'apellidos', 'ciudad', 'sede']:
            if field in payload and payload[field] not in (None, ''):
                assignments.append(f'{field} = :{field}')
                params[field] = payload[field]
        if not assignments:
            return self.get_technician(technician_id)
        try:
            self.session.execute(
                text(f'UPDATE inventario.tecnicos SET {", ".join(assignments)} WHERE identificacion = :identificacion'),
                params,
            )
            self.session.commit()
            return self.get_technician(technician_id)
        except Exception as error:
            self.session.rollback()
            _translate_db_error(error, 'No fue posible actualizar el técnico.')

    def delete_technician(self, technician_id):
        try:
            row = self.get_technician(technician_id)
            if row is None:
                return None
            self.session.execute(
                text('DELETE FROM inventario.tecnicos WHERE identificacion = :identificacion'),
                {'identificacion': str(technician_id)},
            )
            self.session.commit()
            return row
        except Exception as error:
            self.session.rollback()
            _translate_db_error(error, 'No fue posible eliminar el técnico.')


class UnconfiguredInventoryRepository:
    def _not_configured(self, *args, **kwargs):
        raise PersistenceNotConfigured(
            'La persistencia de inventario requiere una base PostgreSQL configurada y el SQL oficial del proyecto.'
        )

    register_entries = _not_configured
    register_deliveries = _not_configured
    get_history_by_mac = _not_configured
    list_available = _not_configured
    list_operations = _not_configured
    daily_volume = _not_configured


class UnconfiguredUserRepository:
    def authenticate(self, username: str):
        raise PersistenceNotConfigured(
            'La autenticación requiere que la tabla usuarios del esquema inventario esté disponible.'
        )

    def __getattr__(self, name):
        def not_configured(*args, **kwargs):
            raise PersistenceNotConfigured(
                'La administración requiere un esquema PostgreSQL configurado y un repositorio real.'
            )
        return not_configured


class UnconfiguredAdministrationRepository:
    def __getattr__(self, name):
        def not_configured(*args, **kwargs):
            raise PersistenceNotConfigured(
                'La administración requiere confirmar la tabla y columnas reales del esquema PostgreSQL.'
            )
        return not_configured