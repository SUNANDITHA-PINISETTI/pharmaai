import pandas as pd
import numpy as np
from sqlalchemy import create_engine

# ===============================
# 🔥 STEP 1: LOAD DATA FROM MYSQL
# ===============================
engine = create_engine("mysql+mysqlconnector://sunanditha:1234@localhost/production_db")

df = pd.read_sql("SELECT * FROM production_table", engine)

print("Data Loaded")
print(df.head())
print("Shape:", df.shape)


# ===============================
# 🔥 STEP 2: CONVERT TO NUMERIC
# ===============================
df_numeric = df.copy()

for col in df_numeric.columns:
    df_numeric[col] = pd.to_numeric(df_numeric[col], errors='coerce')

# remove empty numeric columns
df_numeric = df_numeric.dropna(axis=1, how='all')

# fill missing
df_numeric = df_numeric.fillna(0)

print("Numeric columns:", df_numeric.columns)


# ===============================
# 🔥 STEP 3: SCALING
# ===============================
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X = scaler.fit_transform(df_numeric)


# ===============================
# 🔥 STEP 4: MODEL 1 - Isolation Forest
# ===============================
from sklearn.ensemble import IsolationForest

iso_model = IsolationForest(contamination=0.05, random_state=42)
df["iso_error"] = iso_model.fit_predict(X)
df["iso_error"] = df["iso_error"].apply(lambda x: 1 if x == -1 else 0)


# ===============================
# 🔥 STEP 5: MODEL 2 - LOF
# ===============================
from sklearn.neighbors import LocalOutlierFactor

lof = LocalOutlierFactor(n_neighbors=20, contamination=0.05)
lof_pred = lof.fit_predict(X)

df["lof_error"] = [1 if x == -1 else 0 for x in lof_pred]


# ===============================
# 🔥 STEP 6: MODEL 3 - One-Class SVM
# ===============================
from sklearn.svm import OneClassSVM

svm = OneClassSVM(nu=0.05, kernel="rbf", gamma="scale")
svm_pred = svm.fit_predict(X)

df["svm_error"] = [1 if x == -1 else 0 for x in svm_pred]


# ===============================
# 🔥 STEP 7: MODEL 4 - Z-SCORE
# ===============================
std = df_numeric.std().replace(0, 1)  # avoid divide by zero
z_scores = np.abs((df_numeric - df_numeric.mean()) / std)

df["zscore_error"] = (z_scores > 3).any(axis=1).astype(int)


# ===============================
# 🔥 STEP 8: MODEL 5 - IQR
# ===============================
Q1 = df_numeric.quantile(0.25)
Q3 = df_numeric.quantile(0.75)
IQR = Q3 - Q1

iqr_mask = ((df_numeric < (Q1 - 1.5 * IQR)) | (df_numeric > (Q3 + 1.5 * IQR)))
df["iqr_error"] = iqr_mask.any(axis=1).astype(int)


# ===============================
# 🔥 STEP 9: MODEL 6 - SEQUENCE ERROR
# ===============================
df["sequence_error"] = 0

for col in df_numeric.columns:
    diff = df_numeric[col].diff().fillna(0)

    threshold = diff.mean() + 2 * diff.std()

    df["sequence_error"] |= (abs(diff) > threshold).astype(int)


# ===============================
# 🔥 STEP 10: FINAL ENSEMBLE
# ===============================
df["total_votes"] = (
    df["iso_error"] +
    df["lof_error"] +
    df["svm_error"] +
    df["zscore_error"] +
    df["iqr_error"] +
    df["sequence_error"]
)

# 🔥 At least 2 models must agree
df["final_error"] = df["total_votes"].apply(
    lambda x: "Error" if x >= 2 else "Normal"
)


# ===============================
# 🔍 STEP 11: RESULT
# ===============================
print("\nFinal Error Distribution:")
print(df["final_error"].value_counts())
def explain_error(row):
    reasons = []

    # 🔹 Extreme value (Z-score)
    if row["zscore_error"]:
        reasons.append("Extreme value detected (beyond normal limits)")

    # 🔹 Out of acceptable range (IQR)
    if row["iqr_error"]:
        reasons.append("Value outside acceptable operating range")

    # 🔹 Sequence issue
    if row["sequence_error"]:
        reasons.append("Sudden change detected in process sequence")

    # 🔹 Pattern anomaly (ML combined)
    if row["iso_error"] or row["lof_error"] or row["svm_error"]:
        reasons.append("Unusual pattern compared to normal production data")

    return ", ".join(reasons) if reasons else "Normal"


df["justification"] = df.apply(explain_error, axis=1)


# ===============================
# 💾 STEP 12: SAVE TO MYSQL
# ===============================
df.to_sql("production_ml_results", con=engine, if_exists="replace", index=False)

print("\n✅ ML Results Saved to MySQL")
