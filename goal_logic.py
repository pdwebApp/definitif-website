# Importing all the necessary libraries
import pandas as pd
import numpy as np
import numpy_financial as npf
import plotly.express as px

# Import time related 
from dateutil import relativedelta
from datetime import datetime, timedelta
from pandas.tseries.offsets import Day, MonthEnd

def incrementalSIP(pf_return, tenure, amount, quantSIPinc):
# Number of increments (If there are any kind of increments in monthly investments)
    
    tenure = tenure + 1
    no_inc = np.nan
    if tenure  % 12 > 0:
        no_inc = tenure // 12 + 1
    else:
        no_inc = tenure // 12

    sip_amt = []
    for multiple in range(no_inc):
        for mth in range(1,12+1):
            sip_amt.append(round(amount*(1 + quantSIPinc)**multiple))
    if tenure % 12 > 0:
        sip_amt = sip_amt[:-(no_inc*12 - tenure)]
    sip_amt[-1] = 0
    # Incremental Principle Amounts
    inc_principle = [amount]
    for i in range(1,tenure):
        inc_principle.append(inc_principle[-1] + sip_amt[i])

    # Incremental Investment Values
    inc_values = [inc_principle[0]]
    for i in range(1,tenure):
        inc_values.append(round(inc_values[-1]*(1+pf_return) + sip_amt[i]))
    values = [inc_principle,inc_values]   
    return values


# Main Function for Goal Calculations
def goalCalci(curCost_goal,investTenure,currentSavings_goal,expInflation,invApproach,percentage_SIPinc,):
    # Derived Values
    # Inflation to float
    inflation = expInflation/100
    # Error factor
    errorAcceptFactor = int(1000)
    # Annual Percentage in SIP - Converting to float/percentage
    quantumSIPinc = percentage_SIPinc/100
    # Future Monthly Expenses at the time of Goal
    futCost_goal = int(curCost_goal*(1 + inflation)**investTenure)
    # Expected Returns during accumulation Phase - Converting the Annual Returns to Monthly
    annual_inv_return = invApproach / 100
    portfolio_return_mth = (1 + annual_inv_return)**(1/12) - 1

    
    # What needs to be done to achieve the amount required for Goal
    # Total Required Amount when the Goal is to be achieved
    amtRequired_goal = int(futCost_goal)
    
    # Future Value of Current Savings
    value_currentSavings = int(currentSavings_goal*(1 + portfolio_return_mth)**(investTenure*12-1))
    
    # Lumpsum (One Time) Investment Required today
    investToday = int(
                        (amtRequired_goal - value_currentSavings) /
                        ((1 + annual_inv_return) ** investTenure)
                    )
    # Monthly SIP needed to achieve the target principal amount required on the first yaer of retirement
    if investToday <= 0:
        amountSIP = 0
    else:
        amountSIP = int(npf.pmt(portfolio_return_mth, investTenure*12, 0, 
                            -(amtRequired_goal-value_currentSavings), 0))
    
    # Creating dummy dates based on todays dates (Taking month start)
    initial_date = datetime.today().strftime('%Y-%m-%d')
    
    # Make 02-29 to 02-28 where applicable
    if '02-29' in initial_date:
        initial_date = datetime.strptime(initial_date, '%Y-%m-%d').replace(day=28).strftime('%Y-%m-%d')
            
    # Extracting the dates based on the chosen tenure
    value_dates = [initial_date]
    for month in range(1,investTenure*12+1):
        value_dates.append((datetime.strptime(initial_date, '%Y-%m-%d') +     \
                            relativedelta.relativedelta(months=month)).strftime('%Y-%m-%d'))
    
    # Dataframe to save the investment schedule
    incSIPschedule = pd.DataFrame(index = value_dates, columns = ['SIP Amount', 'SIP Value'])

    if investToday <= 0:
        incSIPschedule['SIP Amount'] = 0
        incSIPschedule['SIP Value'] = 0
    else:
        # Incremental SIP value - Back Calculation
        period = investTenure*12
        upperSIPlimit = int(npf.pmt(portfolio_return_mth, period, 0, -(amtRequired_goal-value_currentSavings), 0))
        # Setting up the Left Right and Mid point of the data for Binary Search
        sipStart_left = int(1)
        sipStart_right = int(upperSIPlimit)
        sipStart_mid = int((sipStart_left + sipStart_right)/2)
        # Just a dummy value to start the while loop
        sipError_mid = errorAcceptFactor*2
        
        # Loop runs as long as the error factor is above "errorAcceptFactor"
        while (sipError_mid >= errorAcceptFactor):   
            value_left = incrementalSIP(portfolio_return_mth, period, sipStart_left, quantumSIPinc)
            value_right = incrementalSIP(portfolio_return_mth, period, sipStart_right, quantumSIPinc)
            value_mid = incrementalSIP(portfolio_return_mth, period, sipStart_mid, quantumSIPinc)
        # Error Values
            sipError_left = abs(value_left[1][-1] - (amtRequired_goal-value_currentSavings))
            sipError_right = abs(value_right[1][-1] - (amtRequired_goal-value_currentSavings))
            sipError_mid = abs(value_mid[1][-1] - (amtRequired_goal-value_currentSavings))
        # Binary Search method to eleminate data quickly
            if (sipError_mid == sipError_left) & (sipError_mid == sipError_left):
                sipError_mid = errorAcceptFactor - 1
            elif sipError_left == max(sipError_left, sipError_mid, sipError_right):
                sipStart_left = sipStart_mid
            elif sipError_right == max(sipError_left, sipError_mid, sipError_right):
                sipStart_right = sipStart_mid
            sipStart_mid = int((sipStart_left + sipStart_right)/2)
        # Allocating the data to respective fields in the dataframe
        incSIPschedule['SIP Amount'] = value_mid[0]
        incSIPschedule['SIP Value'] = value_mid[1]
    
    # Current Savings Schedule
    savingsSchedule = pd.DataFrame(index = value_dates, columns = ['Savings Amount', 'Savings Value'])
    if currentSavings_goal > 0:
        savingsSchedule['Savings Amount'] = currentSavings_goal
        savingsValue = [currentSavings_goal]
        
        for i in range(len(savingsSchedule.index)-1):
            savingsValue.append(int(savingsValue[i]*(1+portfolio_return_mth)))
    
        savingsSchedule['Savings Value'] = savingsValue
    else:
        savingsSchedule['Savings Amount'] = 0
        savingsSchedule['Savings Value'] = 0
    
    # Investment Journey
    goalSchedule = pd.concat([incSIPschedule,savingsSchedule], axis=1)
    goalSchedule['Investment Amount'] = (
            goalSchedule['SIP Amount'] + goalSchedule['Savings Amount']
        )
    goalSchedule['Expected Value'] = (
            goalSchedule['SIP Value'] + goalSchedule['Savings Value']
        )
    # FORCE NUMERIC
    goalSchedule = goalSchedule.apply(pd.to_numeric, errors='coerce')

    # Investment Schedule for Graph
    goalSchedule_graph = pd.DataFrame({
        'Date': goalSchedule.index.astype(str).to_list(),
        'Investment Amount': goalSchedule['Investment Amount'].to_list(),
        'Expected Value': goalSchedule['Expected Value'].to_list()
        })

    # Plotting a graph for pre retirement Investmentflow
    # ----------------------------
    # Goal Corpus Growth
    # ----------------------------

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    
    fig1 = make_subplots(specs=[[{"secondary_y": False}]])

    fig1.add_trace(
        go.Scatter(
            x=goalSchedule_graph['Date'].astype(str).tolist(),
            y=goalSchedule_graph['Expected Value'].tolist(),
            name="Expected Value",
            mode="lines+markers",
            hovertemplate=
            "<b>Expected Value</b>: ₹%{y:,.0f}" +
            "<extra></extra>"
        )
    )    
    fig1.add_trace(
        go.Scatter(
            x=goalSchedule_graph['Date'].astype(str).tolist(),
            y=goalSchedule_graph['Investment Amount'].tolist(),
            name="Investment Amount",
            mode="lines+markers",
            hovertemplate=
            "<b>Investment Amount</b>: ₹%{y:,.0f}" +
            "<extra></extra>"
        )
    )
    
    fig1.update_layout(
        title="",
        template="plotly_white",
        xaxis_title="",
        yaxis_title="",
        autosize=True,
        margin=dict(l=5,r=5,t=10,b=5),
        legend=dict(x=0.01,y=0.99,bgcolor="rgba(0,0,0,0)",borderwidth=0),
        hovermode="x unified",
        yaxis=dict(
            separatethousands=True
        )
    )
    fig1.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color="white"),
        xaxis=dict(gridcolor="#444"),
        yaxis=dict(gridcolor="#444")
    )
    
    fig1.update_xaxes(showline=True, showgrid=False)
    fig1.update_yaxes(showline=True, showgrid=False)

    # Force convert numpy arrays to Python lists (prevents binary encoding)
    fig1_dict = fig1.to_dict()

    for trace in fig1_dict["data"]:
        if hasattr(trace["x"], "tolist"):
            trace["x"] = trace["x"].tolist()
        if hasattr(trace["y"], "tolist"):
            trace["y"] = trace["y"].tolist()

    fig1 = go.Figure(fig1_dict)

    # Requirement Message
    requirement_message = (
        f"At the time when your goal approaches, you will need Rs. {int(amtRequired_goal)} \n\n"
        f"and currently you have earmarked Rs. {int(currentSavings_goal)} for the same."
    )
    
    if investToday <= 0:
        goal_message = (
            f"You’re all set! Your current savings cover your needs, \n\n"
            f"and with our investment guidance, you’ll stay perfectly aligned with your goals—today, tomorrow, and beyond."
        )
    else:
        if (quantumSIPinc == 0) or (investTenure <=1):
            goal_message = (
                f"We can help you implement either of the <b>two</b> options to achieve your goal successfully.<br><br>"
                f"<i>Option 1. Invest <b>Rs. {investToday}</b> today for the next <b>{investTenure}</b> years.<br></i>"
                f"<i>Option 2. Invest <b>Rs. {amountSIP}</b> monthly for the next <b>{investTenure}</b> years.</i>"
            )
        else:
            goal_message = (
                f"We can help you implement either of the <b>three</b> options to achieve your goal.<br><br>"
                f"<i>Option 1. Invest <b>Rs. {investToday}</b> today for the next <b>{investTenure}</b> years.<br></i>"
                f"<i>Option 2. Invest <b>Rs. {amountSIP}</b> monthly for the next <b>{investTenure}</b> years.<br></i>"
                f"<i>Option 3. Start investing <b>Rs. {incSIPschedule['SIP Amount'].iloc[0]}</b> monthly "
                f"and increase it by <b>{percentage_SIPinc}%</b> annually.</i>"
            )

    return goalSchedule, fig1, requirement_message, goal_message