import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- CONFIGURASI DASAR ---
st.set_page_config(page_title="-`♡´-SAMARETA BERJAYA-`♡´-", layout="wide", page_icon="📈")
st.title("⸜(｡˃ ᵕ ˂ )⸝♡ -SAMARETA BERJAYA-")

# --- KONFIGURASI MODAL DARI SECRETS ---
try:
    daftar_modal = st.secrets["MODAL_PRODUK"]
except:
    daftar_modal = {"DEFAULT": 25000}

with st.sidebar:
    st.header("⚙️ Filter & Konfigurasi")
    modal_fix = st.number_input("Modal Default (Rp)", value=int(daftar_modal.get("DEFAULT", 25000)))
    
    st.divider()
    search_query = st.text_input("🔍 Cari Produk (Filter Tabel & AI)", "")
    st.info("Ketik nama produk untuk memfilter data sebelum dianalisis AI.")

uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Identifikasi Kolom
        col_pendapatan = next((c for c in df.columns if any(k.lower() in c.lower() for k in ['penghasilan', 'amount', 'settlement', 'total'])), None)
        col_nama_produk = next((c for c in df.columns if any(k in c.lower() for k in ['product', 'nama', 'item'])), None)

        if col_pendapatan and col_nama_produk:
            # 1. FILTER DATA
            if search_query:
                df = df[df[col_nama_produk].str.contains(search_query, case=False, na=False)]

            # 2. HITUNG MODAL OTOMATIS
            def get_modal(row):
                nama_item = str(row[col_nama_produk]).lower()
                qty = row.get('Quantity', 1)
                for key, harga in daftar_modal.items():
                    if key.lower() in nama_item:
                        return harga * qty
                return modal_fix * qty

            df['Modal_Baris'] = df.apply(get_modal, axis=1)
            df[col_pendapatan] = pd.to_numeric(df[col_pendapatan], errors='coerce')
            
            # 3. KALKULASI ANGKA UTAMA
            omset = df[col_pendapatan].sum()
            orders = len(df)
            total_modal = df['Modal_Baris'].sum()
            profit = omset - total_modal
            
            # 4. TAMPILAN DASHBOARD
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Omset (Filtered)", f"Rp {omset:,.0f}")
            c2.metric("Orders", f"{orders}")
            c3.metric("Total Modal", f"Rp {total_modal:,.0f}")
            c4.metric("Profit Bersih", f"Rp {profit:,.0f}")

            st.success(f"### 🤝 Jatah Per Orang (Bagi 3): Rp {profit/3:,.0f}")

            with st.expander("📂 Lihat Detail Data Terfilter"):
                st.dataframe(df[[col_nama_produk, col_pendapatan, 'Modal_Baris']], use_container_width=True)

            # --- 5. TANYA AI ---
            st.divider()
            st.subheader("🤖 Tanya Manajer AI tentang Data Ini")
            user_instruction = st.text_area("Apa yang ingin Anda ketahui?", placeholder="Contoh: Berikan ringkasan performa penjualan produk ini...")
            
            if st.button("Kirim ke AI"):
                if user_instruction:
                    try:
                        api_key = st.secrets["GEMINI_API_KEY"]
                        genai.configure(api_key=api_key)
                        
                        # Ambil daftar model yang support generateContent
                        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        
                        # PERBAIKAN DI SINI: Memastikan kurung tutup lengkap
                        selected_model = next((m for m in models if 'flash' in m), models[0])
                        
                        model = genai.GenerativeModel(selected_model)
                        
                        sample_data = df[[col_nama_produk, col_pendapatan]].head(15).to_string()
                        
                        full_prompt = f"""
                        Data Bisnis Saya:
                        - Omset: Rp {omset:,.0f}
                        - Modal: Rp {total_modal:,.0f}
                        - Profit: Rp {profit:,.0f}
                        - Sampel Data Produk:
                        {sample_data}

                        Pertanyaan/Instruksi User: {user_instruction}
                        """

                        with st.spinner(f'Menganalisis dengan {selected_model}...'):
                            response = model.generate_content(full_prompt)
                            st.info(f"**Jawaban AI:**\n\n{response.text}")
                    except Exception as e:
                        st.error(f"Gagal menghubungi AI: {e}")
                else:
                    st.warning("Silakan isi pertanyaan Anda.")
        else:
            st.error("Kolom 'Product Name' atau 'Amount' tidak ditemukan di CSV!")
    except Exception as e:
        st.error(f"Error Aplikasi: {e}")
