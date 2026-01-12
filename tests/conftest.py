import base64
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_s3():
    with patch("handler.s3") as mock:
        yield mock


@pytest.fixture
def mock_table():
    with patch("handler.table") as mock:
        yield mock


@pytest.fixture
def fixed_uuid():
    with patch("handler.uuid.uuid4", return_value="fixed-uuid"):
        yield


@pytest.fixture
def fixed_datetime():
    fixed_time = datetime(2024, 1, 1, 0, 0, 0)
    with patch("handler.datetime") as mock_dt:
        mock_dt.utcnow.return_value = fixed_time
        yield


@pytest.fixture
def base64_image():
    return base64.b64encode(b"fake-image-bytes").decode()


@pytest.fixture
def upload_event(base64_image):
    return {
        "httpMethod": "POST",
        "path": "/upload",
        "body": json.dumps({
            "image": base64_image,
            "metadata": {
                "user_id": "user1",
                "content_type": "image/png",
                "tags": ["nature"],
                "description": "sunset"
            }
        })
    }
