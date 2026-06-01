import fitz
import os
import pandas as pd

folder_path = r"production report"

all_records = []
all_columns = set()

pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]

print("Total PDFs:", len(pdf_files))


# 🔥 STEP 1: CLEAN EXTRACTION
for file in pdf_files:
    file_path = os.path.join(folder_path, file)
    print(f"\nReading: {file}")

    doc = fitz.open(file_path)
    record = {}

    for page in doc:
        text = page.get_text()
        lines = [l.strip() for l in text.split("\n") if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # CASE 1: normal key:value
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # value in next line
                if not value and i + 1 < len(lines):
                    value = lines[i + 1]
                    i += 1

                if key and value:
                    record[key] = value

            # CASE 2: key in one line, ":" in next line
            elif i + 1 < len(lines) and ":" in lines[i + 1]:
                next_line = lines[i + 1]
                _, value = next_line.split(":", 1)

                key = line
                value = value.strip()

                if key and value:
                    record[key] = value
                    i += 1

            i += 1

    if record:
        all_records.append(record)
        all_columns.update(record.keys())


print("\nTotal records:", len(all_records))
print("Total columns:", len(all_columns))


# 🔥 STEP 2: CREATE DATAFRAME (AUTO COLUMNS)
df = pd.DataFrame(all_records)

# fill missing values
df = df.fillna("")
from sqlalchemy import create_engine

# 🔥 Create MySQL connection
engine = create_engine("mysql+mysqlconnector://sunanditha:1234@localhost/production_db")

# 🔥 Send DataFrame to MySQL
df.to_sql("production_table", con=engine, if_exists="replace", index=False)

print("✅ Data sent to MySQL")

# 🔥 STEP 3: SAVE TO CSV
df.to_csv("final_output.csv", index=False)

print("✅ CSV created with dynamic columns")