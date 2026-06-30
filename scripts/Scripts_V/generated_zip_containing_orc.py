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

df_src.write_orc("src.orc")
df_tgt.write_orc("tgt.orc")
with zipfile.ZipFile("case3_src.zip", "w") as z: z.write("src.orc")
with zipfile.ZipFile("case3_tgt.zip", "w") as z: z.write("tgt.orc")
cleanup_temps(["src.orc", "tgt.orc"])
print("Case 3 generated.")