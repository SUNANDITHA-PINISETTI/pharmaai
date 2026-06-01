import pandas as pd
from sqlalchemy import create_engine

# 🔥 MySQL connection
engine = create_engine("mysql+mysqlconnector://sunanditha:1234@localhost/production_db")

# 🔥 Load table
df = pd.read_sql("SELECT * FROM production_table", engine)

# 🔍 Check data
print(df.head())
print("Shape:", df.shape)
# 🔥 Convert to numeric
# 🔥 Convert to numeric
df_numeric = df.copy()

for col in df_numeric.columns:
    df_numeric[col] = pd.to_numeric(df_numeric[col], errors='coerce')

df_numeric = df_numeric.dropna(axis=1, how='all')
df_numeric = df_numeric.fillna(0)

print("Numeric columns:", df_numeric.columns)
from sklearn.preprocessing import StandardScaler

scaler = StandardScaler()
X = scaler.fit_transform(df_numeric)