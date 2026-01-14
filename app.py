import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

# --- CONFIG ---
st.set_page_config(page_title="Samareta Pro: Fix Error", layout="wide")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Konfigurasi Secrets Error!")
    st.stop()

st.title("💰 Samareta Pro: Fix Tanggal & Harga")

# --- FUNGSI PEMBERSIH DATA ---
def clean_string(text):
    if pd.isna(text): return ""
    # Buang karakter \t (Tab), spasi di ujung, dan simbol aneh
    text = str(text).replace('\t', '').strip()
    return text

# --- SIDEBAR ---
with st.sidebar:
    f_order = st.file_uploader("Upload CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("Upload CSV SETTLEMENT", type=["csv"])

if f_order and f_settle:
    try:
        # Load Data
        df_o = pd.read_csv(f_order)
        df_s = pd.read_csv(f_settle, sep=';')
        
        # 1. BERSIHKAN SEMUA TAB DAN SPASI DI SELURUH TABEL
        df_o = df_o.applymap(clean_string)
        df_s = df_s.applymap(clean_string)
        
        # Bersihkan nama kolom
        df_o.columns = [clean_string(c) for c in df_o.columns]
        df_s.columns = [clean_string(c).replace('  ', ' ') for c in df_s.columns]

        # 2. MATCHING ID
        col_id_s = 'Order/adjustment ID'
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = 'Created Time' # Sesuai cuplikan file Anda
        
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=[col_id_s])
        df_o_clean = df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time_o]]
        
        df_final = pd.merge(df_s, df_o_clean, left_on=col_id_s, right_on=col_id_o, how='inner')

        # 3. FIX TANGGAL
        df_final['Time'] = pd.to_datetime(df_final[col_time_o], errors='coerce')
        
        # 4. FIX HARGA & MODAL
        def find_modal_v4(row):
            combined = f"{row['Product Name']} {row['Variation']}".lower()
            qty = int(row['Quantity']) if str(row['Quantity']).isdigit() else 1
            
            match_key = "TIDAK DITEMUKAN"
            price = 0
            
            # Sort keys by length
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in combined:
                    match_key = k
                    price = DAFTAR_MODAL[k]
                    break
            
            is_paket = any(x in combined or x in match_key.lower() for x in ["paket", "isi", "bundle"])
            total_m = price if is_paket else price * qty
            tipe = "📦 Paket" if is_paket else f"🛍️ Satuan (x{qty})"
            
            return pd.Series([match_key, price, total_m, tipe])

        df_final[['Key', 'Hrg_Unit', 'Total_Modal', 'Tipe']] = df_final.apply(find_modal_v4, axis=1)

        # 5. HITUNG PROFIT
        df_final['Settlement'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Net_Rev'] = df_final['Settlement'] - df_final['Ongkir_C']
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # --- TAMPILAN ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omset Net", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Final", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        # Tabel Audit Tanggal
        st.subheader("📅 Pengecekan Tanggal & Detail")
        st.dataframe(df_final[['Time', 'Product Name', 'Variation', 'Key', 'Total_Modal', 'Profit']], use_container_width=True)

    except Exception as e:
        st.error(f"Gagal memproses data: {e}")
