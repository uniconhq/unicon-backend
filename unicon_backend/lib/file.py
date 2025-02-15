import io

from minio import Minio

from unicon_backend.constants import MINIO_ACCESS_KEY, MINIO_HOST, MINIO_SECRET_KEY

_client = Minio(MINIO_HOST, access_key=MINIO_ACCESS_KEY, secret_key=MINIO_SECRET_KEY, secure=False)


def upload_file(bucket_name: str, object_name: str, data: bytes, content_type: str | None = None):
    """Upload a file to Minio.

    Note: you can upload files without content_type - but since we are using UUIDs for object names,
    Minio will not be able to infer the content type from the object name (and cannot show you a preview on the GUI without this.)
    """

    # Make the bucket if it doesn't exist.
    found = _client.bucket_exists(bucket_name)
    if not found:
        _client.make_bucket(bucket_name)
        print(f"Bucket {bucket_name} created")

    _client.put_object(
        bucket_name,
        object_name,
        io.BytesIO(data),
        len(data),
        content_type=content_type or "application/octet-stream",
    )


def download_file(bucket_name: str, object_name: str) -> bytes:
    response = _client.get_object(bucket_name, object_name)
    data = response.read()
    response.close()
    response.release_conn()
    return data
