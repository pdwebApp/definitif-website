from flask import Flask, render_template, request, send_file
import pandas as pd, plotly, json
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import investment_logic   # import the file directly

app = Flask(__name__, template_folder='templates', static_folder='static')

# template_folder='.' → look for HTML in current folder
# static_folder='.' → look for CSS/images in current folder

last_table = None

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/calculators")
def calculators():
    return render_template("calculators.html")

@app.route("/investment", methods=["GET","POST"])
def investment():
    global last_table
    table_html, graph_json = None, None
    if request.method == "POST":
        equity_return = int(request.form["equity_return"])
        debt_return = int(request.form["debt_return"])
        equity_allocation = int(request.form["equity_allocation"])
        onetime_amount = int(request.form["onetime_amount"])
        sip_amount = int(request.form["sip_amount"])
        tenure_months = int(request.form["tenure_months"])
        annual_SIP_increment_in = request.form["annual_SIP_increment_in"]
        sip_increment = int(request.form.get("sip_increment", 0))

        # call the function from investment_logic.py
        table, fig = investment_logic.investmentGrowth_calci(
            equity_return, debt_return,
            equity_allocation, onetime_amount,
            sip_amount, tenure_months,
            annual_SIP_increment_in, sip_increment
        )

        last_table = table
        table_html = table.to_html(classes="table table-striped", index=False)
        graph_json = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)

    return render_template("investment.html",
                           table_html=table_html,
                           graph_json=graph_json)

@app.route("/download_pdf")
def download_pdf():
    global last_table
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    story = [Paragraph("Investment Growth Results", styles['Title'])]
    if last_table is not None:
        story.append(Paragraph(last_table.to_html(), styles['Normal']))
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="results.pdf")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
