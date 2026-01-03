import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="AI Business Manager", layout="centered", page_icon="📈")
st.title("📈 AI Business Manager")

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    # Sekarang kita tidak minta API Key di sini lagi
    modal_fix = st.number_input("Modal per Barang (Rp)", value=25000)
    st.divider()
    st.success("Aplikasi terhubung ke AI via Secrets ✅")

# ... (kode upload file tetap sama) ...

            if st.button("Jalankan Analisis AI"):
                try:
                    # AMBIL KEY DARI SECRETS
                    api_key = st.secrets["GEMINI_API_KEY"]
                    genai.configure(api_key=api_key)
                    
                    # (Sisa kode analisis AI lainnya tetap sama)
                    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    model_name = next((m for m in models if 'gemini-1.5-flash' in m), models[0])
                    model = genai.GenerativeModel(model_name)
                    
                    prompt = f"Berikan analisis bisnis untuk profit Rp {profit:,.0f}" # contoh prompt singkat
                    response = model.generate_content(prompt)
                    st.markdown(f"**Hasil Analisis:**\n\n{response.text}")
                except Exception as e:
                    st.error(f"Gagal mengambil API Key dari Secrets: {e}")
