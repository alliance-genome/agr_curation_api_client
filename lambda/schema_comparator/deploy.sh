#!/bin/bash
# Deploy schema comparator Lambda function
#
# Usage: ./deploy.sh [--create|--update]
#   --create  Create a new Lambda function
#   --update  Update existing Lambda function code (default)
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Access to Alliance Genome AWS account (100225593120)
#
# Note: psycopg2 is provided via a Lambda Layer, not bundled in the deployment package.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Alliance Genome AWS Account Configuration
# These are resource identifiers, not secrets
AWS_ACCOUNT_ID="100225593120"
AWS_REGION="us-east-1"

# Lambda Configuration
FUNCTION_NAME="agr-schema-comparator"
ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/agr-schema-comparator-role"
HANDLER="handler.lambda_handler"
RUNTIME="python3.11"
TIMEOUT=300
MEMORY=256

# Lambda Layer for psycopg2 (created separately, see README)
PSYCOPG2_LAYER_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:layer:psycopg2-py311:2"

# VPC Configuration - private subnets with NAT Gateway access
VPC_SUBNET_IDS="subnet-0d4703177afb1797d,subnet-04019d42d5c9e6fb9,subnet-049778993fb504a7c"
VPC_SECURITY_GROUP="sg-03a0d277f55da5161"

# SNS Topic for notifications
SNS_TOPIC_ARN="arn:aws:sns:${AWS_REGION}:${AWS_ACCOUNT_ID}:agr-schema-change-notifications"

# Parse arguments
ACTION="update"
if [[ "$1" == "--create" ]]; then
    ACTION="create"
elif [[ "$1" == "--update" ]]; then
    ACTION="update"
fi

echo "=== AGR Schema Comparator Lambda Deployment ==="
echo "Action: $ACTION"
echo "Function: $FUNCTION_NAME"
echo "Region: $AWS_REGION"
echo ""

# Package the function
echo "Step 1: Packaging Lambda function..."
rm -rf package lambda.zip 2>/dev/null || true
mkdir package

# Copy source files
cp handler.py schema_diff.py package/

# Install boto3 only (psycopg2 comes from layer)
pip install boto3 -t package/ --quiet

# Create zip
cd package
zip -r ../lambda.zip . --quiet
cd ..

echo "  Package created: lambda.zip ($(du -h lambda.zip | cut -f1))"

if [[ "$ACTION" == "create" ]]; then
    echo ""
    echo "Step 2: Creating new Lambda function..."

    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime "$RUNTIME" \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --timeout "$TIMEOUT" \
        --memory-size "$MEMORY" \
        --zip-file fileb://lambda.zip \
        --layers "$PSYCOPG2_LAYER_ARN" \
        --vpc-config "SubnetIds=$VPC_SUBNET_IDS,SecurityGroupIds=$VPC_SECURITY_GROUP" \
        --environment "Variables={SNS_TOPIC_ARN=$SNS_TOPIC_ARN}" \
        --region "$AWS_REGION" \
        --output json

    echo "  Lambda function created successfully!"

else
    echo ""
    echo "Step 2: Updating Lambda function code..."

    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file fileb://lambda.zip \
        --region "$AWS_REGION" \
        --output json | jq '{FunctionName, LastModified, CodeSize}'

    echo "  Lambda function updated successfully!"
fi

# Cleanup
echo ""
echo "Step 3: Cleaning up..."
rm -rf package lambda.zip

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "To test the function:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME --payload '{\"skip_notification\": true}' --cli-binary-format raw-in-base64-out response.json --region $AWS_REGION && cat response.json"
echo ""
echo "Note: psycopg2 is provided via Lambda Layer: $PSYCOPG2_LAYER_ARN"
echo ""
echo "To recreate the psycopg2 layer if needed:"
echo "  pip install --platform manylinux2014_x86_64 --target layer/python --only-binary=:all: --python-version 3.11 psycopg2-binary"
echo "  cd layer && zip -r ../psycopg2-layer.zip python/ && cd .."
echo "  aws lambda publish-layer-version --layer-name psycopg2-py311 --zip-file fileb://psycopg2-layer.zip --compatible-runtimes python3.11 --region $AWS_REGION"
