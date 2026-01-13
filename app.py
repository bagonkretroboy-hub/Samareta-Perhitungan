import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Settlement Intelligence", layout="wide", page_icon="💰")

# --- CUSTOM CSS (FIX DARK MODE CONTRAST) ---
st.markdown("""
    <style>
    /* Mengatur kotak metrik agar kontras tinggi di Dark Mode Chrome */
    [data-testid="stMetric"] {
        background-color: #1e1e1e !important; 
        border: 1px solid #333333 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }
    /* Warna Label (Teks Kecil) */
    [data-testid="stMetricLabel"] {
        color: #bbbbbb !important;
        font-size: 14px !important;
    }
    /* Warna Angka (Teks Besar) */
    [data-testid="stMetricValue"] {
        color: #00ff00 !important; /* Hijau Terang agar mudah dibaca */
        font-size: 24px !important;
        font-weight: bold !important;
    }
    /* Memperbaiki tampilan tabel agar tetap nyaman di mata */
    .stDataFrame {
        border: 1px solid #444;
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Settlement Intelligence")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Konfigurasi Secrets (MODAL_PRODUK / GEMINI_API_KEY) tidak ditemukan!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Kontrol Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN (File Biasa)", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (File Income)", type=["csv"])
    st.caption("Tips: File Income TikTok biasanya menggunakan pemisah titik koma (;)")

# --- PROSES DATA UTAMA ---
if file_order and file_settle:
    try:
        # 1. Load Data
        df_order = pd.read_csv(file_order)
        # File Settlement Anda menggunakan pemisah ;
        df_settle = pd.read_csv(file_settle, sep=';')
        
        # Bersihkan nama kolom dari spasi berlebih
        df_order.columns = [c.strip() for c in df_order.columns]
        df_settle.columns = [c.replace('  ', ' ').strip() for c in df_settle.columns]

        # 2. Identifikasi Kolom Kunci (Berdasarkan file yang Anda berikan)
        col_id_settle = 'Order/adjustment ID'
        col_id_order = next((c for c in df_order.columns if 'Order ID' in c), None)

        if not col_id_order:
            st.error("Kolom 'Order ID' tidak ditemukan di file Pesanan.")
            st.stop()

        # 3. Sinkronisasi Tipe Data (String agar bisa digabung)
        df_settle[col_id_settle] = df_settle[col_id_settle].astype(str).str.strip()
        df_order[col_id_order] = df_order[col_id_order].astype(str).str.strip()

        # 4. Gabungkan Data (Merge)
        # Mengambil Nominal dari Settle, Mengambil Nama Produk dari Order
        df_merged = pd.merge(
            df_settle, 
            df_order[[col_id_order, 'Product Name', 'Quantity']], 
            left_on=col_id_settle, 
            right_on=col_id_order, 
            how='inner'
        )

        # 5. Konversi Uang & Waktu
        col_uang = 'Total settlement amount'
        df_merged[col_uang] = pd.to_numeric(df_merged[col_uang], errors='coerce').fillna(0)
        df_merged['Order settled time'] = pd.to_datetime(df_merged['Order settled time'], errors='coerce')
        
        # 6. Filter Tanggal
        min_d = df_merged['Order settled time'].min().date()
        max_d = df_merged['Order settled time'].max().date()
        date_range = st.sidebar.date_input("Pilih Rentang Waktu", [min_d, max_d])

        df_final = df_merged.copy()
        if len(date_range) == 2:
            df_final = df_final[(df_final['Order settled time'].dt.date >= date_range[0]) & (df_final['Order settled time'].dt.date <= date_range[1])]

        # 7. Hitung Modal (COGS)
        def get_cogs(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            # Urutkan modal dari nama terpanjang agar pencocokan lebih akurat
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in nm:
                    # Jika nama mengandung kata 'paket', asumsikan itu harga per paket
                    return DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
            return 0

        df_final['Total_Modal'] = df_final.apply(get_cogs, axis=1)
        df_final['Net_Profit'] = df_final[col_uang] - df_final['Total_Modal']

        # --- DISPLAY DASHBOARD ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        total_cair = df_final[col_uang].sum()
        total_modal = df_final['Total_Modal'].sum()
        total_profit = df_final['Net_Profit'].sum()
        
        m1.metric("Uang Cair (Net TikTok)", f"Rp {total_cair:,.0f}")
        m2.metric("Total Modal (COGS)", f"Rp {total_modal:,.0f}")
        m3.metric("Untung Bersih", f"Rp {total_profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {total_profit/3:,.0f}")

        # 8. Visualisasi
        st.divider()
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df_final.groupby(df_final['Order settled time'].dt.date)[col_uang].sum().reset_index()
            fig = px.line(daily, x='Order settled time', y=col_uang, title="Tren Uang Masuk per Hari", template="plotly_dark")
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            fig_pie = px.pie(df_final, values=col_uang, names='Product Name', title="Kontribusi Produk", hole=0.4, template="plotly_dark")
            st.plotly_chart(fig_pie, use_container_width=True)

        # 9. Tabel Ringkasan untuk AI
        df_final['Tanggal'] = df_final['Order settled time'].dt.date
        summary = df_final.groupby(['Tanggal', 'Product Name']).agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Net_Profit': 'sum'
        }).reset_index().sort_values('Tanggal', ascending=False)

        st.subheader("📋 Detail Transaksi per Produk")
        st.dataframe(summary, use_container_width=True)

        # 10. AI BUSINESS ANALYST
        st.divider()
        st.subheader("🤖 AI Business Strategist")
        u_in = st.text_input("Tanya AI (Contoh: Analisis tren profit saya minggu ini):")
        
        if st.button("Jalankan Analisis AI") and u_in:
            try:
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Mengirim konteks 50 baris terakhir agar AI paham tren waktu & produk
                ai_context = summary.head(50).to_string(index=False)
                prompt = f"""
                Anda adalah konsultan bisnis toko Samareta. 
                Gunakan data SETTLEMENT (uang masuk bersih) berikut:
                
                {ai_context}
                
                Total Untung Periode Ini: Rp {total_profit:,.0f}
                
                Pertanyaan User: "{u_in}"
                Berikan jawaban berbasis data, sebutkan tanggal atau produk spesifik jika perlu.
                """
                
                with st.spinner("AI sedang menyisir data..."):
                    response = model.generate_content(prompt)
                    st.info(f"💡 **Analisis AI:**\n\n{response.text}")
            except Exception as e:
                st.error(f"Gagal memanggil AI: {e}")

    except Exception as e:
        st.error(f"Terjadi kesalahan pemrosesan: {e}")
        st.info("Pastikan file yang diunggah adalah CSV asli dari TikTok.")
else:
    st.info("👋 Selamat Datang! Harap unggah **File Pesanan** dan **File Settlement (Income)** di sidebar untuk melihat analisis.")
