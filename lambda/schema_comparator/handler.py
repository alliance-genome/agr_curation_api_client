"""
Lambda function to compare database schemas between alpha and production.

Triggered by EventBridge schedule or manually invoked.
Publishes differences to SNS topic.
"""

import json
import os
import boto3
from schema_diff import compare_schemas, format_diff_report

# Configuration from environment variables
SNS_TOPIC_ARN = os.environ.get(
    "SNS_TOPIC_ARN",
    "arn:aws:sns:us-east-1:100225593120:agr-schema-change-notifications",
)
ALPHA_SECRET_NAME = os.environ.get("ALPHA_SECRET_NAME", "curation-db-readonly")
PROD_SECRET_NAME = os.environ.get(
    "PROD_SECRET_NAME", "ai-curation/db/curation-production-readonly"
)

# Database endpoints
ALPHA_HOST = "curation-db-alpha.cmnnhlso7wdi.us-east-1.rds.amazonaws.com"
PROD_HOST = "curation-db.cmnnhlso7wdi.us-east-1.rds.amazonaws.com"
DB_PORT = 5432

# SNS VPC Endpoint (Lambda in VPC requires VPC endpoint to reach SNS)
SNS_VPC_ENDPOINT_URL = os.environ.get(
    "SNS_VPC_ENDPOINT_URL",
    "https://vpce-000ad81aa19208694-veipou4n.sns.us-east-1.vpce.amazonaws.com",
)


def get_db_credentials(secret_name: str) -> dict:
    """Retrieve database credentials from Secrets Manager."""
    client = boto3.client("secretsmanager")
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response["SecretString"])


def lambda_handler(event, context):
    """
    Main Lambda handler.

    Event can optionally contain:
    - skip_notification: bool - If True, return diff without publishing to SNS
    - tables_filter: list - Only compare specific tables
    """
    print(f"Schema comparison triggered. Event: {json.dumps(event)}")

    skip_notification = event.get("skip_notification", False)
    tables_filter = event.get("tables_filter", None)

    try:
        # Get credentials
        alpha_creds = get_db_credentials(ALPHA_SECRET_NAME)
        prod_creds = get_db_credentials(PROD_SECRET_NAME)

        # Determine database names from secrets or defaults
        alpha_db = alpha_creds.get("dbname", "curation")
        prod_db = prod_creds.get("dbname", "curation")

        # Build connection configs
        alpha_config = {
            "host": ALPHA_HOST,
            "port": DB_PORT,
            "database": alpha_db,
            "user": alpha_creds.get("username"),
            "password": alpha_creds.get("password"),
        }

        prod_config = {
            "host": PROD_HOST,
            "port": DB_PORT,
            "database": prod_db,
            "user": prod_creds.get("username"),
            "password": prod_creds.get("password"),
        }

        # Compare schemas
        diff = compare_schemas(alpha_config, prod_config, tables_filter=tables_filter)

        # Check if there are any differences
        has_changes = (
            diff.get("added_tables")
            or diff.get("removed_tables")
            or diff.get("modified_tables")
            or diff.get("added_indexes")
            or diff.get("removed_indexes")
        )

        if has_changes and not skip_notification:
            # Format and send notification
            report = format_diff_report(diff)

            # Build human-readable email message
            message_lines = [
                "AGR Schema Drift Detected",
                "=" * 50,
                "",
                "The alpha database has schema changes that differ from production.",
                "",
                report,
                "",
                "ACTION REQUIRED",
                "-" * 50,
                "Review these changes and update agr_curation_api_client if needed.",
                "",
                "This notification was sent automatically by the",
                "agr-schema-comparator Lambda function.",
            ]

            sns = boto3.client("sns", endpoint_url=SNS_VPC_ENDPOINT_URL)
            sns.publish(
                TopicArn=SNS_TOPIC_ARN,
                Subject="[AGR] Schema Drift Detected: Alpha vs Production",
                Message="\n".join(message_lines),
            )

            print("Schema drift detected and notification sent")
        elif has_changes:
            print("Schema drift detected (notification skipped)")
        else:
            print("No schema differences found")

        return {
            "statusCode": 200,
            "body": {"hasChanges": has_changes, "diff": diff if has_changes else None},
        }

    except Exception as e:
        print(f"Error comparing schemas: {str(e)}")
        raise
