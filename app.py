import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

# --- CONFIG ---
st.set_page_config(page_title="Samareta Intelligence", layout="wide")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Konfigurasi Secrets Error!")
    st.stop()

st.title("💰 Samareta Pro: Fix Modal Error")

# --- SIDEBAR ---
with st.sidebar:
    f_order = st.file_uploader("Upload CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("Upload CSV SETTLEMENT", type=["csv"])

if f_order and f_settle:
    try:
        df_o = pd.read_csv(f_order)
        df_s = pd.read_csv(f_settle, sep=';')
        
        # Cleaning Kolom
        df_o.columns = [c.strip() for c in df_o.columns]
        df_s.columns = [c.replace('  ', ' ').strip() for c in df_s.columns]

        # Merge Data
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=['Order/adjustment ID'])
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = next(c for c in df_o.columns if 'Order create time' in c or 'Created Time' in c)
        
        df_o_clean = df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time_o]].drop_duplicates(subset=[col_id_o])
        df_final = pd.merge(df_s, df_o_clean, left_on='Order/adjustment ID', right_on=col_id_o, how='inner')

        # Logika Pencarian Modal
        def find_modal(row):
            # Gabungkan Nama Produk & Variasi, lalu bersihkan dari karakter aneh
            raw_text = f"{row['Product Name']} {row['Variation']}".lower()
            clean_text = re.sub(r'[^a-zA-Z0-0\s]', ' ', raw_text) # Buang simbol [] () - 
            
            match_key = "TIDAK DITEMUKAN"
            price = 0
            
            # Sort keys by length (Longest first)
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in clean_text:
                    match_key = k
                    price = DAFTAR_MODAL[k]
                    break
            
            is_paket = any(x in clean_text or x in match_key.lower() for x in ["paket", "isi", "bundle"])
            total_m = price if is_paket else price * row['Quantity']
            tipe = "📦 Paket" if is_paket else f"🛍️ Satuan (x{row['Quantity']})"
            
            return pd.Series([match_key, price, total_m, tipe])

        df_final[['Key', 'Hrg_Satuan', 'Total_Modal', 'Tipe']] = df_final.apply(find_modal, axis=1)
        
        # Hitung Uang Net
        df_final['Settlement'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Net_Rev'] = df_final['Settlement'] - df_final['Ongkir_C']
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # Tampilan Metrik
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omset Bersih", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Final", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        # Tabel Audit - Fokus pada yang ERROR
        st.subheader("⚠️ Cek Produk yang Belum Ada Modalnya")
        error_df = df_final[df_final['Key'] == "TIDAK DITEMUKAN"][['Product Name', 'Variation', 'Quantity']]
        if not error_df.empty:
            st.warning(f"Ada {len(error_df)} transaksi yang modalnya belum terdaftar!")
            st.dataframe(error_df, use_container_width=True)
        else:
            st.success("Semua produk sudah terdeteksi modalnya! ✅")

        st.divider()
        st.subheader("📋 Seluruh Transaksi")
        st.dataframe(df_final[['Order/adjustment ID', 'Product Name', 'Key', 'Tipe', 'Total_Modal', 'Profit']], use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
