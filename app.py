import streamlit as st
import pandas as pd
import google.generativeai as genai
import io

# Konfigurasi Halaman
st.set_page_config(page_title="TikTok Profit Splitter", layout="centered", page_icon="💰")

st.title("💰 TikTok Profit Splitter")
st.markdown("Aplikasi bagi hasil otomatis untuk tim 3 orang.")

# Sidebar untuk input sensitif
with st.sidebar:
    st.header("⚙️ Pengaturan")
    api_key = st.text_input("Masukkan Gemini API Key", type="password", help="Dapatkan di Google AI Studio")
    modal_fix = st.number_input("Modal per Barang (Rp)", value=25000, step=1000)
    st.info("API Key diperlukan untuk fitur Analisis AI.")

# Upload File
uploaded_file = st.file_uploader("Upload file CSV TikTok (Laporan Penghasilan)", type=["csv"])

if uploaded_file:
    # Baca Data
    try:
        df = pd.read_csv(uploaded_file)
        
        # Cari kolom pendapatan (TikTok sering mengubah nama kolom: 'Penghasilan Konten', 'Settlement Amount', dll)
        # Kita cari kolom yang mengandung kata kunci pendapatan
        keywords = ['Penghasilan', 'Amount', 'Settlement', 'Revenue', 'Total']
        target_col = None
        for col in df.columns:
            if any(key.lower() in col.lower() for key in keywords):
                target_col = col
                break

        if target_col:
            # Hitung Angka Utama
            total_omset = pd.to_numeric(df[target_col], errors='coerce').sum()
            total_order = len(df)
            total_modal = total_order * modal_fix
            profit_bersih = total_omset - total_modal
            bagi_tiga = profit_bersih / 3
            
            # Tampilan Dashboard Utama
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Total Omset", f"Rp {total_omset:,.0f}")
                st.metric("Total Order", f"{total_order} Pesanan")
            with c2:
                st.metric("Total Modal", f"Rp
