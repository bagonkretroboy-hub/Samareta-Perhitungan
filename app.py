import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

# --- 1. CONFIG ---
st.set_page_config(page_title="Samareta Pro: Multiplier Mode", layout="wide")

# --- 2. LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets Error!")
    st.stop()

# --- 3. FUNGSI PEMBERSIH ---
def super_clean(text):
    if pd.isna(text): return ""
    text = str(text).replace('\t', ' ').replace('\n', ' ')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    return ' '.join(text.split()).lower()

st.title("💰 Samareta Pro: Smart Multiplier")

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("Upload Data")
    f_order = st.file_uploader("1. Upload PESANAN (CSV)", type=["csv"])
    f_settle = st.file_uploader("2. Upload SETTLEMENT (CSV)", type=["csv"])

if f_order and f_settle:
    try:
        # Load & Clean
        df_o = pd.read_csv(f_order)
        try: df_s = pd.read_csv(f_settle, sep=';')
        except: df_s = pd.read_csv(f_settle)

        df_o.columns = [c.replace('\t', '').strip() for c in df_o.columns]
        df_s.columns = [c.replace('\t', '').strip() for c in df_s.columns]
        df_o = df_o.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)
        df_s = df_s.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)

        # Merge
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=['Order/adjustment ID'])
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = next(c for c in df_o.columns if 'Created Time' in c or 'Order create time' in c)
        
        df_final = pd.merge(df_s, df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time_o]], 
                           left_on='Order/adjustment ID', right_on=col_id_o, how='inner')

        df_final['Tanggal_Fix'] = pd.to_datetime(df_final[col_time_o], dayfirst=True, errors='coerce')

        # --- FILTER TANGGAL DI SIDEBAR ---
        min_d = df_final['Tanggal_Fix'].min().date()
        max_d = df_final['Tanggal_Fix'].max().date()
        with st.sidebar:
            st.divider()
            date_range = st.date_input("Pilih Periode Laporan:", value=(min_d, max_d), min_value=min_d, max_value=max_d)

        if len(date_range) == 2:
            df_final = df_final[(df_final['Tanggal_Fix'].dt.date >= date_range[0]) & (df_final['Tanggal_Fix'].dt.date <= date_range[1])]

        # --- 5. LOGIKA MULTIPLIER (ISI 2, 3, 4, 5) ---
        def get_smart_modal(row):
            combined = super_clean(f"{row['Product Name']} {row['Variation']}")
            qty_order = int(float(row['Quantity']))
            
            # 1. Cari Produk Base di Secrets
            match_key = "TIDAK DITEMUKAN"
            base_price = 0
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if super_clean(k) in combined:
                    match_key = k
                    base_price = DAFTAR_MODAL[k]
                    break
            
            # 2. Cek apakah ada kata "isi [angka]" di variasi/judul
            multiplier = 1
            find_isi = re.search(r'isi\s*(\d+)', combined)
            if find_isi:
                multiplier = int(find_isi.group(1)) # Ambil angka setelah kata 'isi'
            
            # 3. Hitung Total Modal
            # Jika ada "isi 3", maka modal = harga_satuan * 3 * qty_order
            total_modal = base_price * multiplier * qty_order
            
            detail_tipe = f"Satuan x{qty_order}"
            if multiplier > 1:
                detail_tipe = f"Paket Isi {multiplier} (x{qty_order} pesanan)"
                
            return pd.Series([match_key, base_price, multiplier, total_modal, detail_tipe])

        df_final[['Key', 'Harga_Satu', 'Isi', 'Total_Modal', 'Tipe']] = df_final.apply(get_smart_modal, axis=1)

        # --- 6. HITUNG KEUANGAN ---
        df_final['Settlement'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Net_Rev'] = df_final['Settlement'] - df_final['Ongkir_C']
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # --- 7. TAMPILAN ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omset Net", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Final", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        st.subheader("📋 Rincian Audit Modal")
        st.dataframe(df_final[['Tanggal_Fix', 'Product Name', 'Variation', 'Key', 'Tipe', 'Total_Modal', 'Profit']], use_container_width=True)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
