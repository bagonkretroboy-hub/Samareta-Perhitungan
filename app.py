import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="AI Business Manager", layout="centered", page_icon="📈")
st.title("📈 AI Business Manager")

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    api_key = st.text_input("Masukkan Gemini API Key", type="password")
    modal_fix = st.number_input("Modal per Barang (Rp)", value=25000)
    st.divider()
    st.info("API Key digunakan untuk analisis strategi oleh AI.")

uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        keywords = ['Penghasilan', 'Amount', 'Settlement', 'Total']
        target_col = next((c for c in df.columns if any(k.lower() in c.lower() for k in keywords)), None)

        if target_col:
            omset = pd.to_numeric(df[target_col], errors='coerce').sum()
            orders = len(df)
            modal = orders * modal_fix
            profit = omset - modal
            bagi_hasil = profit / 3

            # --- DASHBOARD ANGKA ---
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Total Omset", f"Rp {omset:,.0f}")
            c1.metric("Total Order", f"{orders} Pesanan")
            c2.metric("Total Modal", f"Rp {modal:,.0f}")
            c2.metric("Profit Bersih", f"Rp {profit:,.0f}")
            st.success(f"### 🤝 Jatah Per Orang: Rp {bagi_hasil:,.0f}")

            # --- BAGIAN ANALISIS AI ---
            st.divider()
            st.subheader("🤖 Analisis Strategi Manager AI")
            
            if st.button("Jalankan Analisis AI"):
                if api_key:
                    try:
                        genai.configure(api_key=api_key)
                        # Auto-detect model yang tersedia
                        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        model_name = next((m for m in models if 'gemini-1.5-flash' in m), models[0])
                        model = genai.GenerativeModel(model_name)

                        # --- DI SINI LETAK PROMPT-NYA ---
                        prompt = f"""
                        Anda adalah seorang Manajer Bisnis E-commerce ahli. 
                        Analisis data penjualan TikTok berikut:
                        - Total Omset: Rp {omset:,.0f}
                        - Jumlah Order: {orders}
                        - Modal (HPP): Rp {modal:,.0f}
                        - Profit Bersih: Rp {profit:,.0f}

                        Berikan analisis singkat dalam 3 poin:
                        1. Evaluasi margin keuntungan (apakah sehat atau tipis?).
                        2. Strategi untuk meningkatkan jumlah order berdasarkan profit saat ini.
                        3. Pesan motivasi singkat untuk tim yang terdiri dari 3 orang.
                        Gunakan bahasa yang santai tapi profesional.
                        """
                        # --------------------------------

                        with st.spinner('Manajer AI sedang berpikir...'):
                            response = model.generate_content(prompt)
                            st.markdown(f"**Hasil Analisis:**\n\n{response.text}")
                    
                    except Exception as e:
                        st.error(f"Gagal memanggil AI: {e}")
                else:
                    st.error("Silakan masukkan API Key di sidebar!")
        else:
            st.error("Kolom pendapatan tidak ditemukan!")
    except Exception as e:
        st.error(f"Error: {e}")
