"""
notification_service.py - Notification & Alert Service

Handles budget alerts and spending notifications.
- Budget threshold alerts (configurable per category)
- Monthly spending warnings
- Real email notifications via AWS SNS
"""

import logging
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT MONTHLY BUDGET LIMITS (in USD/INR)
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_BUDGETS = {
    "Food & Dining":    500.0,
    "Transportation":   200.0,
    "Shopping":         300.0,
    "Entertainment":    150.0,
    "Health & Medical": 200.0,
    "Housing & Rent":  1500.0,
    "Utilities":        200.0,
    "Education":        300.0,
    "Travel":           500.0,
    "Personal Care":    100.0,
    "Subscriptions":     50.0,
    "Other":            200.0,
}

# Alert when spending reaches this percentage of the budget
ALERT_THRESHOLD_PERCENT = 80  # 80%


# ─────────────────────────────────────────────────────────────────────────────
# AWS SNS CLIENT
# ─────────────────────────────────────────────────────────────────────────────

def _get_sns_client():
    """Return a boto3 SNS client using credentials from Config."""
    return boto3.client(
        "sns",
        region_name=Config.AWS_REGION,
        aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
    )


def send_sns_email(subject: str, message: str) -> bool:
    """
    Publish a notification to the AWS SNS topic defined in Config.

    This sends an email to all subscribers of the SNS topic
    (set SNS_TOPIC_ARN and subscribe your email in the AWS Console).

    Args:
        subject (str): Email subject line (max 100 chars).
        message (str): Email body text.

    Returns:
        bool: True if published successfully, False otherwise.
    """
    topic_arn = Config.SNS_TOPIC_ARN
    if not topic_arn:
        logger.warning(
            "SNS_TOPIC_ARN not set in .env — skipping email notification. "
            "Set SNS_TOPIC_ARN to enable real email alerts."
        )
        return False

    try:
        sns = _get_sns_client()
        response = sns.publish(
            TopicArn=topic_arn,
            Subject=subject[:100],   # SNS subject limit
            Message=message,
        )
        msg_id = response.get("MessageId", "unknown")
        logger.info(f"SNS notification sent → MessageId: {msg_id} | Subject: {subject}")
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error(f"SNS publish failed [{error_code}]: {e.response['Error']['Message']}")
        return False
    except Exception as e:
        logger.error(f"SNS unexpected error: {e}")
        return False


def send_budget_alert_email(alerts: list, username: str = "User") -> bool:
    """
    Send a consolidated budget alert email via SNS when any category is
    at or over its budget threshold.

    Args:
        alerts (list): List of alert dicts from check_budget_alerts().
        username (str): Username to personalise the email.

    Returns:
        bool: True if email was sent, False if skipped or failed.
    """
    if not alerts:
        return False

    category_exceeded_alerts = [a for a in alerts if a["level"] == "category_exceeded"]
    warning_alerts           = [a for a in alerts if a["level"] == "warning"]

    if not category_exceeded_alerts and not warning_alerts:
        return False

    # Build subject line
    # Note: "OVER BUDGET" is reserved for overall monthly budget (see send_overspend_email).
    # Per-category overages use a softer subject.
    if category_exceeded_alerts:
        subject = (
            f"🔔 Budget Alert: {len(category_exceeded_alerts)} "
            f"categor{'y' if len(category_exceeded_alerts)==1 else 'ies'} "
            f"exceeded its limit"
        )
    else:
        subject = f"⚠️ Budget Warning: {len(warning_alerts)} categor{'y' if len(warning_alerts)==1 else 'ies'} near limit"

    # Build email body
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"Hello {username},",
        "",
        f"Your Expense Tracker has detected the following budget alerts as of {now}:",
        "",
    ]

    if category_exceeded_alerts:
        lines.append("🟠 CATEGORY LIMIT EXCEEDED:")
        for a in category_exceeded_alerts:
            lines.append(
                f"  • {a['category']}: spent ₹{a['spent']:.2f} of ₹{a['budget']:.2f} "
                f"({a['percent']:.1f}%) — category limit exceeded"
            )
        lines.append("")

    if warning_alerts:
        lines.append("🟡 NEAR CATEGORY LIMIT:")
        for a in warning_alerts:
            lines.append(
                f"  • {a['category']}: spent ₹{a['spent']:.2f} of ₹{a['budget']:.2f} "
                f"({a['percent']:.1f}%)"
            )
        lines.append("")

    lines += [
        "Please review your expenses and adjust your spending if needed.",
        "",
        "— AWS FinStack Expense Tracker",
    ]

    message = "\n".join(lines)
    return send_sns_email(subject, message)


def send_overspend_email(username: str, forecast: float, budget: float) -> bool:
    """
    Send an overspending forecast warning email.

    Args:
        username (str): The user's name.
        forecast (float): Projected month-end spend.
        budget (float): The user's monthly budget.

    Returns:
        bool: True if sent successfully.
    """
    if budget <= 0 or forecast <= budget:
        return False

    overage = forecast - budget
    subject = f"📈 Forecast Alert: You may exceed your monthly budget by ₹{overage:.2f}"
    message = (
        f"Hello {username},\n\n"
        f"Based on your current spending rate, you are projected to exceed "
        f"your monthly budget this month.\n\n"
        f"  • Your Budget:       ₹{budget:.2f}\n"
        f"  • Projected Spend:   ₹{forecast:.2f}\n"
        f"  • Expected Overage:  ₹{overage:.2f}\n\n"
        f"Consider reducing discretionary spending to stay on track.\n\n"
        f"— AWS FinStack Expense Tracker"
    )
    return send_sns_email(subject, message)


# ─────────────────────────────────────────────────────────────────────────────
# ALERT LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def check_budget_alerts(summary: dict) -> list[dict]:
    """
    Compare current monthly spending against budget limits
    and return a list of alert messages for any categories
    that are at or over the threshold.

    Args:
        summary (dict): The summary dict from expense_service.get_summary().

    Returns:
        list[dict]: List of alert dicts with keys:
            category, spent, budget, percent, level, message
    """
    alerts = []
    by_category = summary.get("by_category", {})

    for category, budget_limit in DEFAULT_BUDGETS.items():
        spent = by_category.get(category, 0.0)

        if budget_limit <= 0:
            continue

        percent_used = (spent / budget_limit) * 100

        if percent_used >= 100:
            alerts.append({
                "category": category,
                "spent":    round(spent, 2),
                "budget":   budget_limit,
                "percent":  round(percent_used, 1),
                "level":    "category_exceeded",
                "message":  (
                    f"🟠 {category}: Category limit exceeded "
                    f"(₹{spent:.2f} / ₹{budget_limit:.2f})"
                ),
            })
            logger.warning(f"Category limit exceeded: {category} — ₹{spent:.2f} / ₹{budget_limit:.2f}")

        elif percent_used >= ALERT_THRESHOLD_PERCENT:
            alerts.append({
                "category": category,
                "spent":    round(spent, 2),
                "budget":   budget_limit,
                "percent":  round(percent_used, 1),
                "level":    "warning",
                "message":  (
                    f"🔔 {category}: {percent_used:.0f}% of budget used "
                    f"(₹{spent:.2f} / ₹{budget_limit:.2f})"
                ),
            })
            logger.info(f"Budget warning: {category} — {percent_used:.0f}%")

    return alerts


def get_spending_trend(monthly_data: dict) -> dict:
    """
    Analyze the monthly spending trend — is spending going up or down?

    Args:
        monthly_data (dict): { "YYYY-MM": amount } from get_summary().

    Returns:
        dict: { trend, current_month, previous_month, change_percent, message }
    """
    if not monthly_data:
        return {
            "trend": "no_data",
            "current_month": 0.0,
            "previous_month": 0.0,
            "change_percent": 0.0,
            "message": "Not enough data to calculate trend.",
        }

    sorted_months = sorted(monthly_data.keys(), reverse=True)

    current_amount  = monthly_data[sorted_months[0]] if len(sorted_months) >= 1 else 0.0
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

    if trend == "up":
        message = f"📈 Spending up {change_percent:.1f}% from last month."
    elif trend == "down":
        message = f"📉 Spending down {abs(change_percent):.1f}% from last month."
    else:
        message = "📊 Spending is similar to last month."

    return {
        "trend":          trend,
        "current_month":  round(current_amount, 2),
        "previous_month": round(previous_amount, 2),
        "change_percent": round(change_percent, 1),
        "message":        message,
    }
