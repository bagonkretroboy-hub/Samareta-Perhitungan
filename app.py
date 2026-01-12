import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence", layout="wide", page_icon="📈")
st.title("📈 Samareta Business Intelligence (Strict Mode)")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("Konfigurasi Secrets tidak ditemukan! Pastikan MODAL_PRODUK sudah ada di Streamlit Cloud.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("🔍 Filter Dashboard")
    uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file)
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'].str.strip(), dayfirst=True, errors='coerce')
        
        min_d = df_raw['Created Time'].min().date()
        max_d = df_raw['Created Time'].max().date()
        date_range = st.date_input("Rentang Waktu", [min_d, max_d])
        
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

        # Fungsi Hitung Modal Tanpa Default (Return 0 if not found)
        def get_cogs(row):
            nama_csv = str(row['Product Name']).lower()
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for kunci in sorted_keys:
                if kunci.lower() in nama_csv:
                    return DAFTAR_MODAL[kunci]
            return 0 # <--- MODAL DIJADIKAN 0 JIKA TIDAK ADA DI LIST

        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df[col_uang] - df['Total_Modal']

        # --- FITUR PERINGATAN MODAL KOSONG ---
        unmapped = df[df['Total_Modal'] == 0]['Product Name'].unique()
        if len(unmapped) > 0:
            st.warning(f"⚠️ Ditemukan {len(unmapped)} produk yang belum ada harga modalnya di Secrets!")
            with st.expander("Lihat daftar produk tanpa modal"):
                st.write(unmapped)

        # --- METRIK UTAMA ---
        m1, m2, m3, m4 = st.columns(4)
        omset = df[col_uang].sum()
        profit = df['Net_Profit'].sum()
        m1.metric("Total Omset", f"Rp {omset:,.0f}")
        m2.metric("Total Modal", f"Rp {df['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Bersih", f"Rp {profit:,.0f}")
        m4.metric("Jatah/Orang (1/3)", f"Rp {profit/3:,.0f}")

        # --- VISUALISASI ---
        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            daily = df.groupby(df['Created Time'].dt.date)[col_uang].sum().reset_index()
            fig_line = px.line(daily, x='Created Time', y=col_uang, title="Tren Omset Harian", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
        with c2:
            fig_pie = px.pie(df, values=col_uang, names='Product Category', title="Kategori Terlaris", hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- TABEL DATA ---
        st.subheader("📋 Analisis Profit Per Produk")
        summary = df.groupby('Product Name').agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).sort_values('Net_Profit', ascending=False)
        st.dataframe(summary, use_container_width=True)

        # --- AI MANAGER ---
        st.divider()
        st.subheader("🤖 Analisis Strategis AI")
        user_ask = st.text_area("Tanya AI tentang performa toko:")
        if st.button("Jalankan AI"):
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Data Samareta: Omset Rp {omset:,.0f}, Profit Rp {profit:,.0f}. Tanya: {user_ask}"
            with st.spinner("AI sedang menganalisis..."):
                res = model.generate_content(prompt)
                st.info(res.text)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Silakan unggah CSV TikTok di sidebar untuk melihat dashboard.")
