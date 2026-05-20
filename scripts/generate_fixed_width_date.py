from datetime import datetime

# 1. Define configuration for the fixed-width files
# Format: (Column Name, Start Index, Length)
SOURCE_LAYOUT = [
    ("name", 0, 20),
    ("email", 20, 30),
    ("dob", 50, 10),  # Expected format: DD/MM/YYYY
]

TARGET_LAYOUT = [
    ("name", 0, 20),
    ("email", 20, 30),
    ("dob", 50, 10),  # Desired format: YYYY/MM/DD
]

SOURCE_FILE = "source_data.txt"
TARGET_FILE = "target_data.txt"


# Helper function to create a line padded to fixed widths
def build_fixed_width_line(data, layout):
    line = ""
    for col_name, _, length in layout:
        val = str(data.get(col_name, ""))
        # Left-justify text and pad with spaces up to the specified length
        line += val.ljust(length)[:length]
    return line + "\n"


# 2. Step 1: Create a mock Source File (DD/MM/YYYY)
mock_source_data = [
    {"name": "Alice Smith", "email": "alice@example.com", "dob": "10/06/2026"},
    {"name": "Bob Jones", "email": "bob@example.com", "dob": "25/12/1995"},
    {"name": "Charlie Brown", "email": "charlie@example.com", "dob": "02/01/2000"},
]

print("Generating source file...")
with open(SOURCE_FILE, "w", encoding="utf-8") as f:
    for record in mock_source_data:
        f.write(build_fixed_width_line(record, SOURCE_LAYOUT))


# 3. Step 2: Read Source, Transform Date, and Write to Target (YYYY/MM/DD)
print("Processing source to target with date transformation...")

with open(SOURCE_FILE, "r", encoding="utf-8") as src, open(
    TARGET_FILE, "w", encoding="utf-8"
) as tgt:
    for line in src:
        if not line.strip():
            continue  # Skip empty lines

        # Parse fixed-width line based on SOURCE_LAYOUT positions
        record = {}
        for col_name, start, length in SOURCE_LAYOUT:
            record[col_name] = line[start : start + length].strip()

        # Date Transformation Logic
        try:
            # Parse the source date format (DD/MM/YYYY)
            parsed_date = datetime.strptime(record["dob"], "%d/%m/%Y")

            # Convert to target date format (YYYY/MM/DD)
            # Change this format string to "%m/%d/%Y" if you prefer MM/DD/YYYY
            record["dob"] = parsed_date.strftime("%Y/%m/%Y")
        except ValueError:
            print(f"Warning: Could not parse date '{record['dob']}' for {record['name']}")
            # Keeps the original string if parsing fails, or handle error as needed

        # Write the transformed data to the target file
        tgt.write(build_fixed_width_line(record, TARGET_LAYOUT))

print("Done! Both 'source_data.txt' and 'target_data.txt' have been created.")