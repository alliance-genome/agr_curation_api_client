# AGR Schema Comparator Lambda

This Lambda function compares database schemas between the AGR curation alpha and production databases, sending notifications when differences are detected.

## Purpose

When the alpha environment is deployed with schema changes (new tables, columns, indexes, etc.), this function detects those differences and sends an SNS notification to alert developers maintaining downstream clients like `agr_curation_api_client`.

## Architecture

```
Alpha Deployed → EventBridge → Lambda → Compare Schemas → SNS Notification
                              (alpha vs prod)
```

## Trigger

The Lambda is triggered by EventBridge when the `curation-alpha` Elastic Beanstalk environment completes an update:

```json
{
  "source": ["aws.elasticbeanstalk"],
  "detail-type": ["Elastic Beanstalk resource status change"],
  "detail": {
    "EnvironmentName": ["curation-alpha"],
    "Status": ["Environment update completed successfully."]
  }
}
```

## What it Compares

- Tables (added/removed)
- Columns (added/removed/modified types)
- Indexes (added/removed)

## AWS Resources

| Resource | ARN/Name |
|----------|----------|
| Lambda Function | `agr-schema-comparator` |
| IAM Role | `agr-schema-comparator-role` |
| SNS Topic | `agr-schema-change-notifications` |
| EventBridge Rule | `agr-schema-comparison-on-alpha-deploy` |
| Lambda Layer | `psycopg2-py311:2` |

## Deployment

```bash
# Update existing function
./deploy.sh

# Or create new function
./deploy.sh --create
```

## Manual Testing

```bash
# Test without sending notification
aws lambda invoke \
  --function-name agr-schema-comparator \
  --payload '{"skip_notification": true}' \
  --cli-binary-format raw-in-base64-out \
  response.json \
  --profile ctabone

cat response.json

# Test specific tables only
aws lambda invoke \
  --function-name agr-schema-comparator \
  --payload '{"skip_notification": true, "tables_filter": ["diseaseannotation", "gene"]}' \
  --cli-binary-format raw-in-base64-out \
  response.json \
  --profile ctabone
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `SNS_TOPIC_ARN` | ARN of SNS topic for notifications |
| `ALPHA_SECRET_NAME` | Secrets Manager name for alpha DB credentials |
| `PROD_SECRET_NAME` | Secrets Manager name for production DB credentials |

## Lambda Layer

psycopg2 is provided via a Lambda Layer (`psycopg2-py311:2`) rather than bundled in the deployment package. This is because psycopg2-binary compiled locally doesn't work on Lambda's Amazon Linux environment.

To recreate the layer:

```bash
pip install --platform manylinux2014_x86_64 --target layer/python --only-binary=:all: --python-version 3.11 psycopg2-binary
cd layer && zip -r ../psycopg2-layer.zip python/
aws lambda publish-layer-version --layer-name psycopg2-py311 --zip-file fileb://psycopg2-layer.zip --compatible-runtimes python3.11 --profile ctabone
```

## Notification Format

```json
{
  "source": "lambda-schema-comparator",
  "eventType": "CONFIRMED_SCHEMA_DRIFT",
  "comparison": {
    "base": "production",
    "target": "alpha"
  },
  "diff": {
    "added_tables": ["new_table"],
    "removed_tables": [],
    "modified_tables": {
      "existing_table": {
        "added_columns": ["new_column"]
      }
    },
    "added_indexes": ["table.idx_new"],
    "removed_indexes": []
  },
  "summary": "Human-readable report...",
  "actionRequired": "Alpha database has schema changes..."
}
```
