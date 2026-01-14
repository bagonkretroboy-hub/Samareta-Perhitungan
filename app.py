import streamlit as st
import pandas as pd
import google.generativeai as genai
import re

# --- CONFIG ---
st.set_page_config(page_title="Samareta Pro: Fix Modal", layout="wide", page_icon="💰")

# Styling Kontras Tinggi
st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #1a1a1a !important; border: 1px solid #333; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; }
    .stDataFrame { border: 1px solid #444; }
    .err-box { background-color: #441111; color: white; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Pro: Fix Modal Error")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Gagal memuat Secrets! Pastikan MODAL_PRODUK sudah diisi di Dashboard Streamlit Cloud.")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Data Source")
    f_order = st.file_uploader("1. Upload SEMUA PESANAN", type=["csv"])
    f_settle = st.file_uploader("2. Upload SETTLEMENT", type=["csv"])
    st.divider()
    st.write("### 📝 Logika Perhitungan")
    st.info("Sistem akan mencari kata kunci di Judul Produk + Variasi secara otomatis.")

# --- LOGIKA CORE ---
if f_order and f_settle:
    try:
        # Load & Clean Kolom
        df_o = pd.read_csv(f_order)
        try:
            df_s = pd.read_csv(f_settle, sep=';')
        except:
            df_s = pd.read_csv(f_settle) # Fallback jika sep adalah koma

        df_o.columns = [c.strip() for c in df_o.columns]
        df_s.columns = [c.replace('  ', ' ').strip() for c in df_s.columns]

        # Sync Data
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=['Order/adjustment ID'])
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = next(c for c in df_o.columns if 'Order create time' in c or 'Created Time' in c)
        
        df_o_clean = df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time_o]].drop_duplicates(subset=[col_id_o])
        df_final = pd.merge(df_s, df_o_clean, left_on='Order/adjustment ID', right_on=col_id_o, how='inner')

        # --- LOGIKA PENCARIAN MODAL (FUZZY MATCHING) ---
        def normalize_text(text):
            # Buang karakter aneh agar pencocokan gampang
            return re.sub(r'[^a-zA-Z0-9\s]', ' ', str(text).lower())

        def find_modal_smart(row):
            combined_text = normalize_text(f"{row['Product Name']} {row['Variation']}")
            qty = row['Quantity']
            match_key = "TIDAK DITEMUKAN"
            price = 0
            
            # Cari dari kunci terpanjang (paling spesifik) ke yang pendek
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                clean_key = normalize_text(k)
                if clean_key in combined_text:
                    match_key = k
                    price = DAFTAR_MODAL[k]
                    break
            
            # Deteksi apakah ini paket
            is_paket = any(x in combined_text or x in normalize_text(match_key) for x in ["paket", "isi", "bundle"])
            total_m = price if is_paket else price * qty
            tipe = "📦 Paket" if is_paket else f"🛍️ Satuan (x{qty})"
            
            return pd.Series([match_key, price, total_m, tipe])

        df_final[['Key_Secrets', 'Hrg_Satuan', 'Total_Modal', 'Tipe']] = df_final.apply(find_modal_smart, axis=1)

        # Hitung Keuangan
        df_final['Settlement'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Net_Rev'] = df_final['Settlement'] - df_final['Ongkir_C']
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']
        df_final['Time'] = pd.to_datetime(df_final[col_time_o])

        # --- TAMPILAN METRIK ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Omset Bersih", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m3.metric("Profit Final", f"Rp {df_final['Profit'].sum():,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {df_final['Profit'].sum()/3:,.0f}")

        # --- WARNING BOX: PRODUK BERMASALAH ---
        missing_df = df_final[df_final['Key_Secrets'] == "TIDAK DITEMUKAN"]
        if not missing_df.empty:
            st.markdown('<div class="err-box">⚠️ Ada produk yang belum terdaftar di Secret! Tambahkan kata kunci di bawah ini ke Secrets Anda agar profit akurat.</div>', unsafe_allow_html=True)
            # Tampilkan unik produk saja yang error
            err_summary = missing_df[['Product Name', 'Variation']].drop_duplicates()
            st.table(err_summary)
        else:
            st.success("Semua produk terdeteksi dengan sempurna! ✅")

        # --- TABEL DATA ---
        with st.expander("Klik untuk lihat rincian seluruh transaksi"):
            st.dataframe(df_final[['Order/adjustment ID', 'Product Name', 'Variation', 'Key_Secrets', 'Tipe', 'Total_Modal', 'Profit']], use_container_width=True)

        # --- AI STRATEGIST ---
        st.divider()
        u_in = st.text_input("Tanya AI (Contoh: Analisa kenapa produk Arkanda paling laku?)")
        if st.button("Analisis AI") and u_in:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            context = df_final[['Product Name', 'Quantity', 'Profit']].head(30).to_string()
            res = model.generate_content(f"Data:\n{context}\n\nUser: {u_in}")
            st.info(res.text)

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
else:
    st.info("Silakan unggah file CSV Pesanan dan Settlement di sidebar.")
