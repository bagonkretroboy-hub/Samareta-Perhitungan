import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- CONFIGURASI DASAR ---
st.set_page_config(page_title="AI Business Manager", layout="wide", page_icon="📈")
st.title("📈 AI Business Manager Pro")

# --- KONFIGURASI MODAL DARI SECRETS ---
try:
    daftar_modal = st.secrets["MODAL_PRODUK"]
except:
    daftar_modal = {"DEFAULT": 25000}

with st.sidebar:
    st.header("⚙️ Filter & Konfigurasi")
    modal_fix = st.number_input("Modal Default (Rp)", value=int(daftar_modal.get("DEFAULT", 25000)))
    
    st.divider()
    search_query = st.text_input("🔍 Cari Produk (Filter Tabel & AI)", "")
    st.info("Ketik nama produk untuk memfilter data sebelum dianalisis AI.")

uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Identifikasi Kolom
        col_pendapatan = next((c for c in df.columns if any(k.lower() in c.lower() for k in ['penghasilan', 'amount', 'settlement', 'total'])), None)
        col_nama_produk = next((c for c in df.columns if any(k in c.lower() for k in ['product', 'nama', 'item'])), None)

        if col_pendapatan and col_nama_produk:
            # 1. FILTER DATA
            if search_query:
                df = df[df[col_nama_produk].str.contains(search_query, case=False, na=False)]

            # 2. HITUNG MODAL OTOMATIS
            def get_modal(row):
                nama_item = str(row[col_nama_produk]).lower()
                qty = row.get('Quantity', 1)
                for key, harga in daftar_modal.items():
                    if key.lower() in nama_item:
                        return harga * qty
                return modal_fix * qty

            df['Modal_Baris'] = df.apply(get_modal, axis=1)
            df[col_pendapatan] = pd.to_numeric(df[col_pendapatan], errors='coerce')
            
            # 3. KALKULASI ANGKA UTAMA
            omset = df[col_pendapatan].sum()
            orders = len(df)
            total_modal = df['Modal_Baris'].sum()
            profit = omset - total_modal
            
            # 4. TAMPILAN DASHBOARD
            c1, c2, c3, c4
