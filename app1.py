#python -m streamlit run app1.py
import pandas as pd
import numpy as np
from pathlib import Path
from lxml import etree
import streamlit as st
import pickle
import gzip

#import os
#st.write("Current files:", os.listdir())
st.set_page_config(layout="wide")

@st.cache_data
def load_data():
    with gzip.open("span_data.pkl.gz", "rb") as f:
        return pickle.load(f)

data = load_data()

lot_size = data["lot_size"]
OTH_rate = data["OTH_rate"]
OTM_rate = data["OTM_rate"]
fut_name_expiry = data["fut_name_expiry"]
fut_name_price = data["fut_name_price"]
underlying_price = data["underlying_price"]
call_name_expiry_strike = data["call_data"]
put_name_expiry_strike = data["put_data"]
call_expiry_strike = data["call_expiry_strike"]
put_expiry_strike = data["put_expiry_strike"]
deriv_names = data["deriv_names"]
spread_name_date1_date2=data["spread_name_date1_date2"]
call_expiry=data["call_expiry"]
put_expiry=data["put_expiry"]

# -----------------------------
# SESSION STATE
# -----------------------------
if "orders" not in st.session_state:
    st.session_state.orders = []

# -----------------------------
# UI
# -----------------------------
st.title("📊 Margin Calculator")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    instrument = st.selectbox("Instrument", ["Future", "Option"])

with col2:
    symbol = st.selectbox("Symbol", deriv_names)

if instrument == "Option":
    with col3:
        optn_type = st.selectbox("Option Type", ["Call", "Put"])
else:
    optn_type = ""

if instrument == "Future":
    expiry_list = sorted({k[1] for k in fut_name_expiry if k[0] == symbol})
elif optn_type=="Call":
    expiry_list= sorted(call_expiry.get((symbol)))
elif optn_type=="Put":
    expiry_list= sorted(put_expiry.get((symbol)))

with col4:
    expiry = st.selectbox("Expiry", expiry_list)

if instrument == "Option":
    if optn_type == "Call":
        strikes = call_expiry_strike.get((symbol, expiry), [])
    else:
        strikes = put_expiry_strike.get((symbol, expiry), [])

    with col5:
        strike = st.selectbox("Strike", strikes if strikes else [0])
else:
    strike = 0

col6, col7 = st.columns(2)

with col6:
    subcol1, subcol2 = st.columns([2,1])

    with subcol1:
        qty = st.number_input("Quantity", min_value=1, value=1)

    with subcol2:
        st.markdown("**Lot Size**")
        st.write(int(lot_size.get(symbol, 0)))

with col7:
    side = st.radio("Side", ["Buy","Sell"])

# -----------------------------
# ADD ORDER
# -----------------------------
if st.button("Add Order"):
    st.session_state.orders.append({
        "Type": instrument,
        "Symbol": symbol,
        "Expiry": expiry,
        "OptionType": optn_type,
        "Strike": strike,
        "Qty": qty,
        "Side": side
    })

if st.button("Reset"):
    st.session_state.orders = []

# -----------------------------
# DISPLAY TABLE
# -----------------------------
st.subheader("📋 Orders")

if st.session_state.orders:

    header = st.columns([1,1,1,1,1,1,1,0.5])
    headers = ["Type","Symbol","Expiry","OptType","Strike","Qty","Side",""]
    
    for col, h in zip(header, headers):
        col.markdown(f"**{h}**")

    for i, order in enumerate(st.session_state.orders):
        row = st.columns([1,1,1,1,1,1,1,0.5])

        row[0].write(order["Type"])
        row[1].write(order["Symbol"])
        row[2].write(order["Expiry"])
        row[3].write(order["OptionType"])
        row[4].write(order["Strike"])
        row[5].write(order["Qty"])
        row[6].write(order["Side"])

        if row[7].button("❌", key=f"delete_{i}"):
            st.session_state.orders.pop(i)
            st.rerun()
#st.dataframe(df, use_container_width=True)
#=================================================================================================
#Creating a function to find span margin and exposure margin for futures
def future_margins(symbol,expiry_date,qty,b_s_side):
    risk_array=fut_name_expiry.get((symbol,expiry_date))
    price=fut_name_price.get((symbol,expiry_date))
    if b_s_side=="Buy":
        value=max(risk_array)
    else:
        value=abs(min(risk_array))
    lot=lot_size.get(symbol)
    span_margin=value*lot*qty
    if OTH_rate.get((symbol)) is None:
        exposure_margin=0.02*qty*price*lot
    else:
        exposure_margin=OTH_rate.get((symbol))*qty*price*lot
    premium=0
    paid_received=""
    total_margin=span_margin+exposure_margin
    return span_margin,exposure_margin,total_margin,premium,paid_received
#================================================================================================
#Creating a function to find span, exposure margin and premium of call option
def call_margins_premium(symbol,expiry_date,qty,strike,b_s_side):
    contract_info=call_name_expiry_strike.get((symbol, expiry_date,strike))
    price=contract_info["Price"]
    risk_array=contract_info["Risk Array"]
    u_price=underlying_price.get(symbol)
    lot=lot_size.get(symbol)
    if OTH_rate.get(symbol) is None and strike>1.1*u_price:
        exposure_rate=0.03
    elif OTH_rate.get(symbol) is None and strike<=1.1*u_price:
        exposure_rate=0.02
    elif OTM_rate.get(symbol) is not None and strike>1.3*u_price:
        exposure_rate=OTM_rate.get(symbol)
    else:
        exposure_rate=OTH_rate.get(symbol)
    if b_s_side=="Sell":
        value=abs(min(risk_array))
        paid_received="received"
        span_margin=(price+value)*lot*qty
        exposure_margin=u_price*qty*lot*exposure_rate
    else:
        paid_received="Paid"
        value=max(risk_array)
        span_margin=0
        exposure_margin=0

    premium=price*qty*lot
    total_margin=span_margin+exposure_margin
    return span_margin,exposure_margin,total_margin,premium,paid_received

#================================================================================================
#Creating a function to find span, exposure margin and premium of put option

def put_margins_premium(symbol,expiry_date,qty,strike,b_s_side):
    contract_info=put_name_expiry_strike.get((symbol, expiry_date,strike))
    price=contract_info["Price"]
    risk_array=contract_info["Risk Array"]
    u_price=underlying_price.get(symbol)
    lot=lot_size.get(symbol)
    if OTH_rate.get(symbol) is None and strike<0.9*u_price:
        exposure_rate=0.03
    elif OTH_rate.get(symbol) is None and strike>=0.9*u_price:
        exposure_rate=0.02
    elif OTM_rate.get(symbol) is not None and strike<=0.7*u_price:
        exposure_rate=OTM_rate.get(symbol)
    else:
        exposure_rate=OTH_rate.get(symbol)
    if b_s_side=="Sell":
        value=abs(min(risk_array))
        paid_received="received"
        span_margin=(price+value)*lot*qty
        exposure_margin=u_price*qty*lot*exposure_rate
    else:
        paid_received="Paid"
        value=max(risk_array)
        span_margin=0
        exposure_margin=0
    premium=price*qty*lot
    total_margin=span_margin+exposure_margin
    return span_margin,exposure_margin,total_margin,premium,paid_received
#=========================================================================================
# Updating Table
# -----------------------------
if st.session_state.orders:

    enriched_orders = []

    for order in st.session_state.orders:
        if order["Type"]=="Future":
            span, exposure, total, premium,paid_received = future_margins(order["Symbol"],order["Expiry"],order["Qty"],order["Side"])
        elif order["OptionType"]=="Call":
            span, exposure, total, premium,paid_received = call_margins_premium(order["Symbol"],order["Expiry"],order["Qty"],order["Strike"],order["Side"])
        else:
            span, exposure, total, premium,paid_received = put_margins_premium(order["Symbol"],order["Expiry"],order["Qty"],order["Strike"],order["Side"])


        enriched_orders.append({
            **order,
            "Span": round(span,2),
            "Exposure": round(exposure,2),
            "Total": round(total,2),
            "Premium":paid_received ,
            "Premium Amount": round(premium,2)
        })

    df = pd.DataFrame(enriched_orders)
    st.dataframe(df, use_container_width=True)
#=========================================================================================

# Portfolio Margins

st.subheader("📊 Combined Margin Requirements")

if st.button("Calculate Margin"):
#========================================================
#Removing consolidating similar orders
    combined_orders = {}

    for order in st.session_state.orders:
        key = (
            order["Type"],
            order["Symbol"],
            order["Expiry"],
            order["OptionType"],
            order["Strike"],
            order["Side"]
        )
        if key not in combined_orders:
            combined_orders[key] = order.copy()
        else:
            combined_orders[key]["Qty"] += order["Qty"]
    
    # Replace orders safely
    st.session_state.orders = list(combined_orders.values())
                        
    position_details={}
    #Storing relevant data in dictionary
    for order in st.session_state.orders:
        buy_sell=order["Side"]
        name=order["Symbol"]
        if order["Type"]=="Future":
            type1="Future"
            d1=order["Type"]
            d2=order["Side"]
            d3=order["Expiry"]
            d4=0
            qty=order["Qty"]
            premium=0
            strike=0
            price=fut_name_price.get((order["Symbol"],order["Expiry"]))
            lot=lot_size.get(order["Symbol"])
            if OTH_rate.get((order["Symbol"])) is None:
                exposure_rate=0.02*price*lot
            else:
                exposure_rate=OTH_rate.get((order["Symbol"]))*price*lot

            if order["Side"]=="Buy":
                risk_array=fut_name_expiry.get((order["Symbol"],order["Expiry"]))
                delta=1
            if order["Side"]=="Sell":
                risk_array=fut_name_expiry.get((order["Symbol"],order["Expiry"]))
                risk_array = [-val for val in risk_array]
                delta=-1
            exposure_margin=exposure_rate

        if order["Type"]=="Option":
            d1=order["OptionType"]
            d2=order["Side"]
            d3=order["Expiry"]
            d4=order["Strike"]
            qty=order["Qty"]
            u_price=underlying_price.get((order["Symbol"]))
            strike=order["Strike"]
            
            if order["OptionType"]=="Call":
                type1="Call"
                contract_info=call_name_expiry_strike.get((order["Symbol"], order["Expiry"],order["Strike"]))
                price=contract_info["Price"]
                risk_array=contract_info["Risk Array"]
                delta=abs(contract_info["Delta"])
                if order["Side"]=="Sell":
                    risk_array = [-val for val in risk_array]
                    delta=-abs(contract_info["Delta"])
                lot=lot_size.get(order["Symbol"])
                if OTH_rate.get(order["Symbol"]) is None and strike>1.1*u_price:
                    exposure_rate=0.03
                elif OTH_rate.get(order["Symbol"]) is None and strike<=1.1*u_price:
                    exposure_rate=0.02
                elif OTM_rate.get(order["Symbol"]) is not None and strike>1.3*u_price:
                    exposure_rate=OTM_rate.get(order["Symbol"])
                else:
                    exposure_rate=OTH_rate.get(order["Symbol"])

                premium=-(price)*lot*order["Qty"]
                if order["Side"]=="Sell":
                    premium=-premium
                exposure_margin=u_price*lot*exposure_rate
                if order["Side"]=="Buy":
                    exposure_margin=0

            elif order["OptionType"]=="Put":
                type1="Put"
                contract_info=put_name_expiry_strike.get((order["Symbol"], order["Expiry"],order["Strike"]))
                price=contract_info["Price"]
                risk_array=contract_info["Risk Array"]
                delta=-abs(contract_info["Delta"])
                if order["Side"]=="Sell":
                    risk_array = [-val for val in risk_array]
                    delta=abs(contract_info["Delta"])
                lot=lot_size.get(order["Symbol"])
                if OTH_rate.get(order["Symbol"]) is None and strike<0.9*u_price:
                    exposure_rate=0.03
                elif OTH_rate.get(order["Symbol"]) is None and strike>=0.9*u_price:
                    exposure_rate=0.02
                elif OTM_rate.get(order["Symbol"]) is not None and strike<=0.7*u_price:
                    exposure_rate=OTM_rate.get(order["Symbol"])
                else:
                    exposure_rate=OTH_rate.get(order["Symbol"])
                premium=-(price)*lot*order["Qty"]
                if order["Side"]=="Sell":
                    premium=-premium
                exposure_margin=u_price*lot*exposure_rate
                if order["Side"]=="Buy":
                    exposure_margin=0

        position_details[(d1,d2,d3,d4)]= {
                    "Name":name,
                    "Buy/Sell":buy_sell,
                    "Type":type1,
                    "Expiry Date":order["Expiry"],
                    "Strike":strike,
                    "Quantity": qty,
                    "Risk Array": risk_array,
                    "Delta":delta,
                    "Price":price,
                    "Exposure per unit":exposure_margin,
                    "Lot Size":lot,
                    "Premium":premium,
                }

    array = pd.DataFrame(position_details)

    # 1. Create a dictionary to store the aggregated risk array per underlying
    underlying_risk = {}

    for details in position_details.values():
        name = details["Name"]
        # Multiply the risk array by quantity (and lot size if risk array is per unit)
        # Most NSE risk arrays are per lot or per unit; adjust 'multiplier' accordingly
        multiplier1 = details["Quantity"] 
        multiplier2=details["Lot Size"]
        current_risk = [val * multiplier1*multiplier2 for val in details["Risk Array"]]
        
        if name not in underlying_risk:
            # Initialize with the first found array
            underlying_risk[name] = current_risk
        else:
            # Element-wise addition for the same underlying
            underlying_risk[name] = [sum(x) for x in zip(underlying_risk[name], current_risk)]

    # 2. Find the Max Loss (Span Margin) for each underlying
    span_margins = {}
    for name, final_array in underlying_risk.items():
        # NSE Span is usually the maximum value in the risk array
        span_margins[name] = max(final_array)

    #print("SPAN Margin per Underlying:", span_margins)
    final_workbook=[]
    for details in position_details.values():
        workbook={
            "Name":details["Name"],
            "Type":details["Type"],
            "Buy/Sell":details["Buy/Sell"],
            "Expiry Date":float(details["Expiry Date"]),
            "Strike":details["Strike"],
            "Quantity":details["Quantity"],
            "Delta":details["Delta"],
            "Price":details["Price"],
            "Exposure per unit":details["Exposure per unit"],
            "Lot Size":details["Lot Size"],
            "Premium":details["Premium"],
            "Quantity_spread":details["Quantity"]
        }
        final_workbook.append(workbook)

    priority = {
        "Future": 0,
        "Call": 1,
        "Put": 2
    }

    priority1 = {
        "Sell": 0,
        "Buy": 1
    }

    sorted_data = sorted(
        final_workbook,
        key=lambda x: (
            x["Name"],                   
            priority[x["Type"]], 
            priority1[x["Buy/Sell"]],         
            x["Expiry Date"],                   
            -int(x["Delta"])
        )
    )

    new_array = pd.DataFrame(sorted_data)
    new_array1 = pd.DataFrame(sorted_data)
    unique_name=new_array["Name"].unique()

    #Netting all the positions that are exactly opposite to each other
    for i in range(len(new_array)):
        for j in range (len(new_array)):
            if new_array.loc[i,"Quantity"]>0 and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]==new_array.loc[j,"Type"] and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"] and new_array.loc[i,"Strike"]==new_array.loc[j,"Strike"] and new_array.loc[i,"Buy/Sell"]!=new_array.loc[j,"Buy/Sell"]:
                if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                    m=new_array.loc[j,"Quantity"]
                else:
                    m=new_array.loc[i,"Quantity"]

                new_array.loc[i,"Quantity_spread"]=new_array[i,"Quantity"]-m
                new_array.loc[j,"Quantity_spread"]=new_array[j,"Quantity"]-m

    #Calculating spread margins
    #Netting spread for long future with short call (same expiry)
    #Netting spread for long future with long put (same expiry)
    for name in unique_name:
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Buy" and new_array.loc[i,"Quantity_spread"]>0:
                        if new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity_spread"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                m=new_array.loc[j,"Quantity_spread"]
                            else:
                                m=new_array.loc[i,"Quantity_spread"]
                            new_array.loc[i,"Quantity_spread"]=new_array.loc[i,"Quantity_spread"]-m
                            new_array.loc[j,"Quantity_spread"]=new_array.loc[j,"Quantity_spread"]-m
                        elif new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity_spread"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                m=new_array.loc[j,"Quantity_spread"]
                            else:
                                m=new_array.loc[i,"Quantity_spread"]
                            new_array.loc[i,"Quantity_spread"]=new_array.loc[i,"Quantity_spread"]-m
                            new_array.loc[j,"Quantity_spread"]=new_array.loc[j,"Quantity_spread"]-m
                        
    #Netting spread for short future with short put
    #Netting spread for short future with long call
    for name in unique_name:
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity_spread"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity_spread"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                m=new_array.loc[j,"Quantity_spread"]
                            else:
                                m=new_array.loc[i,"Quantity_spread"]
                            new_array.loc[i,"Quantity_spread"]=new_array.loc[i,"Quantity_spread"]-m
                            new_array.loc[j,"Quantity_spread"]=new_array.loc[j,"Quantity_spread"]-m
                        elif new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity_spread"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                m=new_array.loc[j,"Quantity_spread"]
                            else:
                                m=new_array.loc[i,"Quantity_spread"]
                            new_array.loc[i,"Quantity_spread"]=new_array.loc[i,"Quantity_spread"]-m
                            new_array.loc[j,"Quantity_spread"]=new_array.loc[j,"Quantity_spread"]-m


    #Netting spread for short call with short put (same expiry)(no consideration for strike)
    for name in unique_name:
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Call" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity_spread"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity_spread"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                m=new_array.loc[j,"Quantity_spread"]
                            else:
                                m=new_array.loc[i,"Quantity_spread"]
                            new_array.loc[i,"Quantity_spread"]=new_array.loc[i,"Quantity_spread"]-m
                            new_array.loc[j,"Quantity_spread"]=new_array.loc[j,"Quantity_spread"]-m


    #Netting spread for long call with long put (same expiry)(no consideration for strike)
    for name in unique_name:
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Call" and new_array.loc[i,"Buy/Sell"]=="Buy" and new_array.loc[i,"Quantity_spread"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity_spread"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                m=new_array.loc[j,"Quantity_spread"]
                            else:
                                m=new_array.loc[i,"Quantity_spread"]
                            new_array.loc[i,"Quantity_spread"]=new_array.loc[i,"Quantity_spread"]-m
                            new_array.loc[j,"Quantity_spread"]=new_array.loc[j,"Quantity_spread"]-m


    option_price={}
    for name in unique_name:
        option_cost=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                if new_array.loc[i,"Type"]!="Future":
                    if new_array.loc[i,"Buy/Sell"]=="Buy":
                        option_cost=option_cost-(new_array.loc[i,"Quantity"]*new_array.loc[i,"Price"])*new_array.loc[i,"Lot Size"]
                    elif new_array.loc[i,"Buy/Sell"]=="Sell":
                        option_cost=option_cost+(new_array.loc[i,"Quantity"]*new_array.loc[i,"Price"])*new_array.loc[i,"Lot Size"]
        option_price[name]={"Option Price":option_cost}
    
    #Priority 1 poistions netting
    #Netting futures with opposite direction 
    #Netting short futures with short put (with same expiry)
    exposure_margin1={}
    spread1={}
    for name in unique_name:
        exposure=0
        s_s=0
        vv=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Future" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            if new_array.loc[i,"Expiry Date"]>new_array.loc[j,"Expiry Date"]:
                                exposure=exposure+m*new_array.loc[i,"Exposure per unit"]/3
                                v=i
                            elif new_array.loc[i,"Expiry Date"]<new_array.loc[j,"Expiry Date"]:
                                exposure=exposure+m*new_array.loc[j,"Exposure per unit"]/3
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))

                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"] 
                            spread1[(name)]=s_s
                                
                        elif new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Quantity"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"] :
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+ m*(new_array.loc[i,"Exposure per unit"]+new_array.loc[j,"Exposure per unit"])
                        exposure_margin1[(name)]={"Exposure":exposure}
                        
                    

    #Priority 2 poistions netting
    #Netting long futures with short call (with same expiry)
    exposure_margin2={}
    for name in unique_name:
        exposure=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Buy" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"] :
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+ m*(new_array.loc[i,"Exposure per unit"]+new_array.loc[j,"Exposure per unit"])
                        exposure_margin2[(name)]={"Exposure":exposure}


    #Priority 5 poistions netting
    #Netting short future with long call (with same expiry)
    #Netting long future with long put (with same expiry)
    exposure_margin5={}
    for name in unique_name:
        exposure=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+(m*new_array.loc[i,"Exposure per unit"])

                    elif new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Buy" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+(m*new_array.loc[i,"Exposure per unit"])
                        
                    exposure_margin5[(name)]={"Exposure":exposure}

    #Priority 5.1 poistions netting
    #Netting short call with short put (with same expiry)
    #Netting short call with short put (with different expiry)
    exposure_margin5_1={}
    spread1_1={}
    for name in unique_name:
        exposure=0
        s_s=0
        vv=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Call" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+m*(new_array.loc[i,"Exposure per unit"]+new_array.loc[j,"Exposure per unit"])
                    elif new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Call" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Expiry Date"]!=new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+m*(new_array.loc[i,"Exposure per unit"]+new_array.loc[j,"Exposure per unit"])
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))

                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]

                            spread1_1[(name)]=s_s
                    exposure_margin5_1[(name)]={"Exposure":exposure}
    
    #Priority 6 poistions netting
    #Netting short future with long call (with different expiry)
    #Netting long future with long put (with different expiry)
    exposure_margin6={}
    spread3={}
    for name in unique_name:
        exposure=0
        s_s=0
        vv=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+ m*(new_array.loc[i,"Exposure per unit"]+new_array.loc[j,"Exposure per unit"])
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]

                    elif new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Buy" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+ m*(new_array.loc[i,"Exposure per unit"]+new_array.loc[j,"Exposure per unit"])
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]

                    exposure_margin6[(name)]={"Exposure":exposure}   
                    spread3[(name)]=s_s 

    #Priority 3 poistions netting
    #Netting short call with long call (with same expiry)
    #Netting short put with long put (with same expiry)
    exposure_margin3={}
    for name in unique_name:
        exposure=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Call" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+(m*new_array.loc[i,"Exposure per unit"])

                    elif new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Put" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Expiry Date"]==new_array.loc[j,"Expiry Date"]:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=(exposure+m*new_array.loc[i,"Exposure per unit"])

                        
                    exposure_margin3[(name)]={"Exposure":exposure}


    #Priority 4 poistions netting
    #Netting short futures with short put (with different expiry)
    #Netting long futures with short call (with different expiry)
    exposure_margin4={}
    spread2={}
    for name in unique_name:
        exposure=0
        s_s=0
        vv=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and  new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0 :
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity"]>0:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+ m*(new_array.loc[i,"Exposure per unit"]+new_array.loc[j,"Exposure per unit"])
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]

                    
                    elif new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Future" and new_array.loc[i,"Buy/Sell"]=="Buy" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Sell" and new_array.loc[j,"Quantity"]>0:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+ m*(new_array.loc[i,"Exposure per unit"]+new_array.loc[j,"Exposure per unit"])  
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]

                    exposure_margin4[(name)]={"Exposure":exposure} 
                    spread2[(name)]=s_s           


    
            
    #Priority 7 poistions netting
    #Netting Short call with long call (with same strike and different expiry)
    #Netting Short put with long put (with same strike and different expiry)
    exposure_margin7={}
    spread4={}
    for name in unique_name:
        exposure=0
        s_s=0
        vv=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Call" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Strike"]==new_array.loc[j,"Strike"]:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+(m*new_array.loc[i,"Exposure per unit"])
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]
                            
                    elif new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Put" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0 and new_array.loc[i,"Strike"]==new_array.loc[j,"Strike"]:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+(m*new_array.loc[i,"Exposure per unit"])
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]
                        
                    exposure_margin7[(name)]={"Exposure":exposure}    
                    spread4[(name)]=s_s
    


    #Priority 8 poistions netting
    #Netting Short call with long call (with different strike and different expiry)
    #Netting Short put with long put (with different strike and different expiry)
    exposure_margin8={}
    spread5={}
    for name in unique_name:
        exposure=0
        s_s=0
        vv=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                for j in range(len(new_array)):
                    if new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Call" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Call" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+(m*new_array.loc[i,"Exposure per unit"])
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]
                            
                    elif new_array.loc[i,"Name"]==new_array.loc[j,"Name"] and new_array.loc[i,"Type"]=="Put" and new_array.loc[i,"Buy/Sell"]=="Sell" and new_array.loc[i,"Quantity"]>0:
                        if new_array.loc[j,"Type"]=="Put" and new_array.loc[j,"Buy/Sell"]=="Buy" and new_array.loc[j,"Quantity"]>0:
                            if new_array.loc[i,"Quantity"]>=new_array.loc[j,"Quantity"]:
                                m=new_array.loc[j,"Quantity"]
                            else:
                                m=new_array.loc[i,"Quantity"]
                            new_array.loc[i,"Quantity"]=new_array.loc[i,"Quantity"]-m
                            new_array.loc[j,"Quantity"]=new_array.loc[j,"Quantity"]-m
                            exposure=exposure+m*new_array.loc[i,"Exposure per unit"]
                            if float(new_array.loc[i,"Expiry Date"])>float(new_array.loc[j,"Expiry Date"]):
                                v=i
                            else:
                                v=j
                            min_d=min(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            max_d=max(float(new_array.loc[i,"Expiry Date"]),float(new_array.loc[j,"Expiry Date"]))
                            if new_array.loc[i,"Quantity_spread"]>=new_array.loc[j,"Quantity_spread"]:
                                vv=new_array.loc[j,"Quantity_spread"]
                            else:
                                vv=new_array.loc[i,"Quantity_spread"]
                            s_s=s_s+vv*new_array.loc[i,"Lot Size"]*spread_name_date1_date2.get((name,str(int(min_d)),str(int(max_d))))*new_array.loc[v,"Delta"]
                                                    
                    exposure_margin8[(name)]={"Exposure":exposure}    
                    spread5[(name)]=s_s

    #Checking if any quantity is left and finding exposure of same
    exposure_margin9={}
    for name in unique_name:
        exposure=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                if new_array.loc[i,"Quantity"]>0:
                    exposure=exposure+new_array.loc[i,"Quantity"]*new_array.loc[i,"Exposure per unit"]
                exposure_margin9[(name)]={"Exposure":exposure}    

    premium_o={}
    for name in unique_name:
        premium_opt=0
        for i in range(len(new_array)):
            if name==new_array.loc[i,"Name"]:
                premium_opt=premium_opt+new_array.loc[i,"Premium"]
        premium_o[(name)]={"Premium":premium_opt}

            
    #Finding delta of the fartest expiry for a position


    f_e=0
    f_s=0
    p_p=0
    t_m=0
    security_margins=[]

    for name in unique_name:
        f_es=0
        f_ss=0
        p_ps=0
        t_ms=0
        paid_received_s=""

        
        f_es = exposure_margin1.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin2.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin3.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin4.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin5.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin5_1.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin6.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin7.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin8.get(name, {"Exposure": 0})["Exposure"] + \
        exposure_margin9.get(name, {"Exposure": 0})["Exposure"]

        f_e=f_e+f_es

        #f_e=f_e+exposure_margin1.get((name))["Exposure"]+exposure_margin2.get((name))["Exposure"]+exposure_margin3.get((name))["Exposure"]+exposure_margin4.get((name))["Exposure"]+exposure_margin5.get((name))["Exposure"]+exposure_margin6.get((name))["Exposure"]+exposure_margin7.get((name))["Exposure"]+exposure_margin8.get((name))["Exposure"]+exposure_margin9.get((name))["Exposure"]
       
        f_ss=abs(spread1.get(name,0)) + \
        abs(spread2.get(name,0)) + \
        abs(spread3.get(name,0)) + \
        abs(spread4.get(name,0)) + \
        abs(spread5.get(name,0)) + \
        abs(spread1_1.get(name,0)) + \
        span_margins.get(name, 0) + \
        option_price.get(name, {"Option Price": 0})["Option Price"]

        if f_ss<0:
            f_ss=0

        f_s=f_s+f_ss
        #f_s=f_s+delta0.get((name))["Delta"]+delta1.get((name))["Delta"]+delta2.get((name))["Delta"]+delta3.get((name))["Delta"]+delta4.get((name))["Delta"]+span_margins.get((name))+option_price.get((name))["Option Price"]
        
        p_ps= premium_o.get(name, {"Premium": 0})["Premium"]
        #p_p=p_p+premium_o.get((name))["Premium"]
        if p_ps<0:
            paid_received_s = "paid"
        elif p_ps>0:
            paid_received_s = "received"

        p_p=p_p+p_ps
        p_ps=abs(p_ps)
        
        t_ms=f_ss+f_es

        security_margins.append({
            "Symbol": name,
            "Span": round(f_ss, 2),
            "Exposure": round(f_es, 2),
            "Total Margin": round(t_ms, 2),
            "Premium": round(p_ps, 2),
            "Paid/Received": paid_received_s
        })

    if f_s<0:
        f_s=0

    if p_p<0:
        paid_received = "paid"
    elif p_p>0:
        paid_received = "received"
    else:
        paid_received = ""

    if f_s<0:
        f_s=0

    p_p=abs(p_p)

    t_m=f_s+f_e

# MARGIN OUTPUT PANEL
# -----------------------------
#Security wise margin
    st.subheader("📊 Security-wise Margin")

    sec_df = pd.DataFrame(security_margins)
    st.dataframe(sec_df, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Span Margin", f"₹{f_s:,.2f}")
        st.metric("Exposure Margin", f"₹{f_e:,.2f}")

    with col2:
        st.metric("Total Margin", f"₹{t_m:,.2f}")
        st.metric(f"Premium to be {paid_received}", f"₹{p_p:,.2f}")
