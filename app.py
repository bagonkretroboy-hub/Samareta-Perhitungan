import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Settlement Pro", layout="wide", page_icon="💰")

# Custom CSS: Metrik Rapi
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
except Exception:
    st.error("Secrets tidak ditemukan! Pastikan MODAL_PRODUK dan GEMINI_API_KEY tersedia.")
    st.stop()

# --- SIDEBAR: DOUBLE UPLOAD ---
with st.sidebar:
    st.header("⚙️ Unggah Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN (Ada Nama Produk)", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (Ada Uang Bersih)", type=["csv"])
    
    date_range = []
    sel_status = []

# --- LOGIKA PENGGABUNGAN DATA ---
if file_order and file_settle:
    try:
        # Load data
        df_order = pd.read_csv(file_order)
        df_settle = pd.read_csv(file_settle)
        
        # Bersihkan nama kolom (hapus spasi tersembunyi)
        df_
