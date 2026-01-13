import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Settlement Pro", layout="wide", page_icon="💰")

# --- CUSTOM CSS (DARK MODE OPTIMIZED) ---
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #1e1e1e !important; 
        border: 1px solid #333333 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }
    [data-testid="stMetricLabel"] { color: #bbbbbb !important; font-size: 14px !important; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; font-weight: bold !important; }
    .stDataFrame { border: 1px solid #444; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Business Intelligence (Accurate Mode)")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets (MODAL_PRODUK / GEMINI_API_KEY) belum disetting!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (Income)", type=["csv"])
    st.info("Sistem otomatis membuang data duplikat untuk akurasi profit.")

# --- PROSES DATA UTAMA ---
if file_order and file_settle:
    try:
        # 1. Load Data
        df_order = pd.read_csv(file_order)
        df_settle = pd.read_csv(file_settle, sep=';') # Sesuai format file income Anda
        
        # Bersihkan nama kolom
        df_order.columns = [c.strip() for c in df_order.columns]
        df_settle.columns = [c.replace('  ', ' ').strip() for c in df_settle.columns]

        # 2. FILTER AKURASI: Hanya ambil tipe 'Order' dan buang duplikat ID
        # Ini mencegah angka membengkak karena baris adjustment/refund
        if 'Type' in df_settle.columns:
            df_settle = df_settle[df_settle['Type'] == 'Order']
        
        col_id_settle = 'Order/adjustment ID'
        df_settle = df_settle.drop_duplicates(subset=[col_id_settle])

        # 3. Identifikasi Kolom Order ID di File Pesanan
        col_id_order = next((c for c in df_order.columns if 'Order ID' in c), None)

        if not col_id_order:
            st.error("Kolom 'Order ID' tidak ditemukan di file Pesanan.")
            st.stop()

        # 4. Sinkronisasi & Merge
        df_settle[col_id_settle] = df_settle[col_id_settle].astype(str).str.strip()
        df_order[col_id_order] = df_order[col_id_order].astype(str).str.strip()

        # Merge dengan menghapus duplikat di file order juga agar tidak terjadi perkalian baris
        df_order_clean = df_order[[col_id_order, 'Product Name', 'Quantity']].drop_duplicates(subset=[col_id_order])
        
        df_final = pd.merge(
            df_settle, 
            df_order_clean, 
            left_on=col_id_settle, 
            right_on=col_id_order, 
            how='inner'
        )

        # 5. Konversi Uang & Waktu
        col_uang = 'Total settlement amount'
        df_final[col_uang] = pd.to_numeric(df_final[col_uang], errors='coerce').fillna(0)
        df_final['Order settled time'] = pd.to_datetime(df_final['Order settled time'], errors='coerce')
        
        # 6. Filter Tanggal
        min_d, max_d = df_final['Order settled time'].min().date(), df_final['Order settled time'].max().date()
        date_range = st.sidebar.date_input("Rentang Waktu", [min_d, max_d])

        if len(date_range) == 2:
            df_final = df_final[(df_final['Order settled time'].dt.date >= date_range[0]) & (df_final['Order settled time'].dt.date <= date_range[1])]

        # 7. Hitung Modal (COGS)
        def get_cogs(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in nm:
                    return DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
            return 0

        df_final['Total_Modal'] = df_final.apply(get_cogs, axis=1)
        df_final['Net_Profit'] = df_final[col_uang] - df_final['Total_Modal']

        # --- TAMPILAN METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        total_cair = df_final[col_uang].sum()
        total_modal = df_final['Total_Modal'].sum()
        total_profit = df_final['Net_Profit'].sum()
        
        m1.metric("Uang Cair (Net)", f"Rp {total_cair:,.0f}")
        m2.metric("Total Modal", f"Rp {total_modal:,.0f}")
        m3.metric("Profit Bersih", f"Rp {total_profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {total_profit/3:,.0f}")

        # 8. Visualisasi
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df_final.groupby(df_final['Order settled time'].dt.date)[col_uang].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Order settled time', y=col_uang, title="Tren Uang Masuk", template="plotly_dark"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_final, values=col_uang, names='Product Name', title="Kontribusi Produk", hole=0.4, template="plotly_dark"), use_container_width=True)

        # 9. Tabel Ringkasan
        df_final['Tgl'] = df_final['Order settled time'].dt.date
        summary = df_final.groupby(['Tgl', 'Product Name']).agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).reset_index().sort_values('Tgl', ascending=False)

        st.subheader("📋 Rincian Settlement per Item")
        st.dataframe(summary, use_container_width=True)

        # 10. AI ANALYST
        st.divider()
        u_in = st.text_input("Tanya AI (Contoh: Mengapa profit tanggal 12 turun?):")
        if st.button("Analisis AI") and u_in:
            try:
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                context = summary.head(40).to_string(index=False)
                prompt = f"Data Samareta:\n{context}\n\nUser: {u_in}\nJawab dengan singkat dan padat."
                res = model.generate_content(prompt)
                st.info(res.text)
            except Exception as e:
                st.error(f"AI Error: {e}")

    except Exception as e:
        st.error(f"Gagal memproses data: {e}")
else:
    st.info("Harap unggah File Pesanan dan File Income di sidebar.")
