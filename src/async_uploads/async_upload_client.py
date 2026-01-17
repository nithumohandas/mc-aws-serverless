"""
Client script for uploading large files to the queue-based upload system
This shows how a user would interact with the async upload API
"""

import os
import time
import requests
from typing import Callable, Optional


class AsyncFileUploader:
    def __init__(self, api_base_url='http://localhost:5000'):
        """
        Initialize the async file uploader client

        Args:
            api_base_url: Base URL of the upload API server
        """
        self.api_base_url = api_base_url

    def upload_file_chunked(self, file_path: str, s3_key: Optional[str] = None,
                            chunk_size: int = 10 * 1024 * 1024,
                            progress_callback: Optional[Callable] = None):
        """
        Upload a file in chunks to the async upload system

        Args:
            file_path: Path to the file to upload
            s3_key: Desired S3 key (optional, defaults to filename)
            chunk_size: Size of each chunk in bytes (default 10MB)
            progress_callback: Optional callback function(stage, progress, message)

        Returns:
            str: Job ID for tracking the upload
        """
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        if not s3_key:
            s3_key = f'uploads/{filename}'

        print(f"Uploading {filename} ({file_size / (1024 ** 3):.2f} GB)")

        # Step 1: Initiate upload session
        if progress_callback:
            progress_callback('initiating', 0, 'Initiating upload session...')

        response = requests.post(
            f'{self.api_base_url}/upload/initiate',
            json={
                'filename': filename,
                'file_size': file_size,
                's3_key': s3_key
            }
        )
        response.raise_for_status()

        data = response.json()
        job_id = data['job_id']
        upload_url = f"{self.api_base_url}{data['upload_url']}"

        print(f"Upload session initiated. Job ID: {job_id}")

        # Step 2: Upload file in chunks
        total_chunks = (file_size + chunk_size - 1) // chunk_size

        with open(file_path, 'rb') as f:
            chunk_number = 1

            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                # Upload chunk
                files = {'chunk': ('chunk', chunk)}
                data = {
                    'chunk_number': chunk_number,
                    'total_chunks': total_chunks
                }

                try:
                    response = requests.post(upload_url, files=files, data=data)
                    response.raise_for_status()
                except requests.RequestException as e:
                    print(f"Error uploading chunk {chunk_number}: {e}")
                    raise

                # Update progress
                upload_progress = (chunk_number / total_chunks) * 100
                message = f'Uploading chunk {chunk_number}/{total_chunks}'

                if progress_callback:
                    progress_callback('uploading', upload_progress, message)
                else:
                    print(f"{message} ({upload_progress:.1f}%)")

                chunk_number += 1

        print(f"\n✓ All chunks uploaded successfully!")
        print(f"Upload queued for S3 processing. Job ID: {job_id}")

        return job_id

    def upload_file_direct(self, file_path: str, s3_key: Optional[str] = None):
        """
        Upload file directly in a single request (for smaller files)

        Args:
            file_path: Path to the file
            s3_key: Desired S3 key (optional)

        Returns:
            str: Job ID for tracking
        """
        filename = os.path.basename(file_path)

        if not s3_key:
            s3_key = f'uploads/{filename}'

        print(f"Uploading {filename} directly...")

        with open(file_path, 'rb') as f:
            files = {'file': (filename, f)}
            data = {'s3_key': s3_key}

            response = requests.post(
                f'{self.api_base_url}/upload/direct',
                files=files,
                data=data
            )
            response.raise_for_status()

        result = response.json()
        job_id = result['job_id']

        print(f"✓ Upload queued. Job ID: {job_id}")
        return job_id

    def track_upload(self, job_id: str, poll_interval: int = 5,
                     progress_callback: Optional[Callable] = None):
        """
        Track the progress of an upload job

        Args:
            job_id: Job ID to track
            poll_interval: Seconds between status checks
            progress_callback: Optional callback function(stage, progress, message)

        Returns:
            dict: Final job status
        """
        print(f"\nTracking upload progress for job: {job_id}")
        print("=" * 60)

        while True:
            try:
                response = requests.get(
                    f'{self.api_base_url}/upload/status/{job_id}'
                )
                response.raise_for_status()

                status_data = response.json()
                status = status_data['status']
                progress = status_data.get('progress', 0)

                message = f"Status: {status.upper()} | Progress: {progress:.1f}%"

                if progress_callback:
                    progress_callback('processing', progress, message)
                else:
                    print(message)

                # Check if completed or failed
                if status == 'completed':
                    print("\n✓ Upload completed successfully!")
                    if 'metadata' in status_data:
                        print(f"  Location: {status_data['metadata']['location']}")
                        print(f"  ETag: {status_data['metadata']['etag']}")
                    return status_data

                elif status == 'failed':
                    print("\n✗ Upload failed!")
                    if 'metadata' in status_data:
                        print(f"  Error: {status_data['metadata']['error']}")
                    return status_data

                # Still processing, wait and poll again
                time.sleep(poll_interval)

            except requests.RequestException as e:
                print(f"Error checking status: {e}")
                time.sleep(poll_interval)

    def upload_and_wait(self, file_path: str, s3_key: Optional[str] = None,
                        chunk_size: int = 10 * 1024 * 1024,
                        poll_interval: int = 5):
        """
        Convenience method: upload file and wait for completion

        Args:
            file_path: Path to the file
            s3_key: Desired S3 key (optional)
            chunk_size: Chunk size for upload
            poll_interval: Status polling interval

        Returns:
            dict: Final job status
        """
        # Upload file
        job_id = self.upload_file_chunked(
            file_path=file_path,
            s3_key=s3_key,
            chunk_size=chunk_size
        )

        # Track progress
        return self.track_upload(job_id, poll_interval)


# ============================================================================
# Example Usage
# ============================================================================

def main():
    # Initialize uploader
    uploader = AsyncFileUploader(api_base_url='http://localhost:5000')

    # Example 1: Upload with custom progress callback
    def my_progress_callback(stage, progress, message):
        """Custom progress handler"""
        print(f"[{stage.upper()}] {progress:.1f}% - {message}")

    job_id = uploader.upload_file_chunked(
        file_path='/path/to/large/video.mp4',
        s3_key='videos/my-video.mp4',
        chunk_size=20 * 1024 * 1024,  # 20MB chunks
        progress_callback=my_progress_callback
    )

    # User can now close the application - upload continues in background
    print("\nYou can safely close this window now.")
    print("The upload will continue in the background.")
    print(f"To check status later, use job ID: {job_id}")

    # Example 2: Upload and wait for completion
    print("\n" + "=" * 60)
    print("Example 2: Upload and wait")
    print("=" * 60)

    result = uploader.upload_and_wait(
        file_path='/path/to/large/archive.zip',
        s3_key='archives/data-archive.zip',
        chunk_size=50 * 1024 * 1024,  # 50MB chunks
        poll_interval=3
    )

    if result['status'] == 'completed':
        print(f"\n🎉 Success! File uploaded to: {result['metadata']['location']}")

    # Example 3: Check status of existing job
    print("\n" + "=" * 60)
    print("Example 3: Check existing job")
    print("=" * 60)

    existing_job_id = "upload_1234567890_myfile.zip"
    status = uploader.track_upload(existing_job_id, poll_interval=5)


if __name__ == '__main__':
    main()