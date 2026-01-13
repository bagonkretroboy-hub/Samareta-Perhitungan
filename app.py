import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Settlement Intelligence", layout="wide", page_icon="💰")

# Custom CSS untuk Metrik
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
except:
    st.error("Konfigurasi Secrets tidak ditemukan!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Unggah Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN (Daftar Pesanan)", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (File Income)", type=["csv"])
    st.caption("Gunakan pemisah titik koma (;) untuk file Settlement.")

# --- PROSES DATA ---
if file_order and file_settle:
    try:
        # 1. Load File Pesanan
        df_order = pd.read_csv(file_order)
        df_order.columns = [c.strip() for c in df_order.columns]
        
        # 2. Load File Settlement (Sesuai file user: pemisah ;)
        df_settle = pd.read_csv(file_settle, sep=';')
        df_settle.columns = [c.strip() for c in df_settle.columns]

        # 3. Identifikasi Kolom (Berdasarkan file asli Anda)
        # Di file Anda: 'Order/adjustment ID  ' (ada spasi ganda)
        col_id_settle = 'Order/adjustment ID'
        # Kita bersihkan dulu kolom settle agar spasi hilang
        df_settle.columns = [c.replace('  ', ' ').strip() for c in df_settle.columns]
        
        # Cari kolom Order ID di file Pesanan
        col_id_order = next((c for c in df_order.columns if 'Order ID' in c), None)

        if not col_id_order:
            st.error("Kolom 'Order ID' tidak ditemukan di file Pesanan.")
            st.stop()

        # 4. Sinkronisasi Tipe Data
        df_settle[col_id_settle] = df_settle[col_id_settle].astype(str).str.strip()
        df_order[col_id_order] = df_order[col_id_order].astype(str).str.strip()

        # 5. Gabungkan Data (Merge)
        df_merged = pd.merge(
            df_settle, 
            df_order[[col_id_order, 'Product Name', 'Quantity']], 
            left_on=col_id_settle, 
            right_on=col_id_order, 
            how='inner'
        )

        # 6. Konversi Uang & Waktu
        col_uang = 'Total settlement amount'
        df_merged[col_uang] = pd.to_numeric(df_merged[col_uang], errors='coerce').fillna(0)
        df_merged['Order settled time'] = pd.to_datetime(df_merged['Order settled time'], errors='coerce')
        
        # Filter Tanggal
        min_d = df_merged['Order settled time'].min().date()
        max_d = df_merged['Order settled time'].max().date()
        date_range = st.sidebar.date_input("Rentang Waktu", [min_d, max_d])

        df_final = df_merged.copy()
        if len(date_range) == 2:
            df_final = df_final[(df_final['Order settled time'].dt.date >= date_range[0]) & (df_final['Order settled time'].dt.date <= date_range[1])]

        # 7. Hitung Modal
        def get_cogs(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            sorted_k = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_k:
                if k.lower() in nm:
                    return DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
            return 0

        df_final['Total_Modal'] = df_final.apply(get_cogs, axis=1)
        df_final['Net_Profit'] = df_final[col_uang] - df_final['Total_Modal']

        # --- TAMPILAN DASHBOARD ---
        m1, m2, m3, m4 = st.columns(4)
        cair = df_final[col_uang].sum()
        modal = df_final['Total_Modal'].sum()
        profit = df_final['Net_Profit'].sum()
        
        m1.metric("Uang Cair (Net)", f"Rp {cair:,.0f}")
        m2.metric("Total Modal", f"Rp {modal:,.0f}")
        m3.metric("Profit Final", f"Rp {profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {profit/3:,.0f}")

        # Visualisasi
        st.divider()
        daily = df_final.groupby(df_final['Order settled time'].dt.date)[col_uang].sum().reset_index()
        st.plotly_chart(px.line(daily, x='Order settled time', y=col_uang, title="Tren Pencairan Dana"), use_container_width=True)

        # Tabel Ringkasan
        st.subheader("📋 Analisis Profit per Produk")
        summary = df_final.groupby('Product Name').agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).reset_index().sort_values('Net_Profit', ascending=False)
        st.dataframe(summary, use_container_width=True)

        # AI Analyst
        st.divider()
        u_in = st.text_input("Tanya AI (Contoh: Produk apa yang paling menguntungkan?)")
        if st.button("Analisis AI") and u_in:
            try:
                genai.configure(api_key=API_KEY)
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                selected_model = next((m for m in models if "1.5-flash" in m), models[0])
                model = genai.GenerativeModel(selected_model)
                
                context = summary.head(30).to_string(index=False)
                prompt = f"Data Keuangan:\n{context}\n\nUser: {u_in}"
                with st.spinner("AI sedang menganalisis..."):
                    res = model.generate_content(prompt)
                    st.info(res.text)
            except Exception as e:
                st.error(f"AI Error: {e}")

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
else:
    st.info("💡 Unggah **File Pesanan** dan **File Settlement** (CSV) untuk melihat hasil.")
