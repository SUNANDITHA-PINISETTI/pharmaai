print("RUNNING CORRECT APP.PY")
from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import session
from flask import url_for
from flask import jsonify

import pandas as pd

from sqlalchemy import create_engine

import os
import re
import fitz

# =====================================================
# FLASK APP
# =====================================================

app = Flask(__name__)

app.secret_key = "secret123"


# =====================================================
# MYSQL CONNECTION
# =====================================================

engine = create_engine(
    "mysql+mysqlconnector://root:Team%40work123@localhost/production_db"
)


# =====================================================
# UPLOAD FOLDER
# =====================================================

UPLOAD_FOLDER = "uploads"

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =====================================================
# ML FUNCTION
# =====================================================

def run_ml(df):

    df_numeric = df.apply(
        pd.to_numeric,
        errors="coerce"
    ).fillna(0)

    mean = df_numeric.mean()

    std = df_numeric.std().replace(0, 1)

    stage_errors = []

    error_cols = []

    error_vals = []

    for i in range(len(df_numeric)):

        row_errors = []

        col_name = "None"

        val = 0

        for col in df_numeric.columns:

            z = abs(
                (
                    df_numeric.iloc[i][col]
                    - mean[col]
                ) / std[col]
            )

            if z > 3:

                row_errors.append(col)

                col_name = col

                val = df_numeric.iloc[i][col]

        stage_errors.append(

            ", ".join(row_errors)

            if row_errors

            else "No Error"
        )

        error_cols.append(col_name)

        error_vals.append(val)

    # ADD RESULT COLUMNS
    df["stage_error"] = stage_errors

    df["error_column"] = error_cols

    df["error_value"] = error_vals

    df["final_error"] = df["stage_error"].apply(

        lambda x:

        "Error"

        if x != "No Error"

        else "Normal"
    )

    # JUSTIFICATION
    df["justification"] = df.apply(

        lambda row:

        f"{row['stage_error']} issue in "
        f"{row['error_column']} "
        f"(value: {row['error_value']})"

        if row["final_error"] == "Error"

        else "Normal",

        axis=1
    )

    return df


# =====================================================
# AI INSIGHT
# =====================================================

def generate_insight(df):

    if len(df) == 0:

        return "No issues detected."

    if "stage_error" in df.columns:

        top = (

            df["stage_error"]
            .value_counts()
            .idxmax()
        )

        return (
            f"Most errors are occurring "
            f"in {top} stage."
        )

    return "Upload processed data to get insights."


# =====================================================
# ROOT
# =====================================================

@app.route("/")
def root():

    return redirect(
        url_for("login")
    )



# =====================================================
# CHATBOT PAGE
# =====================================================

@app.route("/chatbot")
def chatbot():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    return render_template(
        "chatbot.html"
    )



# =====================================================
# LOGIN
# =====================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    error = None

    if request.method == "POST":

        username = request.form.get("username")

        password = request.form.get("password")

        # LOGIN CHECK
        if (
            username == "admin"
            and
            password == "admin123"
        ):

            session["user"] = username

            return redirect(
                url_for("home")
            )

        else:

            error = "Invalid Username or Password"

    return render_template(
        "login.html",
        error=error
    )


# =====================================================
# HOME DASHBOARD
# =====================================================

@app.route("/home")
def home():

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    try:

        # LOAD DATABASE
        df = pd.read_sql(

            "SELECT * FROM production_ml_results",

            engine
        )

    except Exception as e:

        return f"""
        DATABASE ERROR:<br><br>
        {str(e)}
        """

    # TOTAL RECORDS
    total = len(df)

    # TOTAL ERRORS
    errors = len(

        df[
            df["final_error"] == "Error"
        ]

    ) if "final_error" in df.columns else 0

    # ERROR RATE
    error_rate = round(

        (errors / total) * 100,

        2

    ) if total else 0

    # STAGE DATA
    if (
        "stage_error" in df.columns
        and
        "final_error" in df.columns
    ):

        stage_data = (

            df[
                df["final_error"] == "Error"
            ]

            ["stage_error"]

            .value_counts()

            .to_dict()
        )

    else:

        stage_data = {}

    # ERROR TABLE
    if "final_error" in df.columns:

        error_df = df[
            df["final_error"] == "Error"
        ]

    else:

        error_df = df

    # REQUIRED COLUMNS
    required_cols = [

        "Batch NO.",

        "stage_error",

        "justification"

    ]

    available_cols = [

        col

        for col in required_cols

        if col in error_df.columns
    ]

    # FILTER TABLE
    error_df = error_df[
        available_cols
    ].head(100)

    # INSIGHT
    insight = generate_insight(error_df)

    return render_template(

        "index.html",

        total=total,

        errors=errors,

        error_rate=error_rate,

        stage_data=stage_data,

        table=error_df.to_dict(
            orient="records"
        ),

        columns=available_cols,

        insight=insight
    )


# =====================================================
# DASHBOARD REDIRECT
# =====================================================

@app.route("/dashboard")
def dashboard():

    return redirect(
        url_for("home")
    )


# =====================================================
# UPLOAD
# =====================================================



@app.route(
    "/upload",
    methods=["GET", "POST"]
)
def upload():

    # =====================================
    # LOGIN CHECK
    # =====================================

    if "user" not in session:

        return redirect(
            url_for("login")
        )

    # =====================================
    # OPEN PAGE
    # =====================================

    if request.method == "GET":

        return render_template(
            "upload.html"
        )

    try:

        # =====================================
        # GET FILE
        # =====================================

        file = request.files.get("file")

        if not file or file.filename == "":

            return render_template(
                "upload.html",
                error="Please select a file."
            )

        filename = file.filename

        # =====================================
        # SAVE FILE
        # =====================================

        filepath = os.path.join(

            app.config["UPLOAD_FOLDER"],

            filename
        )

        file.save(filepath)

        # =====================================
        # CSV FILE
        # =====================================

        if filename.lower().endswith(".csv"):

            df = pd.read_csv(filepath)

            df_processed = run_ml(df)

            df_processed.to_sql(

                "production_ml_results",

                con=engine,

                if_exists="append",

                index=False
            )

            return render_template(
                "upload.html",
                success=True
            )

        # =====================================
        # PDF FILE
        # =====================================

        elif filename.lower().endswith(".pdf"):

            return render_template(
                "upload.html",
                success=True
            )

        # =====================================
        # INVALID FILE
        # =====================================

        else:

            return render_template(
                "upload.html",
                error="Only CSV and PDF files are allowed."
            )

    except Exception as e:

        return render_template(
            "upload.html",
            error=f"Upload Failed: {str(e)}"
        )





# =====================================================
# AI CHATBOT
# =====================================================

# =====================================================
# AI CHATBOT
# =====================================================


@app.route("/ask_ai", methods=["POST"])
def ask_ai():

    try:

        question = request.json.get(
            "question",
            ""
        ).strip()

        if not question:

            return jsonify({
                "answer":
                "Please enter a question."
            })

        question_lower = question.lower()

        # =====================================
        # HUMAN CHAT
        # =====================================

        if question_lower in [
            "hi",
            "hello",
            "hey",
            "good morning",
            "good evening"
        ]:

            return jsonify({
                "answer":
                """
Hello 👋

I'm your Manufacturing AI Assistant.

You can ask me:

• error 
• justification
• Why did batch fail?
• Which machine has highest failures?


How can I help you today?
"""
            })

        # =====================================
        # LOAD DATABASE
        # =====================================

        df = pd.read_sql(
            "SELECT * FROM production_ml_results",
            engine
        )
        
        original_df = df.copy()

        df = df.astype(str)

        # =====================================
        # MACHINE WITH HIGHEST FAILURES
        # =====================================

        if (
            "machine" in question_lower
            and
            "highest" in question_lower
        ):

            if (
                "Machine Name" in original_df.columns
                and
                "final_error" in original_df.columns
            ):

                error_df = original_df[
                    original_df["final_error"] == "Error"
                ]

                result = (
                    error_df["Machine Name"]
                    .value_counts()
                    .head(1)
                )

                if len(result):

                    return jsonify({
                        "answer":
                        f"""
The machine with the highest failures is:

{result.index[0]}

Total Failures:
{result.iloc[0]}
"""
                    })

        # =====================================
        # FIND BATCH
        # =====================================

        batch_match = re.search(
            r'([A-Z]{2,}[0-9]+)',
            question.upper()
        )

        matched_df = pd.DataFrame()

        if batch_match:

            batch_no = batch_match.group(1)

            if "Batch NO." in df.columns:

                matched_df = df[
                    df["Batch NO."]
                    .str.upper()
                    .str.contains(
                        batch_no,
                        na=False
                    )
                ]

        else:

            matched_df = df[
                df.apply(
                    lambda row:
                    row.astype(str)
                    .str.lower()
                    .str.contains(
                        question_lower,
                        na=False
                    )
                    .any(),
                    axis=1
                )
            ]

        if len(matched_df) == 0:

            return jsonify({
                "answer":
                f"""
Sorry,

I couldn't find any manufacturing records related to:

{question}
"""
            })

        row = matched_df.iloc[0]

        # =====================================
        # ERROR ONLY
        # =====================================

        if "error" in question_lower:

            return jsonify({
                "answer":
                f"""
Batch:
{row.get('Batch NO.','Unknown')}

Error:
{row.get('stage_error','No Error')}
"""
            })

        # =====================================
        # JUSTIFICATION
        # =====================================

        if "justification" in question_lower:

            justification = row.get(
                "justification",
                "No justification available"
            )

            error = row.get(
                "stage_error",
                "Unknown Error"
            )

            error_lower = error.lower()

            if "compression" in error_lower:

                detailed_reason = """
The compression stage experienced abnormal operating conditions.

This can affect tablet hardness, thickness, weight consistency and overall product quality.
"""

            elif "contamination" in error_lower:

                detailed_reason = """
Possible contamination indicators were detected during manufacturing.

This may indicate environmental contamination, foreign particle presence, or cleaning issues.
"""

            elif "temperature" in error_lower:

                detailed_reason = """
The manufacturing temperature exceeded the approved operating range.

Temperature deviations can impact product stability and process quality.
"""

            elif "pressure" in justification.lower():

                detailed_reason = """
The recorded pressure value was outside the expected operating limits.

This may impact process consistency and manufacturing performance.
"""

            else:

                detailed_reason = """
A manufacturing deviation was detected during production.

The process parameters should be reviewed to determine the exact source of the issue.
"""

            return jsonify({
                "answer":
                f"""
Batch:
{row.get('Batch NO.','Unknown')}

Justification:
{justification}

Explanation:
{detailed_reason}

Impact:

• Product quality may be affected
• Process consistency should be reviewed
• Equipment and sensors should be verified

Recommended Action:

• Review production logs
• Verify process parameters
• Inspect equipment
• Perform corrective action
"""
            })

        # =====================================
        # ROOT CAUSE
        # =====================================

        if (
            "why" in question_lower
            or
            "cause" in question_lower
            or
            "root cause" in question_lower
        ):

            return jsonify({
                "answer":
                f"""
Root Cause Analysis

Batch:
{row.get('Batch NO.','Unknown')}

Possible Cause:

{row.get('justification','Not Available')}
"""
            })

    
        # =====================================
        # MACHINE DETAILS
        # =====================================

        if "machine" in question_lower:

            machine_name = ""

            machine_match = re.search(
                r"machine(?:\s+name)?\s+(.+)",
                question,
                re.IGNORECASE
            )

            if machine_match:

                machine_name = machine_match.group(1).strip()

            if (
                machine_name
                and
                "Machine Name" in df.columns
            ):

                machine_df = df[
                    df["Machine Name"]
                    .str.lower()
                    .str.contains(
                        machine_name.lower(),
                        na=False
                    )
                ]

                if len(machine_df):

                    row = machine_df.iloc[0]

                    return jsonify({
                        "answer":
                        f"""
Machine Name:
{row.get('Machine Name','Unknown')}

Batch:
{row.get('Batch NO.','Unknown')}

Error:
{row.get('stage_error','No Error')}

Justification:
{row.get('justification','No Justification Available')}
"""
                    })

                else:

                    return jsonify({
                        "answer":
                        f"""
No records found for machine:

{machine_name}
"""
                    })
                
        # =====================================
        # PRODUCT NAME
        # =====================================

        if "product" in question_lower:

            return jsonify({
                "answer":
                f"""
Batch:
{row.get('Batch NO.','Unknown')}

Product Name:
{row.get('Product Name','Unknown')}
"""
            })

        # =====================================
        # CAPACITY
        # =====================================

        if "capacity" in question_lower:

            return jsonify({
                "answer":
                f"""
Machine:
{row.get('Machine Name','Unknown')}

Capacity:
{row.get('Capacity','Unknown')}
"""
            })

        # =====================================
        # RUNNING TIME
        # =====================================

        if (
            "running time" in question_lower
            or
            "runtime" in question_lower
        ):

            return jsonify({
                "answer":
                f"""
Machine:
{row.get('Machine Name','Unknown')}

Running Time:
{row.get('Running Time','Unknown')}
"""
            })

        # =====================================
        # AIR PRESSURE
        # =====================================

        if (
            "air pressure" in question_lower
            or
            "pressure" in question_lower
        ):

            return jsonify({
                "answer":
                f"""
Machine:
{row.get('Machine Name','Unknown')}

Main Air Pressure:
{row.get('Main Air pressure','Unknown')}

Air Pressure Low Limit:
{row.get('Air Pressure Low Limit','Unknown')}
"""
            })

        # =====================================
        # DUST COLLECTOR
        # =====================================

        if "dust collector" in question_lower:

            return jsonify({
                "answer":
                f"""
Machine:
{row.get('Machine Name','Unknown')}

Dust Collector Status:
{row.get('Dust Collector','Unknown')}
"""
            })

  
        # =====================================
        # DEFAULT RESPONSE
        # =====================================

        return jsonify({
            "answer":
            f"""
Batch:
{row.get('Batch NO.','Unknown')}

Machine:
{row.get('Machine Name','Unknown')}

Product:
{row.get('Product Name','Unknown')}

Error:
{row.get('stage_error','No Error')}

Justification:
{row.get('justification','No Justification Available')}
"""
        })

    except Exception as e:

        return jsonify({
            "answer":
            f"System Error: {str(e)}"
        })


# =====================================================
# LOGOUT
# =====================================================

@app.route("/logout")
def logout():

    session.pop("user", None)

    return redirect(
        url_for("login")
    )



# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":

    app.run(debug=True)