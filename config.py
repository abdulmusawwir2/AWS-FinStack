"""
config.py - Application Configuration

This module loads environment variables and provides configuration
settings for the entire Flask application. All sensitive data
(like AWS credentials) must be stored in the .env file.

Usage:
    from config import Config
    app.config.from_object(Config)
"""

import os
from dotenv import load_dotenv

# Load variables from .env file into the environment
load_dotenv()


class Config:
    """
    Central configuration class.
    All settings are read from environment variables.
    """

    # ─── Flask Settings ────────────────────────────────────────────
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    ENV = os.getenv("FLASK_ENV", "production")
    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", 5000))

    # ─── AWS Credentials ───────────────────────────────────────────
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

    # ─── DynamoDB Settings ─────────────────────────────────────────
    DYNAMODB_TABLE_NAME = os.getenv("DYNAMODB_TABLE_NAME", "ExpenseTracker")

    # ─── Login Credentials ─────────────────────────────────────────
    LOGIN_USERNAME = os.getenv("LOGIN_USERNAME", "admin")
    LOGIN_PASSWORD = os.getenv("LOGIN_PASSWORD", "admin123")

    # ─── Expense Categories ────────────────────────────────────────
    # Pre-defined list of expense categories shown in the UI dropdown
    EXPENSE_CATEGORIES = [
        "Food & Dining",
        "Transportation",
        "Shopping",
        "Entertainment",
        "Health & Medical",
        "Housing & Rent",
        "Utilities",
        "Education",
        "Travel",
        "Personal Care",
        "Subscriptions",
        "Other",
    ]
