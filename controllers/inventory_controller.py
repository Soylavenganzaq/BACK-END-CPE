from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity

from config.authorization import requires_permission
from models.inventory import (
    DuplicateActiveEquipment,
    PersistenceNotConfigured,
    ValidationError,
)
from repositories.pending_repositories import UnconfiguredInventoryRepository
from services.inventory_service import InventoryService


def create_inventory_blueprint(repository=None):
    blueprint = Blueprint('inventory', __name__)
    service = InventoryService(repository or UnconfiguredInventoryRepository())

    def actor_id():
        value = get_jwt().get('user_id') or get_jwt_identity()
        try:
            actor = int(value)
        except (TypeError, ValueError) as error:
            raise ValidationError('El token no contiene un identificador de usuario válido.') from error
        if actor <= 0:
            raise ValidationError('El token no contiene un identificador de usuario válido.')
        return actor

    def execute(action):
        try:
            result = action()
            return jsonify({'data': result}), 200
        except ValidationError as error:
            return jsonify({'error': str(error)}), 400
        except DuplicateActiveEquipment as error:
            return jsonify({'error': str(error)}), 409
        except PersistenceNotConfigured as error:
            current_app.logger.info('Inventory persistence unavailable: %s', error)
            return jsonify({'error': 'Persistencia de inventario no configurada'}), 503

    @blueprint.post('/inventory/entries')
    @requires_permission('operations:write')
    def register_entries():
        payload = request.get_json(silent=True)
        return execute(lambda: service.register_entries(payload, actor_id()))

    @blueprint.post('/inventory/deliveries')
    @requires_permission('operations:write')
    def register_deliveries():
        payload = request.get_json(silent=True)
        return execute(lambda: service.register_deliveries(payload, actor_id()))

    @blueprint.get('/inventory/mac/<mac>')
    @requires_permission('inventory:read')
    def history_by_mac(mac):
        return execute(lambda: service.get_history_by_mac(mac))

    @blueprint.get('/inventory/available')
    @requires_permission('inventory:read')
    def available():
        return execute(lambda: service.list_available(request.args))

    @blueprint.get('/reports/operations')
    @requires_permission('reports:read')
    def operations_report():
        return execute(lambda: service.list_operations(request.args))

    @blueprint.get('/reports/daily-volume')
    @requires_permission('reports:read')
    def daily_volume_report():
        return execute(lambda: service.daily_volume(request.args))

    return blueprint