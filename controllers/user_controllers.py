from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from config.authorization import requires_permission, role_has_permission
from models.inventory import PersistenceNotConfigured, ValidationError
from repositories.pending_repositories import (
    UnconfiguredAdministrationRepository,
    UnconfiguredUserRepository,
)
from services.auth_service import AuthenticationService


def _value(record, key):
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)


def _public_data(value):
    if isinstance(value, dict):
        return {
            key: _public_data(item)
            for key, item in value.items()
            if key not in {'password', 'password_hash'} and not key.startswith('_')
        }
    if isinstance(value, (list, tuple)):
        return [_public_data(item) for item in value]
    if hasattr(value, '__dict__'):
        return _public_data(vars(value))
    return value


def create_user_blueprint(auth_repository=None, administration_repository=None):
    blueprint = Blueprint('users', __name__)
    authentication = AuthenticationService(auth_repository or UnconfiguredUserRepository())
    administration = administration_repository or UnconfiguredAdministrationRepository()

    def execute(action, success_status=200):
        try:
            result = action()
            if result is None:
                return jsonify({'error': 'Registro no encontrado'}), 404
            return jsonify(_public_data(result)), success_status
        except ValidationError as error:
            return jsonify({'error': str(error)}), 400
        except PersistenceNotConfigured as error:
            current_app.logger.info('Administration persistence unavailable: %s', error)
            return jsonify({'error': 'Persistencia de usuarios/técnicos no configurada'}), 503

    @blueprint.post('/login')
    def login():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'error': 'El cuerpo debe ser un objeto JSON'}), 400
        username = payload.get('username')
        password = payload.get('password')
        if not isinstance(username, str) or not username.strip() or not isinstance(password, str) or not password:
            return jsonify({'error': 'username y password son obligatorios'}), 400
        if not current_app.config.get('JWT_SECRET_KEY'):
            return jsonify({'error': 'JWT no está configurado'}), 503
        try:
            user = authentication.authenticate(username.strip(), password)
        except PersistenceNotConfigured as error:
            current_app.logger.info('Authentication persistence unavailable: %s', error)
            return jsonify({'error': 'Autenticación no configurada'}), 503
        if user is None:
            return jsonify({'error': 'Credenciales inválidas'}), 401
        user_id = _value(user, 'id')
        role = _value(user, 'role') or _value(user, 'role_name')
        if not user_id or not role_has_permission(role, 'inventory:read'):
            return jsonify({'error': 'El usuario no tiene un rol habilitado'}), 403
        token = create_access_token(
            identity=str(user_id),
            additional_claims={'user_id': user_id, 'role': role},
        )
        return jsonify({
            'access_token': token,
            'user': {'id': user_id, 'username': _value(user, 'username'), 'role': role},
        }), 200

    @blueprint.post('/registry')
    @requires_permission('users:manage')
    def create_user():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'error': 'El cuerpo debe ser un objeto JSON'}), 400
        username = payload.get('username')
        password = payload.get('password')
        role = payload.get('role')
        if not isinstance(username, str) or not username.strip():
            return jsonify({'error': 'username es obligatorio'}), 400
        if not isinstance(password, str) or len(password) < 12:
            return jsonify({'error': 'password debe tener al menos 12 caracteres'}), 400
        if role not in ('Super Admin', 'Admin', 'Usuario'):
            return jsonify({'error': 'role no válido'}), 400
        body = {'username': username.strip(), 'password_hash': generate_password_hash(password), 'role': role}
        return execute(lambda: administration.create_user(body), 201)

    @blueprint.get('/users')
    @requires_permission('users:read')
    def list_users():
        return execute(administration.list_users)

    @blueprint.get('/users/<int:user_id>')
    @requires_permission('users:read')
    def get_user(user_id):
        return execute(lambda: administration.get_user(user_id))

    @blueprint.put('/users/<int:user_id>')
    @requires_permission('users:manage')
    def update_user(user_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'error': 'El cuerpo debe ser un objeto JSON'}), 400
        body = {}
        if 'username' in payload:
            username = payload['username']
            if not isinstance(username, str) or not username.strip():
                return jsonify({'error': 'username no puede estar vacío'}), 400
            body['username'] = username.strip()
        if 'password' in payload:
            password = payload['password']
            if not isinstance(password, str) or len(password) < 12:
                return jsonify({'error': 'password debe tener al menos 12 caracteres'}), 400
            body['password_hash'] = generate_password_hash(password)
        if 'role' in payload:
            if payload['role'] not in ('Super Admin', 'Admin', 'Usuario'):
                return jsonify({'error': 'role no válido'}), 400
            body['role'] = payload['role']
        return execute(lambda: administration.update_user(user_id, body))

    @blueprint.delete('/users/<int:user_id>')
    @requires_permission('users:manage')
    def delete_user(user_id):
        return execute(lambda: administration.delete_user(user_id))

    @blueprint.get('/technicians')
    @requires_permission('technicians:read')
    def list_technicians():
        return execute(administration.list_technicians)

    @blueprint.post('/technicians')
    @requires_permission('technicians:write')
    def create_technician():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'error': 'El cuerpo debe ser un objeto JSON'}), 400
        return execute(lambda: administration.create_technician(payload), 201)

    @blueprint.get('/technicians/<int:technician_id>')
    @requires_permission('technicians:read')
    def get_technician(technician_id):
        return execute(lambda: administration.get_technician(technician_id))

    @blueprint.put('/technicians/<int:technician_id>')
    @requires_permission('technicians:write')
    def update_technician(technician_id):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({'error': 'El cuerpo debe ser un objeto JSON'}), 400
        return execute(lambda: administration.update_technician(technician_id, payload))

    @blueprint.delete('/technicians/<int:technician_id>')
    @requires_permission('technicians:write')
    def delete_technician(technician_id):
        return execute(lambda: administration.delete_technician(technician_id))

    return blueprint
