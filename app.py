import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="📊")

# Custom CSS: Mengecilkan tulisan metrik sesuai permintaan
st.markdown("""
    <style>
    [data-testid="stMetricLabel"] { font-size: 13px !important; color: #666666 !important; }
    [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: 700 !important; color: #1f1f1f !important; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 5px 10px !important; border-radius: 8px; border: 1px solid #eeeeee; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Samareta Business Intelligence")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("Konfigurasi Secrets bermasalah!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Data")
    uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file)
        df_raw = df_raw.applymap(lambda x: x.strip().replace('\t', '') if isinstance(x, str) else x)
        df_raw.columns = [c.strip().replace('\t', '') for c in df_raw.columns]
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'], dayfirst=True, errors='coerce')
        
        min_date = df_raw['Created Time'].min().date()
        max_date = df_raw['Created Time'].max().date()
        date_range = st.date_input("Rentang Waktu", [min_date, max_date])
        sel_status = st.multiselect("Status Pesanan", df_raw['Order Status'].unique().tolist(), default=["Selesai"])

# --- PROSES DATA ---
if uploaded_file:
    try:
        df = df_raw.copy()
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]
        df = df[df['Order Status'].isin(sel_status)]

        col_uang = 'SKU Subtotal After Discount'
        df[col_uang] = pd.to_numeric(df[col_uang], errors='coerce').fillna(0)

        # FUNGSI HITUNG MODAL
        def get_cogs(row):
            nama_p = str(row['Product Name']).lower()
            qty = row['Quantity']
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in nama_p:
                    return DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
            return 0

        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df[col_uang] - df['Total_Modal']

        # VALIDASI PRODUK 0 (BAGIAN YANG TADI ERROR)
        unmapped = df[df['Total_Modal'] == 0]['Product Name'].unique()
        if len(unmapped) > 0:
            st.warning(f"⚠️ {len(unmapped)} Produk belum ada harga modal.")

        # --- TAMPILAN METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        omset, modal, profit = df[col_uang].sum(), df['Total_Modal'].sum(), df['Net_Profit'].sum()
        
        m1.metric("Total Omset", f"Rp {omset:,.0f}")
        m2.metric("Total Modal", f"Rp {modal:,.0f}")
        m3.metric("Profit Bersih", f"Rp {profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {profit/3:,.0f}")

        # --- VISUALISASI ---
        cl, cr = st.columns([2,1])
        with cl:
            daily = df.groupby(df['Created Time'].dt.date)[col_uang].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Created Time', y=col_uang, template="plotly_white"), use_container_width=True)
        with cr:
            st.plotly_chart(px.pie(df, values=col_uang, names='Product Category', hole=0.4), use_container_width=True)

        # --- TABEL & AI ---
        st.subheader("📋 Ringkasan Per Produk")
        summary = df.groupby('Product Name').agg({'Quantity':'sum', col_uang:'sum', 'Net_Profit':'sum'}).sort_values('Net_Profit', ascending=False)
        st.dataframe(summary, use_container_width=True)

        st.divider()
        st.subheader("🤖 AI Analyst")
        u_in = st.text_input("Tanya AI Manager:")
        if st.button("Analisis") and u_in:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Data: Omset {omset}, Profit {profit}. Tanya: {u_in}"
            try:
                st.info(model.generate_content(prompt).text)
            except:
                st.info(genai.GenerativeModel('gemini-pro').generate_content(prompt).text)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Silakan unggah file CSV di sidebar.")
