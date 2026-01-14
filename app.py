import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
from datetime import datetime

# --- 1. CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="💰")

# Custom Styling
st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #1a1a1a !important; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets Belum Terisi! Pastikan MODAL_PRODUK ada di Dashboard Streamlit.")
    st.stop()

st.title("💰 Samareta Pro: Laporan Profit & Multiplier")

# --- 3. FUNGSI PEMBERSIH (Anti-Karakter Hantu) ---
def super_clean(text):
    if pd.isna(text): return ""
    # Buang karakter tab (\t) dan newline (\n) yang sering ada di file TikTok
    text = str(text).replace('\t', ' ').replace('\n', ' ')
    # Hanya sisakan huruf dan angka (buang simbol []-() dll)
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    return ' '.join(text.split()).lower()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Data Source")
    f_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("2. Upload CSV SETTLEMENT", type=["csv"])
    
    # Placeholder untuk filter tanggal yang akan muncul nanti
    date_range = None

# --- 5. LOGIKA UTAMA ---
if f_order and f_settle:
    try:
        # Load Raw Data
        df_o = pd.read_csv(f_order)
        try:
            df_s = pd.read_csv(f_settle, sep=';')
        except:
            df_s = pd.read_csv(f_settle)

        # A. BERSIHKAN SEMUA KOLOM & DATA (PENTING!)
        df_o.columns = [c.replace('\t', '').strip() for c in df_o.columns]
        df_s.columns = [c.replace('\t', '').strip() for c in df_s.columns]
        df_o = df_o.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)
        df_s = df_s.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)

        # B. SYNC / MERGE
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=['Order/adjustment ID'])
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = next(c for c in df_o.columns if 'Created Time' in c or 'Order create time' in c)
        
        df_final = pd.merge(df_s, df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time_o]], 
                           left_on='Order/adjustment ID', right_on=col_id_o, how='inner')

        # C. FIX TANGGAL
        df_final['Tanggal_Fix'] = pd.to_datetime(df_final[col_time_o], dayfirst=True, errors='coerce')

        # --- 6. FILTER TANGGAL DI SIDEBAR (VERSI DESEMBER) ---
        with st.sidebar:
            st.divider()
            st.write("### 📅 Filter Laporan")
            
            # Jika ada tanggal yang terbaca, kita ambil default-nya
            if not df_final['Tanggal_Fix'].dropna().empty:
                start_def = df_final['Tanggal_Fix'].min().date()
                end_def = df_final['Tanggal_Fix'].max().date()
            else:
                start_def, end_def = datetime(2025,1,1).date(), datetime(2025,12,31).date()

            date_range = st.date_input(
                "Pilih Periode:",
                value=(start_def, end_def),
                min_value=datetime(2024, 1, 1).date(),
                max_value=datetime(2026, 12, 31).date() # Bisa pilih sampai akhir tahun depan
            )

        # Terapkan Filter Tanggal
        if isinstance(date_range, tuple) and len(date_range) == 2:
            df_final = df_final[
                (df_final['Tanggal_Fix'].dt.date >= date_range[0]) & 
                (df_final['Tanggal_Fix'].dt.date <= date_range[1])
            ]

        # --- 7. LOGIKA MATCHING & MULTIPLIER ---
        def get_smart_modal(row):
            combined = super_clean(f"{row['Product Name']} {row['Variation']}")
            qty_order = int(float(row['Quantity']))
            
            match_key = "TIDAK DITEMUKAN"
            base_price = 0
            
            # Cari Base Product di Secrets
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if super_clean(k) in combined:
                    match_key = k
                    base_price = DAFTAR_MODAL[k]
                    break
            
            # Deteksi Angka Isi (Multiplier)
            multiplier = 1
            find_isi = re.search(r'isi\s*(\d+)', combined)
            if find_isi:
                multiplier = int(find_isi.group(1))
            
            total_modal = base_price * multiplier * qty_order
            tipe = f"Satuan x{qty_order}" if multiplier == 1 else f"Paket Isi {multiplier} (x{qty_order})"
            
            return pd.Series([match_key, base_price, total_modal, tipe])

        df_final[['Key_Secrets', 'Hrg_Base', 'Total_Modal', 'Tipe']] = df_final.apply(get_smart_modal, axis=1)

        # --- 8. HITUNG KEUANGAN ---
        df_final['Settlement'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Net_Rev'] = df_final['Settlement'] - df_final['Ongkir_C']
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # --- 9. DISPLAY ---
        st.divider()
        st.subheader(f"📊 Laporan: {date_range[0]} s/d {date_range[1]}")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omset Net", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Final", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        # Tabel Audit
        st.dataframe(df_final[['Tanggal_Fix', 'Product Name', 'Variation', 'Key_Secrets', 'Tipe', 'Total_Modal', 'Profit']], use_container_width=True)

    except Exception as e:
        st.error(f"Sistem Gagal Memproses: {e}")
