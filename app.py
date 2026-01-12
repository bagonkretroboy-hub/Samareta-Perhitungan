import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import re

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="📊")

# Custom CSS untuk tampilan lebih profesional
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Samareta Business Intelligence")
st.subheader("Analisis Penjualan & Profit TikTok Shop")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("Konfigurasi Secrets tidak ditemukan! Pastikan MODAL_PRODUK dan GEMINI_API_KEY sudah ada di Streamlit Cloud.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Data")
    uploaded_file = st.file_uploader("Upload CSV TikTok (Semua Pesanan)", type=["csv"])
    st.divider()
    
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file)
        # Bersihkan data: Hilangkan karakter tab (\t) yang sering ada di CSV TikTok
        df_raw = df_raw.applymap(lambda x: x.strip() if isinstance(x, str) else x)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        
        # Konversi Tanggal
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'], dayfirst=True, errors='coerce')
        
        # Filter Tanggal
        min_date = df_raw['Created Time'].min().date()
        max_date = df_raw['Created Time'].max().date()
        date_range = st.date_input("Rentang Waktu", [min_date, max_date])
        
        # Filter Status
        all_status = df_raw['Order Status'].unique().tolist()
        sel_status = st.multiselect("Status Pesanan", all_status, default=["Selesai"])

# --- PROSES DATA ---
if uploaded_file:
    try:
        df = df_raw.copy()
        
        # Apply Filter
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]
        df = df[df['Order Status'].isin(sel_status)]

        # Konversi Kolom Uang
        col_uang = 'SKU Subtotal After Discount'
        df[col_uang] = pd.to_numeric(df[col_uang], errors='coerce').fillna(0)

        # --- FUNGSI HITUNG MODAL CERDAS (FUZZY MATCHING) ---
        def get_cogs(row):
            nama_produk = str(row['Product Name']).lower()
            quantity = row['Quantity']
            
            # Urutkan kunci modal dari yang terpanjang ke terpendek (Prioritas Paket)
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            
            # Tahap 1: Pencarian String Langsung
            for kunci in sorted_keys:
                if kunci.lower() in nama_produk:
                    # Jika di kunci ada kata "paket", jangan dikali quantity (karena harga sudah harga paket)
                    # Jika tidak ada kata "paket", maka itu harga satuan, perlu dikali quantity
                    if "paket" in kunci.lower():
                        return DAFTAR_MODAL[kunci]
                    else:
                        return DAFTAR_MODAL[kunci] * quantity
            
            return 0

        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df[col_uang] - df['Total_Modal']

        # --- VALIDASI PRODUK TANPA MODAL ---
        unmapped = df[df['Total_Modal'] == 0]['Product Name'].unique()
        if len(unmapped) > 0:
            st.warning(f"⚠️ Ditemukan {len(unmapped)} jenis produk yang belum terdaftar di list modal.")
            with st.expander("Klik untuk lihat daftar produk yang harganya masih 0"):
                for p in unmapped:
                    st.write(f"- {p}")

        # --- TAMPILAN METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        total_omset = df[col_uang].sum()
        total_modal = df['Total_Modal'].sum()
        total_profit = df['Net_Profit'].sum()
        
        m1.metric("Total Omset", f"Rp {total_omset:,.0f}")
        m2.metric("Total Modal", f"Rp {total_modal:,.0f}")
        m3.metric("Profit Bersih", f"Rp {total_profit:,.0f}", delta=f"{total_profit/total_omset*100:.1f}% Margin")
        m4.metric("Jatah Per Orang (1/3)", f"Rp {total_profit/3:,.0f}")

        # --- VISUALISASI ---
        st.divider()
        col_a, col_b = st.columns([2,1])
        
        with col_a:
            st.subheader("📈 Tren Penjualan Harian")
            daily_sales = df.groupby(df['Created Time'].dt.date)[col_uang].sum().reset_index()
            fig_trend = px.line(daily_sales, x='Created Time', y=col_uang, markers=True, 
                                labels={'Created Time': 'Tanggal', col_uang: 'Omset'})
            st.plotly_chart(fig_trend, use_container_width=True)
            
        with col_b:
            st.subheader("🍕 Proporsi Kategori")
            fig_pie = px.pie(df, values=col_uang, names='Product Category', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()
        col_c, col_d = st.columns(2)
        
        with col_c:
            st.subheader("📍 Top 10 Wilayah (Provinsi)")
            prov_sales = df.groupby('Province')[col_uang].sum().sort_values(ascending=True).tail(10).reset_index()
            fig_prov = px.bar(prov_sales, x=col_uang, y='Province', orientation='h', color=col_uang)
            st.plotly_chart(fig_prov, use_container_width=True)
            
        with col_d:
            st.subheader("💳 Metode Pembayaran")
            pay_data = df.groupby('Payment Method').size().reset_index(name='Jumlah')
            fig_pay = px.bar(pay_data, x='Payment Method', y='Jumlah', color='Payment Method')
            st.plotly_chart(fig_pay, use_container_width=True)

        # --- TABEL RINGKASAN PRODUK ---
        st.divider()
        st.subheader("📋 Ringkasan Profit Per Produk")
        product_summary = df.groupby('Product Name').agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).sort_values('Net_Profit', ascending=False)
        st.dataframe(product_summary, use_container_width=True)

        # --- AI MANAGER ---
        st.divider()
        st.subheader("🤖 Manager AI Samareta")
        user_input = st.text_input("Tanya AI (Contoh: Produk mana yang paling laku di Jawa Barat?)")
        
        if st.button("Tanya Manager AI"):
            if user_input:
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                context = f"""
                Data Bisnis Samareta:
                - Omset: Rp {total_omset:,.0f}
                - Profit: Rp {total_profit:,.0f}
                - Produk Terlaris: {product_summary.head(3).index.tolist()}
                - Provinsi Terbanyak: {prov_sales.tail(3)['Province'].tolist()}
                
                Pertanyaan: {user_input}
                """
                
                with st.spinner("AI sedang berpikir..."):
                    response = model.generate_content(context)
                    st.info(response.text)

    except Exception as e:
        st.error(f"Terjadi kesalahan teknis: {e}")
        st.info("Pastikan file yang diupload adalah CSV asli dari TikTok Shop.")
else:
    st.info("👋 Selamat Datang! Silakan unggah file CSV 'Semua Pesanan' dari TikTok Seller Center untuk memulai.")
