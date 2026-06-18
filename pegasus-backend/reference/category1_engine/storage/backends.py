# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-18T05:25:31Z
# --- END GENERATED FILE METADATA ---

"""Pluggable partition storage backends."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class PartitionStorage(ABC):
    @abstractmethod
    def write_partition(self, side: str, partition_id: int, data: bytes) -> str:
        ...

    @abstractmethod
    def read_partition(self, side: str, partition_id: int) -> Optional[bytes]:
        ...

    @abstractmethod
    def list_partitions(self, side: str) -> list[int]:
        ...

    @abstractmethod
    def delete_job_data(self, job_id: str) -> None:
        ...


class LocalPartitionStorage(PartitionStorage):
    """Local filesystem storage for partition files."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, side: str, partition_id: int) -> Path:
        return self.base_dir / side / f"part_{partition_id:05d}.bin"

    def write_partition(self, side: str, partition_id: int, data: bytes) -> str:
        path = self._path(side, partition_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def read_partition(self, side: str, partition_id: int) -> Optional[bytes]:
        path = self._path(side, partition_id)
        return path.read_bytes() if path.exists() else None

    def list_partitions(self, side: str) -> list[int]:
        side_dir = self.base_dir / side
        if not side_dir.exists():
            return []
        ids = []
        for p in side_dir.glob("part_*.bin"):
            ids.append(int(p.stem.split("_")[1]))
        return sorted(ids)

    def delete_job_data(self, job_id: str) -> None:
        import shutil
        path = self.base_dir / job_id
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


class ObjectPartitionStorage(PartitionStorage):
    """S3-compatible object storage for partition files."""

    def __init__(self, bucket: str, endpoint: Optional[str] = None, prefix: str = "category1"):
        self.bucket = bucket
        self.endpoint = endpoint
        self.prefix = prefix
        self._client = None

    def _get_client(self):
        if self._client is None:
            import boto3
            kwargs = {}
            if self.endpoint:
                kwargs["endpoint_url"] = self.endpoint
            self._client = boto3.client("s3", **kwargs)
        return self._client

    def _key(self, job_id: str, side: str, partition_id: int) -> str:
        return f"{self.prefix}/{job_id}/{side}/part_{partition_id:05d}.bin"

    def write_partition(self, side: str, partition_id: int, data: bytes) -> str:
        raise NotImplementedError("Use job-scoped write via write_job_partition")

    def write_job_partition(self, job_id: str, side: str, partition_id: int, data: bytes) -> str:
        key = self._key(job_id, side, partition_id)
        self._get_client().put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def read_partition(self, side: str, partition_id: int) -> Optional[bytes]:
        raise NotImplementedError("Use job-scoped read")

    def read_job_partition(self, job_id: str, side: str, partition_id: int) -> Optional[bytes]:
        key = self._key(job_id, side, partition_id)
        try:
            resp = self._get_client().get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except Exception:
            return None

    def list_partitions(self, side: str) -> list[int]:
        return []

    def delete_job_data(self, job_id: str) -> None:
        client = self._get_client()
        prefix = f"{self.prefix}/{job_id}/"
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if objects:
                client.delete_objects(Bucket=self.bucket, Delete={"Objects": objects})
