import polars as pl
import zipfile
import tarfile
import os
import fastavro

# Source Data (10 Rows)
df_src = pl.DataFrame({
    "id": [1, 2, 3, 4, 5, 7, 8, 9, 10],
    "value": ["A", "B", "C", "D", "E", "G", "H", "I", "J"]
})

# Target Data (10 Rows - with mismatch, missing, and extra)
df_tgt = pl.DataFrame({
    "id": [1, 2, 3, 5, 6, 7, 8, 9, 10],
    "value": ["A", "X", "C", "E", "F", "G", "H", "I", "J"]
})

# Helper function to write Avro (since Polars doesn't have write_avro)
def write_avro_file(df, filepath):
    schema = fastavro.parse_schema({
        "type": "record",
        "name": "Data",
        "fields": [
            {"name": "id", "type": "int"},
            {"name": "value", "type": ["null", "string"]}
        ]
    })
    with open(filepath, 'wb') as f:
        fastavro.writer(f, schema, df.to_dicts())

# Helper function to cleanup temporary files
def cleanup_temps(files):
    for f in files:
        if os.path.exists(f):
            os.remove(f)

write_avro_file(df_src, "src.avro")
write_avro_file(df_tgt, "tgt.avro")
for p in ["src", "tgt"]:
    with zipfile.ZipFile(f"inner_{p}.zip", "w") as z: z.write(f"{p}.avro")
    with tarfile.open(f"case8_{p}.tar", "w") as tar: tar.add(f"inner_{p}.zip")
cleanup_temps(["src.avro", "tgt.avro", "inner_src.zip", "inner_tgt.zip"])
print("Case 8 generated.")