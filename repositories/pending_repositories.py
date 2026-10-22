from models.inventory import PersistenceNotConfigured


class UnconfiguredInventoryRepository:
    def _not_configured(self, *args, **kwargs):
        raise PersistenceNotConfigured(
            'La persistencia de inventario requiere el SQL oficial y su adaptador PostgreSQL.'
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
            'La autenticación requiere confirmar el esquema de usuarios y roles.'
        )


class UnconfiguredAdministrationRepository:
    def __getattr__(self, name):
        def not_configured(*args, **kwargs):
            raise PersistenceNotConfigured(
                'La administración requiere confirmar las tablas y columnas del SQL oficial.'
            )
        return not_configured