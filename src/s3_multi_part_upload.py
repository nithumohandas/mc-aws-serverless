import boto3
import os
import math
from botocore.exceptions import ClientError


class S3MultipartUploader:
    def __init__(self, bucket_name, aws_access_key=None, aws_secret_key=None, region='us-east-1'):
        """
        Initialize S3 client for multipart uploads

        Args:
            bucket_name: S3 bucket name
            aws_access_key: AWS access key (optional, uses default credentials if None)
            aws_secret_key: AWS secret key (optional, uses default credentials if None)
            region: AWS region
        """
        if aws_access_key and aws_secret_key:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=region
            )
        else:
            # Uses default credentials from AWS CLI or environment
            self.s3_client = boto3.client('s3', region_name=region)

        self.bucket_name = bucket_name

    def upload_large_file(self, file_path, s3_key, chunk_size=10 * 1024 * 1024,
                          max_retries=3, callback=None):
        """
        Upload a large file to S3 using multipart upload

        Args:
            file_path: Path to the file to upload
            s3_key: S3 object key (path in S3)
            chunk_size: Size of each chunk in bytes (default 10MB)
            max_retries: Maximum retry attempts for each chunk
            callback: Optional callback function(part_num, total_parts, bytes_uploaded)

        Returns:
            dict: Upload result with location and etag
        """
        file_size = os.path.getsize(file_path)
        total_parts = math.ceil(file_size / chunk_size)

        print(f"Starting multipart upload for {file_path}")
        print(f"File size: {file_size / (1024 ** 3):.2f} GB")
        print(f"Chunk size: {chunk_size / (1024 ** 2):.2f} MB")
        print(f"Total parts: {total_parts}")

        try:
            # Step 1: Initiate multipart upload
            response = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            upload_id = response['UploadId']
            print(f"Upload ID: {upload_id}")

            # Step 2: Upload parts
            parts = []
            bytes_uploaded = 0

            with open(file_path, 'rb') as f:
                for part_num in range(1, total_parts + 1):
                    # Read chunk
                    chunk_data = f.read(chunk_size)

                    # Upload part with retry logic
                    for attempt in range(max_retries):
                        try:
                            part_response = self.s3_client.upload_part(
                                Bucket=self.bucket_name,
                                Key=s3_key,
                                PartNumber=part_num,
                                UploadId=upload_id,
                                Body=chunk_data
                            )

                            parts.append({
                                'PartNumber': part_num,
                                'ETag': part_response['ETag']
                            })

                            bytes_uploaded += len(chunk_data)
                            progress = (bytes_uploaded / file_size) * 100
                            print(f"Part {part_num}/{total_parts} uploaded - {progress:.1f}% complete")

                            # Call callback if provided
                            if callback:
                                callback(part_num, total_parts, bytes_uploaded)

                            break  # Success, exit retry loop

                        except ClientError as e:
                            if attempt < max_retries - 1:
                                print(f"Retry {attempt + 1}/{max_retries} for part {part_num}")
                            else:
                                raise Exception(f"Failed to upload part {part_num} after {max_retries} attempts") from e

            # Step 3: Complete multipart upload
            result = self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )

            print(f"Upload complete! Location: {result['Location']}")
            return result

        except Exception as e:
            # Abort multipart upload on failure
            print(f"Upload failed: {str(e)}")
            try:
                self.s3_client.abort_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    UploadId=upload_id
                )
                print("Multipart upload aborted")
            except:
                pass
            raise

    def resume_upload(self, file_path, s3_key, upload_id, uploaded_parts,
                      chunk_size=10 * 1024 * 1024):
        """
        Resume a failed multipart upload

        Args:
            file_path: Path to the file
            s3_key: S3 object key
            upload_id: Previous upload ID
            uploaded_parts: List of already uploaded parts
            chunk_size: Size of each chunk
        """
        file_size = os.path.getsize(file_path)
        total_parts = math.ceil(file_size / chunk_size)
        uploaded_part_nums = {part['PartNumber'] for part in uploaded_parts}

        parts = list(uploaded_parts)

        print(f"Resuming upload from part {len(uploaded_parts) + 1}")

        with open(file_path, 'rb') as f:
            for part_num in range(1, total_parts + 1):
                chunk_data = f.read(chunk_size)

                if part_num in uploaded_part_nums:
                    continue  # Skip already uploaded parts

                part_response = self.s3_client.upload_part(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    PartNumber=part_num,
                    UploadId=upload_id,
                    Body=chunk_data
                )

                parts.append({
                    'PartNumber': part_num,
                    'ETag': part_response['ETag']
                })

                print(f"Part {part_num}/{total_parts} uploaded")

        # Complete upload
        result = self.s3_client.complete_multipart_upload(
            Bucket=self.bucket_name,
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={'Parts': parts}
        )

        return result


# Example usage
if __name__ == "__main__":
    # Initialize uploader
    uploader = S3MultipartUploader(
        bucket_name='my-large-files-bucket',
        region='us-east-1'
    )


    # Define callback for progress tracking
    def progress_callback(part_num, total_parts, bytes_uploaded):
        """Custom progress tracking"""
        print(f"  → Uploaded {bytes_uploaded / (1024 ** 3):.2f} GB so far")


    # Upload large file
    try:
        result = uploader.upload_large_file(
            file_path='/path/to/large/file.zip',
            s3_key='uploads/large-file.zip',
            chunk_size=50 * 1024 * 1024,  # 50MB chunks
            callback=progress_callback
        )
        print(f"Success! ETag: {result['ETag']}")
    except Exception as e:
        print(f"Upload failed: {e}")