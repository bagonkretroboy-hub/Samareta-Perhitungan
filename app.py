import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="📊")

# Custom CSS: Mengecilkan tulisan metrik agar dashboard lebih rapi
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
except Exception:
    st.error("Secrets bermasalah! Cek MODAL_PRODUK dan GEMINI_API_KEY di Streamlit Cloud.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Data")
    uploaded_file = st.file_uploader("Upload CSV TikTok (Daftar Pesanan)", type=["csv"])
    if uploaded_file:
        df_raw = pd.read_csv(uploaded_file)
        # Pembersihan data otomatis
        df_raw = df_raw.applymap(lambda x: x.strip().replace('\t', '') if isinstance(x, str) else x)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        df_raw['Created Time'] = pd.to_datetime(df_raw['Created Time'], dayfirst=True, errors='coerce')
        
        min_d, max_d = df_raw['Created Time'].min().date(), df_raw['Created Time'].max().date()
        date_range = st.date_input("Rentang Waktu", [min_d, max_d])
        sel_status = st.multiselect("Status Pesanan", df_raw['Order Status'].unique().tolist(), default=["Selesai"])

# --- PROSES DATA (PYTHON CALCULATOR) ---
if uploaded_file:
    try:
        df = df_raw.copy()
        if len(date_range) == 2:
            df = df[(df['Created Time'].dt.date >= date_range[0]) & (df['Created Time'].dt.date <= date_range[1])]
        df = df[df['Order Status'].isin(sel_status)]

        col_uang = 'SKU Subtotal After Discount'
        df[col_uang] = pd.to_numeric(df[col_uang], errors='coerce').fillna(0)

        # Fungsi pencocokan modal (Logic Python)
        def get_cogs(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            sorted_k = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_k:
                if k.lower() in nm:
                    return DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
            return 0

        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df[col_uang] - df['Total_Modal']

        # --- TAMPILAN METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        omset, modal, profit = df[col_uang].sum(), df['Total_Modal'].sum(), df['Net_Profit'].sum()
        
        m1.metric("Total Omset", f"Rp {omset:,.0f}")
        m2.metric("Total Modal", f"Rp {modal:,.0f}")
        m3.metric("Profit Bersih", f"Rp {profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {profit/3:,.0f}")

        # --- VISUALISASI ---
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df.groupby(df['Created Time'].dt.date)[col_uang].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Created Time', y=col_uang, title="Tren Omset Harian", template="plotly_white"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df, values=col_uang, names='Product Category', title="Kategori Terlaris", hole=0.4), use_container_width=True)

        # --- TABEL RINGKASAN PRODUK ---
        st.subheader("📋 Performa Detail per Produk")
        summary = df.groupby('Product Name').agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).sort_values('Net_Profit', ascending=False)
        st.dataframe(summary, use_container_width=True)

        # --- AI BUSINESS CONSULTANT (HYBRID VERSION) ---
        st.divider()
        st.subheader("🤖 AI Strategist (Hybrid)")
        u_in = st.text_input("Tanya AI Manager (Contoh: Analisis produk mana yang untungnya paling kecil):")
        
        if st.button("Jalankan Analisis AI") and u_in:
            try:
                genai.configure(api_key=API_KEY)
                
                # Mendeteksi model yang tersedia secara dinamis
                available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                selected_model = next((m for m in available_models if "1.5-flash" in m), available_models[0])
                model = genai.GenerativeModel(selected_model)
                
                # Menyiapkan data untuk dikirim ke AI (Hybrid Context)
                # Kita kirimkan ringkasan semua produk agar AI bisa menyisir semuanya
                product_context = summary.to_string()
                
                prompt = f"""
                Kamu adalah Senior Business Consultant untuk toko 'Samareta'.
                Analisis data berikut yang sudah dihitung akurat oleh sistem:

                RINGKASAN KEUANGAN:
                - Omset Total: Rp {omset:,.0f}
                - Modal Total: Rp {modal:,.0f}
                - Profit Bersih: Rp {profit:,.0f}

                DETAIL PRODUK (Nama, Qty Terjual, Omset, Profit):
                {product_context}

                PERTANYAAN USER: "{u_in}"

                TUGASMU:
                1. Jawab pertanyaan user berdasarkan data di atas.
                2. Berikan 1 saran strategis (marketing atau stok) yang paling relevan.
                3. Gunakan Bahasa Indonesia yang profesional tapi mudah dimengerti.
                """
                
                with st.spinner("AI sedang menganalisis seluruh data produk..."):
                    response = model.generate_content(prompt)
                    st.info(f"💡 **Analisis AI ({selected_model}):**\n\n{response.text}")
                    
            except Exception as e:
                st.error(f"Gagal memanggil AI: {e}")

    except Exception as e:
        st.error(f"Terjadi kesalahan saat memproses data: {e}")
else:
    st.info("Silakan unggah file CSV TikTok di sidebar untuk memulai.")
