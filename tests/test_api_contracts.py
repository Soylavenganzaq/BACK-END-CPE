import unittest

from flask_jwt_extended import create_access_token
from werkzeug.security import generate_password_hash

from main import create_app


class FakeAuthenticationRepository:
    def __init__(self, role='Usuario'):
        self.role = role

    def authenticate(self, username):
        if username != 'tester':
            return None
        return {
            'id': 7,
            'username': username,
            'role': self.role,
            'password_hash': generate_password_hash('correct horse battery staple'),
        }


class ApiContractTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {'TESTING': True, 'JWT_SECRET_KEY': 'test-secret-not-for-production-32-bytes'},
            auth_repository=FakeAuthenticationRepository(),
        )
        self.client = self.app.test_client()

    def token(self, role='Usuario'):
        with self.app.app_context():
            return create_access_token(
                identity='7', additional_claims={'user_id': 7, 'role': role}
            )

    def test_login_issues_token_for_valid_credentials(self):
        response = self.client.post('/login', json={
            'username': 'tester', 'password': 'correct horse battery staple'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('access_token', response.json)
        self.assertEqual(response.json['user']['role'], 'Usuario')

    def test_login_rejects_invalid_password(self):
        response = self.client.post('/login', json={
            'username': 'tester', 'password': 'incorrect'
        })
        self.assertEqual(response.status_code, 401)

    def test_protected_inventory_requires_token(self):
        response = self.client.get('/inventory/available')
        self.assertEqual(response.status_code, 401)

    def test_role_without_report_permission_is_forbidden(self):
        response = self.client.get('/reports/operations', headers={
            'Authorization': f'Bearer {self.token("Usuario")}'
        })
        self.assertEqual(response.status_code, 403)

    def test_inventory_write_without_adapter_is_not_reported_as_saved(self):
        response = self.client.post('/inventory/entries', json={
            'macs': ['AA:BB:CC:DD:EE:FF'],
            'technician_id': 2,
            'equipment_type_id': 3,
            'condition_id': 1,
        }, headers={'Authorization': f'Bearer {self.token("Usuario")}'})
        self.assertEqual(response.status_code, 503)
        self.assertIn('no configurada', response.json['error'])

    def test_database_health_reports_configuration_without_connecting(self):
        response = self.client.get('/health/database')
        self.assertFalse(response.json['connection_checked'])
        self.assertIn(response.json['database'], {'configured', 'not_configured'})


if __name__ == '__main__':
    unittest.main()