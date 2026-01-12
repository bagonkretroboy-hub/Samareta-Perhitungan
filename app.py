import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
from datetime import datetime

# --- 1. DATA MODAL (Sesuai List Anda) ---
# Data ini dipetakan agar sistem mencari nama terpanjang lebih dulu
DAFTAR_MODAL = {
    "Arkanda kotak-kokak mul (paket isi 4)": 120000,
    "Arkanda kotak-kokak mul (paket isi 3)": 100000,
    "Arkanda kotak-kokak mul (paket isi 2)": 60000,
    "Arkanda kotak-kokak mul": 30000,
    "Baron - Kaos pendek jumbo baby terry (isi 4)": 104000,
    "Baron - Kaos pendek jumbo baby terry": 26000,
    "celana jumbo kaos wanita itachi (paket isi 5)": 580000,
    "celana jumbo kaos wanita itachi (paket isi 4)": 116000,
    "celana jumbo kaos wanita itachi (paket isi 3)": 87000,
    "Celana kaos jumbo wanita itachi": 21000,
    "Nollan paket isi 3": 78000,
    "Celana kaos nollan": 26000,
    "celana kaos pria alaska jumbo (paket isi 5)": 130000,
    "celana kaos pria alaska jumbo (paket isi 3)": 87000,
    "Celana kaos pria alaska jumbo di bawah lutut": 21000,
    "Celana kotak isi 3 Yanto di atas lutut": 75000,
    "Celana kurduroy Yanto": 33000,
    "Celana pendek paket isi 3": 60000,
    "Celana santai kaos pria itaka (paket isi 3)": 100000,
    "Celana sirwal Ayah": 75000,
    "Celana tribal paket isi 3 yanto": 75000,
    "Celana tribal motif Yanto kantau": 25000,
    "Daisy paket isi 4": 132000,
    "Daisy paket isi 3": 91000,
    "Daisy paket isi 2": 66000,
    "Daisy": 33000,
    "Florals lavender (paket isi 2)": 46000,
    "Jumbo Yanto (paket isi 2)": 66000,
    "Jumbo Yanto": 33000,
    "Loan cargo pendek premium": 52000,
    "Loreng cargo 7/8 (paket isi 2)": 64000,
    "Loreng cargo 7/8": 32000,
    "Nado paket isi 4": 104000,
    "Nado pants isi 3": 90000,
    "Nado pants isi 2": 60000,
    "Nado Pants": 26000,
    "Nesa paket isi 3": 100000,
    "Nesa": 30000,
    "Noah paket isi 3": 94500,
    "Noah paket isi 2": 63000,
    "Noah Jumbo": 35000,
    "Noah": 31500,
    "Noka paket isi 4 rami di bawah lutut": 104000,
    "noka paket isi 3": 78000,
    "Noka paket isi 2": 52000,
    "Noka rami di bawah lutut": 26000,
    "Paket isi 3 sizukan": 75000,
    "Raskal (paket isi 3)": 114000,
    "Raskal - Cargo kantong 3": 38000,
    "Ratali pants (paket isi 4)": 116000,
    "Ratali pants (paket isi 3)": 87000,
    "Ratali Pants (kaos baby terry jumbo di bawah lutut)": 21000,
    "Tiedye Hotpants": 60000,
    "Tiedye XXL Paket isi 3": 100000,
    "Tiedye XXL": 30000,
    "Tiedye XL paket isi 3": 100000,
    "Tiedye XL": 30000,
    "Titan paket isi 3": 75000,
    "Tora Loreng cargo army (paket isi 2)": 64000,
    "Tora Loreng cargo army": 32000,
    "Ziatbu (paket isi 3)": 91000,
    "Ziatbu": 33000,
    "Celana pendek Yovas di atas lutut - Hawaii": 28000,
    "Bebos": 43000,
    "Bernadi levis BND": 43000
}

# --- 2. CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Pro Analytics", layout="wide", page_icon="🚀")
st.title("🚀 Samareta Business Dashboard")

# --- 3. SIDEBAR FILTERS ---
with st.sidebar:
    st.header("🔍 Filter Data")
    uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])
    st.divider()
    
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file)
        # Clean Data Tanggal & Uang (TikTok CSV often has tabs '\t')
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'].str.strip(), dayfirst=True, errors='coerce')
        df_raw['SKU Subtotal After Discount'] = pd.to_numeric(df_raw['SKU Subtotal After Discount'], errors='coerce').fillna(0)
        
        # Date Filter
        min_date = df_raw['Created Time'].min().date()
        max_date = df_raw['Created Time'].max().date()
        date_range = st.date_input("Rentang Waktu", [min_date, max_date])
        
        # Status Filter
        status_list = df_raw['Order Status'].unique().tolist()
        sel_status = st.multiselect("Status Pesanan", status_list, default=["Selesai"])
        
        # Payment Filter
        pay_list = df_raw['Payment Method'].unique().tolist()
        sel_pay = st.multiselect("Metode Pembayaran", pay_list, default=pay_list)

# --- 4. LOGIKA PERHITUNGAN ---
if uploaded_file:
    try:
        df = df_raw.copy()
        
        # Jalankan Filter
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]
        df = df[df['Order Status'].isin(sel_status)]
        df = df[df['Payment Method'].isin(sel_pay)]

        # Fungsi Hitung Modal Cerdas (Longest Match First)
        def get_cogs(row):
            nama_csv = str(row['Product Name']).lower()
            # Urutkan kunci dari yang terpanjang agar "Paket isi 3" ketemu sebelum "Satuan"
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for kunci in sorted_keys:
                if kunci.lower() in nama_csv:
                    return DAFTAR_MODAL[kunci]
            return 25000 * row['Quantity'] # Default jika tidak ada di list

        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df['SKU Subtotal After Discount'] - df['Total_Modal']

        # --- 5. TAMPILAN METRIK ---
        m1, m2, m3, m4 = st.columns(4)
        omset = df['SKU Subtotal After Discount'].sum()
        profit = df['Net_Profit'].sum()
        
        m1.metric("Total Omset", f"Rp {omset:,.0f}")
        m2.metric("Total Modal", f"Rp {df['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Bersih", f"Rp {profit:,.0f}")
        m4.metric("Jatah Per Orang (1/3)", f"Rp {profit/3:,.0f}")

        # --- 6. VISUALISASI ---
        st.divider()
        c1, c2 = st.columns([2, 1])
        
        with c1:
            st.subheader("📈 Tren Omset Harian")
            daily = df.groupby(df['Created Time'].dt.date)['SKU Subtotal After Discount'].sum().reset_index()
            fig_line = px.line(daily, x='Created Time', y='SKU Subtotal After Discount', markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
            
        with c2:
            st.subheader("📍 Top 10 Kota")
            top_city = df.groupby('Regency and City')['SKU Subtotal After Discount'].sum().sort_values(ascending=False).head(10).reset_index()
            fig_bar = px.bar(top_city, x='SKU Subtotal After Discount', y='Regency and City', orientation='h', color='SKU Subtotal After Discount')
            st.plotly_chart(fig_bar, use_container_width=True)

        # --- 7. TABEL & AI ---
        st.divider()
        t1, t2 = st.columns(2)
        
        with t1:
            st.subheader("📋 Ringkasan Per Produk")
            summary = df.groupby('Product Name').agg({
                'Quantity': 'sum',
                'SKU Subtotal After Discount': 'sum',
                'Net_Profit': 'sum'
            }).sort_values('Net_Profit', ascending=False)
            st.dataframe(summary, use_container_width=True)

        with t2:
            st.subheader("🤖 AI Strategis Manager")
            user_ask = st.text_area("Tanya AI tentang data ini:", placeholder="Contoh: Produk mana yang marginnya paling tipis?")
            
            if st.button("Tanya AI"):
                try:
                    api_key = st.secrets["GEMINI_API_KEY"]
                    genai.configure(api_key=api_key)
                    
                    # Detect Model
                    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    selected_model = next((m for m in models if 'flash' in m), models[0])
                    model = genai.GenerativeModel(selected_model)
                    
                    # Context untuk AI
                    prompt = f"""
                    Data Samareta:
                    Periode: {date_range}
                    Total Profit: Rp {profit:,.0f}
                    Top 3 Produk Untung: {summary.head(3).index.tolist()}
                    
                    Pertanyaan User: {user_ask}
                    """
                    
                    with st.spinner("AI sedang menganalisis..."):
                        response = model.generate_content(prompt)
                        st.info(response.text)
                except Exception as e:
                    st.error(f"Gagal memanggil AI: {e}")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("💡 Silakan unggah file CSV pesanan TikTok untuk melihat dashboard.")
