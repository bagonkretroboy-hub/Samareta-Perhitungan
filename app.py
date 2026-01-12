import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="📊")

# Custom CSS: Metrik Kecil & Rapi
st.markdown("""
    <style>
    [data-testid="stMetricLabel"] { font-size: 13px !important; color: #666666 !important; }
    [data-testid="stMetricValue"] { font-size: 20px !important; font-weight: 700 !important; }
    [data-testid="stMetric"] { background-color: #ffffff; padding: 5px 10px !important; border-radius: 8px; border: 1px solid #eeeeee; }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Samareta Business Intelligence")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception:
    st.error("Secrets bermasalah! Cek MODAL_PRODUK dan GEMINI_API_KEY.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Data")
    uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file)
        df_raw = df_raw.applymap(lambda x: x.strip().replace('\t', '') if isinstance(x, str) else x)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'], dayfirst=True, errors='coerce')
        
        min_d, max_d = df_raw['Created Time'].min().date(), df_raw['Created Time'].max().date()
        date_range = st.date_input("Rentang Waktu", [min_d, max_d])
        sel_status = st.multiselect("Status", df_raw['Order Status'].unique().tolist(), default=["Selesai"])

# --- PROSES DATA ---
if uploaded_file:
    try:
        df = df_raw.copy()
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]
        df = df[df['Order Status'].isin(sel_status)]

        col_uang = 'SKU Subtotal After Discount'
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

        # METRIK
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        omset, modal, profit = df[col_uang].sum(), df['Total_Modal'].sum(), df['Net_Profit'].sum()
        m1.metric("Total Omset", f"Rp {omset:,.0f}")
        m2.metric("Total Modal", f"Rp {modal:,.0f}")
        m3.metric("Profit Bersih", f"Rp {profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {profit/3:,.0f}")

        # --- DATA UNTUK ANALISIS DETAIL (TANGGAL + PRODUK) ---
        # Membuat tabel gabungan Tanggal dan Produk untuk dibaca AI
        df['Tanggal_Saja'] = df['Created Time'].dt.date
        detail_analysis = df.groupby(['Tanggal_Saja', 'Product Name']).agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).reset_index()

        # VISUALISASI
        daily_trend = df.groupby('Tanggal_Saja')[col_uang].sum().reset_index()
        c1, c2 = st.columns([2,1])
        with c1:
            st.plotly_chart(px.line(daily_trend, x='Tanggal_Saja', y=col_uang, title="Tren Omset", template="plotly_white"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df, values=col_uang, names='Product Category', title="Kategori", hole=0.4), use_container_width=True)

        # TABEL RINGKASAN PRODUK
        summary = df.groupby('Product Name').agg({'Quantity':'sum', col_uang:'sum', 'Net_Profit':'sum'}).sort_values('Net_Profit', ascending=False)
        st.subheader("📋 Performa Detail per Produk")
        st.dataframe(summary, use_container_width=True)

        # --- AI STRATEGIST (VERSI ULTRA-DETAIL) ---
        st.divider()
        st.subheader("🤖 AI Strategist (Deep Analysis)")
        u_in = st.text_input("Tanya AI (Contoh: Kapan Produk A paling laku dan berapa untungnya?):")
        
        if st.button("Analisis AI Sekarang") and u_in:
            try:
                genai.configure(api_key=API_KEY)
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                selected_model = next((m for m in models if "1.5-flash" in m), models[0])
                model = genai.GenerativeModel(selected_model)
                
                # Mengirimkan data detail gabungan Tanggal & Produk ke AI
                # Kita batasi 50 baris teratas agar tidak kepanjangan (bisa disesuaikan)
                detail_context = detail_analysis.sort_values(['Net_Profit'], ascending=False).head(50).to_string(index=False)
                
                prompt = f"""
                Kamu adalah Analis Data Samareta. Gunakan data detail di bawah ini:

                DATA DETAIL (Tanggal, Nama Produk, Qty, Omset, Profit):
                {detail_context}

                PERTANYAAN USER: "{u_in}"

                TUGAS:
                Jawab dengan menyebutkan tanggal spesifik, nama produk, jumlah (pcs), dan nominal profitnya sesuai data di atas.
                Jika data tidak ditemukan dalam 50 baris teratas, beri tahu user berdasarkan tren umum.
                """
                
                with st.spinner("AI sedang menghitung detail transaksi..."):
                    res = model.generate_content(prompt)
                    st.info(f"💡 **Hasil Analisis:**\n\n{res.text}")
            except Exception as e:
                st.error(f"Gagal memanggil AI: {e}")

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Silakan unggah file CSV di sidebar.")
