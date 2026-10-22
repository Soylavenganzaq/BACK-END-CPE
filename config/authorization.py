from functools import wraps

from flask import current_app, jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request


ROLE_PERMISSIONS = {
    'Super Admin': frozenset({
        'users:read', 'users:manage', 'technicians:read', 'technicians:write',
        'inventory:read', 'operations:read', 'operations:write', 'reports:read',
    }),
    'Admin': frozenset({
        'users:read', 'technicians:read', 'technicians:write', 'inventory:read',
        'operations:read', 'operations:write', 'reports:read',
    }),
    'Usuario': frozenset({
        'inventory:read', 'operations:read', 'operations:write',
    }),
}


def role_has_permission(role: str | None, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def requires_permission(permission: str):
    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_app.config.get('JWT_SECRET_KEY'):
                return jsonify({'error': 'JWT no está configurado'}), 503
            verify_jwt_in_request()
            role = get_jwt().get('role')
            if not role_has_permission(role, permission):
                return jsonify({'error': 'Permiso insuficiente'}), 403
            return view(*args, **kwargs)
        return wrapped
    return decorate