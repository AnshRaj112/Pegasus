from datetime import datetime

# 1. Define configuration for the fixed-width files
# Format: (Column Name, Start Index, Length)
# Added a 3-character intentional gap between 'id' and 'name'
SOURCE_LAYOUT = [
    ("id", 0, 5),       # Starts at 0, spans 5 characters (0-4)
    # Positions 5, 6, and 7 will naturally remain empty spaces
    ("name", 8, 20),    # Starts at 8, spans 20 characters (8-27)
    ("email", 28, 30),  # Starts at 28, spans 30 characters (28-57)
    ("dob", 58, 10),    # Starts at 58, spans 10 characters (58-67) -- Expected format: DD/MM/YYYY
]

TARGET_LAYOUT = [
    ("id", 0, 5),
    ("name", 8, 20),
    ("email", 28, 30),
    ("dob", 58, 10),    # Desired format: YYYY/MM/DD
]

SOURCE_FILE = "source_data.txt"
TARGET_FILE = "target_data.txt"


# Updated helper function to honor exact start positions with gaps
def build_fixed_width_line(data, layout):
    # Determine total line length required based on the last column's reach
    total_length = layout[-1][1] + layout[-1][2]
    # Create a base string completely filled with spaces
    line_chars = list(" " * total_length)
    
    for col_name, start, length in layout:
        val = str(data.get(col_name, ""))
        # Pad/truncate the value to its strict field length
        padded_val = val.ljust(length)[:length]
        # Insert it exactly where it belongs in the line layout
        line_chars[start:start+length] = list(padded_val)
        
    return "".join(line_chars) + "\n"


# 2. Step 1: Create a mock Source File (DD/MM/YYYY)
mock_source_data = [
    {"id": "00001", "name": "Alice Smith", "email": "alice@example.com", "dob": "10/06/2026"},
    {"id": "00002", "name": "Bob Jones", "email": "bob@example.com", "dob": "25/12/1995"},
    {"id": "00003", "name": "Charlie Brown", "email": "charlie@example.com", "dob": "02/01/2000"},
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
            record["dob"] = parsed_date.strftime("%Y/%m/%d")
        except ValueError:
            print(f"Warning: Could not parse date '{record['dob']}' for {record['name']}")

        # Write the transformed data to the target file
        tgt.write(build_fixed_width_line(record, TARGET_LAYOUT))

print("Done! Both 'source_data.txt' and 'target_data.txt' have been created.")