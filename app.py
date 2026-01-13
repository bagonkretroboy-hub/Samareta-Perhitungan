import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Settlement Pro", layout="wide", page_icon="💰")

# Custom CSS: Metrik Rapi & Kecil
st.markdown("""
    <style>
    [data-testid="stMetricLabel"] { font-size: 13px !important; color: #666666 !important; }
    [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: 700 !important; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 5px 10px !important; border-radius: 8px; border: 1px solid #eeeeee; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Settlement Intelligence")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Konfigurasi Secrets tidak ditemukan!")
    st.stop()

# --- SIDEBAR: DOUBLE UPLOAD ---
with st.sidebar:
    st.header("⚙️ Unggah Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT", type=["csv"])
    st.info("Catatan: Gunakan 'Order ID' sebagai kunci penghubung.")

# --- PROSES DATA UTAMA ---
if file_order and file_settle:
    try:
        # Load data
        df_order = pd.read_csv(file_order)
        df_settle = pd.read_csv(file_settle)
        
        # Bersihkan nama kolom dari spasi/tab
        df_order.columns = [c.strip() for c in df_order.columns]
        df_settle.columns = [c.strip() for c in df_settle.columns]

        # Gabungkan data berdasarkan Order ID
        # Mengambil info produk dari file Order, dan uang dari file Settlement
        df_merged = pd.merge(
            df_settle, 
            df_order[['Order ID', 'Product Name', 'Quantity', 'Created Time', 'Order Status']], 
            on='Order ID', 
            how='inner'
        )
        
        # Konversi Tanggal
        df_merged['Created Time'] = pd.to_datetime(df_merged['Created Time'], dayfirst=True, errors='coerce')
        
        # Filter Sidebar
        with st.sidebar:
            st.divider()
            min_d, max_d = df_merged['Created Time'].min().date(), df_merged['Created Time'].max().date()
            date_range = st.date_input("Rentang Waktu", [min_d, max_d])
            st.divider()

        # Jalankan Filtering
        df = df_merged.copy()
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]

        # Perhitungan Keuangan
        col_uang = 'Settlement Amount'
        df[col_uang] = pd.to_numeric(df[col_uang], errors='coerce').fillna(0)

        def get_cogs(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            sorted_k = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_k:
                if k.lower() in nm:
                    return DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
            return 0

        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df[col_uang] - df['Total_Modal']

        # --- TAMPILAN DASHBOARD ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        omset_cair = df[col_uang].sum()
        total_modal = df['Total_Modal'].sum()
        profit_final = df['Net_Profit'].sum()
        
        m1.metric("Uang Cair (Net)", f"Rp {omset_cair:,.0f}")
        m2.metric("Total Modal", f"Rp {total_modal:,.0f}")
        m3.metric("Profit Final", f"Rp {profit_final:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {profit_final/3:,.0f}")

        # Visualisasi
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df.groupby(df['Created Time'].dt.date)[col_uang].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Created Time', y=col_uang, title="Tren Pencairan Dana", template="plotly_white"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df, values=col_uang, names='Product Name', title="Kontribusi Produk", hole=0.4), use_container_width=True)

        # Tabel Ringkasan
        df['Tanggal'] = df['Created Time'].dt.date
        summary_table = df.groupby(['Tanggal', 'Product Name']).agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).reset_index().sort_values('Tanggal', ascending=False)

        st.subheader("📋 Detail Transaksi Settlement")
        st.dataframe(summary_table, use_container_width=True)

        # AI Analyst
        st.divider()
        st.subheader("🤖 AI Strategist")
        u_in = st.text_input("Tanya AI (Contoh: Mana produk yang paling untung bersihnya?):")
        
        if st.button("Analisis AI") and u_in:
            try:
                genai.configure(api_key=API_KEY)
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                selected_model = next((m for m in models if "1.5-flash" in m), models[0])
                model = genai.GenerativeModel(selected_model)
                
                context = summary_table.head(50).to_string(index=False)
                prompt = f"Data Settlement Terlampir:\n{context}\n\nUser Question: {u_in}"
                
                with st.spinner("AI sedang berpikir..."):
                    res = model.generate_content(prompt)
                    st.info(res.text)
            except Exception as e:
                st.error(f"AI Error: {e}")

    except Exception as e:
        st.error(f"Gagal memproses data: {e}")
else:
    st.info("💡 Unggah **File Pesanan** DAN **File Settlement** untuk melihat hasil.")
