import os
import random
import string
from datetime import datetime, timedelta
from pathlib import Path

# ==========================================
# 1. USER CONFIGURATION (Interactive)
# ==========================================
print("--- Data Generation Setup ---")

# Ask for the number of rows
try:
    NUM_ROWS = int(input("Enter the total number of rows to generate (e.g., 10000): "))
except ValueError:
    print("Invalid number. Defaulting to 10,000 rows.")
    NUM_ROWS = 10_000

# Ask for the number of mismatches
try:
    NUM_MISMATCHES = int(input(f"Enter the number of mismatches (max {NUM_ROWS}): "))
    # Ensure mismatches don't exceed total rows
    if NUM_MISMATCHES > NUM_ROWS:
        print(f"Mismatches cannot exceed total rows. Capping at {NUM_ROWS}.")
        NUM_MISMATCHES = NUM_ROWS
except ValueError:
    print("Invalid number. Defaulting to 0 mismatches.")
    NUM_MISMATCHES = 0

# Ask for the folder name
FOLDER_NAME = input("Enter the folder name to save the files (e.g., my_test_run): ").strip()
if not FOLDER_NAME:
    print("No folder name provided. Defaulting to 'default_test_run'.")
    FOLDER_NAME = "default_test_run"

print("-" * 27)

CHUNK_SIZE = 50_000  # Keeping this hardcoded as it's an internal memory management setting

# Directory setup
try:
    BASE_DIR = Path(__file__).resolve().parent.parent
except NameError:
    BASE_DIR = Path(os.getcwd()).parent 

OUTPUT_DIR = BASE_DIR / "test-data" / FOLDER_NAME
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_FILE = OUTPUT_DIR / "source_data.txt"
TARGET_FILE = OUTPUT_DIR / "target_data.txt"

# ==========================================
# 2. FILE LAYOUTS
# ==========================================
SOURCE_LAYOUT = [
    ("id", 0, 5),       
    ("name", 8, 20),    
    ("email", 28, 30),  
    ("dob", 58, 10),    
]

TARGET_LAYOUT = [
    ("id", 0, 5),
    ("name", 8, 20),
    ("email", 28, 30),
    ("dob", 58, 10),    
]

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def build_fixed_width_line(data, layout):
    total_length = layout[-1][1] + layout[-1][2]
    line_chars = list(" " * total_length)
    
    for col_name, start, length in layout:
        val = str(data.get(col_name, ""))
        padded_val = val.ljust(length)[:length]
        line_chars[start:start+length] = list(padded_val)
        
    return "".join(line_chars) + "\n"

BASE62_ALPHABET = string.digits + string.ascii_letters
def generate_base62_id(num):
    if num == 0:
        return BASE62_ALPHABET[0].zfill(5)
    arr = []
    base = len(BASE62_ALPHABET)
    while num:
        num, rem = divmod(num, base)
        arr.append(BASE62_ALPHABET[rem])
    arr.reverse()
    return "".join(arr).zfill(5)[-5:]

def random_date_string(start_year=1960, end_year=2010):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    rand_date = start + timedelta(days=random.randint(0, (end - start).days))
    return rand_date.strftime("%d/%m/%Y")

# ==========================================
# 4. GENERATE SOURCE FILE
# ==========================================
print(f"\nGenerating {NUM_ROWS} rows in source file...")
with open(SOURCE_FILE, "w", encoding="utf-8") as f:
    for i in range(NUM_ROWS):
        record = {
            "id": generate_base62_id(i),
            "name": f"User_{i}",
            "email": f"user{i}@example.com",
            "dob": random_date_string()
        }
        f.write(build_fixed_width_line(record, SOURCE_LAYOUT))

# ==========================================
# 5. PROCESS, MISMATCH, AND UNSORT TARGET
# ==========================================
print(f"Processing target file (introducing {NUM_MISMATCHES} mismatches and shuffling)...")

mismatch_indices = set(random.sample(range(NUM_ROWS), NUM_MISMATCHES))

with open(SOURCE_FILE, "r", encoding="utf-8") as src, \
     open(TARGET_FILE, "w", encoding="utf-8") as tgt:
    
    chunk_buffer = []
    current_row_idx = 0
    
    for line in src:
        if not line.strip():
            continue

        record = {}
        for col_name, start, length in SOURCE_LAYOUT:
            record[col_name] = line[start : start + length].strip()

        try:
            parsed_date = datetime.strptime(record["dob"], "%d/%m/%Y")
            record["dob"] = parsed_date.strftime("%Y/%m/%d")
        except ValueError:
            pass 

        if current_row_idx in mismatch_indices:
            record["name"] = (record["name"] + "-ERR")[:20]

        chunk_buffer.append(build_fixed_width_line(record, TARGET_LAYOUT))
        current_row_idx += 1

        if len(chunk_buffer) >= CHUNK_SIZE:
            random.shuffle(chunk_buffer)
            tgt.writelines(chunk_buffer)
            chunk_buffer.clear()
            
    if chunk_buffer:
        random.shuffle(chunk_buffer)
        tgt.writelines(chunk_buffer)

print(f"Done! Files created in: {OUTPUT_DIR.resolve()}")