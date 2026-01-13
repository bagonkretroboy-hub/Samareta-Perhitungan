import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Settlement Intelligence", layout="wide", page_icon="💰")

# Custom CSS untuk Metrik
st.markdown("""
    <style>
    [data-testid="stMetricLabel"] { font-size: 13px !important; color: #666666 !important; }
    [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: 700 !important; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 5px 10px !important; border-radius: 8px; border: 1px solid #eeeeee; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Settlement Intelligence")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Konfigurasi Secrets tidak ditemukan!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Unggah Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN (Daftar Pesanan)", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (File Income)", type=["csv"])
    st.caption("Gunakan pemisah titik koma (;) untuk file Settlement.")

# --- PROSES DATA ---
if file_order and file_settle:
    try:
        # 1. Load File Pesanan (Biasanya koma)
        df_order = pd.read_csv(file_order)
        df_order.columns = [c.strip() for c in df_order.columns]
        
        # 2. Load File Settlement (Sesuai file user: pemisah ;)
        df_settle = pd.read_csv(file_settle, sep=';')
        df_settle.columns = [c.strip() for c in df_settle.columns]

        # 3. Cari Kolom ID di File Settlement (Mencari yang mengandung 'Order/adjustment ID')
        col_id_settle = next((c for c in df_settle.columns if 'Order/adjustment ID' in c or 'Order ID' in c), None)
        # Cari Kolom ID di File Pesanan
        col_id_order = next((c for c in df_order.columns if 'Order ID' in c), None)

        if not col_id_settle or not col_id_order:
            st.error(f"Kolom ID tidak cocok. Di Settle: {col_id_settle}, Di Pesanan: {col_id_order}")
            st.stop()

        # 4. Pastikan Tipe Data sama (String) untuk penggabungan
        df_settle[col_id_settle] = df_settle[col_id_settle].astype(str).str.strip()
        df_order[col_id_order] = df_order[col_id_order].astype(str).str.strip()

        # 5. Gabungkan Data (Merge)
        df_merged = pd.merge(
