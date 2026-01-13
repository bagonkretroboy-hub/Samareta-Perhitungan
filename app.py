import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Analytics (Created Time)", layout="wide", page_icon="💰")

# --- CUSTOM CSS (HIGH CONTRAST DARK MODE) ---
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #1e1e1e !important; 
        border: 1px solid #444444 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }
    [data-testid="stMetricLabel"] { color: #bbbbbb !important; font-size: 14px !important; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; font-weight: bold !important; }
    .stDataFrame { border: 1px solid #444; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Analytics (Order Created Time)")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Konfigurasi Secrets tidak ditemukan!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Unggah Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (Income)", type=["csv"])
    st.divider()
    st.info("Patokan Waktu: Tanggal Pesanan Dibuat (Order Created Time)")

# --- PROSES DATA ---
if file_order and file_settle:
    try:
        # 1. Load Data
        df_order = pd.read_csv(file_order)
        df_settle = pd.read_csv(file_settle, sep=';')
        
        df_order.columns = [c.strip() for c in df_order.columns]
        df_settle.columns = [c.replace('  ', ' ').strip() for c in df_settle.columns]

        # 2. Filter Settlement (Hanya tipe Order & Buang Duplikat)
        if 'Type' in df_settle.columns:
            df_settle = df_settle[df_settle['Type'] == 'Order']
        
        col_id_settle = 'Order/adjustment ID'
        df_settle = df_settle.drop_duplicates(subset=[col_id_settle])

        # 3. Identifikasi Kolom di File Pesanan
        col_id_order = next((c for c in df_order.columns if 'Order ID' in c), None)
        # Mencari kolom Created Time di file pesanan
        col_created_time = next((c for c in df_order.columns if 'Order create time' in c or 'Created Time' in c or 'Order creation time' in c), None)

        if not col_id_order or not col_created_time:
            st.error(f"Kolom ID atau Waktu tidak ditemukan di file Pesanan. (Cek: {col_id_order}, {col_created_time})")
            st.stop()

        # 4. Sinkronisasi & Merge
        df_settle[col_id_settle] = df_settle[col_id_settle].astype(str).str.strip()
        df_order[col_id_order] = df_order[col_id_order].astype(str).str.strip()
        
        # Ambil kolom penting dari file pesanan
        df_order_clean = df_order[[col_id_order, 'Product Name', 'Quantity', col_created_time]].drop_duplicates(subset=[col_id_order])

        df_final = pd.merge(df_settle, df_order_clean, left_on=col_id_settle, right_on=col_id_order, how='inner')

        # 5. Konversi Uang & Waktu (PATOKAN: CREATED TIME)
        col_settle = 'Total settlement amount'
        col_ongkir_cust = 'Shipping cost paid by the customer'
        
        df_final[col_settle] = pd.to_numeric(df_final[col_settle], errors='coerce').fillna(0)
        df_final[col_ongkir_cust] = pd.to_numeric(df_final[col_ongkir_cust], errors='coerce').fillna(0)
        df_final[col_created_time] = pd.to_datetime(df_final[col_created_time], errors='coerce')

        # Rumus Omset Bersih
        df_final['Omset_Barang_Net'] = df_final[col_settle] - df_final[col_ongkir_cust]

        # 6. FILTER TANGGAL BERDASARKAN ORDER CREATED TIME (SIDEBAR)
        min_d = df_final[col_created_time].min().date()
        max_d = df_final[col_created_time].max().date()
        date_range = st.sidebar.date_input("Rentang Tanggal Pesanan", [min_d, max_d])
        
        if len(date_range) == 2:
            df_final = df_final[(df_final[col_created_time].dt.date >= date_range[0]) & (df_final[col_created_time].dt.date <= date_range[1])]

        # 7. HITUNG MODAL & AUDIT
        def get_cogs_audit(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in nm:
                    val = DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
                    return val, True
            return 0, False

        audit_res = df_final.apply(get_cogs_audit, axis=1)
        df_final['Total_Modal'] = [x[0] for x in audit_res]
        df_final['Modal_Found'] = [x[1] for x in audit_res]
        df_final['Actual_Profit'] = df_final['Omset_Barang_Net'] - df_final['Total_Modal']

        # --- TAMPILAN METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        total_omset = df_final['Omset_Barang_Net'].sum()
        total_modal = df_final['Total_Modal'].sum()
        total_profit = df_final['Actual_Profit'].sum()

        m1.metric("Omset Bersih (Net)", f"Rp {total_omset:,.0f}")
        m2.metric("Total Modal", f"Rp {total_modal:,.0f}")
        m3.metric("Profit Bersih", f"Rp {total_profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {total_profit/3:,.0f}")

        # 8. Visualisasi (Tren Berdasarkan Created Time)
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df_final.groupby(df_final[col_created_time].dt.date)['Actual_Profit'].sum().reset_index()
            st.plotly_chart(px.line(daily, x=col_created_time, y='Actual_Profit', title="Tren Profit (Waktu Pesanan Dibuat)", template="plotly_dark"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_final, values='Actual_Profit', names='Product Name', title="Kontribusi Profit", hole=0.4, template="plotly_dark"), use_container_width=True)

        # 9. Tabel Detail
        df_final['Tgl_Dibuat'] = df_final[col_created_time].dt.date
        summary = df_final.groupby(['Tgl_Dibuat', 'Product Name', 'Modal_Found']).agg({
            'Quantity': 'sum',
            'Omset_Barang_Net': 'sum',
            'Total_Modal': 'sum',
            'Actual_Profit': 'sum'
        }).reset_index().sort_values('Tgl_Dibuat', ascending=False)

        st.subheader("📋 Rincian Transaksi (Patokan Tanggal Pesanan)")
        st.dataframe(summary.style.apply(lambda x: ['background-color: #441111' if not x.Modal_Found else '' for i in x], axis=1), use_container_width=True)

        # 10. AI ANALYST
        st.divider()
        st.subheader("🤖 AI Business Strategist")
        u_in = st.text_input("Tanya AI tentang data penjualan Anda:")
        if st.button("Jalankan AI") and u_in:
            try:
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                context = summary.head(40).to_string(index=False)
                prompt = f"Data Penjualan (Order Created Time):\n{context}\n\nPertanyaan User: {u_in}"
                with st.spinner("AI sedang menganalisis..."):
                    res = model.generate_content(prompt)
                    st.info(res.text)
            except Exception as e:
                st.error(f"AI Error: {e}")

    except Exception as e:
        st.error(f"Gagal memproses: {e}")
else:
    st.info("Silakan unggah kedua file CSV untuk melihat laporan berdasarkan waktu pesanan dibuat.")
