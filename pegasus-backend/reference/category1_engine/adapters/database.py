# --- BEGIN GENERATED FILE METADATA ---
# Authors: Ansh Raj
# Last edited: 2026-06-08T10:46:43Z
# --- END GENERATED FILE METADATA ---

"""Database source adapters — streaming cursors only, no heavy source-side computation."""

from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional

from category1.models.schemas import ColumnSchema, ConnectionConfig, DataSourceType, DatasetSchema
from category1.readers.base import StreamingReader


class DatabaseReader(StreamingReader):
    """Base database reader using server-side cursors for streaming."""

    @abstractmethod
    def _get_connection(self) -> Any:
        ...

    @abstractmethod
    def _build_query(self) -> str:
        ...

    @abstractmethod
    def _fetch_schema(self) -> DatasetSchema:
        ...

    def get_schema(self) -> DatasetSchema:
        return self._fetch_schema()

    def read_chunks(self, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            query = self._build_query()
            cursor.execute(query)
            col_names = [desc[0] for desc in cursor.description]
            chunk: list[dict[str, Any]] = []
            while True:
                rows = cursor.fetchmany(chunk_size)
                if not rows:
                    break
                for row in rows:
                    record = {col_names[i]: row[i] for i in range(len(col_names))}
                    chunk.append(record)
                    if len(chunk) >= chunk_size:
                        yield chunk
                        chunk = []
            if chunk:
                yield chunk
            cursor.close()
        finally:
            conn.close()

    def get_row_count(self) -> Optional[int]:
        """Uses COUNT(*) — single cheap aggregation, skippable via config."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            table = self._config.table
            schema = self._config.schema_name or "public"
            cursor.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
            result = cursor.fetchone()
            cursor.close()
            return result[0] if result else None
        except Exception:
            return None
        finally:
            conn.close()


class PostgresReader(DatabaseReader):
    def _get_connection(self):
        import psycopg2
        c = self._config
        return psycopg2.connect(
            host=c.host, port=c.port or 5432,
            database=c.database, user=c.credentials.get("user"),
            password=c.credentials.get("password"),
        )

    def _build_query(self) -> str:
        if self._config.query:
            return self._config.query
        schema = self._config.schema_name or "public"
        return f"SELECT * FROM {schema}.{self._config.table}"

    def _fetch_schema(self) -> DatasetSchema:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            schema = self._config.schema_name or "public"
            cursor.execute("""
                SELECT column_name, data_type, is_nullable,
                       numeric_precision, numeric_scale, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, self._config.table))
            columns = []
            for row in cursor.fetchall():
                columns.append(ColumnSchema(
                    name=row[0], data_type=row[1],
                    nullable=row[2] == "YES",
                    precision=row[3], scale=row[4], position=row[5],
                ))
            cursor.close()
            return DatasetSchema(columns=columns)
        finally:
            conn.close()


class OracleReader(DatabaseReader):
    def _get_connection(self):
        import oracledb
        c = self._config
        dsn = c.connection_string or f"{c.host}:{c.port or 1521}/{c.database}"
        return oracledb.connect(
            user=c.credentials.get("user"),
            password=c.credentials.get("password"),
            dsn=dsn,
        )

    def _build_query(self) -> str:
        if self._config.query:
            return self._config.query
        schema = self._config.schema_name or self._config.credentials.get("user", "").upper()
        return f"SELECT * FROM {schema}.{self._config.table}"

    def _fetch_schema(self) -> DatasetSchema:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT column_name, data_type, nullable,
                       data_precision, data_scale, column_id
                FROM all_tab_columns
                WHERE table_name = :tbl AND owner = :owner
                ORDER BY column_id
            """, {"tbl": self._config.table.upper(),
                  "owner": (self._config.schema_name or "").upper()})
            columns = []
            for row in cursor.fetchall():
                columns.append(ColumnSchema(
                    name=row[0], data_type=row[1],
                    nullable=row[2] == "Y",
                    precision=row[3], scale=row[4], position=row[5],
                ))
            cursor.close()
            return DatasetSchema(columns=columns)
        finally:
            conn.close()


class SQLServerReader(DatabaseReader):
    def _get_connection(self):
        import pyodbc
        c = self._config
        conn_str = c.connection_string or (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={c.host},{c.port or 1433};"
            f"DATABASE={c.database};"
            f"UID={c.credentials.get('user')};"
            f"PWD={c.credentials.get('password')}"
        )
        return pyodbc.connect(conn_str)

    def _build_query(self) -> str:
        if self._config.query:
            return self._config.query
        schema = self._config.schema_name or "dbo"
        return f"SELECT * FROM [{schema}].[{self._config.table}]"

    def _fetch_schema(self) -> DatasetSchema:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            schema = self._config.schema_name or "dbo"
            cursor.execute("""
                SELECT c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE,
                       c.NUMERIC_PRECISION, c.NUMERIC_SCALE, c.ORDINAL_POSITION
                FROM INFORMATION_SCHEMA.COLUMNS c
                WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
                ORDER BY c.ORDINAL_POSITION
            """, (schema, self._config.table))
            columns = []
            for row in cursor.fetchall():
                columns.append(ColumnSchema(
                    name=row[0], data_type=row[1],
                    nullable=row[2] == "YES",
                    precision=row[3], scale=row[4], position=row[5],
                ))
            cursor.close()
            return DatasetSchema(columns=columns)
        finally:
            conn.close()


class TeradataReader(DatabaseReader):
    def _get_connection(self):
        import teradatasql
        c = self._config
        return teradatasql.connect(
            host=c.host, user=c.credentials.get("user"),
            password=c.credentials.get("password"), database=c.database,
        )

    def _build_query(self) -> str:
        if self._config.query:
            return self._config.query
        return f"SELECT * FROM {self._config.table}"

    def _fetch_schema(self) -> DatasetSchema:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"HELP COLUMN {self._config.table}.*")
            columns = []
            for i, row in enumerate(cursor.fetchall()):
                columns.append(ColumnSchema(
                    name=row[0] if row else f"col_{i}",
                    data_type=str(row[1]) if len(row) > 1 else "string",
                    position=i,
                ))
            cursor.close()
            return DatasetSchema(columns=columns)
        finally:
            conn.close()


class SnowflakeReader(DatabaseReader):
    def _get_connection(self):
        import snowflake.connector
        c = self._config
        return snowflake.connector.connect(
            user=c.credentials.get("user"),
            password=c.credentials.get("password"),
            account=c.credentials.get("account", c.host),
            warehouse=c.credentials.get("warehouse"),
            database=c.database,
            schema=c.schema_name or "PUBLIC",
        )

    def _build_query(self) -> str:
        if self._config.query:
            return self._config.query
        schema = self._config.schema_name or "PUBLIC"
        return f"SELECT * FROM {schema}.{self._config.table}"

    def _fetch_schema(self) -> DatasetSchema:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            schema = self._config.schema_name or "PUBLIC"
            cursor.execute(f"DESCRIBE TABLE {schema}.{self._config.table}")
            columns = []
            for i, row in enumerate(cursor.fetchall()):
                columns.append(ColumnSchema(
                    name=row[0], data_type=row[1], nullable=row[3] == "Y", position=i,
                ))
            cursor.close()
            return DatasetSchema(columns=columns)
        finally:
            conn.close()


class BigQueryReader(DatabaseReader):
    def _get_connection(self):
        from google.cloud import bigquery
        return bigquery.Client(project=self._config.credentials.get("project"))

    def _build_query(self) -> str:
        if self._config.query:
            return self._config.query
        return f"SELECT * FROM `{self._config.database}.{self._config.schema_name}.{self._config.table}`"

    def _fetch_schema(self) -> DatasetSchema:
        from google.cloud import bigquery
        client = bigquery.Client(project=self._config.credentials.get("project"))
        table_ref = f"{self._config.database}.{self._config.schema_name}.{self._config.table}"
        table = client.get_table(table_ref)
        columns = []
        for i, field in enumerate(table.schema):
            columns.append(ColumnSchema(
                name=field.name, data_type=field.field_type,
                nullable=field.mode != "REQUIRED", position=i,
            ))
        return DatasetSchema(columns=columns, row_count=table.num_rows)

    def read_chunks(self, chunk_size: int) -> Iterator[list[dict[str, Any]]]:
        from google.cloud import bigquery
        client = bigquery.Client(project=self._config.credentials.get("project"))
        query_job = client.query(self._build_query())
        chunk: list[dict[str, Any]] = []
        for row in query_job.result(page_size=chunk_size):
            chunk.append(dict(row.items()))
            if len(chunk) >= chunk_size:
                yield chunk
                chunk = []
        if chunk:
            yield chunk


class RedshiftReader(DatabaseReader):
    def _get_connection(self):
        import redshift_connector
        c = self._config
        return redshift_connector.connect(
            host=c.host, port=c.port or 5439,
            database=c.database,
            user=c.credentials.get("user"),
            password=c.credentials.get("password"),
        )

    def _build_query(self) -> str:
        if self._config.query:
            return self._config.query
        schema = self._config.schema_name or "public"
        return f"SELECT * FROM {schema}.{self._config.table}"

    def _fetch_schema(self) -> DatasetSchema:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            schema = self._config.schema_name or "public"
            cursor.execute("""
                SELECT column_name, data_type, is_nullable,
                       numeric_precision, numeric_scale, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
            """, (schema, self._config.table))
            columns = []
            for row in cursor.fetchall():
                columns.append(ColumnSchema(
                    name=row[0], data_type=row[1],
                    nullable=row[2] == "YES",
                    precision=row[3], scale=row[4], position=row[5],
                ))
            cursor.close()
            return DatasetSchema(columns=columns)
        finally:
            conn.close()


class HiveReader(DatabaseReader):
    def _get_connection(self):
        from pyhive import hive
        c = self._config
        return hive.Connection(
            host=c.host, port=c.port or 10000,
            username=c.credentials.get("user"),
            database=c.database or "default",
            auth=c.credentials.get("auth", "NONE"),
        )

    def _build_query(self) -> str:
        if self._config.query:
            return self._config.query
        return f"SELECT * FROM {self._config.table}"

    def _fetch_schema(self) -> DatasetSchema:
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"DESCRIBE {self._config.table}")
            columns = []
            for i, row in enumerate(cursor.fetchall()):
                if row[0] and not row[0].startswith("#"):
                    columns.append(ColumnSchema(
                        name=row[0], data_type=row[1] if len(row) > 1 else "string", position=i,
                    ))
            cursor.close()
            return DatasetSchema(columns=columns)
        finally:
            conn.close()


class DatabaseReaderFactory:
    _readers = {
        DataSourceType.POSTGRES: PostgresReader,
        DataSourceType.ORACLE: OracleReader,
        DataSourceType.SQLSERVER: SQLServerReader,
        DataSourceType.TERADATA: TeradataReader,
        DataSourceType.SNOWFLAKE: SnowflakeReader,
        DataSourceType.BIGQUERY: BigQueryReader,
        DataSourceType.REDSHIFT: RedshiftReader,
        DataSourceType.HIVE: HiveReader,
    }

    @classmethod
    def create(cls, config: ConnectionConfig) -> DatabaseReader:
        reader_cls = cls._readers.get(config.source_type)
        if not reader_cls:
            raise ValueError(f"Unsupported database type: {config.source_type}")
        return reader_cls(config)
