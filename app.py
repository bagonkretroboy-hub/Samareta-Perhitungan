import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- SETUP DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide")

st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: #1e1e1e !important; border: 1px solid #444; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 22px !important; }
    .metric-sub { color: #888; font-size: 12px; margin-top: -5px; font-style: italic; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Intelligence Pro")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("⚠️ Secrets (MODAL_PRODUK / GEMINI_API_KEY) tidak ditemukan!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Data Source")
    f_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    f_settle = st.file_uploader("2. Upload CSV SETTLEMENT", type=["csv"])
    st.divider()
    st.info("Patokan: Created Time | Rumus: Settlement - Ongkir - Modal")

# --- LOGIKA PEMROSESAN ---
if f_order and f_settle:
    try:
        # 1. Load Data
        df_o = pd.read_csv(f_order)
        df_s = pd.read_csv(f_settle, sep=';')
        
        # Bersihkan spasi di nama kolom
        df_o.columns = [c.strip() for c in df_o.columns]
        df_s.columns = [c.replace('  ', ' ').strip() for c in df_s.columns]

        # 2. Sinkronisasi Data
        # Filter Settlement hanya tipe 'Order' dan ID unik
        df_s = df_s[df_s['Type'] == 'Order'].drop_duplicates(subset=['Order/adjustment ID'])
        
        # Identifikasi kolom ID dan Waktu di file pesanan
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = next(c for c in df_o.columns if 'Order create time' in c or 'Created Time' in c)
        
        # Ambil kolom yang dibutuhkan dari Pesanan
        df_o_clean = df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time_o]].drop_duplicates(subset=[col_id_o])
        
        # Merge Settlement + Pesanan
        df_final = pd.merge(df_s, df_o_clean, left_on='Order/adjustment ID', right_on=col_id_o, how='inner')

        # 3. Konversi Angka & Waktu
        df_final['Settlement'] = pd.to_numeric(df_final['Total settlement amount'], errors='coerce').fillna(0)
        df_final['Ongkir_C'] = pd.to_numeric(df_final['Shipping cost paid by the customer'], errors='coerce').fillna(0)
        df_final['Time'] = pd.to_datetime(df_final[col_time_o], errors='coerce')
        
        # Rumus Omset Bersih (Tanpa Ongkir)
        df_final['Net_Rev'] = df_final['Settlement'] - df_final['Ongkir_C']

        # 4. FILTER TANGGAL
        min_d, max_d = df_final['Time'].min().date(), df_final['Time'].max().date()
        dr = st.sidebar.date_input("Filter Rentang Waktu", [min_d, max_d])
        if len(dr) == 2:
            df_final = df_final[(df_final['Time'].dt.date >= dr[0]) & (df_final['Time'].dt.date <= dr[1])]

        # 5. LOGIKA AUDIT MODAL (Anti Tumpang Tindih + Cek Variasi)
        def get_modal_audit(row):
            # Gabungkan Nama Produk + Variasi agar "paket isi 2" terdeteksi
            combined_text = f"{str(row['Product Name'])} {str(row['Variation'])}".lower()
            qty = row['Quantity']
            match_key = "TIDAK DITEMUKAN"
            price_unit = 0
            
            # Cari dari kunci terpanjang ke terpendek
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in combined_text:
                    match_key = k
                    price_unit = DAFTAR_MODAL[k]
                    break
            
            # Penentuan apakah ini paket atau satuan
            is_paket = any(x in combined_text or x in match_key.lower() for x in ["paket", "isi", "bundle"])
            total_m = price_unit if is_paket else price_unit * qty
            tipe_l = "📦 Paket/Isi" if is_paket else f"🛍️ Satuan (x{qty})"
            
            return pd.Series([match_key, price_unit, total_m, tipe_l])

        df_final[['Key', 'Hrg_Secret', 'Total_Modal', 'Logika']] = df_final.apply(get_modal_audit, axis=1)
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # --- DISPLAY METRICS ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        q_total = df_final['Quantity'].sum()
        p_total = df_final['Profit'].sum()
        
        m1.metric("Omset Bersih", f"Rp {df_final['Net_Rev'].sum():,.0f}")
        m1.markdown(f"<p class='metric-sub'>📦 Terjual: {q_total:,.0f} pcs</p>", unsafe_allow_html=True)
        
        m2.metric("Total Modal", f"Rp {df_final['Total_Modal'].sum():,.0f}")
        m2.markdown(f"<p class='metric-sub'>💵 Berdasarkan HPP Secret</p>", unsafe_allow_html=True)
        
        m3.metric("Profit Final", f"Rp {p_total:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {p_total/3:,.0f}")

        # --- VISUALISASI ---
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df_final.groupby(df_final['Time'].dt.date)['Profit'].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Time', y='Profit', title="Tren Profit Harian", template="plotly_dark"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_final, values='Quantity', names='Product Name', title="Kontribusi Pcs", hole=0.4, template="plotly_dark"), use_container_width=True)

        # --- TABEL DETAIL ---
        st.subheader("📋 Rincian & Audit Modal")
        df_final['Tgl'] = df_final['Time'].dt.date
        audit_tab = df_final[['Tgl', 'Product Name', 'Variation', 'Key', 'Logika', 'Total_Modal', 'Profit']]
        
        def highlight_err(s):
            return ['background-color: #441111' if s.Key == "TIDAK DITEMUKAN" else '' for _ in s]
        
        st.dataframe(audit_tab.style.apply(highlight_err, axis=1), use_container_width=True)

        # --- AI STRATEGIST ---
        st.divider()
        st.subheader("🤖 AI Business Strategist")
        u_in = st.text_input("Tanya AI tentang performa Desember Anda:")
        if st.button("Analisis AI") and u_in:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            context = audit_tab.head(40).to_string(index=False)
            prompt = f"Data Transaksi:\n{context}\n\nAnalisis data tersebut dan jawab: {u_in}"
            with st.spinner("AI sedang berpikir..."):
                res = model.generate_content(prompt)
                st.info(res.text)

    except Exception as e:
        st.error(f"Kesalahan: {e}")
else:
    st.info("Silakan unggah kedua file CSV untuk melihat laporan.")
