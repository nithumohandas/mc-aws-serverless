"""
Queue-Based Async Upload System
This solution uses Redis for job queuing and RQ (Redis Queue) for background processing.

Installation required:
pip install redis rq boto3 flask
"""

import os
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify
from redis import Redis
from rq import Queue
from rq.job import Job
import boto3
from botocore.exceptions import ClientError

# ============================================================================
# Configuration
# ============================================================================

UPLOAD_FOLDER = '/tmp/uploads'
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
S3_BUCKET = 'my-large-files-bucket'
CHUNK_SIZE = 50 * 1024 * 1024  # 50MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Redis and Queue
redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT)
upload_queue = Queue('uploads', connection=redis_conn)


# ============================================================================
# Background Worker Task
# ============================================================================

def upload_to_s3_background(file_path, s3_key, bucket_name, job_id):
    """
    Background task to upload file to S3 using multipart upload
    This runs in a separate worker process

    Args:
        file_path: Local path to the file
        s3_key: S3 object key
        bucket_name: S3 bucket name
        job_id: Unique job identifier for tracking
    """
    s3_client = boto3.client('s3')

    try:
        # Update job status
        update_job_status(job_id, 'processing', 0)

        file_size = os.path.getsize(file_path)

        # Initiate multipart upload
        response = s3_client.create_multipart_upload(
            Bucket=bucket_name,
            Key=s3_key
        )
        upload_id = response['UploadId']

        parts = []
        bytes_uploaded = 0
        part_num = 1

        # Upload file in chunks
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break

                # Upload part
                part_response = s3_client.upload_part(
                    Bucket=bucket_name,
                    Key=s3_key,
                    PartNumber=part_num,
                    UploadId=upload_id,
                    Body=chunk
                )

                parts.append({
                    'PartNumber': part_num,
                    'ETag': part_response['ETag']
                })

                bytes_uploaded += len(chunk)
                progress = (bytes_uploaded / file_size) * 100

                # Update progress
                update_job_status(job_id, 'processing', progress)

                part_num += 1

        # Complete multipart upload
        result = s3_client.complete_multipart_upload(
            Bucket=bucket_name,
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )

        # Clean up local file
        os.remove(file_path)

        # Update job status to completed
        update_job_status(job_id, 'completed', 100, {
            'location': result['Location'],
            'etag': result['ETag']
        })

        return {
            'status': 'success',
            'location': result['Location']
        }

    except Exception as e:
        # Abort multipart upload on failure
        try:
            s3_client.abort_multipart_upload(
                Bucket=bucket_name,
                Key=s3_key,
                UploadId=upload_id
            )
        except:
            pass

        # Update job status to failed
        update_job_status(job_id, 'failed', 0, {'error': str(e)})

        # Clean up local file
        if os.path.exists(file_path):
            os.remove(file_path)

        raise


def update_job_status(job_id, status, progress, metadata=None):
    """Update job status in Redis"""
    job_data = {
        'job_id': job_id,
        'status': status,
        'progress': progress,
        'updated_at': datetime.utcnow().isoformat()
    }
    if metadata:
        job_data['metadata'] = metadata

    redis_conn.setex(
        f'job:{job_id}',
        3600 * 24,  # Expire after 24 hours
        json.dumps(job_data)
    )


# ============================================================================
# Flask API Server
# ============================================================================

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024 * 1024  # 100GB max


@app.route('/upload/initiate', methods=['POST'])
def initiate_upload():
    """
    Initiate a chunked upload session
    Client will upload file in chunks to this endpoint
    """
    data = request.json
    filename = data.get('filename')
    file_size = data.get('file_size')
    s3_key = data.get('s3_key', f'uploads/{filename}')

    # Generate unique job ID
    job_id = f"upload_{int(time.time())}_{filename}"

    # Store upload metadata
    upload_data = {
        'job_id': job_id,
        'filename': filename,
        'file_size': file_size,
        's3_key': s3_key,
        'status': 'initiated',
        'created_at': datetime.utcnow().isoformat()
    }

    redis_conn.setex(
        f'upload:{job_id}',
        3600 * 24,
        json.dumps(upload_data)
    )

    return jsonify({
        'job_id': job_id,
        'upload_url': f'/upload/chunk/{job_id}'
    })


@app.route('/upload/chunk/<job_id>', methods=['POST'])
def upload_chunk(job_id):
    """
    Receive file chunks from client
    Chunks are appended to a temporary file
    """
    chunk = request.files.get('chunk')
    chunk_number = int(request.form.get('chunk_number'))
    total_chunks = int(request.form.get('total_chunks'))

    # Get upload metadata
    upload_data_str = redis_conn.get(f'upload:{job_id}')
    if not upload_data_str:
        return jsonify({'error': 'Upload session not found'}), 404

    upload_data = json.loads(upload_data_str)
    filename = upload_data['filename']

    # Save chunk to temporary file
    temp_file_path = os.path.join(UPLOAD_FOLDER, f'{job_id}.tmp')

    with open(temp_file_path, 'ab') as f:
        chunk.save(f)

    # If this is the last chunk, queue background upload
    if chunk_number == total_chunks:
        s3_key = upload_data['s3_key']

        # Enqueue background job
        job = upload_queue.enqueue(
            upload_to_s3_background,
            temp_file_path,
            s3_key,
            S3_BUCKET,
            job_id,
            job_timeout='4h'  # 4 hour timeout for large files
        )

        return jsonify({
            'status': 'queued',
            'job_id': job_id,
            'message': 'Upload queued for processing'
        })

    return jsonify({
        'status': 'chunk_received',
        'chunk_number': chunk_number,
        'total_chunks': total_chunks
    })


@app.route('/upload/direct', methods=['POST'])
def upload_direct():
    """
    Direct file upload endpoint (for smaller files or single-request uploads)
    Immediately queues the file for background S3 upload
    """
    file = request.files.get('file')
    s3_key = request.form.get('s3_key', f'uploads/{file.filename}')

    if not file:
        return jsonify({'error': 'No file provided'}), 400

    # Generate job ID
    job_id = f"upload_{int(time.time())}_{file.filename}"

    # Save file temporarily
    temp_file_path = os.path.join(UPLOAD_FOLDER, f'{job_id}.tmp')
    file.save(temp_file_path)

    # Enqueue background job
    job = upload_queue.enqueue(
        upload_to_s3_background,
        temp_file_path,
        s3_key,
        S3_BUCKET,
        job_id,
        job_timeout='4h'
    )

    return jsonify({
        'status': 'queued',
        'job_id': job_id,
        'message': 'File queued for upload to S3'
    }), 202


@app.route('/upload/status/<job_id>', methods=['GET'])
def get_upload_status(job_id):
    """
    Get the status of an upload job
    Client polls this endpoint to track progress
    """
    job_data_str = redis_conn.get(f'job:{job_id}')

    if not job_data_str:
        return jsonify({'error': 'Job not found'}), 404

    job_data = json.loads(job_data_str)
    return jsonify(job_data)


# ============================================================================
# Client Example
# ============================================================================

def client_upload_example():
    """
    Example client code showing how to upload a large file
    """
    import requests

    API_BASE_URL = 'http://localhost:5000'
    FILE_PATH = '/path/to/large/file.zip'
    CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks

    # Step 1: Initiate upload
    filename = os.path.basename(FILE_PATH)
    file_size = os.path.getsize(FILE_PATH)

    response = requests.post(f'{API_BASE_URL}/upload/initiate', json={
        'filename': filename,
        'file_size': file_size,
        's3_key': f'uploads/{filename}'
    })

    data = response.json()
    job_id = data['job_id']
    upload_url = f"{API_BASE_URL}{data['upload_url']}"

    print(f"Upload initiated. Job ID: {job_id}")

    # Step 2: Upload file in chunks
    with open(FILE_PATH, 'rb') as f:
        chunk_number = 1
        total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break

            files = {'chunk': chunk}
            data = {
                'chunk_number': chunk_number,
                'total_chunks': total_chunks
            }

            response = requests.post(upload_url, files=files, data=data)
            print(f"Chunk {chunk_number}/{total_chunks} uploaded")

            chunk_number += 1

    print("All chunks uploaded. Upload queued for S3 processing.")

    # Step 3: Poll for status
    while True:
        response = requests.get(f'{API_BASE_URL}/upload/status/{job_id}')
        status_data = response.json()

        print(f"Status: {status_data['status']}, Progress: {status_data['progress']:.1f}%")

        if status_data['status'] in ['completed', 'failed']:
            break

        time.sleep(5)  # Poll every 5 seconds

    if status_data['status'] == 'completed':
        print(f"Upload complete! Location: {status_data['metadata']['location']}")
    else:
        print(f"Upload failed: {status_data['metadata']['error']}")


if __name__ == '__main__':
    # Run Flask server
    app.run(host='0.0.0.0', port=5000, debug=True)

    # To run the worker process (in a separate terminal):
    # rq worker uploads --with-scheduler