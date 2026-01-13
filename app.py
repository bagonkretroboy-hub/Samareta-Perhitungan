import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Settlement Pro", layout="wide", page_icon="💰")

# Custom CSS: Metrik Rapi
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
    st.error("Secrets tidak ditemukan!")
    st.stop()

# --- SIDEBAR: DOUBLE UPLOAD ---
with st.sidebar:
    st.header("⚙️ Unggah Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN (Ada Nama Produk)", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (Ada Uang Bersih)", type=["csv"])
    
    if file_order and file_settle:
        # Load data
        df_order = pd.read_csv(file_order)
        df_settle = pd.read_csv(file_settle)
        
        # Bersihkan nama kolom
        df_order.columns = [c.strip() for c in df_order.columns]
        df_settle.columns = [c.strip() for c in df_settle.columns]

        # Gabungkan data berdasarkan Order ID
        # Pastikan kolom Order ID namanya sesuai (biasanya 'Order ID' di kedua file)
        try:
            df_raw = pd.merge(df_settle, df_order[['Order ID', 'Product Name', 'Quantity', 'Created Time']], on='Order ID', how='left')
            df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'], dayfirst=True, errors='coerce')
            
            min_d, max_d = df_raw['Created Time'].min().date(), df_raw['Created Time'].max().date()
            date_range = st.date_input("Rentang Waktu", [min_d, max_d])
        except Exception as e:
            st.error(f"Gagal menggabungkan file: {e}")

# --- PROSES DATA ---
if file_order and file_settle:
    try:
        df = df_raw.copy()
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]

        # Kolom uang di file settlement biasanya 'Settlement Amount'
        col_uang = 'Settlement Amount'
        df[col_uang] = pd.to_numeric(df[col_uang], errors='coerce').fillna(0)

        # Hitung Modal
        def get_cogs(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            sorted_k = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_k:
                if k.lower() in nm:
                    return DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
            return 0

        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df[col_uang] - df['Total_Modal']

        # METRIK
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        omset_bersih = df[col_uang].sum() # Ini sudah potong admin TikTok
        total_modal = df['Total_Modal'].sum()
        profit_fix = df['Net_Profit'].sum()
        
        m1.metric("Uang Masuk (Bersih)", f"Rp {omset_bersih:,.0f}")
        m2.metric("Total Modal", f"Rp {total_modal:,.0f}")
        m3.metric("Profit Final", f"Rp {profit_fix:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {profit_fix/3:,.0f}")

        # TABEL ANALISIS UNTUK AI
        df['Tanggal'] = df['Created Time'].dt.date
        analysis_table = df.groupby(['Tanggal', 'Product Name']).agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).reset_index()

        st.subheader("📋 Ringkasan Profit per Produk")
        st.dataframe(analysis_table.sort_values('Net_Profit', ascending=False), use_container_width=True)

        # AI STRATEGIST
        st.divider()
        st.subheader("🤖 AI Strategist (Settlement Mode)")
        u_in = st.text_input("Tanya AI tentang detail keuangan:")
        
        if st.button("Analisis AI") and u_in:
            genai.configure(api_key=API_KEY)
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            selected_model = next((m for m in models if "1.5-flash" in m), models[0])
            model = genai.GenerativeModel(selected_model)
            
            context = analysis_table.head(60).to_string(index=False)
            prompt = f"Data Settlement (Sudah potong admin):\n{context}\n\nUser: {u_in}\nJawab dengan detail berdasarkan data settlement."
            
            with st.spinner("AI sedang memproses data gabungan..."):
                res = model.generate_content(prompt)
                st.info(res.text)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Silakan unggah kedua file (Pesanan & Settlement) di sidebar.")
