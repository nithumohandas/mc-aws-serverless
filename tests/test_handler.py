import json
import base64
from unittest.mock import MagicMock

from handler import (
    lambda_handler,
    upload_image,
    list_images,
    get_image,
    delete_image
)

def test_upload_image_success(
    upload_event,
    mock_s3,
    mock_table,
    fixed_uuid,
    fixed_datetime
):
    response = upload_image(upload_event)

    assert response["statusCode"] == 201

    body = json.loads(response["body"])
    assert body["image_id"] == "fixed-uuid"
    assert body["user_id"] == "user1"
    assert body["tags"] == ["nature"]

    mock_s3.put_object.assert_called_once()
    mock_table.put_item.assert_called_once()

def test_list_images_by_user(mock_table):
    mock_table.query.return_value = {
        "Items": [{"image_id": "1"}]
    }

    event = {
        "httpMethod": "GET",
        "path": "/images",
        "queryStringParameters": {"user_id": "user1"}
    }

    response = list_images(event)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == [{"image_id": "1"}]

    mock_table.query.assert_called_once()

def test_list_images_by_tag(mock_table):
    mock_table.scan.return_value = {
        "Items": [{"image_id": "2"}]
    }

    event = {
        "httpMethod": "GET",
        "path": "/images",
        "queryStringParameters": {"tag": "nature"}
    }

    response = list_images(event)

    assert response["statusCode"] == 200
    mock_table.scan.assert_called_once()

def test_get_image_success(mock_s3, mock_table):
    mock_table.get_item.return_value = {
        "Item": {
            "image_id": "1",
            "s3_bucket": "image-bucket",
            "s3_key": "user1/1"
        }
    }

    mock_s3.get_object.return_value = {
        "Body": MagicMock(read=lambda: b"image-bytes")
    }

    event = {
        "httpMethod": "GET",
        "path": "/images/1",
        "pathParameters": {"id": "1"}
    }

    response = get_image(event)

    body = json.loads(response["body"])
    assert base64.b64decode(body["image"]) == b"image-bytes"

def test_get_image_not_found(mock_table):
    mock_table.get_item.return_value = {}

    event = {
        "httpMethod": "GET",
        "path": "/images/404",
        "pathParameters": {"id": "404"}
    }

    response = get_image(event)
    assert response["statusCode"] == 404

def test_delete_image_success(mock_s3, mock_table):
    mock_table.get_item.return_value = {
        "Item": {
            "image_id": "1",
            "s3_bucket": "image-bucket",
            "s3_key": "user1/1"
        }
    }

    event = {
        "httpMethod": "DELETE",
        "path": "/images/1",
        "pathParameters": {"id": "1"}
    }

    response = delete_image(event)

    assert response["statusCode"] == 204
    mock_s3.delete_object.assert_called_once()
    mock_table.delete_item.assert_called_once()

def test_delete_image_not_found(mock_table):
    mock_table.get_item.return_value = {}

    event = {
        "httpMethod": "DELETE",
        "path": "/images/404",
        "pathParameters": {"id": "404"}
    }

    response = delete_image(event)
    assert response["statusCode"] == 404

def test_lambda_handler_routes(upload_event, mock_s3, mock_table, fixed_uuid, fixed_datetime):
    response = lambda_handler(upload_event, None)
    assert response["statusCode"] == 201
