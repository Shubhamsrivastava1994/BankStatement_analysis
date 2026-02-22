from flask import Flask, request, render_template, send_file, jsonify
import pdfplumber
import pandas as pd
import os
import uuid
import re
import requests

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

current_df = None

import os
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

@app.route("/")
def home():
    return render_template("index.html")


# 🔥 PDF → DataFrame (Excel logic)
def parse_pdf(pdf_path):

    rows = []
    prev_balance = None

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:

            text = page.extract_text()

            if not text:
                continue

            lines = text.split("\n")

            for line in lines:

                if re.match(r"\d{2}/\d{2}/\d{2}", line):

                    date = line.split()[0]
                    numbers = re.findall(r"\d[\d,]*\.\d+", line)

                    if len(numbers) < 2:
                        continue

                    balance = float(numbers[-1].replace(",", ""))
                    amount = float(numbers[-2].replace(",", ""))

                    withdrawal = 0
                    deposit = 0

                    if prev_balance is None:
                        withdrawal = amount
                    else:
                        if balance > prev_balance:
                            deposit = amount
                        else:
                            withdrawal = amount

                    prev_balance = balance

                    narration = line.replace(date, "")
                    narration = narration.replace(numbers[-1], "")
                    narration = narration.replace(numbers[-2], "")

                    rows.append({
                        "Date": date,
                        "Narration": narration.strip(),
                        "Withdrawal": withdrawal,
                        "Deposit": deposit,
                        "Closing Balance": balance
                    })

    return pd.DataFrame(rows)


# 🔥 Upload PDF
@app.route("/upload", methods=["POST"])
def upload():

    global current_df

    file = request.files["file"]

    path = f"{UPLOAD_FOLDER}/{uuid.uuid4()}.pdf"
    file.save(path)

    # internal convert to dataframe
    current_df = parse_pdf(path)

    return jsonify({"status": "success"})


# 🔥 Download Excel
@app.route("/download")
def download():

    global current_df

    if current_df is None:
        return "Upload file first"

    excel_path = f"{UPLOAD_FOLDER}/statement.xlsx"
    current_df.to_excel(excel_path, index=False)

    return send_file(excel_path, as_attachment=True)


# 🤖 AI Analysis
# @app.route("/analysis")
# def analysis():

#     global current_df

#     if current_df is None:
#         return jsonify({"error": "Upload first"})

#     df = current_df.copy()

#     total_income = df["Deposit"].sum()
#     total_expense = df["Withdrawal"].sum()
#     avg_balance = df["Closing Balance"].mean()

#     data = {
#         "total_income": float(total_income),
#         "total_expense": float(total_expense),
#         "average_balance": float(avg_balance)
#     }

#     prompt = f"""
#     Analyze financial stability and loan eligibility.

#     Data:
#     {data}

#     Give:
#     - Stability level
#     - Loan eligibility
#     - Risk level
#     - Suggestions
#     """

#     response = requests.post(
#         "https://openrouter.ai/api/v1/chat/completions",
#         headers={
#             "Authorization": f"Bearer {OPENROUTER_API_KEY}",
#             "Content-Type": "application/json"
#         },
#         json={
#             "model": "openai/gpt-4o-mini",
#             "messages": [
#                 {"role": "system", "content": "You are financial analyst."},
#                 {"role": "user", "content": prompt}
#             ]
#         }
#     )

#     result = response.json()

#     return jsonify({
#         "analysis": result["choices"][0]["message"]["content"]
#     })

@app.route("/analysis")
def analysis():

    global current_df

    if current_df is None:
        return jsonify({"error": "Upload first"})

    df = current_df.copy()

    # Minimal data preparation (NOT underwriting logic)
    df["Deposit"] = pd.to_numeric(df["Deposit"], errors="coerce").fillna(0)
    df["Withdrawal"] = pd.to_numeric(df["Withdrawal"], errors="coerce").fillna(0)
    df["Closing Balance"] = pd.to_numeric(df["Closing Balance"], errors="coerce").fillna(0)

    total_income = df["Deposit"].sum()
    total_expense = df["Withdrawal"].sum()
    avg_balance = df["Closing Balance"].mean()

    # Monthly grouping (AI ko better understanding mile)
    monthly_summary = df.groupby(df["Date"].str[3:8]).agg({
        "Deposit":"sum",
        "Withdrawal":"sum"
    }).to_dict()

    # Some transaction samples (pattern detection ke liye)
    narration_sample = df["Narration"].dropna().head(40).tolist()

    data = {
        "total_income_6_months": float(total_income),
        "total_expense_6_months": float(total_expense),
        "average_balance": float(avg_balance),
        "monthly_summary": monthly_summary,
        "transaction_samples": narration_sample
    }

    prompt = f"""
    You are a senior Indian bank credit underwriting AI.

    Analyse the following bank statement summary:

    {data}

    Act like real bank loan approval system and give:

    1. Final loan decision:
       - APPROVE
       - REJECT
       - CONDITIONAL APPROVAL

    2. Risk score out of 100.

    3. Risk category:
       - LOW
       - MEDIUM
       - HIGH

    4. Which loan types bank can safely give:
       - Personal Loan
       - Home Loan
       - Business Loan
       - Credit Card
       - Vehicle Loan

    5. Maximum safe loan amount estimate.

    6. Hidden financial risk signals.

    7. Professional reasoning like bank credit committee.

    Think deeply before answering.
    """

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a professional Indian bank underwriting system."},
                {"role": "user", "content": prompt}
            ]
        }
    )

    result = response.json()

    return jsonify({
        "analysis": result["choices"][0]["message"]["content"]
    })
if __name__ == "__main__":
    app.run(debug=True)