#!/bin/bash

echo "Setting up LocalStack resources..."

# Configuration
REGION="us-east-1"
BUCKET_NAME="image-bucket"
TABLE_NAME="ImagesTable"
LAMBDA_FUNCTION_NAME="image-handler"
API_NAME="image-api"

# Create S3 bucket
echo "Creating S3 bucket: $BUCKET_NAME"
awslocal s3 mb s3://$BUCKET_NAME

# Create DynamoDB table with GSIs
echo "Creating DynamoDB table: $TABLE_NAME"

awslocal dynamodb create-table \
  --table-name $TABLE_NAME \
  --attribute-definitions \
      AttributeName=image_id,AttributeType=S \
      AttributeName=user_id,AttributeType=S \
  --key-schema \
      AttributeName=image_id,KeyType=HASH \
  --global-secondary-indexes \
      "[
        {
          \"IndexName\": \"UserIndex\",
          \"KeySchema\": [
            {\"AttributeName\":\"user_id\",\"KeyType\":\"HASH\"}
          ],
          \"Projection\": {\"ProjectionType\":\"ALL\"},
          \"ProvisionedThroughput\": {
            \"ReadCapacityUnits\":5,
            \"WriteCapacityUnits\":5
          }
        }
      ]" \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --region $REGION


# Wait for table to be active
echo "Waiting for DynamoDB table to be active..."
awslocal dynamodb wait table-exists --table-name $TABLE_NAME --region $REGION

# Create Lambda function ZIP
echo "Creating Lambda function package..."
# Create deployment package
zip -j function.zip ./src/handler.py

# Create IAM role for Lambda
echo "Creating IAM role..."
awslocal iam create-role \
    --role-name lambda-execution-role \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' 2>/dev/null || echo "Role already exists"

awslocal iam attach-role-policy \
    --role-name lambda-execution-role \
    --policy-arn arn:aws:iam::aws:policy/AWSLambdaExecute 2>/dev/null || true

# Create Lambda function
echo "Creating Lambda function: $LAMBDA_FUNCTION_NAME"
awslocal lambda create-function \
    --function-name $LAMBDA_FUNCTION_NAME \
    --runtime python3.11 \
    --role arn:aws:iam::000000000000:role/lambda-execution-role \
    --handler handler.lambda_handler \
    --zip-file fileb://function.zip \
    --environment Variables="{AWS_ENDPOINT_URL=http://localstack:4566}" \
    --timeout 30 \
    --memory-size 2048 \
    --region $REGION

# Wait for Lambda to be active
echo "Waiting for Lambda to be active..."
awslocal lambda wait function-active --function-name $LAMBDA_FUNCTION_NAME --region $REGION

# Create REST API Gateway
echo "Creating API Gateway..."
API_ID=$(awslocal apigateway create-rest-api \
    --name $API_NAME \
    --description "Image Management API" \
    --region $REGION \
    --query 'id' \
    --output text)

echo "API ID: $API_ID"

# Get root resource ID
ROOT_ID=$(awslocal apigateway get-resources \
    --rest-api-id $API_ID \
    --region $REGION \
    --query 'items[0].id' \
    --output text)

# Create /upload resource
echo "Creating /upload endpoint..."
UPLOAD_RESOURCE_ID=$(awslocal apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $ROOT_ID \
    --path-part upload \
    --region $REGION \
    --query 'id' \
    --output text)

# Set up POST /upload
awslocal apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $UPLOAD_RESOURCE_ID \
    --http-method POST \
    --authorization-type NONE \
    --region $REGION

awslocal apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $UPLOAD_RESOURCE_ID \
    --http-method POST \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$LAMBDA_FUNCTION_NAME/invocations" \
    --region $REGION

# Create /images resource
echo "Creating /images endpoint..."
IMAGES_RESOURCE_ID=$(awslocal apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $ROOT_ID \
    --path-part images \
    --region $REGION \
    --query 'id' \
    --output text)

# Set up GET /images
awslocal apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $IMAGES_RESOURCE_ID \
    --http-method GET \
    --authorization-type NONE \
    --region $REGION

awslocal apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $IMAGES_RESOURCE_ID \
    --http-method GET \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$LAMBDA_FUNCTION_NAME/invocations" \
    --region $REGION

# Create /images/{id} resource
echo "Creating /images/{id} endpoint..."
IMAGE_ID_RESOURCE_ID=$(awslocal apigateway create-resource \
    --rest-api-id $API_ID \
    --parent-id $IMAGES_RESOURCE_ID \
    --path-part '{id}' \
    --region $REGION \
    --query 'id' \
    --output text)

# Set up GET /images/{id}
awslocal apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $IMAGE_ID_RESOURCE_ID \
    --http-method GET \
    --authorization-type NONE \
    --region $REGION

awslocal apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $IMAGE_ID_RESOURCE_ID \
    --http-method GET \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$LAMBDA_FUNCTION_NAME/invocations" \
    --region $REGION

# Set up DELETE /images/{id}
awslocal apigateway put-method \
    --rest-api-id $API_ID \
    --resource-id $IMAGE_ID_RESOURCE_ID \
    --http-method DELETE \
    --authorization-type NONE \
    --region $REGION

awslocal apigateway put-integration \
    --rest-api-id $API_ID \
    --resource-id $IMAGE_ID_RESOURCE_ID \
    --http-method DELETE \
    --type AWS_PROXY \
    --integration-http-method POST \
    --uri "arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/arn:aws:lambda:$REGION:000000000000:function:$LAMBDA_FUNCTION_NAME/invocations" \
    --region $REGION

# Deploy API
echo "Deploying API to 'dev' stage..."
awslocal apigateway create-deployment \
    --rest-api-id $API_ID \
    --stage-name dev \
    --region $REGION

# Grant API Gateway permission to invoke Lambda
awslocal lambda add-permission \
    --function-name $LAMBDA_FUNCTION_NAME \
    --statement-id apigateway-invoke \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGION:000000000000:$API_ID/*/*" \
    --region $REGION 2>/dev/null || echo "Permission already exists"

echo ""
echo "=========================================="
echo "LocalStack Image API Setup Complete!"
echo "=========================================="
echo "API Gateway URL: http://localhost:4566/restapis/$API_ID/dev/_user_request_"
echo "S3 Bucket: $BUCKET_NAME"
echo "DynamoDB Table: $TABLE_NAME"
echo "Lambda Function: $LAMBDA_FUNCTION_NAME"
echo ""
echo "Available Endpoints:"
echo "  POST   /upload           - Upload an image"
echo "  GET    /images           - List all images (supports ?user_id= and ?tag= filters)"
echo "  GET    /images/{id}      - Get specific image with metadata"
echo "  DELETE /images/{id}      - Delete an image"
echo ""
echo "Example API calls:"
echo ""
echo "1. Upload an image:"
echo "   curl -X POST http://localhost:4566/restapis/$API_ID/dev/_user_request_/upload \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{
  \"image\": \"'"\\$(base64 -w 0 image.jpg)"'\",
  \"metadata\": {
    \"user_id\": \"user123\",
    \"content_type\": \"image/jpeg\",
    \"tags\": [\"vacation\", \"beach\"],
    \"description\": \"Beach sunset photo\"
  }
}'"
echo ""
echo "2. List all images:"
echo "   curl http://localhost:4566/restapis/$API_ID/dev/_user_request_/images"
echo ""
echo "3. List images by user:"
echo "   curl http://localhost:4566/restapis/$API_ID/dev/_user_request_/images?user_id=user123"
echo ""
echo "4. List images by tag:"
echo "   curl http://localhost:4566/restapis/$API_ID/dev/_user_request_/images?tag=vacation"
echo ""
echo "5. Get specific image:"
echo "   curl http://localhost:4566/restapis/$API_ID/dev/_user_request_/images/{image-id}"
echo ""
echo "6. Delete an image:"
echo "   curl -X DELETE http://localhost:4566/restapis/$API_ID/dev/_user_request_/images/{image-id}"
echo ""
echo "=========================================="