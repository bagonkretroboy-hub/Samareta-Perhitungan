import streamlit as st
import pandas as pd
import re
from datetime import datetime
import plotly.express as px

# --- 1. CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Selalu Berjaya", layout="wide", page_icon="💰")

# Custom Styling
st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #1a1a1a !important; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; }
    .stAlert { border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
except:
    st.error("Secrets Belum Terisi! Pastikan MODAL_PRODUK ada di Dashboard Streamlit.")
    st.stop()

# --- 3. JUDUL UTAMA ---
st.title("🚀 Samareta Selalu Berjaya")

# --- 4. FUNGSI PEMBERSIH ---
def super_clean(text):
    if pd.isna(text): return ""
    text = str(text).replace('\t', ' ').replace('\n', ' ')
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    return ' '.join(text.split()).lower()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Data Source")
    f_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("2. Upload CSV SETTLEMENT", type=["csv"])

# --- 6. LOGIKA UTAMA ---
if f_order and f_settle:
    try:
        df_o = pd.read_csv(f_order)
        try: df_s = pd.read_csv(f_settle, sep=';')
        except: df_s = pd.read_csv(f_settle)

        # Pembersihan Data
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
        df_final['Quantity'] = pd.to_numeric(df_final['Quantity'], errors='coerce').fillna(0)

        # Filter Tanggal Sidebar
        with st.sidebar:
            st.divider()
            start_def = df_final['Tanggal_Fix'].min().date()
            end_def = df_final['Tanggal_Fix'].max().date()
            date_range = st.date_input("Periode Laporan:", value=(start_def, end_def),
                                      min_value=datetime(2024,1,1).date(),
                                      max_value=datetime(2026,12,31).date())

        if len(date_range) == 2:
            df_final = df_final[(df_final['Tanggal_Fix'].dt.date >= date_range[0]) & (df_final['Tanggal_Fix'].dt.date <= date_range[1])]

        # Logika Smart Matching & Multiplier
        def get_smart_modal(row):
            p_name = super_clean(row['Product Name'])
            p_var = super_clean(row['Variation'])
            combined = f"{p_name} {p_var}"
            qty_order = row['Quantity']
            match_key, base_price = "TIDAK DITEMUKAN", 0
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if super_clean(k) in combined:
                    match_key, base_price = k, DAFTAR_MODAL[k]
                    break
            
            multiplier = 1
            find_isi_var = re.findall(r'isi\s*(\d+)', p_var)
            find_isi_name = re.findall(r'isi\s*(\d+)', p_name)
            if find_isi_var: multiplier = int(find_isi_var[0])
            elif find_isi_name: multiplier = int(find_isi_name[-1])
            
            total_modal = base_price * multiplier * qty_order
            tipe = f"Satuan (x{int(qty_order)})" if multiplier == 1 else f"Paket Isi {multiplier} (x{int(qty_order)})"
            return pd.Series([match_key, total_modal, tipe])

        df_final[['Key_Found', 'Total_Modal', 'Tipe']] = df_final.apply(get_smart_modal, axis=1)

        # Hitung Keuangan
        df_final['Settlement_Gross'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Net_Revenue'] = df_final['Settlement_Gross'] - df_final['Ongkir_C']
        df_final['Profit'] = df_final['Net_Revenue'] - df_final['Total_Modal']

        # --- SISTEM WARNING (Tetap muncul di atas jika ada data bolong) ---
        unmatched = df_final[df_final['Key_Found'] == "TIDAK DITEMUKAN"]
        if not unmatched.empty:
            st.warning("**⚠️ PENTING: Ada produk belum terdaftar di Secrets!**")
            st.table(unmatched[['Product Name', 'Variation']].drop_duplicates())

        # --- 7. GRAFIK TREN KEUNTUNGAN ---
        st.subheader("📈 Tren Keuntungan Harian")
        daily_profit = df_final.groupby(df_final['Tanggal_Fix'].dt.date)['Profit'].sum().reset_index()
        fig_area = px.area(daily_profit, x='Tanggal_Fix', y='Profit', color_discrete_sequence=['#00ff00'])
        st.plotly_chart(fig_area, use_container_width=True)

        # --- 8. TOP 5 BEST SELLER ---
        st.subheader("🔝 Top 5 Best Seller")
        top_products = df_final.groupby('Product Name')['Quantity'].sum().nlargest(5).reset_index()
        fig_bar = px.bar(top_products, x='Quantity', y='Product Name', orientation='h', color='Quantity', color_continuous_scale='Greens')
        st.plotly_chart(fig_bar, use_container_width=True)

        # --- 9. METRIK UTAMA ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Settlement", f"Rp {df_final['Settlement_Gross'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Bersih", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        # --- 10. RINCIAN TRANSAKSI LENGKAP ---
        st.divider()
        st.subheader("📋 Rincian Transaksi Lengkap")
        st.dataframe(df_final[['Tanggal_Fix', 'Order/adjustment ID', 'Product Name', 'Variation', 'Tipe', 'Settlement_Gross', 'Total_Modal', 'Profit', 'Key_Found']], use_container_width=True)

        # --- 11. ANOMALI PROFIT (DI PALING BAWAH) ---
        st.divider()
        anomali = df_final[(df_final['Profit'] <= 0) & (df_final['Key_Found'] != "TIDAK DITEMUKAN")]
        if not anomali.empty:
            st.subheader("🛑 Anomali Profit (Rugi/0)")
            st.error(f"Ditemukan {len(anomali)} transaksi yang merugikan atau tidak profit.")
            st.dataframe(anomali[['Order/adjustment ID', 'Product Name', 'Settlement_Gross', 'Total_Modal', 'Profit']])
        else:
            st.success("✅ Tidak ada anomali profit pada periode ini.")

    except Exception as e:
        st.error(f"Terjadi kesalahan sistem: {e}")
