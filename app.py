"""
app.py - Flask Application Entry Point

This is the main file that starts the Expense Tracker web application.
It defines all Flask routes and wires them to the service layer.

Architecture:
    Browser / Frontend (HTML + JS)
        ↓ HTTP Requests
    app.py (Flask Routes)
        ↓ Function calls
    expense_service.py (Business Logic)
        ↓ Function calls
    db_service.py (DynamoDB Operations)
        ↓ AWS boto3 API
    AWS DynamoDB

How to run locally:
    python app.py

How to run in production (via Gunicorn):
    gunicorn -w 4 -b 0.0.0.0:5000 app:app
"""

import logging
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from config import Config
from services import expense_service, notification_service
from services import user_service

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING SETUP
# Configure logging to output to console with timestamp and log level.
# In production, this would write to a file or a centralized logging service.
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# FLASK APP INITIALIZATION
# ─────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.from_object(Config)  # Load settings from config.py


# ─────────────────────────────────────────────────────────────────────────────
# AUTH: Login Required Decorator
# Protects routes — redirects to /login if the user is not authenticated.
# ─────────────────────────────────────────────────────────────────────────────
def login_required(f):
    """
    Decorator that ensures a user is logged in before accessing a route.
    - For page routes: redirects to /login
    - For API routes (/api/*): returns a 401 JSON response (fixes fetch() delete bug)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            # Return JSON 401 for API routes so fetch() gets proper response
            if request.path.startswith("/api/"):
                return error_response("Authentication required. Please log in.", 401)
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


def current_user() -> str:
    """Return the logged-in username from the session."""
    return session.get("username", "default")


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: Standard JSON Response Builder
# ─────────────────────────────────────────────────────────────────────────────

def success_response(data, message="Success", status_code=200):
    """
    Build a standardized success JSON response.

    Args:
        data: The payload to return (dict, list, etc.)
        message (str): Human-readable success message.
        status_code (int): HTTP status code.

    Returns:
        Flask Response object with JSON body.
    """
    return jsonify({"success": True, "message": message, "data": data}), status_code


def error_response(message, status_code=400):
    """
    Build a standardized error JSON response.

    Args:
        message (str): Human-readable error description.
        status_code (int): HTTP status code (400, 404, 500, etc.)

    Returns:
        Flask Response object with JSON body.
    """
    return jsonify({"success": False, "message": message, "data": None}), status_code


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: LOGIN PAGE
# GET  /login — Show the login form
# POST /login — Validate credentials against DynamoDB Users table
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Handle login. On GET, render the login page.
    On POST, validate credentials stored in DynamoDB.
    """
    if session.get("logged_in"):
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        is_valid, err = user_service.verify_user(username, password)
        if is_valid:
            session["logged_in"] = True
            session["username"] = username.lower()
            logger.info(f"User '{username}' logged in successfully.")
            return redirect(url_for("index"))
        else:
            error = err or "Invalid username or password."
            logger.warning(f"Failed login attempt for username: '{username}'")

    return render_template("login.html", error=error)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: SIGNUP PAGE
# GET  /signup — Show the registration form
# POST /signup — Create a new account in DynamoDB
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/signup", methods=["GET", "POST"])
def signup():
    """Handle new user registration."""
    if session.get("logged_in"):
        return redirect(url_for("index"))

    error = None
    success_msg = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm  = request.form.get("confirm", "").strip()

        if password != confirm:
            error = "Passwords do not match."
        else:
            ok, err = user_service.register_user(username, password)
            if ok:
                logger.info(f"New user registered: {username}")
                return redirect(url_for("login") + "?registered=1")
            else:
                error = err

    return render_template("login.html", error=error, signup_mode=True)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: LOGOUT
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/logout")
def logout():
    """Clear the user session and redirect to the login page."""
    username = session.get("username", "unknown")
    session.clear()
    logger.info(f"User '{username}' logged out.")
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: HOME PAGE
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    """Render the main dashboard page."""
    logger.info("Dashboard page requested.")
    return render_template(
        "index.html",
        categories=Config.EXPENSE_CATEGORIES,
        username=session.get("username", "User"),
    )



# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: GET ALL EXPENSES
# GET /api/expenses
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/expenses", methods=["GET"])
@login_required
def get_expenses():
    """Retrieve all expenses from DynamoDB for the current user."""
    try:
        user_id = current_user()
        expenses = expense_service.get_all_expenses(user_id=user_id)

        # Optional: filter by category
        category_filter = request.args.get("category")
        if category_filter:
            expenses = [e for e in expenses if e.get("category", "").lower() == category_filter.lower()]

        # Optional: filter by month (YYYY-MM)
        month_filter = request.args.get("month")
        if month_filter:
            expenses = [e for e in expenses if e.get("date", "").startswith(month_filter)]

        logger.info(f"Returning {len(expenses)} expenses for user: {user_id}")
        return success_response(expenses, f"Found {len(expenses)} expense(s).")

    except Exception as e:
        logger.error(f"Error in get_expenses: {e}")
        return error_response(f"Failed to retrieve expenses: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: GET SINGLE EXPENSE
# GET /api/expenses/<expense_id>
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/expenses/<expense_id>", methods=["GET"])
@login_required
def get_expense(expense_id):
    """Retrieve a single expense by its unique ID."""
    try:
        expense, error = expense_service.get_expense_by_id(expense_id)
        if error:
            return error_response(error, 404)
        return success_response(expense, "Expense retrieved successfully.")
    except Exception as e:
        logger.error(f"Error in get_expense({expense_id}): {e}")
        return error_response(f"Failed to retrieve expense: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: CREATE EXPENSE
# POST /api/expenses
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/expenses", methods=["POST"])
@login_required
def create_expense():
    """Create a new expense tagged with the current user's ID."""
    try:
        data = request.get_json()
        if not data:
            return error_response("Request body must be valid JSON.", 400)

        user_id = current_user()
        expense, error = expense_service.create_expense(data, user_id=user_id)
        if error:
            return error_response(error, 400)

        logger.info(f"New expense created: {expense.get('expense_id')}")
        return success_response(expense, "Expense created successfully.", 201)

    except Exception as e:
        logger.error(f"Error in create_expense: {e}")
        return error_response(f"Failed to create expense: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: UPDATE EXPENSE
# PUT /api/expenses/<expense_id>
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/expenses/<expense_id>", methods=["PUT"])
@login_required
def update_expense(expense_id):
    """Update an existing expense's fields."""
    try:
        data = request.get_json()
        if not data:
            return error_response("Request body must be valid JSON.", 400)

        updated_expense, error = expense_service.update_expense(expense_id, data)
        if error:
            status = 404 if "not found" in error.lower() else 400
            return error_response(error, status)

        return success_response(updated_expense, "Expense updated successfully.")

    except Exception as e:
        logger.error(f"Error in update_expense({expense_id}): {e}")
        return error_response(f"Failed to update expense: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: DELETE EXPENSE
# DELETE /api/expenses/<expense_id>
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/expenses/<expense_id>", methods=["DELETE"])
@login_required
def delete_expense(expense_id):
    """Delete an expense by its unique ID (must belong to current user)."""
    try:
        user_id = current_user()
        success, error = expense_service.delete_expense(expense_id, user_id=user_id)
        if not success:
            status = 403 if "permission" in error.lower() else 404
            return error_response(error, status)
        return success_response(None, "Expense deleted successfully.")
    except Exception as e:
        logger.error(f"Error in delete_expense({expense_id}): {e}")
        return error_response(f"Failed to delete expense: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: GET SUMMARY & STATISTICS
# GET /api/expenses/summary
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/summary", methods=["GET"])
@login_required
def get_summary():
    """Get expense summary statistics for the current user."""
    try:
        user_id = current_user()
        summary = expense_service.get_summary(user_id=user_id)
        alerts = notification_service.check_budget_alerts(summary)
        trend = notification_service.get_spending_trend(summary.get("monthly", {}))
        full_summary = {**summary, "alerts": alerts, "trend": trend}
        return success_response(full_summary, "Summary calculated successfully.")

    except Exception as e:
        logger.error(f"Error in get_summary: {e}")
        return error_response(f"Failed to calculate summary: {str(e)}", 500)


# ─────────────────────────────────────────────────────────────────────────────
# ROUTE: HEALTH CHECK
# GET /api/health
# Used by load balancers and uptime monitors to verify the app is running.
# ─────────────────────────────────────────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health_check():
    """
    Health check endpoint.

    Returns:
        JSON with app status and environment info.
    """
    from services.db_service import DynamoDBService
    db = DynamoDBService()
    table_ok = db.check_table_exists()

    return success_response(
        {
            "status": "healthy" if table_ok else "degraded",
            "dynamo_table": Config.DYNAMODB_TABLE_NAME,
            "table_connected": table_ok,
            "environment": Config.ENV,
        },
        "Health check complete.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# ERROR HANDLERS
# These catch unhandled Flask exceptions and return clean JSON responses.
# ─────────────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    """Handle 404 Not Found errors."""
    return error_response("The requested resource was not found.", 404)


@app.errorhandler(405)
def method_not_allowed(e):
    """Handle 405 Method Not Allowed errors."""
    return error_response("HTTP method not allowed for this endpoint.", 405)


@app.errorhandler(500)
def internal_error(e):
    """Handle 500 Internal Server Error."""
    logger.error(f"Internal server error: {e}")
    return error_response("An internal server error occurred.", 500)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# This block runs only when executing: python app.py
# It does NOT run when Gunicorn imports the app for production.
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting Expense Tracker Flask application...")
    logger.info(f"Environment: {Config.ENV}")
    logger.info(f"DynamoDB Table: {Config.DYNAMODB_TABLE_NAME}")
    logger.info(f"AWS Region: {Config.AWS_REGION}")
    logger.info(f"Server running at http://{Config.HOST}:{Config.PORT}")

    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
    )
