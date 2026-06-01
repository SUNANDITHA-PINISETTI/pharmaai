from flask import Flask, render_template
import pandas as pd
from sqlalchemy import create_engine

app = Flask(__name__)

# ===============================
# 🔥 DATABASE CONNECTION
# ===============================
engine = create_engine(
    "mysql+mysqlconnector://sunanditha:1234@localhost/production_db"
)

# ===============================
# 🔥 HOME ROUTE
# ===============================
@app.route("/")
def home():
    try:
        df = pd.read_sql("SELECT * FROM production_ml_results", engine)
    except Exception as e:
        return f"Database Error: {e}"

    # ===============================
    # 🔹 BASIC METRICS
    # ===============================
    total = len(df)

    error_df = df[df["final_error"] == "Error"].copy() if "final_error" in df.columns else pd.DataFrame()

    errors = len(error_df)

    # ===============================
    # 🔹 STAGE-WISE DATA (SAFE)
    # ===============================
    if "stage_error" in df.columns and not error_df.empty:
        stage_data = error_df["stage_error"].value_counts().to_dict()
    else:
        stage_data = {}

    # ===============================
    # 🔹 TABLE DATA (SAFE COLUMNS)
    # ===============================
    required_cols = [
        "Batch NO.",
        "stage_error",
        "error_column",
        "error_value",
        "justification"
    ]

    available_cols = [col for col in required_cols if col in df.columns]

    if not error_df.empty and available_cols:
        table_df = error_df[available_cols].head(50)
        table = table_df.to_html(
            classes="table table-hover table-bordered",
            index=False
        )
    else:
        table = "<p>No error data available</p>"

    # ===============================
    # 🔥 RENDER TEMPLATE
    # ===============================
    return render_template(
        "index.html",
        total=total,
        errors=errors,
        stage_data=stage_data,
        table=table
    )


# ===============================
# 🔥 RUN APP
# ===============================
if __name__ == "__main__":
    app.run(debug=True)