"""
user_service.py - User Authentication Service

Handles user registration, login validation, and user lookup.
Passwords are hashed with bcrypt before storing in DynamoDB.

DynamoDB Table: ExpenseTrackerUsers
    Partition Key: username (String)
    Attributes:
        - username (str): unique login name
        - password_hash (str): bcrypt hash of the password
        - created_at (str): ISO timestamp
"""

import bcrypt
import logging
from datetime import datetime

from services.db_service import DynamoDBService

logger = logging.getLogger(__name__)

# Separate DB instance pointing at the Users table
from config import Config
import boto3
from botocore.exceptions import ClientError

USERS_TABLE = "ExpenseTrackerUsers"


def _get_users_table():
    """Return a boto3 DynamoDB Table resource for the Users table."""
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )
    return dynamodb.Table(USERS_TABLE)


def register_user(username: str, password: str) -> tuple[bool, str]:
    """
    Register a new user.

    Args:
        username (str): Desired username (3–30 chars, alphanumeric + _ -)
        password (str): Plain-text password (min 6 chars)

    Returns:
        tuple[bool, str]: (success, error_message)
    """
    username = username.strip().lower()
    password = password.strip()

    # Basic validation
    if not username or len(username) < 3:
        return False, "Username must be at least 3 characters."
    if not username.replace("_", "").replace("-", "").isalnum():
        return False, "Username can only contain letters, numbers, _ and -."
    if len(username) > 30:
        return False, "Username must be 30 characters or fewer."
    if not password or len(password) < 6:
        return False, "Password must be at least 6 characters."

    table = _get_users_table()

    # Check if username already exists
    try:
        response = table.get_item(Key={"username": username})
        if response.get("Item"):
            return False, "Username already taken. Please choose another."
    except ClientError as e:
        logger.error(f"register_user get_item error: {e}")
        return False, "Database error. Please try again."

    # Hash the password
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Store the new user
    try:
        table.put_item(Item={
            "username": username,
            "password_hash": password_hash,
            "created_at": datetime.utcnow().isoformat(),
        })
        logger.info(f"New user registered: {username}")
        return True, ""
    except ClientError as e:
        logger.error(f"register_user put_item error: {e}")
        return False, "Failed to create account. Please try again."


def verify_user(username: str, password: str) -> tuple[bool, str]:
    """
    Verify login credentials.

    Args:
        username (str): Username to look up.
        password (str): Plain-text password to check.

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    username = username.strip().lower()
    password = password.strip()

    if not username or not password:
        return False, "Username and password are required."

    table = _get_users_table()

    try:
        response = table.get_item(Key={"username": username})
        user = response.get("Item")
    except ClientError as e:
        logger.error(f"verify_user get_item error: {e}")
        return False, "Database error. Please try again."

    if not user:
        return False, "Invalid username or password."

    # Check password against stored hash
    stored_hash = user.get("password_hash", "")
    if not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
        return False, "Invalid username or password."

    logger.info(f"User '{username}' authenticated successfully.")
    return True, ""
