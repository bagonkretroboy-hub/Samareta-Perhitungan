import streamlit as st
import pandas as pd
import google.generativeai as genai
from datetime import datetime

# --- CONFIG ---
st.set_page_config(page_title="Samareta Business Suite", layout="wide", page_icon="📊")
st.title("📊 Samareta Business Dashboard")

# --- LOAD SECRETS ---
try:
    daftar_modal = st.secrets["MODAL_PRODUK"]
except:
    daftar_modal = {"DEFAULT": 25000}

# --- SIDEBAR: FILTER CANGGIH ---
with st.sidebar:
    st.header("🔍 Filter Dashboard")
    uploaded_file = st.file_uploader("Upload Data TikTok (CSV)", type=["csv"])
    st.divider()
    
    if uploaded_file:
        # Load data awal untuk filter
        df_raw = pd.read_csv(uploaded_file)
        
        # Bersihkan tanggal (TikTok sering ada karakter aneh di kolom tanggal)
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'].str.strip(), dayfirst=True, errors='coerce')
        
        # 1. Filter Tanggal
        min_date = df_raw['Created Time'].min().date()
        max_date = df_raw['Created Time'].max().date()
        date_range = st.date_input("Rentang Waktu", [min_date, max_date])
        
        # 2. Filter Status
        all_status = df_raw['Order Status'].unique().tolist()
        selected_status = st.multiselect("Status Pesanan", all_status, default=["Selesai"])
        
        # 3. Cari Barang
        search_query = st.text_input("Cari Nama Barang", "")

# --- LOGIKA UTAMA ---
if uploaded_file:
    try:
        df = df_raw.copy()

        # Apply Filter Tanggal
        if len(date_range) == 2:
            start_date, end_date = date_range
            df = df[(df['Created Time'].dt.date >= start_date) & (df['Created Time'].dt.date <= end_date)]

        # Apply Filter Status
        if selected_status:
            df = df[df['Order Status'].isin(selected_status)]
            
        # Apply Filter Nama
        if search_query:
            df = df[df['Product Name'].str.contains(search_query, case=False, na=False)]

        # Identifikasi Kolom Uang (TikTok: 'SKU Subtotal After Discount' atau 'Order Amount')
        col_uang = 'SKU Subtotal After Discount' # Kolom ini paling akurat per item
        
        if col_uang in df.columns:
            # Hitung Modal Otomatis
            def hitung_modal(row):
                nama = str(row['Product Name']).lower()
                qty = row['Quantity']
                for k, v in daftar_modal.items():
                    if k.lower() in nama: return v * qty
                return st.secrets.get("MODAL_DEFAULT", 25000) * qty

            df['Total_Modal'] = df.apply(hitung_modal, axis=1)
            df['Profit'] = df[col_uang] - df['Total_Modal']
            
            # --- DISPLAY METRICS ---
            m1, m2, m3, m4 = st.columns(4)
            total_omset = df[col_uang].sum()
            total_profit = df['Profit'].sum()
            
            m1.metric("Total Omset", f"Rp {total_omset:,.0f}")
            m2.metric("Total Modal", f"Rp {df['Total_Modal'].sum():,.0f}")
            m3.metric("Profit Bersih", f"Rp {total_profit:,.0f}")
            m4.metric("Jatah Per Orang", f"Rp {total_profit/3:,.0f}")

            # --- VISUALISASI SEDERHANA ---
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📍 Penjualan Per Provinsi")
                prov_sales = df.groupby('Province')[col_uang].sum().sort_values(ascending=False).head(5)
                st.bar_chart(prov_sales)
            
            with c2:
                st.subheader("📦 Top Produk (Qty)")
                top_prod = df.groupby('Product Name')['Quantity'].sum().sort_values(ascending=False).head(5)
                st.bar_chart(top_prod)

            # --- AI ANALYSIS ---
            st.divider()
            st.subheader("🤖 Analisis Manager AI")
            user_ask = st.text_area("Tanya AI (Contoh: Analisis penjualan di Jawa Barat atau saran untuk stok)")
            
            if st.button("Jalankan AI"):
                api_key = st.secrets["GEMINI_API_KEY"]
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Kirim ringkasan data agar hemat token dan akurat
                summary_data = df.groupby('Product Name').agg({
                    'Quantity': 'sum',
                    col_uang: 'sum',
                    'Profit': 'sum'
                }).head(20).to_string()

                prompt = f"""
                Data Bisnis Samareta:
                Periode: {date_range}
                Total Profit: Rp {total_profit:,.0f}
                Ringkasan Produk:
                {summary_data}

                Pertanyaan: {user_ask}
                """
                
                with st.spinner("AI sedang menganalisis data..."):
                    res = model.generate_content(prompt)
                    st.info(res.text)

        else:
            st.error("Kolom keuangan tidak ditemukan!")

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
else:
    st.info("Silakan upload file CSV TikTok di sidebar untuk memulai.")
