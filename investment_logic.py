import pandas as pd
import plotly.express as px
from dateutil import relativedelta
from datetime import datetime

def investmentGrowth_calci(equity_return, debt_return, other_return,
                           equity_allocation, debt_allocation, other_allocation,
                           onetime_amount, sip_amount, tenure_months,
                           annual_SIP_increment_in, sip_increment=0):
    
    print("annual_SIP_increment_in:", annual_SIP_increment_in)
    print("sip_increment:", sip_increment)

    # Since tenure starts with 0th month, adding 1 extra month for calculations
    tenure_months = tenure_months + 1

    if annual_SIP_increment_in != 'Nil':
        no_inc = tenure_months // 12 + (1 if tenure_months % 12 > 0 else 0)

    # SIP Cashflow
    if annual_SIP_increment_in == 'Nil':
        sip_amt = [sip_amount for _ in range(tenure_months)]
    elif annual_SIP_increment_in == 'Fixed Amount':
        sip_amt = []
        for multiple in range(no_inc):
            for _ in range(12):
                sip_amt.append(round(sip_amount + multiple * sip_increment))
        sip_amt = sip_amt[:tenure_months]
    elif annual_SIP_increment_in == 'Percentage':
        sip_amt = []
        for multiple in range(no_inc):
            for _ in range(12):
                sip_amt.append(round(sip_amount * (1 + sip_increment/100)**multiple))
        sip_amt = sip_amt[:tenure_months]
    # Since the tenure is actually 12 and we have added 1 month to negate the 
    sip_amt[-1] = 0

    # Portfolio return
    equity_return /= 100
    debt_return /= 100
    other_return /= 100
    portfolio_return = (equity_return * equity_allocation/100) + \
                       (debt_return * debt_allocation/100) + \
                       (other_return * other_allocation/100)
    portfolio_return_mth = (portfolio_return+1)**(1/12)-1

    # Dates
    initial_date = datetime.today().strftime('%Y-%m-%d')
    value_dates = [datetime.strptime(initial_date, '%Y-%m-%d') + 
                   relativedelta.relativedelta(months=i)
                   for i in range(tenure_months)]

    # Invested amount
    inc_principle = [onetime_amount + sip_amount]
    for i in range(1, tenure_months):
        inc_principle.append(inc_principle[-1] + sip_amt[i])

    # Expected value
    inc_values = [inc_principle[0]]
    for i in range(1, tenure_months):
        inc_values.append(round(inc_values[-1]*(1+portfolio_return_mth) + sip_amt[i]))

    # DataFrame
    growth_data = pd.DataFrame({
        'Date': pd.to_datetime(value_dates).astype(str),
        'Invested Amount': list(inc_principle),
        'Expected Value': list(inc_values)
    })

    import plotly.graph_objects as go

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=growth_data["Date"].astype(str).tolist(),
        y=growth_data["Invested Amount"].tolist(),
        mode="lines+markers",
        name="Invested Amount",
        hovertemplate=
        "<b>Invested Amount</b>: ₹%{y:,.0f}" +
        "<extra></extra>"
    ))

    fig.add_trace(go.Scatter(
        x=growth_data["Date"].astype(str).tolist(),
        y=growth_data["Expected Value"].tolist(),
        mode="lines+markers",
        name="Expected Value",
        hovertemplate=
        "<b>Expected Value</b>: ₹%{y:,.0f}" +
        "<extra></extra>"
    ))

    fig.update_layout(
        title="",
        template="plotly_white",
        xaxis_title="",
        yaxis_title="",
        margin=dict(l=5, r=5, t=10, b=10),
        legend=dict(x=0.01,y=0.99,bgcolor="rgba(0,0,0,0)",borderwidth=0),
        hovermode="x unified",
        yaxis=dict(
            separatethousands=True
        )
    )
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
        xaxis=dict(gridcolor="#444"),
        yaxis=dict(gridcolor="#444")
    )
    fig.update_xaxes(title_text = "", showline=True, showgrid=False)
    fig.update_yaxes(title_text = "", showline=True, showgrid=False)
    # Force convert numpy arrays to Python lists (prevents binary encoding)
    fig_dict = fig.to_dict()

    for trace in fig_dict["data"]:
        if hasattr(trace["x"], "tolist"):
            trace["x"] = trace["x"].tolist()
        if hasattr(trace["y"], "tolist"):
            trace["y"] = trace["y"].tolist()

    fig = go.Figure(fig_dict)

    investmentgrowth_message = (
            f"<b>Total investment</b> made was <b>Rs. {int(growth_data['Invested Amount'].iloc[-1])}</b>. \n\n<br>"
            f"At a <b>portfolio growth rate</b> of {portfolio_return*100:.2f}%, you can expect a <b>final value</b> of <b>Rs. {int(growth_data['Expected Value'].iloc[-1])}.</b>"    
        )

    return growth_data, investmentgrowth_message, fig