import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="AI Business Manager", layout="centered", page_icon="📈")
st.title("📈 AI Business Manager")

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    modal_fix = st.number_input("Modal per Barang (Rp)", value=25000)
    st.divider()
    st.success("Mode Otomatis (Secrets) Aktif ✅")

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

            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Total Omset", f"Rp {omset:,.0f}")
            c1.metric("Total Order", f"{orders} Pesanan")
            c2.metric("Total Modal", f"Rp {modal:,.0f}")
            c2.metric("Profit Bersih", f"Rp {profit:,.0f}")
            st.success(f"### 🤝 Jatah Per Orang: Rp {bagi_hasil:,.0f}")

            st.divider()
            st.subheader("🤖 Analisis Strategi Manager AI")
            
            if st.button("Jalankan Analisis AI"):
                try:
                    # Mengambil API Key dari Secrets Streamlit
                    api_key = st.secrets["GEMINI_API_KEY"]
                    genai.configure(api_key=api_key)
                    
                    # Deteksi Model Otomatis
                    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                    model_name = next((m for m in models if 'gemini-1.5-flash' in m), models[0])
                    model = genai.GenerativeModel(model_name)

                    prompt = f"""
                    Analisis data penjualan TikTok ini:
                    - Omset: Rp {omset:,.0f}
                    - Order: {orders}
                    - Profit: Rp {profit:,.0f}
                    Berikan 2 saran singkat untuk meningkatkan margin keuntungan.
                    """

                    with st.spinner('Menghubungi Manajer AI...'):
                        response = model.generate_content(prompt)
                        st.markdown(f"**Saran AI:**\n\n{response.text}")
                
                except Exception as ai_err:
                    st.error(f"AI gagal merespon. Pastikan Secrets sudah diisi! Detail: {ai_err}")
        else:
            st.error("Kolom pendapatan tidak ditemukan!")
    except Exception as e:
        st.error(f"Error: {e}")
