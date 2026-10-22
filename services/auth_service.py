from typing import Any, Protocol

from werkzeug.security import check_password_hash


class AuthenticationRepository(Protocol):
    def authenticate(self, username: str) -> Any: ...


class AuthenticationService:
    def __init__(self, repository: AuthenticationRepository):
        self.repository = repository

    def authenticate(self, username: str, password: str):
        user = self.repository.authenticate(username)
        if user is None:
            return None
        password_hash = _value(user, 'password_hash') or _value(user, 'password')
        if not password_hash or not check_password_hash(password_hash, password):
            return None
        return user


def _value(record: Any, key: str):
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)