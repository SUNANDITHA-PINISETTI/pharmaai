import fitz
import os
import mysql.connector

folder_path = r"production report"

all_records = []
all_columns = set()

pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]

print("Total PDFs:", len(pdf_files))


# 🔥 STEP 1: EXTRACT DATA FROM PDFs
for file in pdf_files:
    file_path = os.path.join(folder_path, file)
    print(f"\nReading: {file}")

    doc = fitz.open(file_path)
    record = {}

    for page in doc:
        text = page.get_text()
        lines = text.split("\n")

        for line in lines:
            line = line.strip()

            if ":" in line:
                parts = line.split(":", 1)

                key = parts[0].strip()
                value = parts[1].strip()

                if key and value:
                    record[key] = value

    if record:
        all_records.append(record)
        all_columns.update(record.keys())


print("\nTotal records:", len(all_records))
print("Total unique columns:", len(all_columns))


# 🔥 STEP 2: CONNECT TO MYSQL
conn = mysql.connector.connect(
    host="localhost",
    user="sunanditha",
    password="1234",
    database="production_db"
)

cursor = conn.cursor()


# 🔥 STEP 3: CREATE TABLE DYNAMICALLY
columns_sql = ", ".join([f"`{col}` TEXT" for col in all_columns])

create_table_query = f"""
CREATE TABLE IF NOT EXISTS production_dynamic (
    id INT AUTO_INCREMENT PRIMARY KEY,
    {columns_sql}
)
"""

cursor.execute("DROP TABLE IF EXISTS production_dynamic")
cursor.execute(create_table_query)

print("✅ Table created dynamically")


# 🔥 STEP 4: INSERT DATA
for record in all_records:
    cols = ", ".join([f"`{k}`" for k in record.keys()])
    vals = ", ".join(["%s"] * len(record))

    query = f"INSERT INTO production_dynamic ({cols}) VALUES ({vals})"

    cursor.execute(query, list(record.values()))

conn.commit()
conn.close()

print("✅ Data inserted successfully")