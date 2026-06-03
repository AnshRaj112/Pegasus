# Native Columnar Format Engine

Pure Python implementations for Parquet and ORC — no PyArrow, fastparquet, pyorc, or pandas.

## Modules

| Module | Purpose |
|--------|---------|
| `thrift_compact.py` | Apache Thrift Compact Protocol reader (Parquet footers/page headers) |
| `snappy_codec.py` | Snappy block decompression |
| `parquet_format.py` | Parquet metadata parsing, schema flattening |
| `parquet_decoder.py` | Page decoding (PLAIN, RLE, dictionary, gzip/snappy) |
| `parquet_file.py` | Row-group streaming reader |
| `parquet_writer.py` | Test/simple Parquet writer (uncompressed, PLAIN) |
| `orc_protobuf.py` | Protobuf wire-format reader (ORC footers) |
| `orc_format.py` | ORC type constants and schema parsing |
| `orc_file.py` | Stripe streaming reader |
| `orc_writer.py` | Test/simple ORC writer (Category-1 direct encoding profile) |

## Supported Encodings

### Parquet (read)
- Compression: UNCOMPRESSED, SNAPPY, GZIP
- Value encoding: PLAIN, RLE, PLAIN_DICTIONARY, RLE_DICTIONARY
- Required and optional columns (definition levels)
- Row-group streaming (one row group in memory at a time)

### ORC (read)
- Category-1 native profile: uncompressed, direct fixed-width INT64 and length-prefixed STRING
- Stripe streaming
- Standard ORC footer/postscript parsing

## Memory Model

Both readers process one row group (Parquet) or stripe (ORC) at a time, converting to row dicts in configurable chunks — consistent with the platform's bounded-memory design.

## Extending

To add Parquet encoding support, extend `parquet_decoder.py`.
To add ORC compression/encoding, extend `orc_file.py` and `orc_format.py`.
