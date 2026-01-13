import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px

# --- CONFIG DASHBOARD ---
st.set_page_config(page_title="Samareta Audit Intelligence", layout="wide", page_icon="📊")

# --- CUSTOM CSS (HIGH CONTRAST DARK MODE) ---
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

st.title("📊 Samareta Business Intelligence (Audit Mode)")

# --- LOAD SECRETS ---
try:
    DAFTAR_MODAL = st.secrets["MODAL_PRODUK"]
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    st.error("Secrets (MODAL_PRODUK / GEMINI_API_KEY) belum dikonfigurasi di Streamlit Cloud!")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Data Source")
    file_order = st.file_uploader("1. Upload CSV PESANAN", type=["csv"])
    file_settle = st.file_uploader("2. Upload CSV SETTLEMENT (Income)", type=["csv"])
    st.info("Sistem akan memvalidasi apakah setiap produk sudah memiliki harga modal di Secrets.")

# --- PROSES DATA ---
if file_order and file_settle:
    try:
        # 1. Load & Clean
        df_order = pd.read_csv(file_order)
        df_settle = pd.read_csv(file_settle, sep=';')
        
        df_order.columns = [c.strip() for c in df_order.columns]
        df_settle.columns = [c.replace('  ', ' ').strip() for c in df_settle.columns]

        # 2. ANTI-DUPLIKASI (PENTING AGAR TIDAK BENGKAK)
        if 'Type' in df_settle.columns:
            df_settle = df_settle[df_settle['Type'] == 'Order']
        
        col_id_settle = 'Order/adjustment ID'
        df_settle = df_settle.drop_duplicates(subset=[col_id_settle])

        col_id_order = next((c for c in df_order.columns if 'Order ID' in c), None)
        df_order_clean = df_order[[col_id_order, 'Product Name', 'Quantity']].drop_duplicates(subset=[col_id_order])

        # 3. Merge
        df_settle[col_id_settle] = df_settle[col_id_settle].astype(str).str.strip()
        df_order_clean[col_id_order] = df_order_clean[col_id_order].astype(str).str.strip()

        df_final = pd.merge(df_settle, df_order_clean, left_on=col_id_settle, right_on=col_id_order, how='inner')

        # 4. Konversi Uang & Waktu
        col_uang = 'Total settlement amount'
        df_final[col_uang] = pd.to_numeric(df_final[col_uang], errors='coerce').fillna(0)
        df_final['Order settled time'] = pd.to_datetime(df_final['Order settled time'], errors='coerce')

        # 5. Filter Tanggal
        min_d, max_d = df_final['Order settled time'].min().date(), df_final['Order settled time'].max().date()
        dr = st.sidebar.date_input("Rentang Waktu", [min_d, max_d])
        if len(dr) == 2:
            df_final = df_final[(df_final['Order settled time'].dt.date >= dr[0]) & (df_final['Order settled time'].dt.date <= dr[1])]

        # 6. LOGIKA AUDIT MODAL
        def get_cogs_audit(row):
            nm, qty = str(row['Product Name']).lower(), row['Quantity']
            sorted_keys = sorted(DAFTAR_MODAL.keys(), key=len, reverse=True)
            for k in sorted_keys:
                if k.lower() in nm:
                    # Menghitung modal
                    val = DAFTAR_MODAL[k] if "paket" in k.lower() else DAFTAR_MODAL[k] * qty
                    return val, True # Ketemu
            return 0, False # Tidak ketemu

        audit_results = df_final.apply(get_cogs_audit, axis=1)
        df_final['Total_Modal'] = [x[0] for x in audit_results]
        df_final['Modal_Found'] = [x[1] for x in audit_results]
        df_final['Net_Profit'] = df_final[col_uang] - df_final['Total_Modal']

        # --- NOTIFIKASI AUDIT ---
        not_found = df_final[df_final['Modal_Found'] == False]
        if not not_found.empty:
            st.warning(f"⚠️ Ditemukan {len(not_found)} transaksi tanpa harga modal di Secrets!")
            with st.expander("Klik untuk lihat produk yang belum terdaftar di Secrets"):
                st.write(not_found['Product Name'].unique())

        # --- METRIK UTAMA ---
        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        cair = df_final[col_uang].sum()
        modal = df_final['Total_Modal'].sum()
        profit = df_final['Net_Profit'].sum()

        m1.metric("Uang Cair (Net)", f"Rp {cair:,.0f}")
        m2.metric("Total Modal", f"Rp {modal:,.0f}")
        m3.metric("Profit Bersih", f"Rp {profit:,.0f}")
        m4.metric("Bagi Hasil (1/3)", f"Rp {profit/3:,.0f}")

        # 7. Visualisasi
        c1, c2 = st.columns([2,1])
        with c1:
            daily = df_final.groupby(df_final['Order settled time'].dt.date)[col_uang].sum().reset_index()
            st.plotly_chart(px.line(daily, x='Order settled time', y=col_uang, title="Tren Pencairan", template="plotly_dark"), use_container_width=True)
        with c2:
            st.plotly_chart(px.pie(df_final, values=col_uang, names='Product Name', title="Kontribusi Produk", hole=0.4, template="plotly_dark"), use_container_width=True)

        # 8. Tabel Detail
        df_final['Tgl'] = df_final['Order settled time'].dt.date
        summary = df_final.groupby(['Tgl', 'Product Name', 'Modal_Found']).agg({
            'Quantity': 'sum',
            col_uang: 'sum',
            'Total_Modal': 'sum',
            'Net_Profit': 'sum'
        }).reset_index().sort_values('Tgl', ascending=False)

        st.subheader("📋 Rincian Transaksi & Status Modal")
        # Beri warna pada baris yang modalnya tidak ditemukan
        st.dataframe(summary.style.apply(lambda x: ['background-color: #721c24' if not x.Modal_Found else '' for i in x], axis=1), use_container_width=True)

        # 9. AI ANALYST
        st.divider()
        u_in = st.text_input("Tanya AI (Contoh: Mengapa profit saya tidak sesuai hitungan manual?):")
        if st.button("Tanya AI") and u_in:
            genai.configure(api_key=API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            # Kirim info audit ke AI
            prompt = f"Data: {summary.head(30).to_string()}\nUser: {u_in}\nInfo: Ada {len(not_found)} produk tanpa modal."
            res = model.generate_content(prompt)
            st.info(res.text)

    except Exception as e:
        st.error(f"Error: {e}")
else:
    st.info("Silakan unggah file Pesanan dan Settlement.")
