"""
notification_service.py - Notification & Alert Service

This module handles budget alerts and spending notifications.
It provides helper functions that can be called from routes
to check if the user is close to or over budget limits.

Currently implemented:
    - Budget threshold alerts (configurable per category)
    - Monthly spending warnings

Future extensions (not implemented):
    - Email notifications via AWS SES
    - SMS alerts via AWS SNS
    - Webhook integrations
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT MONTHLY BUDGET LIMITS (in USD)
# ─────────────────────────────────────────────────────────────────────────────
# These are example defaults. In a production app these would be
# stored per-user in DynamoDB and editable from the UI.

DEFAULT_BUDGETS = {
    "Food & Dining": 500.0,
    "Transportation": 200.0,
    "Shopping": 300.0,
    "Entertainment": 150.0,
    "Health & Medical": 200.0,
    "Housing & Rent": 1500.0,
    "Utilities": 200.0,
    "Education": 300.0,
    "Travel": 500.0,
    "Personal Care": 100.0,
    "Subscriptions": 50.0,
    "Other": 200.0,
}

# Alert when spending reaches this percentage of the budget
ALERT_THRESHOLD_PERCENT = 80  # 80%


def check_budget_alerts(summary: dict) -> list[dict]:
    """
    Compare current monthly spending against budget limits
    and return a list of alert messages for any categories
    that are at or over the threshold.

    Args:
        summary (dict): The summary dict returned by expense_service.get_summary().
                        Must contain "by_category" key.

    Returns:
        list[dict]: List of alert dicts, each containing:
                    - category (str)
                    - spent (float)
                    - budget (float)
                    - percent (float)
                    - level (str): "warning" | "danger"
                    - message (str)

    Example:
        [
            {
                "category": "Food & Dining",
                "spent": 430.0,
                "budget": 500.0,
                "percent": 86.0,
                "level": "warning",
                "message": "Food & Dining: 86% of budget used ($430 / $500)"
            }
        ]
    """
    alerts = []
    by_category = summary.get("by_category", {})

    for category, budget_limit in DEFAULT_BUDGETS.items():
        spent = by_category.get(category, 0.0)

        if budget_limit <= 0:
            continue  # Skip categories with no budget set

        percent_used = (spent / budget_limit) * 100

        if percent_used >= 100:
            # Over budget — DANGER
            alerts.append({
                "category": category,
                "spent": round(spent, 2),
                "budget": budget_limit,
                "percent": round(percent_used, 1),
                "level": "danger",
                "message": (
                    f"⚠️ {category}: OVER BUDGET! "
                    f"Spent ${spent:.2f} of ${budget_limit:.2f}"
                ),
            })
            logger.warning(f"OVER BUDGET: {category} — ${spent:.2f} / ${budget_limit:.2f}")

        elif percent_used >= ALERT_THRESHOLD_PERCENT:
            # Near budget limit — WARNING
            alerts.append({
                "category": category,
                "spent": round(spent, 2),
                "budget": budget_limit,
                "percent": round(percent_used, 1),
                "level": "warning",
                "message": (
                    f"🔔 {category}: {percent_used:.0f}% of budget used "
                    f"(${spent:.2f} / ${budget_limit:.2f})"
                ),
            })
            logger.info(f"Budget warning: {category} — {percent_used:.0f}%")

    return alerts


def get_spending_trend(monthly_data: dict) -> dict:
    """
    Analyze the monthly spending trend to determine if spending
    is increasing or decreasing compared to the previous month.

    Args:
        monthly_data (dict): Dict of {"YYYY-MM": amount} pairs
                             from expense_service.get_summary().

    Returns:
        dict: {
            "trend": "up" | "down" | "stable" | "no_data",
            "current_month": float,
            "previous_month": float,
            "change_percent": float,
            "message": str,
        }
    """
    if not monthly_data:
        return {
            "trend": "no_data",
            "current_month": 0.0,
            "previous_month": 0.0,
            "change_percent": 0.0,
            "message": "Not enough data to calculate trend.",
        }

    # Sort months descending to get the two most recent
    sorted_months = sorted(monthly_data.keys(), reverse=True)

    current_amount = monthly_data[sorted_months[0]] if len(sorted_months) >= 1 else 0.0
    previous_amount = monthly_data[sorted_months[1]] if len(sorted_months) >= 2 else 0.0

    if previous_amount == 0:
        change_percent = 0.0
        trend = "stable"
    else:
        change_percent = ((current_amount - previous_amount) / previous_amount) * 100
        if change_percent > 5:
            trend = "up"
        elif change_percent < -5:
            trend = "down"
        else:
            trend = "stable"

    # Human-readable message
    if trend == "up":
        message = f"📈 Spending up {change_percent:.1f}% from last month."
    elif trend == "down":
        message = f"📉 Spending down {abs(change_percent):.1f}% from last month."
    else:
        message = "📊 Spending is similar to last month."

    return {
        "trend": trend,
        "current_month": round(current_amount, 2),
        "previous_month": round(previous_amount, 2),
        "change_percent": round(change_percent, 1),
        "message": message,
    }
