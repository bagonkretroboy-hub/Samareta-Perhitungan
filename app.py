import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG ---
st.set_page_config(page_title="Samareta Modal Audit", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #1e1e1e !important; border: 1px solid #444; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; }
    .stDataFrame { border: 1px solid #444; }
    .highlight { background-color: #441111; padding: 5px; border-radius: 3px; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta: Koreksi & Audit Modal")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("⚠️ Secrets belum terisi! Silakan isi MODAL_PRODUK di Settings Streamlit.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Data Source")
    f_order = st.file_uploader("1. CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("2. CSV SETTLEMENT", type=["csv"])
    st.divider()
    st.write("### 📝 Daftar Modal di Secrets Anda:")
    st.json(dict(DAFTAR_MODAL)) # Menampilkan isi secrets agar mudah dicocokkan

if f_order and f_settle:
    try:
        # 1. Load & Clean
        df_o = pd.read_csv(f_order)
        df_s = pd.read_csv(f_settle, sep=';')
        df_o.columns = [c.strip() for c in df_o.columns]
        df_s.columns = [c.replace('  ', ' ').strip() for c in df_s.columns]

        # 2. Filter & Merge
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=['Order/adjustment ID'])
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = next(c for c in df_o.columns if 'Order create time' in c or 'Created Time' in c)
        
        df_o_clean = df_o[[col_id_o, 'Product Name', 'Quantity', col_time_o]].drop_duplicates(subset=[col_id_o])
        df_merged = pd.merge(df_s, df_o_clean, left_on='Order/adjustment ID', right_on=col_id_o, how='inner')

        # 3. Konversi Uang & Waktu
        df_merged['Settlement'] = pd.to_numeric(df_merged['Total settlement amount'], errors='coerce').fillna(0)
        df_merged['Ongkir_Cust'] = pd.to_numeric(df_merged['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_merged['Time'] = pd.to_datetime(df_merged[col_time_o])
        
        # Uang murni barang (Settlement - Ongkir Numpang Lewat)
        df_merged['Net_Revenue'] = df_merged['Settlement'] - df_merged['Ongkir_Cust']

        # 4. LOGIKA AUDIT MODAL (Sangat Transparan)
        def audit_modal_logic(row):
            product_name = str(row['Product Name']).lower()
            qty = row['Quantity']
            match_key = "TIDAK DITEMUKAN"
            price_per_unit = 0
            
            # Urutkan kunci secrets dari yang terpanjang agar pencocokan lebih akurat
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            
            for key in sorted_keys:
                if key.lower() in product_name:
                    match_key = key
                    price_per_unit = DAFTAR_MODAL[key]
                    break
            
            # Jika ada kata 'paket', modal biasanya tidak dikali qty (sudah harga paket)
            is_paket = "paket" in match_key.lower() or "isi" in match_key.lower()
            total_modal = price_per_unit if is_paket else price_per_unit * qty
            
            return pd.Series([match_key, price_per_unit, total_modal])

        df_merged[['Key_Ditemukan', 'Harga_Satuan', 'Total_Modal']] = df_merged.apply(audit_modal_logic, axis=1)
        df_merged['Profit'] = df_merged['Net_Revenue'] - df_merged['Total_Modal']

        # 5. Filter Tanggal
        dr = st.sidebar.date_input("Filter Tanggal Pesanan", [df_merged['Time'].min().date(), df_merged['Time'].max().date()])
        if len(dr) == 2:
            df_merged = df_merged[(df_merged['Time'].dt.date >= dr[0]) & (df_merged['Time'].dt.date <= dr[1])]

        # --- TAMPILAN METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        total_p = df_merged['Profit'].sum()
        m1.metric("Omset Net Barang", f"Rp {df_merged['Net_Revenue'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_merged['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Bersih", f"Rp {total_p:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {total_p/3:,.0f}")

        # --- BAGIAN AUDIT (KOREKSI DI SINI) ---
        st.subheader("🔍 Tabel Koreksi: Apakah Modal Sudah Benar?")
        st.info("Cek kolom 'Key_Ditemukan'. Jika isinya 'TIDAK DITEMUKAN', berarti nama produk di Secrets tidak cocok dengan nama di TikTok.")
        
        audit_df = df_merged[['Time', 'Product Name', 'Quantity', 'Key_Ditemukan', 'Harga_Satuan', 'Total_Modal', 'Net_Revenue', 'Profit']]
        
        # Beri warna merah pada baris yang modalnya 0
        def highlight_missing(s):
            return ['background-color: #441111' if s.Key_Ditemukan == "TIDAK DITEMUKAN" else '' for _ in s]
        
        st.dataframe(audit_df.style.apply(highlight_missing, axis=1), use_container_width=True)

        # AI Analyst
        st.divider()
        u_in = st.text_input("Tanya AI (Contoh: Mengapa produk A profitnya kecil?)")
        if st.button("Analisis AI") and u_in:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(f"Data: {audit_df.head(30).to_string()}\n\nUser: {u_in}")
            st.info(res.text)

    except Exception as e:
        st.error(f"Error: {e}")
