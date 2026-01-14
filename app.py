import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
from datetime import datetime

# --- 1. CONFIG ---
st.set_page_config(page_title="Samareta Pro: Filter Tanggal", layout="wide", page_icon="💰")

st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #1a1a1a !important; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets Error! Pastikan MODAL_PRODUK sudah terisi.")
    st.stop()

# --- 3. FUNGSI PEMBERSIH ---
def super_clean_text(text):
    if pd.isna(text): return ""
    text = str(text).replace('\t', ' ').replace('\n', ' ')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    return ' '.join(text.split()).lower()

st.title("💰 Samareta Pro: Laporan per Periode")

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Data & Filter")
    f_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("2. Upload CSV SETTLEMENT", type=["csv"])
    st.divider()
    
    # Placeholder untuk filter tanggal (akan muncul setelah file diupload)
    date_range = None

if f_order and f_settle:
    try:
        # Load Data
        df_o = pd.read_csv(f_order)
        try:
            df_s = pd.read_csv(f_settle, sep=';')
        except:
            df_s = pd.read_csv(f_settle)

        # Cleaning
        df_o.columns = [c.replace('\t', '').strip() for c in df_o.columns]
        df_s.columns = [c.replace('\t', '').strip().replace('  ', ' ') for c in df_s.columns]
        df_o = df_o.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)
        df_s = df_s.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)

        # Sync Data
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=['Order/adjustment ID'])
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = next(c for c in df_o.columns if 'Created Time' in c or 'Order create time' in c)
        
        df_final = pd.merge(df_s, df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time_o]], 
                           left_on='Order/adjustment ID', right_on=col_id_o, how='inner')

        # FIX TANGGAL
        df_final['Tanggal_Fix'] = pd.to_datetime(df_final[col_time_o], dayfirst=True, errors='coerce')
        
        # --- INPUT TANGGAL DI SIDEBAR ---
        min_date = df_final['Tanggal_Fix'].min().date()
        max_date = df_final['Tanggal_Fix'].max().date()
        
        with st.sidebar:
            st.write("### 📅 Pilih Periode")
            date_range = st.date_input(
                "Rentang Waktu:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )

        # FILTER DATA BERDASARKAN TANGGAL
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            df_final = df_final[
                (df_final['Tanggal_Fix'].dt.date >= start_date) & 
                (df_final['Tanggal_Fix'].dt.date <= end_date)
            ]

        # --- LOGIKA MATCHING ---
        def logic_matching(row):
            target = super_clean_text(f"{row['Product Name']} {row['Variation']}")
            qty = int(float(row['Quantity']))
            match_key, price = "TIDAK DITEMUKAN", 0
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if super_clean_text(k) in target:
                    match_key, price = k, DAFTAR_MODAL[k]
                    break
            is_paket = any(x in target or x in super_clean_text(match_key) for x in ["paket", "isi", "bundle"])
            total_m = price if is_paket else price * qty
            return pd.Series([match_key, total_m])

        df_final[['Key_Secrets', 'Total_Modal']] = df_final.apply(logic_matching, axis=1)

        # --- HITUNG PROFIT ---
        df_final['Settlement'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Net_Rev'] = df_final['Settlement'] - df_final['Ongkir_C']
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # --- TAMPILAN METRIK ---
        st.divider()
        st.subheader(f"📊 Laporan Periode: {date_range[0]} s/d {date_range[1]}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omset Net", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Final", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        # TABEL RINCIAN
        st.dataframe(df_final[['Tanggal_Fix', 'Product Name', 'Variation', 'Key_Secrets', 'Total_Modal', 'Profit']], use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
