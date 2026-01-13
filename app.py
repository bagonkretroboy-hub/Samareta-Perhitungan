import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Intelligence Pro", layout="wide", page_icon="💰")

# --- CUSTOM CSS (DARK MODE OPTIMIZED) ---
st.markdown("""
    <style>
    [data-testid="stMetric"] {
        background-color: #1e1e1e !important; 
        border: 1px solid #444444 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }
    [data-testid="stMetricLabel"] { color: #bbbbbb !important; font-size: 14px !important; }
    [data-testid="stMetricValue"] { color: #00ff00 !important; font-size: 24px !important; font-weight: bold !important; }
    .stDataFrame { border: 1px solid #444; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

st.title("💰 Samareta Accurate Intelligence")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Konfigurasi Secrets (MODAL_PRODUK / GEMINI_API_KEY) tidak ditemukan!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Unggah Data")
    file_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (Income)", type=["csv"])
    st.divider()
    st.info("Rumus: (Settlement - Ongkir Customer) - Modal = Profit Murni Barang")

# --- PROSES DATA ---
if file_order and file_settle:
    try:
        # 1. Load Data
        df_order = pd.read_csv(file_order)
        df_settle = pd.read_csv(file_settle, sep=';')
        
        df_order.columns = [c.strip() for c in df_order.columns]
        df_settle.columns = [c.replace('  ', ' ').strip() for c in df_settle.columns]

        # 2. Filter Tipe & Duplikat (Akurasi Keuangan)
        if 'Type' in df_settle.columns:
            df_settle = df_settle[df_settle['Type'] == 'Order']
        
        col_id_settle = 'Order/adjustment ID'
        df_settle = df_settle.drop_duplicates(subset=[col_id_settle])

        col_id_order = next((c for c in df_order.columns if 'Order ID' in c), None)
        df_order_clean = df_order[[col_id_order, 'Product Name', 'Quantity']].drop_duplicates(subset=[col_id_order])

        # 3. Merge Data
        df_settle[col_id_settle] = df_settle[col_id_settle].astype(str).str.strip()
        df_order_clean[col_id_order] = df_order_clean[col_id_order].astype(str).str.strip()
        df_final = pd.merge(df_settle, df_order_clean, left_on=col_id_settle, right_on=col_id_order, how='inner')

        # 4. Konversi Uang & Waktu
        col_settle = 'Total settlement amount'
        col_ongkir_cust = 'Shipping cost paid by the customer'
        
        df_final[col_settle] = pd.to_numeric(df_final[col_settle], errors='coerce').fillna(0)
        df_final[col_ongkir_cust] = pd.to_numeric(df_final[col_ongkir_cust], errors='coerce').fillna(0)
        df_final['Order settled time'] = pd.to_datetime(df_final['Order settled time'], errors='coerce')

        # --- LOGIKA HARGA BARANG MURNI ---
        # Kita kurangi settlement dengan ongkir yang dibayar customer agar ketemu uang asli dari barang
        df_final['Omset_Barang_Net'] = df_final[col_settle] - df_final[col_ongkir_cust]

        # 5. FILTER TANGGAL (SIDEBAR)
        min_d, max_d = df_final['Order settled time'].min().date(), df_final['Order settled time'].max().date()
        date_range = st.sidebar.date_input("Pilih Rentang Waktu", [min_d, max_d])
        
        if len(date_range) == 2:
            df_final = df_final[(df_final['Order settled time'].dt.date >= date_range[0]) & (df_final['Order settled time'].dt.date <= date_range[1])]

        # 6. HITUNG MODAL & AUDIT
        def get_cogs_audit(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in nm:
                    val = DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
                    return val, True
            return 0, False

        audit_res = df_final.apply(get_cogs_audit, axis=1)
        df_final['Total_Modal'] = [x[0] for x in audit_res]
        df_final['Modal_Found'] = [x[1] for x in audit_res]
        df_final['Actual_Profit'] = df_final['Omset_Barang_Net'] - df_final['Total_Modal']

        # --- TAMPILAN DASHBOARD ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        total_omset = df_final['Omset_Barang_Net'].sum()
        total_modal = df_final['Total_Modal'].sum()
        total_profit = df_final['Actual_Profit'].sum()

        m1.metric("Omset Barang (Net)", f"Rp {total_omset:,.0f}")
        m2.metric("Total Modal", f"Rp {total_modal:,.0f}")
        m3.metric("Profit Final", f"Rp {total_profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {total_profit/3:,.0f}")

        # 7. Visualisasi
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df_final.groupby(df_final['Order settled time'].dt.date)['Actual_Profit'].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Order settled time', y='Actual_Profit', title="Tren Profit Harian", template="plotly_dark"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_final, values='Actual_Profit', names='Product Name', title="Kontribusi Produk", hole=0.4, template="plotly_dark"), use_container_width=True)

        # 8. Tabel Detail
        df_final['Tgl'] = df_final['Order settled time'].dt.date
        summary = df_final.groupby(['Tgl', 'Product Name', 'Modal_Found']).agg({
            'Quantity': 'sum',
            'Omset_Barang_Net': 'sum',
            'Total_Modal': 'sum',
            'Actual_Profit': 'sum'
        }).reset_index().sort_values('Tgl', ascending=False)

        st.subheader("📋 Audit Rincian Transaksi")
        st.dataframe(summary.style.apply(lambda x: ['background-color: #441111' if not x.Modal_Found else '' for i in x], axis=1), use_container_width=True)

        # 9. PROMPT AI STRATEGIST
        st.divider()
        st.subheader("🤖 AI Business Strategist")
        u_in = st.text_input("Tanya AI (Contoh: Berikan saran produk mana yang harus dipertahankan?)")
        
        if st.button("Analisis AI") and u_in:
            try:
                genai.configure(api_key=API_KEY)
                model = genai.GenerativeModel('gemini-1.5-flash')
                context = summary.head(40).to_string(index=False)
                prompt = f"""Data Penjualan Samareta:
                {context}
                
                Profit Total: Rp {total_profit:,.0f}
                
                Tugas: Jawab pertanyaan user berikut berdasarkan data di atas secara profesional dan singkat.
                Pertanyaan: {u_in}"""
                
                with st.spinner("AI sedang berpikir..."):
                    res = model.generate_content(prompt)
                    st.info(res.text)
            except Exception as e:
                st.error(f"AI Error: {e}")

    except Exception as e:
        st.error(f"Terjadi kesalahan: {e}")
else:
    st.info("Harap unggah kedua file CSV untuk mengaktifkan dashboard.")
