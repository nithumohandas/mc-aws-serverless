import base64
import json
import os
import uuid
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Key, Attr

ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")

s3 = boto3.client("s3", endpoint_url=ENDPOINT)
dynamodb = boto3.resource("dynamodb", endpoint_url=ENDPOINT)

TABLE_NAME = "ImagesTable"
BUCKET_NAME = "image-bucket"

table = dynamodb.Table(TABLE_NAME)


def lambda_handler(event, context):
    http_method = event['httpMethod']
    path = event['path']
    print(f"EVENT IS >>>>>>>>>>>>>>>>>>>>>>>> {http_method} >>>>>>>>>>>>>>>>>>>>> {path} >>>>>>>>>>>>>>>>>>>>> {event}")

    try:
        if http_method == 'POST' and path == '/upload':
            return upload_image(event)
        elif http_method == 'GET' and path == '/images':
            return list_images(event)
        elif http_method == 'GET' and '/images/' in path:
            return get_image(event)
        elif http_method == 'DELETE' and '/images/' in path:
            return delete_image(event)
    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}

def response(status, body):
    return {
        "statusCode": status,
        "body": json.dumps(body)
    }


def upload_image(event):
    body = event.get("body", "")
    body = json.loads(body)
    image_bytes = base64.b64decode(body["image"])
    metadata = body["metadata"]
    print(f"metadata >>>>>>>>>>>>>>>>>{metadata}")

    image_id = str(uuid.uuid4())
    s3_key = f"{metadata['user_id']}/{image_id}"
    print(f"S3Key >>>>>>>>>>>>>>>>>>>>{s3_key}")

    s3.put_object(
        Bucket=BUCKET_NAME,
        Key=s3_key,
        Body=image_bytes,
        ContentType=metadata.get("content_type", "image/jpeg")
    )

    item = {
        "image_id": image_id,
        "user_id": metadata["user_id"],
        "created_at": datetime.utcnow().isoformat(),
        "s3_bucket": BUCKET_NAME,
        "s3_key": s3_key,
        "content_type": metadata.get("content_type"),
        "tags": metadata.get("tags", []),
        "description": metadata.get("description", ""),
        "status": "ACTIVE"
    }

    table.put_item(Item=item)
    print(item)
    return response(201, item)


def list_images(event):
    params = event.get("queryStringParameters") or {}
    user_id = params.get("user_id")
    tag = params.get("tag")

    if user_id:
        result = table.query(
            IndexName="UserIndex",
            KeyConditionExpression=Key("user_id").eq(user_id)
        )
    elif tag:
        result = table.scan(
            FilterExpression=Attr("tags").contains(tag)
        )
    else:
        result = table.scan()

    return response(200, result["Items"])


def get_image(event):
    image_id = event["pathParameters"]["id"]
    item = table.get_item(Key={"image_id": image_id}).get("Item")

    if not item:
        return response(404, {"message": "Not found"})

    obj = s3.get_object(Bucket=item["s3_bucket"], Key=item["s3_key"])
    encoded = base64.b64encode(obj["Body"].read()).decode()

    return response(200, {
        "image": encoded,
        "metadata": item
    })


def delete_image(event):
    image_id = event["pathParameters"]["id"]

    item = table.get_item(Key={"image_id": image_id}).get("Item")
    if not item:
        return response(404, {"message": "Not found"})

    s3.delete_object(Bucket=item["s3_bucket"], Key=item["s3_key"])
    table.delete_item(Key={"image_id": image_id})

    return response(204, {})
