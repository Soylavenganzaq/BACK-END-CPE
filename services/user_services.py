from repositories.user_repository import UserRepository
from models.user_model import User
from werkzeug.security import generate_password_hash, check_password_hash
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UsersService:
    def __init__(self, db_session):
        self.users_repository = UserRepository(db_session)

    def authenticate_user(self, username: str, password: str):
        user = self.users_repository.db.query(User).filter(User.username == username).first()
        logger.info(f"Authenticating user: {username}")
        if user and check_password_hash(user.password, password):
            logger.info(f"User authenticated successfully: {username}")
            return user
        logger.warning(f"Failed authentication attempt: {username}")
        return None

    def get_all_users(self):
        logger.info("Fetching all users")
        return self.users_repository.get_all_users()

    def get_user_by_id(self, user_id: int):
        logger.info(f"Fetching user by ID: {user_id}")
        return self.users_repository.get_user_by_id(user_id)

    def create_user(self, username: str, password: str):
        password_hashed = generate_password_hash(password)
        logger.info(f"Creating user: {username}")
        return self.users_repository.create_user(username, password_hashed)
    

    def update_user(self, user_id: int, username: str = None, password: str = None):
        logger.info(f"Updating user: {user_id}")
        password_hashed = generate_password_hash(password) if password else None
        return self.users_repository.update_user(user_id, username, password_hashed)

    def delete_user(self, user_id: int):
        logger.info(f"Deleting user: {user_id}")
        return self.users_repository.delete_user(user_id)