import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="TikTok AI Manager", layout="wide", page_icon="📈")
st.title("📈 TikTok AI Business Manager")

# --- 1. KONFIGURASI SECRETS ---
try:
    daftar_modal = st.secrets["MODAL_PRODUK"]
except:
    daftar_modal = {"DEFAULT": 25000}

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    modal_fix = st.number_input("Modal Default (Rp)", value=int(daftar_modal.get("DEFAULT", 25000)))
    st.divider()
    search_query = st.text_input("🔍 Cari & Filter Produk", "")
    st.caption("Data yang difilter di sini adalah data yang akan dianalisis AI.")

uploaded_file = st.file_uploader("Upload CSV Ekspor TikTok", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        
        # Mapping Kolom TikTok (TikTok biasanya pakai bahasa Inggris/Indonesia tergantung region)
        col_pendapatan = next((c for c in df.columns if any(k in c.lower() for k in ['penghasilan', 'amount', 'settlement', 'total price'])), None)
        col_nama_produk = next((c for c in df.columns if any(k in c.lower() for k in ['product', 'nama produk', 'item name'])), None)
        col_qty = next((c for c in df.columns if any(k in c.lower() for k in ['quantity', 'jumlah', 'qty'])), 1)
        col_status = next((c for c in df.columns if any(k in c.lower() for k in ['status', 'order status'])), None)

        if col_pendapatan and col_nama_produk:
            # Filter Pencarian
            if search_query:
                df = df[df[col_nama_produk].str.contains(search_query, case=False, na=False)]

            # Hitung Modal per Baris
            def get_modal(row):
                nama_item = str(row[col_nama_produk]).lower()
                # Ambil qty, jika kolom qty tidak ada anggap 1
                qty = row[col_qty] if isinstance(col_qty, str) else 1
                for key, harga in daftar_modal.items():
                    if key.lower() in nama_item:
                        return harga * qty
                return modal_fix * qty

            df['Modal_Baris'] = df.apply(get_modal, axis=1)
            df[col_pendapatan] = pd.to_numeric(df[col_pendapatan], errors='coerce').fillna(0)
            
            # Kalkulasi Utama
            omset = df[col_pendapatan].sum()
            orders = len(df)
            total_modal = df['Modal_Baris'].sum()
            profit = omset - total_modal
            
            # Dashboard Metrik
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Omset", f"Rp {omset:,.0f}")
            c2.metric("Total Order", f"{orders}")
            c3.metric("Total Modal", f"Rp {total_modal:,.0f}")
            c4.metric("Profit Bersih", f"Rp {profit:,.0f}")
            st.success(f"### 🤝 Jatah Per Orang: Rp {profit/3:,.0f}")

            # Data Preview
            with st.expander("📂 Lihat Tabel Data Lengkap"):
                st.dataframe(df, use_container_width=True)

            # --- 2. FITUR TANYA AI (DATA LEBIH LENGKAP) ---
            st.divider()
            st.subheader("🤖 Analisis Manager AI")
            user_instruction = st.text_area("Tanyakan apa saja tentang data di atas:", placeholder="Contoh: Berapa pesanan yang statusnya 'Completed'? Atau produk apa yang paling untung?")
            
            if st.button("Kirim ke AI"):
                if user_instruction:
                    try:
                        api_key = st.secrets["GEMINI_API_KEY"]
                        genai.configure(api_key=api_key)
                        
                        # Pilih model otomatis
                        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        selected_model = next((m for m in models if 'flash' in m), models[0])
                        model = genai.GenerativeModel(selected_model)
                        
                        # Mengirim kolom penting agar AI punya konteks luas
                        kolom_analisis = [col_nama_produk, col_pendapatan]
                        if isinstance(col_qty, str): kolom_analisis.append(col_qty)
                        if col_status: kolom_analisis.append(col_status)
                        
                        # Kirim 30 baris data terfilter agar AI bisa melihat pola
                        sample_data = df[kolom_analisis].head(30).to_string()
                        
                        full_prompt = f"""
                        Analisis data TikTok Shop berikut:
                        - Total Omset: Rp {omset:,.0f}
                        - Total Modal: Rp {total_modal:,.0f}
                        - Total Profit: Rp {profit:,.0f}
                        
                        Data Detail (Sample 30 baris):
                        {sample_data}

                        Pertanyaan User: {user_instruction}
                        """

                        with st.spinner('AI sedang berpikir...'):
                            response = model.generate_content(full_prompt)
                            st.info(f"**Jawaban AI:**\n\n{response.text}")
                    except Exception as e:
                        st.error(f"Error AI: {e}")
        else:
            st.error("Gagal mendeteksi kolom TikTok. Pastikan file CSV benar.")
    except Exception as e:
        st.error(f"Error Aplikasi: {e}")
