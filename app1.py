#python -m streamlit run app1.py
import pandas as pd
import numpy as np
from pathlib import Path
from lxml import etree
import streamlit as st
import pickle
import gzip


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
df = pd.DataFrame(st.session_state.orders)
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
