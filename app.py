import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- CONFIG ---
st.set_page_config(page_title="Samareta Intelligence", layout="wide")

# --- CSS (Fix Contrast) ---
st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #1e1e1e !important; border: 1px solid #444; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricLabel"] { color: #bbb !important; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 22px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Accurate Audit")

# --- LOAD SECRETS ---
DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
API_KEY = st.secrets["GEMINI_API_KEY"]

# --- SIDEBAR ---
with st.sidebar:
    f_order = st.file_uploader("1. CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("2. CSV SETTLEMENT (Income)", type=["csv"])

if f_order and f_settle:
    try:
        df_o = pd.read_csv(f_order)
        df_s = pd.read_csv(f_settle, sep=';')
        
        df_o.columns = [c.strip() for c in df_o.columns]
        df_s.columns = [c.replace('  ', ' ').strip() for c in df_s.columns]

        # FILTER: Hanya Order & Buang Duplikat
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=['Order/adjustment ID'])

        # MERGE
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        df_merged = pd.merge(df_s, df_o[[col_id_o, 'Product Name', 'Quantity']].drop_duplicates(subset=[col_id_o]), 
                             left_on='Order/adjustment ID', right_on=col_id_o, how='inner')

        # KONVERSI & BERSIHKAN ONGKIR
        # Kita kurangi settlement dengan ongkir yang dibayar customer agar ketemu harga barang murni
        df_merged['Uang_Cair'] = pd.to_numeric(df_merged['Total settlement amount'], errors='coerce').fillna(0)
        df_merged['Ongkir_Masuk'] = pd.to_numeric(df_merged['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        
        # HARGA BARANG NET = Uang yang masuk ke kantong Anda HANYA dari barang (setelah admin, tanpa ongkir)
        df_merged['Omset_Barang_Murni'] = df_merged['Uang_Cair'] - df_merged['Ongkir_Masuk']

        # HITUNG MODAL
        def get_modal(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            for k in sorted(DAFTAR_MODAL.keys(), key=len, reverse=True):
                if k.lower() in nm:
                    return DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
            return 0

        df_merged['Total_Modal'] = df_merged.apply(get_modal, axis=1)
        df_merged['Profit'] = df_merged['Omset_Barang_Murni'] - df_merged['Total_Modal']

        # METRIK
        m1, m2, m3 = st.columns(3)
        m1.metric("Omset Barang (Net)", f"Rp {df_merged['Omset_Barang_Murni'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_merged['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Final", f"Rp {df_merged['Profit'].sum():,.0f}")

        # TABEL AUDIT (Untuk cek kenapa harga murah)
        st.subheader("📋 Audit Transaksi: Mengapa harga lebih murah dari modal?")
        audit_tab = df_merged[['Order/adjustment ID', 'Product Name', 'Omset_Barang_Murni', 'Total_Modal', 'Profit']]
        st.dataframe(audit_tab.sort_values('Profit'), use_container_width=True)

    except Exception as e:
        st.error(f"Error: {e}")
