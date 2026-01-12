import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="📊")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("📊 Samareta Business Intelligence")

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
    uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])
    st.divider()
    
    if uploaded_file:
        # TikTok CSV sering memiliki karakter tab (\t) di akhir string, kita bersihkan
        df_raw = pd.read_csv(uploaded_file)
        df_raw = df_raw.applymap(lambda x: x.strip().replace('\t', '') if isinstance(x, str) else x)
        df_raw.columns = [c.strip().replace('\t', '') for c in df_raw.columns]
        
        # Konversi Tanggal
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

        # --- LOGIKA HITUNG MODAL ---
        def get_cogs(row):
            nama_produk = str(row['Product Name']).lower()
            quantity = row['Quantity']
            
            # Urutkan kunci modal dari yang terpanjang (Priority Match)
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            
            # Tahap 1: Cari Paket dulu
            for kunci in sorted_keys:
                kunci_low = kunci.lower()
                if kunci_low in nama_produk:
                    # Jika nama kunci mengandung kata "paket", gunakan harga tersebut (jangan dikali quantity lagi)
                    if "paket" in kunci_low:
                        return DAFTAR_MODAL[kunci]
                    # Jika bukan paket, asumsikan harga satuan, kalikan dengan quantity
                    return DAFTAR_MODAL[kunci] * quantity
            
            return 0

        df['Total_Modal'] = df.apply(get_cogs, axis=1)
        df['Net_Profit'] = df[col_uang] - df['Total_Modal']

        # --- VALIDASI PRODUK TANPA MODAL ---
        unmapped = df[df['Total_Modal'] == 0]['Product Name'].unique()
        if len(unmapped) > 0:
            st.warning(f"⚠️ Ditemukan {len(unmapped)} produk belum terdaftar modalnya.")
            with st.expander("Klik untuk lihat daftar"):
                for p in unmapped:
                    st.write(f"- {p}")

        # --- METRIK UTAMA ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        total_omset = df[col_uang].sum()
        total_modal = df['Total_Modal'].sum()
        total_profit = df['Net_Profit'].sum()
        
        m1.metric("Total Omset", f"Rp {total_omset:,.0f}")
        m2.metric("Total Modal", f"Rp {total_modal:,.0f}")
        m3.metric("Profit Bersih", f"Rp {total_profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {total_profit/3:,.0f}")

        # --- VISUALISASI ---
        col_left, col_right = st.columns([2,1])
        with col_left:
            st.subheader("📈 Tren Omset")
            daily = df.groupby(df['Created Time'].dt.date)[col_uang].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Created Time', y=col_uang), use_container_width=True)
        with col_right:
            st.subheader("🍕 Kategori")
            st.plotly_chart(px.pie(df, values=col_uang, names='Product Category', hole=0.4), use_container_width=True)

        # --- TABEL PRODUK ---
        st.subheader("📋 Detail Performa Produk")
        product_summary = df.groupby('Product Name').agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).sort_values('Net_Profit', ascending=False)
        st.dataframe(product_summary, use_container_width=True)

        # --- AI ---
        st.divider()
        st.subheader("🤖 AI Strategist")
        user_input = st.text_input("Tanyakan sesuatu tentang data ini:")
        if st.button("Analisis") and user_input:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Data Samareta: Omset {total_omset}, Profit {total_profit}. Top Produk: {product_summary.head(3).index.tolist()}. Pertanyaan: {user_input}"
            res = model.generate_content(prompt)
            st.info(res.text)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Silakan unggah file CSV TikTok di sidebar.")
