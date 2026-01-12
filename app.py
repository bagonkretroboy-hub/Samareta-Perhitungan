import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG ---
st.set_page_config(page_title="Samareta Pro Dashboard", layout="wide", page_icon="🚀")
st.title("🚀 Samareta Business Intelligence Pro")

# --- LOAD SECRETS ---
try:
    daftar_modal = st.secrets["MODAL_PRODUK"]
    modal_default = st.secrets.get("MODAL_DEFAULT", 25000)
except:
    daftar_modal = {"DEFAULT": 25000}
    modal_default = 25000

# --- SIDEBAR: SUPER FILTERS ---
with st.sidebar:
    st.header("🔍 Filter Komprehensif")
    uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])
    st.divider()
    
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file)
        # Pre-processing Tanggal
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'].str.strip(), dayfirst=True, errors='coerce')
        
        # 1. Filter Rentang Waktu
        min_date = df_raw['Created Time'].min().date()
        max_date = df_raw['Created Time'].max().date()
        date_range = st.date_input("📅 Rentang Waktu", [min_date, max_date])
        
        # 2. Filter Kategori & Status
        categories = df_raw['Product Category'].unique().tolist()
        sel_cat = st.multiselect("📦 Kategori Produk", categories, default=categories)
        
        status_list = df_raw['Order Status'].unique().tolist()
        sel_status = st.multiselect("📋 Status Pesanan", status_list, default=["Selesai"])
        
        # 3. Filter Metode Pembayaran & Wilayah
        pay_methods = df_raw['Payment Method'].unique().tolist()
        sel_pay = st.multiselect("💳 Metode Pembayaran", pay_methods, default=pay_methods)
        
        provinces = df_raw['Province'].unique().tolist()
        sel_prov = st.multiselect("📍 Wilayah (Provinsi)", provinces, default=provinces)

# --- LOGIKA DASHBOARD ---
if uploaded_file:
    try:
        # Apply All Filters
        df = df_raw.copy()
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]
        
        df = df[df['Order Status'].isin(sel_status)]
        df = df[df['Product Category'].isin(sel_cat)]
        df = df[df['Payment Method'].isin(sel_pay)]
        df = df[df['Province'].isin(sel_prov)]

        # Kolom Uang TikTok
        col_uang = 'SKU Subtotal After Discount'

        # Hitung Modal & Profit
        def hitung_modal(row):
            nama = str(row['Product Name']).lower()
            qty = row['Quantity']
            for k, v in daftar_modal.items():
                if k.lower() in nama: return v * qty
            return modal_default * qty

        df['Total_Modal'] = df.apply(hitung_modal, axis=1)
        df['Profit'] = df[col_uang] - df['Total_Modal']

        # --- 1. KEY METRICS ---
        m1, m2, m3, m4 = st.columns(4)
        total_omset = df[col_uang].sum()
        total_profit = df['Profit'].sum()
        total_qty = df['Quantity'].sum()
        
        m1.metric("Total Omset", f"Rp {total_omset:,.0f}")
        m2.metric("Total Profit", f"Rp {total_profit:,.0f}")
        m3.metric("Total Produk Terjual", f"{total_qty} pcs")
        m4.metric("Jatah Per Orang (Bagi 3)", f"Rp {total_profit/3:,.0f}")

        # --- 2. VISUALISASI BARIS 1: TREN & KATEGORI ---
        st.divider()
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("📈 Tren Penjualan Harian")
            daily_sales = df.groupby(df['Created Time'].dt.date)[col_uang].sum().reset_index()
            fig_trend = px.line(daily_sales, x='Created Time', y=col_uang, title="Omset Per Hari")
            st.plotly_chart(fig_trend, use_container_width=True)
        
        with c2:
            st.subheader("🍕 Proporsi Kategori")
            fig_pie = px.pie(df, values=col_uang, names='Product Category', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        # --- 3. VISUALISASI BARIS 2: WILAYAH & PEMBAYARAN ---
        c3, c4 = st.columns(2)
        
        with c3:
            st.subheader("📍 Top 10 Kota/Kabupaten")
            city_sales = df.groupby('Regency and City')[col_uang].sum().sort_values(ascending=False).head(10).reset_index()
            fig_city = px.bar(city_sales, x=col_uang, y='Regency and City', orientation='h', color=col_uang)
            st.plotly_chart(fig_city, use_container_width=True)
            
        with c4:
            st.subheader("💳 Metode Pembayaran Terpopuler")
            pay_counts = df.groupby('Payment Method').size().reset_index(name='Jumlah')
            fig_pay = px.bar(pay_counts, x='Payment Method', y='Jumlah', color='Payment Method')
            st.plotly_chart(fig_pay, use_container_width=True)

        # --- 4. DATA TABLE & AI ANALYSIS ---
        st.divider()
        col_tab, col_ai = st.columns([1, 1])
        
        with col_tab:
            st.subheader("📋 Ringkasan Per Produk")
            product_summary = df.groupby('Product Name').agg({
                'Quantity': 'sum',
                col_uang: 'sum',
                'Profit': 'sum'
            }).sort_values(by='Profit', ascending=False)
            st.dataframe(product_summary, use_container_width=True)

        with col_ai:
            st.subheader("🤖 Analisis Strategis AI")
            user_ask = st.text_area("Tanya AI (Contoh: Mengapa profit rendah di wilayah tertentu?)")
            
            if st.button("Jalankan Analisis"):
                api_key = st.secrets["GEMINI_API_KEY"]
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Kirim data ringkas yang lebih kaya
                context = f"""
                Data Terfilter:
                Periode: {date_range}
                Top Kota: {city_sales['Regency and City'].head(3).tolist()}
                Top Produk: {product_summary.head(3).index.tolist()}
                Total Profit: Rp {total_profit:,.0f}
                
                Instruksi: {user_ask}
                """
                
                with st.spinner("AI sedang membaca tren data Anda..."):
                    res = model.generate_content(context)
                    st.info(res.text)

    except Exception as e:
        st.error(f"Terjadi kesalahan teknis: {e}")
else:
    st.info("👋 Selamat Datang! Silakan unggah file CSV ekspor TikTok Anda di sidebar untuk melihat analisis lengkap.")
