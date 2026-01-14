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
    st.error("Konfigurasi Secrets Error! Pastikan MODAL_PRODUK sudah diisi.")
    st.stop()

st.title("💰 Samareta Pro: Fix Tanggal & Modal")

# --- FUNGSI PEMBERSIH EKSTRA ---
def clean_all(df):
    # Buang spasi dan karakter tab \t di nama kolom
    df.columns = [str(c).replace('\t', '').strip() for c in df.columns]
    # Buang spasi dan tab di setiap sel data
    df = df.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)
    return df

# --- SIDEBAR ---
with st.sidebar:
    st.header("Upload Data")
    f_order = st.file_uploader("1. Upload SEMUA PESANAN (CSV)", type=["csv"])
    f_settle = st.file_uploader("2. Upload SETTLEMENT (CSV)", type=["csv"])

if f_order and f_settle:
    try:
        # Load Raw
        df_o_raw = pd.read_csv(f_order)
        try:
            df_s_raw = pd.read_csv(f_settle, sep=';')
        except:
            df_s_raw = pd.read_csv(f_settle)

        # Jalankan Pembersihan Karakter Hantu
        df_o = clean_all(df_o_raw)
        df_s = clean_all(df_s_raw)

        # Mapping Kolom
        # TikTok Settlement ID biasanya 'Order/adjustment ID'
        # TikTok Order ID biasanya 'Order ID'
        col_id_s = 'Order/adjustment ID'
        col_id_o = 'Order ID'
        col_time = 'Created Time' # Kolom tanggal di file pesanan

        # Filter hanya tipe Order
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=[col_id_s])
        
        # Merge
        df_final = pd.merge(
            df_s, 
            df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time]], 
            left_on=col_id_s, 
            right_on=col_id_o, 
            how='inner'
        )

        # --- FIX TANGGAL ---
        # Mencoba parsing dengan format hari di depan (Dayfirst)
        df_final['Time_Parsed'] = pd.to_datetime(df_final[col_time], dayfirst=True, errors='coerce')
        
        # --- LOGIKA MODAL ---
        def get_modal_v5(row):
            text = f"{row['Product Name']} {row['Variation']}".lower()
            qty = int(float(row['Quantity'])) if row['Quantity'] else 1
            
            match_key = "TIDAK DITEMUKAN"
            base_price = 0
            
            # Sort keys by length (paling detail dulu)
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in text:
                    match_key = k
                    base_price = DAFTAR_MODAL[k]
                    break
            
            is_paket = any(x in text or x in match_key.lower() for x in ["paket", "isi", "bundle"])
            total_m = base_price if is_paket else base_price * qty
            tipe = "📦 Paket" if is_paket else f"🛍️ Satuan (x{qty})"
            
            return pd.Series([match_key, base_price, total_m, tipe])

        df_final[['Key', 'Hrg_Secret', 'Total_Modal', 'Tipe']] = df_final.apply(get_modal_v5, axis=1)

        # --- HITUNG PROFIT ---
        df_final['Settlement_Amt'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Shipping_Customer'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        
        # Profit = (Uang Masuk - Ongkir Pembeli) - Modal
        df_final['Net_Rev'] = df_final['Settlement_Amt'] - df_final['Shipping_Customer']
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # --- METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omset Bersih", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Total Profit", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        # --- TABEL AUDIT ---
        st.subheader("📋 Rincian Transaksi (Cek Kolom Time_Parsed)")
        # Tampilkan kolom penting untuk verifikasi manual
        st.dataframe(df_final[['Time_Parsed', 'Product Name', 'Key', 'Tipe', 'Total_Modal', 'Profit']], use_container_width=True)

        if df_final['Time_Parsed'].isnull().any():
            st.warning("⚠️ Beberapa tanggal gagal dibaca. Pastikan kolom 'Created Time' tersedia di file Pesanan.")

    except Exception as e:
        st.error(f"Gagal memproses data: {e}")
