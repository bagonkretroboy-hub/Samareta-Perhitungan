import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

# --- 1. SETUP ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="💰")

st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #1a1a1a !important; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; }
    .stDataFrame { border: 1px solid #444; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets Belum Terisi! Pastikan MODAL_PRODUK sudah ada di Streamlit Secrets.")
    st.stop()

st.title("💰 Samareta Pro: Anti-Error Matching")

# --- 3. FUNGSI PEMBERSIH EKSTRA (KUNCI SUKSES) ---
def super_clean(text):
    """Membuang Tab, Spasi liar, dan simbol agar matching akurat"""
    if pd.isna(text): return ""
    # Buang karakter tab \t dan newline \n
    text = str(text).replace('\t', ' ').replace('\n', ' ')
    # Hanya ambil huruf dan angka, ubah ke kecil
    text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
    # Satukan spasi yang ganda
    return ' '.join(text.split()).lower()

# --- 4. SIDEBAR ---
with st.sidebar:
    st.header("Upload File TikTok")
    f_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("2. Upload CSV SETTLEMENT", type=["csv"])

if f_order and f_settle:
    try:
        # Load Data
        df_o = pd.read_csv(f_order)
        try:
            df_s = pd.read_csv(f_settle, sep=';')
        except:
            df_s = pd.read_csv(f_settle)

        # A. BERSIHKAN NAMA KOLOM DARI TAB \t
        df_o.columns = [c.replace('\t', '').strip() for c in df_o.columns]
        df_s.columns = [c.replace('\t', '').strip().replace('  ', ' ') for c in df_s.columns]

        # B. BERSIHKAN DATA DI SETIAP SEL
        df_o = df_o.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)
        df_s = df_s.applymap(lambda x: str(x).replace('\t', '').strip() if pd.notnull(x) else x)

        # C. SYNC / MERGE DATA
        col_id_s = 'Order/adjustment ID'
        col_id_o = 'Order ID'
        col_time = 'Created Time'
        
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=[col_id_s])
        df_final = pd.merge(df_s, df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time]], 
                           left_on=col_id_s, right_on=col_id_o, how='inner')

        # D. PERBAIKI TANGGAL
        df_final['Tanggal_Fix'] = pd.to_datetime(df_final[col_time], dayfirst=True, errors='coerce')

        # E. LOGIKA MATCHING MODAL
        def logic_matching(row):
            # Gabungkan Nama & Variasi, bersihkan total
            target = super_clean(f"{row['Product Name']} {row['Variation']}")
            qty = int(float(row['Quantity']))
            
            match_key = "TIDAK DITEMUKAN"
            price = 0
            
            # Cari dari kunci terpanjang di Secrets
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                clean_k = super_clean(k)
                if clean_k in target:
                    match_key = k
                    price = DAFTAR_MODAL[k]
                    break
            
            # Cek apakah paket
            is_paket = any(x in target or x in super_clean(match_key) for x in ["paket", "isi", "bundle"])
            total_m = price if is_paket else price * qty
            tipe = "📦 Paket" if is_paket else f"🛍️ Satuan (x{qty})"
            
            return pd.Series([match_key, price, total_m, tipe])

        df_final[['Key_Secrets', 'Hrg_HPP', 'Total_Modal', 'Tipe_L']] = df_final.apply(logic_matching, axis=1)

        # F. PERHITUNGAN KEUANGAN
        df_final['Settlement'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Net_Rev'] = df_final['Settlement'] - df_final['Ongkir_C']
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # --- 5. TAMPILAN ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omset Net", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Final", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        # TABEL AUDIT (UNTUK CEK YANG GAGAL)
        st.subheader("📋 Rincian Transaksi")
        st.dataframe(df_final[['Tanggal_Fix', 'Product Name', 'Variation', 'Key_Secrets', 'Total_Modal', 'Profit']], use_container_width=True)

        # ALERTI JIKA MASIH ADA YANG GAGAL
        errors = df_final[df_final['Key_Secrets'] == "TIDAK DITEMUKAN"]
        if not errors.empty:
            st.warning(f"Ada {len(errors)} produk yang belum terdaftar di Secrets!")
            st.write("Coba tambahkan kata kunci dari tabel ini ke Secrets Anda:")
            st.table(errors[['Product Name', 'Variation']].drop_duplicates())

    except Exception as e:
        st.error(f"Error Sistem: {e}")
else:
    st.info("Harap unggah kedua file CSV di samping untuk melihat hasil analisis.")
