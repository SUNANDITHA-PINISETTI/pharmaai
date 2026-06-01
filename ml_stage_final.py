import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# ===============================
# 🔥 STEP 1: LOAD DATA
# ===============================
engine = create_engine("mysql+mysqlconnector://sunanditha:1234@localhost/production_db")

df = pd.read_sql("SELECT * FROM production_table", engine)

print("✅ Data Loaded:", df.shape)


# ===============================
# 🔥 STEP 2: CLEAN NUMERIC DATA
# ===============================
df_numeric = df.copy()

df_numeric = df_numeric.apply(pd.to_numeric, errors='coerce')
df_numeric = df_numeric.dropna(axis=1, how='all')
df_numeric = df_numeric.fillna(0)

print("Numeric Columns:", df_numeric.columns)


# ===============================
# 🔥 STEP 3: PRECOMPUTE STATS
# ===============================
col_mean = df_numeric.mean()
col_std = df_numeric.std().replace(0, 1)

Q1 = df_numeric.quantile(0.25)
Q3 = df_numeric.quantile(0.75)
IQR = Q3 - Q1

diff = df_numeric.diff().fillna(0)
threshold = diff.mean() + 2 * diff.std()


# ===============================
# 🔥 STEP 4: STAGE MAPPING
# ===============================
def map_stage(col):
    c = col.lower()

    if any(x in c for x in ["pressure", "force", "depth", "counter", "speed", "capacity", "punch", "fill"]):
        return "Compression"

    elif any(x in c for x in ["air", "time", "limit", "interval"]):
        return "Machine"

    elif any(x in c for x in ["sd", "mean", "min", "max"]):
        return "Quality Control"

    elif any(x in c for x in ["hsp", "hcp", "lcp", "lsp", "ref"]):
        return "Calibration"

    else:
        return "Other"


# ===============================
# 🔥 STEP 5: DETECT ERRORS (CORE)
# ===============================
def detect_stage_errors(row):
    stage_errors = []
    error_columns = []
    error_values = []

    idx = row.name

    for col in df_numeric.columns:
        value = df_numeric.loc[idx, col]

        if pd.isna(value):
            continue

        # Z-score
        z = abs((value - col_mean[col]) / col_std[col])

        # IQR
        out_of_range = (
            value < (Q1[col] - 1.5 * IQR[col]) or
            value > (Q3[col] + 1.5 * IQR[col])
        )

        # Sequence
        seq_break = abs(diff.loc[idx, col]) > threshold[col]

        if z > 3 or out_of_range or seq_break:
            stage_errors.append(map_stage(col))
            error_columns.append(col)
            error_values.append(str(round(value, 2)))

    return pd.Series({
        "stage_error": ", ".join(set(stage_errors)) if stage_errors else "No Error",
        "error_column": ", ".join(error_columns),
        "error_value": ", ".join(error_values)
    })


# APPLY FUNCTION
df[["stage_error", "error_column", "error_value"]] = df.apply(
    detect_stage_errors, axis=1
)


# ===============================
# 🔥 STEP 6: FINAL ERROR LABEL
# ===============================
df["final_error"] = df["stage_error"].apply(
    lambda x: "Error" if x != "No Error" else "Normal"
)


# ===============================
# 🔥 STEP 7: JUSTIFICATION
# ===============================
df["justification"] = df.apply(
    lambda row: f"{row['stage_error']} issue in {row['error_column']} (value: {row['error_value']})"
    if row["final_error"] == "Error" else "Normal",
    axis=1
)


# ===============================
# 🔥 STEP 8: SAVE TO MYSQL
# ===============================
df.to_sql("production_ml_results", con=engine, if_exists="replace", index=False)

print("\n✅ DONE: Stage-wise Error Detection Completed")