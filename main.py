import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager

from config.database import DATABASE_URL, DatabaseNotConfigured
from controllers.component_controller import computador_bp
from controllers.inventory_controller import create_inventory_blueprint
from controllers.user_controllers import create_user_blueprint
from models.inventory import PersistenceNotConfigured, ValidationError
from repositories.pending_repositories import (
    UnconfiguredAdministrationRepository,
    UnconfiguredInventoryRepository,
    UnconfiguredUserRepository,
)


def create_app(
    config=None,
    inventory_repository=None,
    auth_repository=None,
    administration_repository=None,
):
    app = Flask(__name__)
    app.config.from_mapping(
        JWT_SECRET_KEY=os.getenv('JWT_SECRET_KEY'),
        JWT_TOKEN_LOCATION=['headers'],
        JWT_ACCESS_TOKEN_EXPIRES=3600,
        JWT_HEADER_NAME='Authorization',
        JWT_HEADER_TYPE='Bearer',
    )
    if config:
        app.config.update(config)

    CORS(app, resources={r'/*': {'origins': '*'}})
    JWTManager(app)
    app.register_blueprint(computador_bp)
    app.register_blueprint(create_user_blueprint(
        auth_repository=auth_repository or UnconfiguredUserRepository(),
        administration_repository=administration_repository or UnconfiguredAdministrationRepository(),
    ))
    app.register_blueprint(create_inventory_blueprint(
        repository=inventory_repository or UnconfiguredInventoryRepository(),
    ))

    @app.errorhandler(DatabaseNotConfigured)
    @app.errorhandler(PersistenceNotConfigured)
    def persistence_not_configured(error):
        app.logger.info('Persistence is not configured: %s', error)
        return jsonify({'error': str(error)}), 503

    @app.errorhandler(ValidationError)
    def validation_error(error):
        return jsonify({'error': str(error)}), 400

    @app.route('/')
    def index():
        return jsonify({'message': 'API backend. Sirve endpoints JSON.'}), 200

    @app.get('/health/database')
    def database_health():
        return jsonify({
            'database': 'configured' if DATABASE_URL else 'not_configured',
            'connection_checked': False,
        }), 200 if DATABASE_URL else 503

    @app.route('/favicon.ico')
    def favicon():
        favicon_path = os.path.join(app.root_path, 'static', 'favicon.ico')
        if os.path.exists(favicon_path):
            return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')
        return '', 204

    @app.post('/logout')
    def logout():
        return jsonify({'message': 'Logged out; elimina el token en el cliente.'}), 200

    @app.errorhandler(401)
    def unauthorized(_error):
        return jsonify({'error': 'Autenticación requerida'}), 401

    @app.errorhandler(422)
    def invalid_jwt(_error):
        return jsonify({'error': 'Token inválido'}), 422

    return app


app = create_app()


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', '4729')),
        debug=os.getenv('FLASK_DEBUG', '').lower() == 'true',
    )