import pandas as pd
import plotly.express as px
from dateutil import relativedelta
from datetime import datetime

def investmentGrowth_calci(equity_return, debt_return, equity_allocation,
                           onetime_amount, sip_amount, tenure_months,
                           annual_SIP_increment_in, sip_increment=0):

    debt_allocation = 100 - equity_allocation
    if annual_SIP_increment_in != 'Nil':
        no_inc = tenure_months // 12 + (1 if tenure_months % 12 > 0 else 0)

                            
    # SIP Cashflow
    if annual_SIP_increment_in == 'Nil':
        sip_amt = [sip_amount for _ in range(tenure_months)]
    elif annual_SIP_increment_in == 'Amount':
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

    equity_return /= 100
    debt_return /= 100
    portfolio_return = equity_return * equity_allocation/100 + debt_return * debt_allocation/100
    portfolio_return_mth = (portfolio_return+1)**(1/12)-1

    initial_date = datetime.today().strftime('%Y-%m-%d')
    value_dates = [(datetime.strptime(initial_date, '%Y-%m-%d') +
                   relativedelta.relativedelta(months=i)).strftime('%Y-%m-%d')
                   for i in range(tenure_months)]

    inc_principle = [onetime_amount + sip_amount]
    for i in range(1, tenure_months):
        inc_principle.append(inc_principle[-1] + sip_amt[i])

    inc_values = [inc_principle[0]]
    for i in range(1, tenure_months):
        inc_values.append(round(inc_values[-1]*(1+portfolio_return_mth) + sip_amt[i]))

    growth_data = pd.DataFrame({
        'Date': value_dates,
        'Invested Amount': inc_principle,
        'Expected Value': inc_values
    })

    fig = px.line(growth_data, x='Date', y=['Invested Amount','Expected Value'],
                  title='Expected Growth of Investment')
    return growth_data, fig
