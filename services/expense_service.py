"""
expense_service.py - Business Logic Service

This module contains all business logic related to expenses.
It sits between the Flask routes (app.py) and the database (db_service.py).

Architecture:
    Routes (app.py) → expense_service.py → db_service.py → DynamoDB

Responsibilities:
    - Validate input data
    - Generate unique IDs for new expenses
    - Format/transform data before storing or returning
    - Calculate totals, summaries, and statistics
    - Call DynamoDBService methods to persist data
"""

import uuid
import logging
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

from services.db_service import DynamoDBService

# Set up module-level logger
logger = logging.getLogger(__name__)

# Create a single shared instance of the DB service
db = DynamoDBService()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_decimals(item: dict) -> dict:
    """
    Convert DynamoDB Decimal types to Python float for JSON serialization.

    DynamoDB stores numbers as Decimal objects. Flask's jsonify can't
    serialize Decimal by default, so we convert them to float here.

    Args:
        item (dict): A raw DynamoDB item dict.

    Returns:
        dict: The same dict with Decimal values replaced by float.
    """
    if not item:
        return item
    serialized = {}
    for key, value in item.items():
        if isinstance(value, Decimal):
            serialized[key] = float(value)
        else:
            serialized[key] = value
    return serialized


def _validate_expense_data(data: dict, require_all: bool = True) -> tuple[bool, str]:
    """
    Validate incoming expense data from the request.

    Args:
        data (dict): The JSON body from the request.
        require_all (bool): If True, all fields are required (for create).
                            If False, partial data is OK (for update).

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    required_fields = ["title", "amount", "category", "date"]

    if require_all:
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                return False, f"Missing required field: '{field}'"

    # Validate amount is a positive number
    if "amount" in data:
        try:
            amount = float(data["amount"])
            if amount <= 0:
                return False, "Amount must be a positive number."
        except (ValueError, TypeError):
            return False, "Amount must be a valid number."

    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# CREATE
# ─────────────────────────────────────────────────────────────────────────────

def create_expense(data: dict, user_id: str = None) -> tuple[dict, str]:
    """
    Create a new expense and store it in DynamoDB.

    Args:
        data (dict): Raw expense data from the API request body.
        user_id (str): The username of the logged-in user.

    Returns:
        tuple[dict, str]: (expense_dict, error_message)
    """
    # Step 1: Validate
    is_valid, error_msg = _validate_expense_data(data, require_all=True)
    if not is_valid:
        return {}, error_msg

    # Step 2: Build the expense item
    expense_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    expense_item = {
        "expense_id": expense_id,
        "user_id": user_id or "default",          # Tag expense with owner
        "title": str(data["title"]).strip(),
        "amount": Decimal(str(data["amount"])),
        "category": str(data["category"]).strip(),
        "date": str(data["date"]).strip(),
        "created_at": now,
        "notes": str(data.get("notes", "")).strip(),
    }

    # Step 3: Save to DynamoDB
    db.put_item(expense_item)
    logger.info(f"New expense created: {expense_id} for user: {user_id}")

    # Step 4: Return serialized (float, not Decimal)
    return _serialize_decimals(expense_item), ""


# ─────────────────────────────────────────────────────────────────────────────
# READ ALL
# ─────────────────────────────────────────────────────────────────────────────

def get_all_expenses(user_id: str = None) -> list[dict]:
    """
    Retrieve all expenses for a specific user, sorted by date (newest first).

    Args:
        user_id (str): Filter to only return this user's expenses.

    Returns:
        list[dict]: List of expense dicts with Decimal → float conversion.
    """
    raw_items = db.scan_all_items()

    # Convert Decimals
    expenses = [_serialize_decimals(item) for item in raw_items]

    # Filter by user_id if provided
    if user_id:
        expenses = [e for e in expenses if e.get("user_id") == user_id]

    # Sort by date descending
    expenses.sort(key=lambda x: x.get("date", ""), reverse=True)

    logger.info(f"Returning {len(expenses)} expenses for user: {user_id}")
    return expenses


# ─────────────────────────────────────────────────────────────────────────────
# READ ONE
# ─────────────────────────────────────────────────────────────────────────────

def get_expense_by_id(expense_id: str) -> tuple[dict, str]:
    """
    Retrieve a single expense by its ID.

    Args:
        expense_id (str): The expense's unique identifier.

    Returns:
        tuple[dict, str]: (expense_dict, error_message)
    """
    item = db.get_item(expense_id)
    if not item:
        return {}, f"Expense with ID '{expense_id}' not found."
    return _serialize_decimals(item), ""


# ─────────────────────────────────────────────────────────────────────────────
# UPDATE
# ─────────────────────────────────────────────────────────────────────────────

def update_expense(expense_id: str, data: dict) -> tuple[dict, str]:
    """
    Update an existing expense's fields.

    Only the fields provided in `data` will be updated.
    Other fields remain unchanged (handled by db_service.update_item).

    Args:
        expense_id (str): The expense to update.
        data (dict): Fields to update with their new values.

    Returns:
        tuple[dict, str]: (updated_expense_dict, error_message)
    """
    # Validate that the expense actually exists first
    existing, err = get_expense_by_id(expense_id)
    if err:
        return {}, err

    # Validate the update data (partial — not all fields required)
    is_valid, error_msg = _validate_expense_data(data, require_all=False)
    if not is_valid:
        return {}, error_msg

    # Build the updates dict (only include provided fields)
    updates = {}
    allowed_fields = ["title", "amount", "category", "date", "notes"]

    for field in allowed_fields:
        if field in data:
            if field == "amount":
                updates[field] = Decimal(str(data[field]))
            else:
                updates[field] = str(data[field]).strip()

    # Add an "updated_at" timestamp
    updates["updated_at"] = datetime.utcnow().isoformat()

    updated_item = db.update_item(expense_id, updates)
    logger.info(f"Expense updated: {expense_id}")

    return _serialize_decimals(updated_item), ""


# ─────────────────────────────────────────────────────────────────────────────
# DELETE
# ─────────────────────────────────────────────────────────────────────────────

def delete_expense(expense_id: str, user_id: str = None) -> tuple[bool, str]:
    """
    Delete an expense by its ID, verifying ownership.

    Args:
        expense_id (str): The expense to delete.
        user_id (str): The requesting user — must match expense owner.

    Returns:
        tuple[bool, str]: (success, error_message)
    """
    # Verify existence before attempting delete
    existing, err = get_expense_by_id(expense_id)
    if err:
        return False, err

    # Ownership check: only delete if the expense belongs to this user
    # (Expenses without user_id are legacy — allow delete for any user)
    if user_id and existing.get("user_id") and existing.get("user_id") != user_id:
        return False, "You do not have permission to delete this expense."

    db.delete_item(expense_id)
    logger.info(f"Expense deleted: {expense_id} by user: {user_id}")
    return True, ""


# ─────────────────────────────────────────────────────────────────────────────
# STATISTICS & SUMMARIES
# ─────────────────────────────────────────────────────────────────────────────

def get_summary(user_id: str = None) -> dict:
    """
    Calculate total and per-category summary for a user's expenses.

    Args:
        user_id (str): Filter expenses to this user only.
    """
    expenses = get_all_expenses(user_id=user_id)

    total = 0.0
    by_category = defaultdict(float)
    monthly = defaultdict(float)

    now = datetime.utcnow()
    current_month_key = now.strftime("%Y-%m")
    current_month_name = now.strftime("%B %Y")

    for expense in expenses:
        amount = float(expense.get("amount", 0))
        category = expense.get("category", "Other")
        date_str = expense.get("date", "")

        total += amount
        by_category[category] += amount

        if len(date_str) >= 7:
            month_key = date_str[:7]
            monthly[month_key] += amount

    current_month_total = monthly.get(current_month_key, 0.0)

    summary = {
        "total": round(total, 2),
        "count": len(expenses),
        "by_category": {k: round(v, 2) for k, v in sorted(by_category.items())},
        "monthly": {k: round(v, 2) for k, v in sorted(monthly.items(), reverse=True)},
        "current_month_total": round(current_month_total, 2),
        "current_month_name": current_month_name,
    }

    logger.info(f"Summary calculated: total={total:.2f}, count={len(expenses)}")
    return summary
