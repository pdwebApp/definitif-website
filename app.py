import os
import json
import traceback
import uuid
import threading
import time
from datetime import date, timedelta
from io import BytesIO, StringIO

import pandas as pd
import plotly
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    redirect,
    session,
    send_file,
)
from supabase import create_client

from goal_logic import goalCalci
import investment_logic
from retirement_logic import retirementCalci
from transaction_view import build_transaction_view
from supabase_storage import fetch_json


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE_DIR, "temp_retirement")
os.makedirs(TEMP_DIR, exist_ok=True)

_cleanup_thread_started = False


def get_supabase():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables")

    return create_client(supabase_url, supabase_key)


def cleanup_temp_files():
    while True:
        try:
            now = time.time()
            for file_name in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, file_name)
                if os.path.isfile(file_path) and now - os.path.getmtime(file_path) > 3600:
                    os.remove(file_path)
        except Exception as e:
            print("Cleanup error:", e, flush=True)

        time.sleep(600)


def start_cleanup_thread():
    global _cleanup_thread_started

    if _cleanup_thread_started:
        return

    cleanup_thread = threading.Thread(
        target=cleanup_temp_files,
        daemon=True
    )
    cleanup_thread.start()
    _cleanup_thread_started = True


def create_app():
    app = Flask(
        __name__,
        template_folder=os.path.join(BASE_DIR, "templates"),
        static_folder=os.path.join(BASE_DIR, "static")
    )

    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-fallback")
    app.config["VALUATION_DATE"] = date.today() - timedelta(days=1)

    print("Starting app...", flush=True)
    print("SUPABASE_URL present:", bool(os.getenv("SUPABASE_URL")), flush=True)
    print("SUPABASE_KEY present:", bool(os.getenv("SUPABASE_KEY")), flush=True)

    supabase = get_supabase()
    start_cleanup_thread()

    @app.before_request
    def redirect_to_www():
        host = request.host.split(":")[0]
        if host == "definitif.app":
            target = f"https://www.definitif.app{request.path}"
            if request.query_string:
                target = f"{target}?{request.query_string.decode()}"
            return redirect(target, code=301)

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/services")
    def services():
        return render_template("services.html")

    @app.route("/calculators")
    def calculators():
        return render_template("calculators.html")

    @app.route("/insights")
    def insights():
        return render_template("insights.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    @app.route("/login")
    def login():
        return render_template("login.html")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dash.html")

    @app.route("/api/user-index")
    def user_index():
        try:
            data = fetch_json("users_index.json")
            if data is None:
                return jsonify({"error": "users_index.json not found"}), 404
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/portfolio/<path:filename>")
    def portfolio_file(filename):
        try:
            data = fetch_json(filename)
            if data is None:
                return jsonify({"error": "Portfolio file not found"}), 404
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/transaction_view")
    def transaction_view():
        try:
            pan = request.args.get("pan", "").strip()
            if not pan:
                return jsonify({"error": "Missing pan"}), 400

            tx = (
                supabase
                .table("rta_transactions")
                .select("*")
                .eq("pan", pan)
                .execute()
                .data
            )

            if not tx:
                return jsonify([])

            rta_df = pd.DataFrame(tx)
            if rta_df.empty or "isin" not in rta_df.columns:
                return jsonify([])

            isins = rta_df["isin"].dropna().unique().tolist()
            if not isins:
                return jsonify([])

            nav_rows = (
                supabase
                .table("amfi_nav")
                .select("isin, nav, nav_date")
                .in_("isin", isins)
                .order("nav_date", desc=True)
                .execute()
                .data
            )
            nav_df = pd.DataFrame(nav_rows)

            mapper_rows = (
                supabase
                .table("isin_mapper")
                .select("*")
                .execute()
                .data
            )
            mapper_df = pd.DataFrame(mapper_rows)

            lots = build_transaction_view(rta_df, nav_df, mapper_df)

            if lots is None or lots.empty:
                return jsonify([])

            return jsonify(lots.to_dict(orient="records"))

        except Exception as e:
            print("TRANSACTION VIEW ERROR", flush=True)
            print(traceback.format_exc(), flush=True)
            return jsonify({"error": str(e)}), 500

    @app.route("/investment", methods=["GET", "POST"])
    def investment():
        default_data = {
            "equity_return": 12,
            "debt_return": 6,
            "other_return": 8,
            "equity_allocation": 60,
            "debt_allocation": 30,
            "other_allocation": 10,
            "onetime_amount": 100000,
            "sip_amount": 5000,
            "tenure_months": 120,
            "annual_SIP_increment_in": "Nil",
            "sip_increment": 0
        }

        if request.method == "POST":
            form_data = request.form.to_dict()

            equity_return = float(request.form.get("equity_return", 12))
            debt_return = float(request.form.get("debt_return", 6))
            other_return = float(request.form.get("other_return", 8))
            equity_allocation = float(request.form.get("equity_allocation", 60))
            debt_allocation = float(request.form.get("debt_allocation", 30))
            other_allocation = float(request.form.get("other_allocation", 10))
            onetime_amount = float(request.form.get("onetime_amount", 100000))
            sip_amount = float(request.form.get("sip_amount", 5000))
            tenure_months = int(request.form.get("tenure_months", 120))
            annual_SIP_increment_in = request.form.get("annual_SIP_increment_in", "Nil")

            sip_increment_raw = request.form.get("sip_increment", "").strip()
            try:
                sip_increment = float(sip_increment_raw) if sip_increment_raw else 0
            except ValueError:
                sip_increment = 0

            if annual_SIP_increment_in == "Nil":
                sip_increment = 0

            growth_data, investmentgrowth_message, fig = investment_logic.investmentGrowth_calci(
                equity_return,
                debt_return,
                other_return,
                equity_allocation,
                debt_allocation,
                other_allocation,
                onetime_amount,
                sip_amount,
                tenure_months,
                annual_SIP_increment_in,
                sip_increment
            )

            session["investment_result_id"] = str(uuid.uuid4())
            session["investment_data"] = growth_data.to_json()

            graph_json = json.dumps(
                fig.to_dict(),
                cls=plotly.utils.PlotlyJSONEncoder
            )

            return render_template(
                "investment.html",
                results=True,
                investmentgrowth_message=investmentgrowth_message,
                graph_json=graph_json,
                form_data=form_data,
                scroll_to_results=True
            )

        return render_template(
            "investment.html",
            investmentgrowth_message=None,
            graph_json=None,
            excel_file=None,
            form_data=default_data
        )

    @app.route("/download/investment-excel")
    def download_investment_excel():
        data_json = session.get("investment_data")
        if not data_json:
            return "No data found. Please recalculate.", 400

        df = pd.read_json(StringIO(data_json))
        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Investment Growth")

        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="Investment_Growth.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route("/retirement", methods=["GET", "POST"])
    def retirement():
        default_data = {
            "clientAge": 30,
            "clientRetAge": 60,
            "curMthExp": 50000,
            "preRetire_invApproach": "Conservatively Moderate",
            "principalProtected": "Yes",
            "preRetireinflation": 5,
            "postRetire_invApproach": "Moderate",
            "lifeExpectency": 85,
            "percentage_SIPinc": 5,
            "currentSavings_Retire": 0
        }

        if request.method == "POST":
            form_data = request.form.to_dict()

            clientAge = int(request.form.get("clientAge", 30))
            clientRetAge = int(request.form.get("clientRetAge", 60))
            curMthExp = float(request.form.get("curMthExp", 50000))
            principalProtected = request.form.get("principalProtected", "Yes")
            preRetireinflation = float(request.form.get("preRetireinflation", 5))
            lifeExpectency = int(request.form.get("lifeExpectency", 85))
            percentage_SIPinc = float(request.form.get("percentage_SIPinc", 5))
            currentSavings_Retire = float(request.form.get("currentSavings_Retire", 0))
            preRetire_invApproach = request.form.get("preRetire_invApproach")
            postRetire_invApproach = request.form.get("postRetire_invApproach")

            mapping = {
                "Conservative": 7,
                "Conservatively Moderate": 9,
                "Moderate": 11,
                "Moderately Aggressive": 13,
                "Aggressive": 15
            }

            invApproach = mapping.get(preRetire_invApproach, 11)
            annuityAnnualRet = mapping.get(postRetire_invApproach, 7)

            (
                investmentSchedule,
                annuitySchedule,
                fig1,
                fig2,
                requirement_message,
                retirement_message
            ) = retirementCalci(
                clientAge,
                clientRetAge,
                curMthExp,
                invApproach,
                principalProtected,
                preRetireinflation,
                annuityAnnualRet,
                lifeExpectency,
                percentage_SIPinc,
                currentSavings_Retire
            )

            result_id = str(uuid.uuid4())
            inv_path = os.path.join(TEMP_DIR, f"{result_id}_investment.json")
            ann_path = os.path.join(TEMP_DIR, f"{result_id}_annuity.json")

            investmentSchedule.to_json(inv_path)
            annuitySchedule.to_json(ann_path)

            invest_graph_json = json.dumps(
                fig1.to_dict(),
                cls=plotly.utils.PlotlyJSONEncoder
            )
            annuity_graph_json = json.dumps(
                fig2.to_dict(),
                cls=plotly.utils.PlotlyJSONEncoder
            )

            return render_template(
                "retirement.html",
                results=True,
                form_data=form_data,
                invest_graph_json=invest_graph_json,
                annuity_graph_json=annuity_graph_json,
                requirement_message=requirement_message,
                retirement_message=retirement_message,
                scroll_to_results=True,
                result_id=result_id
            )

        return render_template("retirement.html", form_data=default_data)

    @app.route("/download/retirement-investment-excel")
    def download_retirement_investment_excel():
        result_id = request.args.get("id")
        if not result_id:
            return "Missing result id", 400

        file_path = os.path.join(TEMP_DIR, f"{result_id}_investment.json")
        if not os.path.exists(file_path):
            return "Session expired or file missing", 400

        df = pd.read_json(file_path)
        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Investment Schedule")

        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="Investment_Schedule.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route("/download/retirement-annuity-excel")
    def download_retirement_annuity_excel():
        result_id = request.args.get("id")
        if not result_id:
            return "Missing result id", 400

        file_path = os.path.join(TEMP_DIR, f"{result_id}_annuity.json")
        if not os.path.exists(file_path):
            return "Session expired or file missing", 400

        df = pd.read_json(file_path)
        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Annuity Schedule")

        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="Annuity_Schedule.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    @app.route("/goal", methods=["GET", "POST"])
    def goal():
        default_data = {
            "curCost_goal": 10000,
            "investTenure": 1,
            "currentSavings_goal": 1000,
            "expInflation": 5,
            "invApproach": "Moderate",
            "percentage_SIPinc": 5,
        }

        if request.method == "POST":
            form_data = request.form.to_dict()

            curCost_goal = int(request.form.get("curCost_goal", 10000))
            investTenure = int(request.form.get("investTenure", 1))
            currentSavings_goal = float(request.form.get("currentSavings_goal", 1000))
            expInflation = float(request.form.get("expInflation", 5))
            invApproach = request.form.get("invApproach", "Moderate")
            percentage_SIPinc = float(request.form.get("percentage_SIPinc", 5))

            mapping = {
                "Conservative": 7,
                "Conservatively Moderate": 9,
                "Moderate": 11,
                "Moderately Aggressive": 13,
                "Aggressive": 15
            }

            invApproach = mapping.get(invApproach, 11)

            goalSchedule, fig1, requirement_message, goal_message = goalCalci(
                curCost_goal,
                investTenure,
                currentSavings_goal,
                expInflation,
                invApproach,
                percentage_SIPinc,
            )

            session["goalSchedule_data"] = goalSchedule.to_json(orient="split")

            goal_graph_json = json.dumps(
                fig1.to_dict(),
                cls=plotly.utils.PlotlyJSONEncoder
            )

            return render_template(
                "goal.html",
                results=True,
                form_data=form_data,
                goal_graph_json=goal_graph_json,
                requirement_message=requirement_message,
                goal_message=goal_message,
                scroll_to_results=True
            )

        return render_template("goal.html", form_data=default_data)

    @app.route("/download/goal-excel")
    def download_goal_excel():
        data_json = session.get("goalSchedule_data")
        if not data_json:
            return "No data found. Please recalculate.", 400

        df = pd.read_json(StringIO(data_json), orient="split")
        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Goal Schedule")

        output.seek(0)

        return send_file(
            output,
            as_attachment=True,
            download_name="Goal_Schedule.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)