import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Settlement Intelligence", layout="wide", page_icon="💰")

# --- CUSTOM CSS (FIX DARK MODE CONTRAST) ---
st.markdown("""
    <style>
    /* Mengatur kotak metrik agar kontras tinggi di Dark Mode Chrome */
    [data-testid="stMetric"] {
        background-color: #1e1e1e !important; 
        border: 1px solid #333333 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }
    /* Warna Label (Teks Kecil) */
    [data-testid="stMetricLabel"] {
        color: #bbbbbb !important;
        font-size: 14px !important;
    }
    /* Warna Angka (Teks Besar) */
    [data-testid="stMetricValue"] {
        color: #00ff00 !important; /* Hijau Terang agar mudah dibaca */
        font-size: 24px !important;
        font-weight: bold !important;
    }
    /* Memperbaiki tampilan tabel agar tetap nyaman di mata */
    .stDataFrame {
        border: 1px solid #444;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Settlement Intelligence")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Konfigurasi Secrets (MODAL_PRODUK / GEMINI_API_KEY) tidak ditemukan!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN (File Biasa)", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (File Income)", type=["csv"])
    st.caption("Tips: File Income TikTok biasanya menggunakan pemisah titik koma (;)")

# --- PROSES DATA UTAMA ---
if file_order and file_settle:
    try:
        # 1. Load Data
        df_order = pd.read_csv(file_order)
        # File Settlement Anda menggunakan pemisah ;
        df_settle = pd.read_csv(file_settle, sep=';')
        
        # Bersihkan nama kolom dari spasi berlebih
        df_order.columns = [c.strip() for c
