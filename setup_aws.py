# -*- coding: utf-8 -*-
"""
setup_aws.py - AWS DynamoDB Setup Script

Run this script ONCE before starting the application.
It will:
    1. Connect to AWS using your credentials from .env
    2. Check if the DynamoDB table already exists
    3. Create the table if it doesn't exist
    4. Wait until the table is ACTIVE before exiting

Usage:
    python setup_aws.py

Requirements:
    - AWS credentials set in your .env file
    - boto3 installed: pip install boto3
    - Your IAM user must have DynamoDB permissions:
        - dynamodb:CreateTable
        - dynamodb:DescribeTable
        - dynamodb:ListTables
"""

import boto3
import time
import sys
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from config import Config

# Load .env variables
load_dotenv()


def create_users_table():
    """
    Create the ExpenseTrackerUsers DynamoDB table.
    Stores registered user accounts with bcrypt-hashed passwords.

    Table Schema:
        - Partition Key: username (String)
    """
    print("\n[...] Setting up Users table...")
    try:
        dynamodb = boto3.client(
            "dynamodb",
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
        )
        existing_tables = dynamodb.list_tables()["TableNames"]
        if "ExpenseTrackerUsers" in existing_tables:
            print("[OK] Users table 'ExpenseTrackerUsers' already exists!")
            return True

        dynamodb.create_table(
            TableName="ExpenseTrackerUsers",
            KeySchema=[{"AttributeName": "username", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "username", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            Tags=[{"Key": "Project", "Value": "ExpenseTracker"}],
        )
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(TableName="ExpenseTrackerUsers", WaiterConfig={"Delay": 5, "MaxAttempts": 20})
        print("[OK] Users table 'ExpenseTrackerUsers' is now ACTIVE!")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceInUseException":
            print("[OK] Users table already exists (concurrent creation).")
            return True
        print(f"[ERROR] Error creating users table: {e.response['Error']['Message']}")
        return False


def create_dynamodb_table():
    """
    Create the ExpenseTracker DynamoDB table with the correct schema.

    Table Schema:
        - Partition Key: expense_id (String)
        - No sort key needed (each expense has a unique UUID)
        - Billing: PAY_PER_REQUEST (no capacity planning needed)

    PAY_PER_REQUEST (On-Demand) means:
        - You pay per API call, not for reserved capacity
        - Great for small apps and internship projects
        - No need to estimate read/write capacity units

    Returns:
        bool: True if table created or already exists, False on error.
    """
    print("=" * 60)
    print("  AWS DynamoDB Setup - Expense Tracker")
    print("=" * 60)
    print(f"  Region:     {Config.AWS_REGION}")
    print(f"  Table Name: {Config.DYNAMODB_TABLE_NAME}")
    print("=" * 60)

    # ── Step 1: Connect to DynamoDB ──────────────────────────────────
    try:
        dynamodb = boto3.client(
            "dynamodb",
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
        )
        print("\n[OK] Connected to AWS DynamoDB successfully.")
    except NoCredentialsError:
        print("\n[ERROR] AWS credentials not found!")
        print("   Please check your .env file and set:")
        print("   AWS_ACCESS_KEY_ID=your_key")
        print("   AWS_SECRET_ACCESS_KEY=your_secret")
        return False

    # ── Step 2: Check if table already exists ────────────────────────
    try:
        existing_tables = dynamodb.list_tables()["TableNames"]
        if Config.DYNAMODB_TABLE_NAME in existing_tables:
            print(f"\n[OK] Table '{Config.DYNAMODB_TABLE_NAME}' already exists!")
            print("   No action needed. You can start the app now.")
            return True
    except ClientError as e:
        print(f"\n[ERROR] Error listing tables: {e.response['Error']['Message']}")
        return False

    # ── Step 3: Create the table ─────────────────────────────────────
    print(f"\n[...] Creating table '{Config.DYNAMODB_TABLE_NAME}'...")

    try:
        table = dynamodb.create_table(
            TableName=Config.DYNAMODB_TABLE_NAME,

            # Define the key schema (primary key only)
            KeySchema=[
                {
                    "AttributeName": "expense_id",  # Partition key
                    "KeyType": "HASH",              # HASH = partition key
                },
                # No RANGE (sort) key needed for this app
            ],

            # Define the data types for key attributes only
            # Non-key attributes (title, amount, etc.) are schema-less in DynamoDB
            AttributeDefinitions=[
                {
                    "AttributeName": "expense_id",
                    "AttributeType": "S",   # S = String
                },
            ],

            # PAY_PER_REQUEST: No capacity planning needed.
            # Ideal for small to medium applications.
            BillingMode="PAY_PER_REQUEST",

            # Add tags for cost tracking in AWS billing console
            Tags=[
                {"Key": "Project", "Value": "ExpenseTracker"},
                {"Key": "Environment", "Value": "Production"},
            ],
        )

        print(f"   Table creation initiated. Waiting for it to become ACTIVE...")

        # Step 4: Wait for table to be ACTIVE
        # DynamoDB tables take a few seconds to provision.
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(
            TableName=Config.DYNAMODB_TABLE_NAME,
            WaiterConfig={
                "Delay": 5,         # Check every 5 seconds
                "MaxAttempts": 20,  # Wait up to 100 seconds total
            }
        )

        print(f"\n[OK] Table '{Config.DYNAMODB_TABLE_NAME}' is now ACTIVE!")
        print("\n   Table Details:")
        print(f"   - Partition Key: expense_id (String)")
        print(f"   - Billing Mode:  PAY_PER_REQUEST (On-Demand)")
        print(f"   - Region:        {Config.AWS_REGION}")
        print(f"\n[DONE] Setup complete! You can now run the app:")
        print(f"   python app.py\n")
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"]["Message"]

        if error_code == "ResourceInUseException":
            print(f"\n[OK] Table already exists (concurrent creation). All good!")
            return True
        elif error_code == "AccessDeniedException":
            print(f"\n[ERROR] ACCESS DENIED: Your IAM user lacks DynamoDB permissions.")
            print("   Required permissions:")
            print("   - dynamodb:CreateTable")
            print("   - dynamodb:DescribeTable")
            print("   - dynamodb:ListTables")
        else:
            print(f"\n[ERROR] Error creating table: {error_code} - {error_msg}")
        return False


def verify_credentials():
    """
    Quick check to verify AWS credentials are set and valid.
    Calls AWS STS (Security Token Service) to get the caller identity.

    Returns:
        bool: True if credentials are valid, False otherwise.
    """
    try:
        sts = boto3.client(
            "sts",
            region_name=Config.AWS_REGION,
            aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
        )
        identity = sts.get_caller_identity()
        print(f"\n[OK] AWS Identity Verified:")
        print(f"   Account: {identity['Account']}")
        print(f"   User ARN: {identity['Arn']}")
        return True
    except Exception as e:
        print(f"\n[WARN] Could not verify identity: {e}")
        print("   Proceeding anyway...")
        return True  # Don't block if STS check fails


# ── MAIN ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n")

    # Verify credentials first
    verify_credentials()

    # Create the expenses table
    success = create_dynamodb_table()

    # Create the users table
    if success:
        success = create_users_table()

    # Exit with appropriate code
    sys.exit(0 if success else 1)
