import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="📊")

# Custom CSS untuk mengecilkan tulisan metrik dan mempercantik box
st.markdown("""
    <style>
    /* Mengecilkan Label Metrik (Judul atas) */
    [data-testid="stMetricLabel"] {
        font-size: 13px !important;
        color: #666666 !important;
    }
    /* Mengecilkan Angka Metrik (Nilai utama) */
    [data-testid="stMetricValue"] {
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #1f1f1f !important;
    }
    /* Mengatur box metrik agar lebih ramping */
    [data-testid="stMetric"] {
        background-color: #ffffff;
        padding: 5px 10px !important;
        border-radius: 8px;
        border: 1px solid #eeeeee;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Samareta Business Intelligence")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("Konfigurasi Secrets bermasalah! Cek menu Secrets di Streamlit Cloud.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Data")
    uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])
    st.divider()
    
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file)
        # Menghilangkan tab tersembunyi & spasi
        df_raw = df_raw.applymap(lambda x: x.strip().replace('\t', '') if isinstance(x, str) else x)
        df_raw.columns = [c.strip().replace('\t', '') for c in df_raw.columns]
        
        # Format Tanggal
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'], dayfirst=True, errors='coerce')
        
        min_date = df_raw['Created Time'].min().date()
        max_date = df_raw['Created Time'].max().date()
        date_range = st.date_input("Rentang Waktu", [min_date, max_date])
        
        sel_status = st.multiselect("Status Pesanan", df_raw['Order Status'].unique().tolist(), default=["Selesai"])

# --- PROSES DATA ---
if uploaded_file:
    try:
        df = df_raw.copy()
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]
        df = df[df['Order Status'].isin(sel_status)]

        col_uang = 'SKU Subtotal After Discount'
        df[col_uang] = pd.to_numeric(df[col_uang], errors='coerce').fillna(0)

        # --- FUNGSI HITUNG MODAL (SINTAKS FIX) ---
        def get_cogs(row):
            nama_produk = str(row['Product Name']).lower()
            quantity = row['Quantity']
            # Cari kunci terpanjang dulu
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for kunci in sorted_keys:
                kunci_low = kunci.lower()
                if kunci_low in nama_produk:
                    if "paket" in kunci_low:
                        return DAFTAR_MODAL[kunci]
                    return DAFTAR_MODAL[kunci] * quantity
            return 0

        # Baris yang tadi error dipastikan lengkap di sini:
        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df[col_uang] - df['Total_Modal']

        # WARNING PRODUK 0
        unmapped = df[df['Total_Modal'] == 0]['Product Name'].unique()
        if len(un
