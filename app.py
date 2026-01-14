import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- 1. KONFIGURASI DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="💰")

# Custom CSS untuk tampilan profesional dan kontras tinggi
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #1e1e1e !important; 
        border: 1px solid #444444 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }
    [data-testid="stMetricLabel"] { color: #bbbbbb !important; font-size: 14px !important; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 22px !important; font-weight: bold !important; }
    .metric-sub { color: #888; font-size: 12px; margin-top: -5px; font-style: italic; }
    .stDataFrame { border: 1px solid #444; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Intelligence (Order Created Time)")

# --- 2. LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except Exception as e:
    st.error("⚠️ Konfigurasi Secrets tidak ditemukan! Pastikan MODAL_PRODUK dan GEMINI_API_KEY sudah diisi di Settings Streamlit Cloud.")
    st.stop()

# --- 3. SIDEBAR (UPLOAD & FILTER) ---
with st.sidebar:
    st.header("⚙️ Data Source")
    file_order = st.file_uploader("1. Upload CSV PESANAN (Semua Pesanan)", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (Laporan Penghasilan)", type=["csv"])
    st.divider()
    st.write("### 📝 Info Sistem")
    st.info("Logika: Harga Paket terdeteksi otomatis dari Variasi. Modal Satuan dikali Quantity.")

# --- 4. PEMROSESAN DATA ---
if file_order and file_settle:
    try:
        # Load Data (Settlement biasanya pakai semicolon di Indonesia)
        df_o = pd.read_csv(file_order)
        try:
            df_s = pd.read_csv(file_settle, sep=';')
        except:
            df_s = pd.read_csv(file_settle) # Fallback ke comma
        
        # Bersihkan nama kolom dari spasi berlebih
        df_o.columns = [c.strip() for c in df_o.columns]
        df_s.columns = [c.replace('  ', ' ').strip() for c in df_s.columns]

        # Filter Settlement: Hanya tipe 'Order' dan ID unik
        if 'Type' in df_s.columns:
            df_s = df_s[df_s['Type'] == 'Order']
        col_id_s = 'Order/adjustment ID'
        df_s = df_s.drop_duplicates(subset=[col_id_s])
        
        # Identifikasi kolom di file Pesanan
        col_id_o = next(c for c in df_o.columns if 'Order ID' in c)
        col_time_o = next(c for c in df_o.columns if 'Order create time' in c or 'Created Time' in c)
        
        # Gabungkan Data (Merge)
        df_o_clean = df_o[[col_id_o, 'Product Name', 'Variation', 'Quantity', col_time_o]].drop_duplicates(subset=[col_id_o])
        df_final = pd.merge(df_s, df_o_clean, left_on=col_id_s, right_on=col_id_o, how='inner')

        # Konversi Angka & Waktu
        c_settle = 'Total settlement amount'
        c_ong_c = 'Shipping cost paid by the customer'
        
        df_final[c_settle] = pd.to_numeric(df_final[c_settle], errors='coerce').fillna(0)
        df_final[c_ong_c] = pd.to_numeric(df_final[c_ong_c], errors='coerce').fillna(0)
        df_final['Time'] = pd.to_datetime(df_final[col_time_o], errors='coerce')
        
        # Rumus Omset Bersih (Net Revenue)
        df_final['Net_Rev'] = df_final[c_settle] - df_final[c_ong_c]

        # Filter Rentang Tanggal berdasarkan Created Time
        min_d, max_d = df_final['Time'].min().date(), df_final['Time'].max().date()
        dr = st.sidebar.date_input("Rentang Tanggal Pesanan", [min_d, max_d])
        if len(dr) == 2:
            df_final = df_final[(df_final['Time'].dt.date >= dr[0]) & (df_final['Time'].dt.date <= dr[1])]

        # --- 5. LOGIKA AUDIT MODAL (ANTI TUMPANG TINDIH) ---
        def calculate_modal(row):
            # Gabungkan Judul + Variasi agar "paket" terdeteksi meski di variasi saja
            combined_text = f"{str(row['Product Name'])} {str(row['Variation'])}".lower()
            qty = row['Quantity']
            match_key = "TIDAK DITEMUKAN"
            price_unit = 0
            
            # Cari dari kunci terpanjang di Secrets untuk akurasi maksimal
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in combined_text:
                    match_key = k
                    price_unit = DAFTAR_MODAL[k]
                    break
            
            # Cek apakah ini produk paket atau satuan
            # Jika ada kata "paket", "isi", atau "bundle", maka harga dianggap harga total per SKU
            is_paket = any(x in combined_text or x in match_key.lower() for x in ["paket", "isi", "bundle"])
            
            total_m = price_unit if is_paket else price_unit * qty
            tipe_l = "📦 Paket (Fixed)" if is_paket else f"🛍️ Satuan (x{qty})"
            
            return pd.Series([match_key, price_unit, total_m, tipe_l])

        df_final[['Key_Found', 'Hrg_Secret', 'Total_Modal', 'Logika']] = df_final.apply(calculate_modal, axis=1)
        df_final['Profit'] = df_final['Net_Rev'] - df_final['Total_Modal']

        # --- 6. DISPLAY METRICS ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        
        total_q = df_final['Quantity'].sum()
        total_r = df_final['Net_Rev'].sum()
        total_m = df_final['Total_Modal'].sum()
        total_p = df_final['Profit'].sum()

        m1.metric("Omset Net Barang", f"Rp {total_r:,.0f}")
        m1.markdown(f"<p class='metric-sub'>📦 Volume: {total_q:,.0f} pcs</p>", unsafe_allow_html=True)
        
        m2.metric("Total Modal", f"Rp {total_m:,.0f}")
        m2.markdown(f"<p class='metric-sub'>💵 Berdasarkan HPP Secrets</p>", unsafe_allow_html=True)
        
        m3.metric("Profit Bersih", f"Rp {total_p:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {total_p/3:,.0f}")

        # --- 7. VISUALISASI ---
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df_final.groupby(df_final['Time'].dt.date)['Profit'].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Time', y='Profit', title="Tren Keuntungan Harian", template="plotly_dark"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_final, values='Quantity', names='Product Name', title="Porsi Penjualan per Produk", hole=0.4, template="plotly_dark"), use_container_width=True)

        # --- 8. TABEL AUDIT & RINCIAN ---
        st.subheader("📋 Audit Transaksi & Koreksi Modal")
        df_final['Tgl_Order'] = df_final['Time'].dt.date
        audit_tab = df_final[['Tgl_Order', 'Product Name', 'Variation', 'Key_Found', 'Logika', 'Total_Modal', 'Profit']]
        
        # Highlight baris yang modalnya tidak ditemukan
        def style_missing(s):
            return ['background-color: #441111' if s.Key_Found == "TIDAK DITEMUKAN" else '' for _ in s]
        
        st.dataframe(audit_tab.style.apply(style_missing, axis=1), use_container_width=True)

        # --- 9. AI STRATEGIST ---
        st.divider()
        st.subheader("🤖 Samareta AI Strategist")
        user_msg = st.text_input("Tanya AI (Contoh: Berikan saran strategi untuk produk yang paling menguntungkan?)")
        if st.button("Jalankan Analisis AI") and user_msg:
            try:
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                # Kirim 30 data teratas sebagai konteks
                context = audit_tab.head(30).to_string(index=False)
                prompt = f"Anda adalah analis bisnis. Berikut data penjualan kami:\n{context}\n\nPertanyaan: {user_msg}"
                with st.spinner("Menganalisis data..."):
                    response = model.generate_content(prompt)
                    st.info(response.text)
            except Exception as e:
                st.error(f"AI Error: {e}")

    except Exception as e:
        st.error(f"Gagal memproses file: {e}")
else:
    st.info("👋 Selamat Datang! Silakan unggah file CSV Pesanan dan Settlement di sidebar untuk memulai.")
