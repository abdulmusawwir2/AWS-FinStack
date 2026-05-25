"""
db_service.py - DynamoDB Database Service

This module handles all direct communication with AWS DynamoDB.
It is the ONLY file that talks to DynamoDB directly — all other
services must call this module to read/write data.

Architecture:
    Routes → expense_service.py → db_service.py → DynamoDB

Responsibilities:
    - Create a DynamoDB client using boto3
    - CRUD operations on the DynamoDB table
    - Return raw DynamoDB items to the service layer
"""

import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from config import Config

# Set up module-level logger
logger = logging.getLogger(__name__)


class DynamoDBService:
    """
    Service class for DynamoDB operations.
    Each method maps to one DynamoDB API operation.
    """

    def __init__(self):
        """
        Initialize the DynamoDB resource using credentials from Config.
        boto3 automatically uses the credentials provided here.
        """
        try:
            # Create a DynamoDB resource (higher-level than client)
            self.dynamodb = boto3.resource(
                "dynamodb",
                region_name=Config.AWS_REGION,
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            )
            # Get a reference to the specific table
            self.table = self.dynamodb.Table(Config.DYNAMODB_TABLE_NAME)
            logger.info(
                f"DynamoDB connected → table: {Config.DYNAMODB_TABLE_NAME}"
            )
        except NoCredentialsError:
            logger.error("AWS credentials not found. Check your .env file.")
            raise

    # ─────────────────────────────────────────────────────────────────
    # CREATE
    # ─────────────────────────────────────────────────────────────────
    def put_item(self, item: dict) -> dict:
        """
        Insert a new item (expense) into DynamoDB.

        Args:
            item (dict): The expense dictionary to store.
                         Must include 'expense_id' as the partition key.

        Returns:
            dict: The DynamoDB response metadata.

        Raises:
            ClientError: If DynamoDB rejects the request.
        """
        try:
            response = self.table.put_item(Item=item)
            logger.info(f"Item saved → expense_id: {item.get('expense_id')}")
            return response
        except ClientError as e:
            logger.error(f"put_item failed: {e.response['Error']['Message']}")
            raise

    # ─────────────────────────────────────────────────────────────────
    # READ ALL
    # ─────────────────────────────────────────────────────────────────
    def scan_all_items(self) -> list:
        """
        Retrieve ALL items from the DynamoDB table using a Scan.

        NOTE: Scan reads every item in the table. For small datasets
        (< a few thousand expenses) this is fine. For large tables,
        consider using Query with a Global Secondary Index instead.

        Returns:
            list: A list of expense dictionaries.
        """
        try:
            response = self.table.scan()
            items = response.get("Items", [])

            # Handle pagination: DynamoDB returns max 1 MB per scan call
            while "LastEvaluatedKey" in response:
                response = self.table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items.extend(response.get("Items", []))

            logger.info(f"Scanned {len(items)} items from DynamoDB.")
            return items
        except ClientError as e:
            logger.error(f"scan_all_items failed: {e.response['Error']['Message']}")
            raise

    # ─────────────────────────────────────────────────────────────────
    # READ ONE
    # ─────────────────────────────────────────────────────────────────
    def get_item(self, expense_id: str) -> dict | None:
        """
        Retrieve a single expense by its primary key (expense_id).

        Args:
            expense_id (str): The unique identifier of the expense.

        Returns:
            dict | None: The expense item, or None if not found.
        """
        try:
            response = self.table.get_item(Key={"expense_id": expense_id})
            item = response.get("Item")
            if item:
                logger.info(f"Item retrieved → expense_id: {expense_id}")
            else:
                logger.warning(f"Item not found → expense_id: {expense_id}")
            return item
        except ClientError as e:
            logger.error(f"get_item failed: {e.response['Error']['Message']}")
            raise

    # ─────────────────────────────────────────────────────────────────
    # UPDATE
    # ─────────────────────────────────────────────────────────────────
    def update_item(self, expense_id: str, updates: dict) -> dict:
        """
        Update specific fields of an existing expense.

        This method dynamically builds the UpdateExpression so only
        the provided fields are modified — other fields stay intact.

        Args:
            expense_id (str): The expense to update.
            updates (dict): Dictionary of field names and new values.
                            Example: {"title": "Lunch", "amount": "12.50"}

        Returns:
            dict: The updated item's attributes.
        """
        try:
            # Build UpdateExpression dynamically from the updates dict
            # Example output: "SET #title = :title, #amount = :amount"
            update_parts = []
            expression_attr_names = {}   # alias for reserved keywords
            expression_attr_values = {}  # placeholder values

            for key, value in updates.items():
                placeholder_name = f"#{key}"       # e.g.  #title
                placeholder_val = f":{key}"        # e.g.  :title
                update_parts.append(f"{placeholder_name} = {placeholder_val}")
                expression_attr_names[placeholder_name] = key
                expression_attr_values[placeholder_val] = value

            update_expression = "SET " + ", ".join(update_parts)

            response = self.table.update_item(
                Key={"expense_id": expense_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attr_names,
                ExpressionAttributeValues=expression_attr_values,
                ReturnValues="ALL_NEW",  # Return the full updated item
            )
            logger.info(f"Item updated → expense_id: {expense_id}")
            return response.get("Attributes", {})
        except ClientError as e:
            logger.error(f"update_item failed: {e.response['Error']['Message']}")
            raise

    # ─────────────────────────────────────────────────────────────────
    # DELETE
    # ─────────────────────────────────────────────────────────────────
    def delete_item(self, expense_id: str) -> dict:
        """
        Delete an expense from DynamoDB by its primary key.

        Args:
            expense_id (str): The expense to delete.

        Returns:
            dict: DynamoDB response metadata.
        """
        try:
            response = self.table.delete_item(Key={"expense_id": expense_id})
            logger.info(f"Item deleted → expense_id: {expense_id}")
            return response
        except ClientError as e:
            logger.error(f"delete_item failed: {e.response['Error']['Message']}")
            raise

    # ─────────────────────────────────────────────────────────────────
    # TABLE HEALTH CHECK
    # ─────────────────────────────────────────────────────────────────
    def check_table_exists(self) -> bool:
        """
        Verify that the DynamoDB table exists and is ACTIVE.

        Returns:
            bool: True if table is ACTIVE, False otherwise.
        """
        try:
            self.table.load()  # Triggers a DescribeTable API call
            status = self.table.table_status
            logger.info(f"Table status: {status}")
            return status == "ACTIVE"
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                logger.error(
                    f"Table '{Config.DYNAMODB_TABLE_NAME}' does not exist. "
                    "Run setup_aws.py to create it."
                )
            else:
                logger.error(f"check_table_exists failed: {e}")
            return False


class BudgetDynamoDBService:
    """
    Service class for persisting per-user monthly budgets in DynamoDB.

    Table schema:
        Partition Key: username (String)
        Attributes:
            - username (str)
            - monthly_budget (Decimal)
            - updated_at (str)
    """

    def __init__(self):
        try:
            dynamodb = boto3.resource(
                "dynamodb",
                region_name=Config.AWS_REGION,
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
            )
            self.table = dynamodb.Table(Config.BUDGET_TABLE_NAME)
            logger.info(f"BudgetDB connected → table: {Config.BUDGET_TABLE_NAME}")
        except NoCredentialsError:
            logger.error("AWS credentials not found for BudgetDynamoDBService.")
            raise

    def get_budget(self, username: str) -> float:
        """
        Retrieve the stored monthly budget for a user.

        Args:
            username (str): The user's login name.

        Returns:
            float: The stored budget amount, or 0.0 if not set.
        """
        try:
            response = self.table.get_item(Key={"username": username})
            item = response.get("Item")
            if item:
                logger.info(f"Budget retrieved for user: {username}")
                return float(item.get("monthly_budget", 0.0))
            logger.info(f"No budget found for user: {username}, returning 0.0")
            return 0.0
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                logger.warning(
                    f"Budget table '{Config.BUDGET_TABLE_NAME}' not found. "
                    "Run setup_aws.py to create it."
                )
                return 0.0
            logger.error(f"get_budget failed: {e.response['Error']['Message']}")
            return 0.0
        except Exception as e:
            logger.error(f"get_budget unexpected error: {e}")
            return 0.0

    def set_budget(self, username: str, monthly_budget: float) -> bool:
        """
        Persist the monthly budget for a user in DynamoDB.

        Args:
            username (str): The user's login name.
            monthly_budget (float): The budget amount to store.

        Returns:
            bool: True if saved successfully, False otherwise.
        """
        from decimal import Decimal
        from datetime import datetime
        try:
            self.table.put_item(Item={
                "username":       username,
                "monthly_budget": Decimal(str(monthly_budget)),
                "updated_at":     datetime.utcnow().isoformat(),
            })
            logger.info(f"Budget saved for user: {username} → {monthly_budget:.2f}")
            return True
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "ResourceNotFoundException":
                logger.warning(
                    f"Budget table '{Config.BUDGET_TABLE_NAME}' not found. "
                    "Run setup_aws.py to create it."
                )
                return False
            logger.error(f"set_budget failed: {e.response['Error']['Message']}")
            return False
        except Exception as e:
            logger.error(f"set_budget unexpected error: {e}")
            return False
