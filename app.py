import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="AI Business Manager", layout="wide", page_icon="📈")
st.title("📈 AI Business Manager Pro")

# --- CONFIG SECRETS ---
try:
    daftar_modal = st.secrets["MODAL_PRODUK"]
except:
    daftar_modal = {"DEFAULT": 25000}

with st.sidebar:
    st.header("⚙️ Filter & Konfigurasi")
    modal_fix = st.number_input("Modal Default (Rp)", value=int(daftar_modal.get("DEFAULT", 25000)))
    
    st.divider()
    # FITUR BARU: Pencarian Produk
    search_query = st.text_input("Cari Produk (misal: Kaos)", "")
    
    # FITUR BARU: Filter Tanggal (Jika ada kolom tanggal di CSV)
    st.info("Tips: Ketik nama produk di atas untuk memfilter tabel.")

uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Standarisasi Kolom
        col_pendapatan = next((c for c in df.columns if any(k.lower() in c.lower() for k in ['penghasilan', 'amount', 'settlement', 'total'])), None)
        col_nama_produk = next((c for c in df.columns if any(k in c.lower() for k in ['product', 'nama', 'item'])), None)
        col_tanggal = next((c for c in df.columns if any(k in c.lower() for k in ['date', 'tanggal', 'time'])), None)

        if col_pendapatan and col_nama_produk:
            # FILTER DATA BERDASARKAN INPUT SIDEBAR
            if search_query:
                df = df[df[col_nama_produk].str.contains(search_query, case=False, na=False)]

            # Hitung Modal Otomatis
            def get_modal(row):
                nama_item = str(row[col_nama_produk]).lower()
                for key, harga in daftar_modal.items():
                    if key.lower() in nama_item:
                        return harga * row.get('Quantity', 1)
                return modal_fix * row.get('Quantity', 1)

            df['Modal_Baris'] = df.apply(get_modal, axis=1)
            df[col_pendapatan] = pd.to_numeric(df[col_pendapatan], errors='coerce')
            
            # Hitung Total
            omset = df[col_pendapatan].sum()
            orders = len(df)
            total_modal = df['Modal_Baris'].sum()
            profit = omset - total_modal
            
            # Tampilan Dashboard
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Omset (Filtered)", f"Rp {omset:,.0f}")
            c2.metric("Orders", f"{orders}")
            c3.metric("Profit", f"Rp {profit:,.0f}")
            c4.metric("Jatah/Orang", f"Rp {profit/3:,.0f}")

            # Tampilkan Tabel yang sudah difilter
            with st.expander("Lihat Rincian Data Terfilter"):
                st.dataframe(df[[col_nama_produk, col_pendapatan, 'Modal_Baris']])

            # --- TANYA AI TENTANG DATA TERFILTER ---
            st.divider()
            st.subheader("🤖 Analisis Data Terfilter")
            user_instruction = st.text_area("Tanya AI tentang data di atas:", placeholder="Contoh: Berikan rangkuman penjualan produk ini saja...")
            
            if st.button("Kirim ke AI"):
                if user_instruction:
                    try:
                        api_key = st.secrets["GEMINI_API_KEY"]
                        genai.configure(api_key=api_key)
                        
                        # Ambil 10 baris pertama data terfilter untuk konteks AI agar tidak terlalu panjang
                        sample_data = df[[col_nama_produk, col_pendapatan]].head(20).to_string()
                        
                        full_prompt = f"""
                        Data Terfilter:
                        - Total Omset: Rp {omset:,.0f}
                        - Total Order: {orders}
                        - Sampel Data:
                        {sample_data}

                        Instruksi: {user_instruction}
                        """

                        with st.spinner('AI sedang menganalisis...'):
                            model = genai.GenerativeModel('gemini-1.5-flash')
                            response = model.generate_content(full_prompt)
                            st.info(f"**Jawaban AI:**\n\n{response.text}")
                    except Exception as e:
                        st.error(f"Error AI: {e}")
        else:
            st.error("Kolom data tidak lengkap!")
    except Exception as e:
        st.error(f"Error: {e}")
