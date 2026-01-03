import streamlit as st
import pandas as pd
import google.generativeai as genai
import io

st.set_page_config(page_title="TikTok Profit Splitter", layout="centered")

st.title("💰 TikTok Profit Splitter")

with st.sidebar:
    st.header("⚙️ Pengaturan")
    api_key = st.text_input("Masukkan Gemini API Key", type="password")
    modal_fix = st.number_input("Modal per Barang (Rp)", value=25000)

uploaded_file = st.file_uploader("Upload file CSV TikTok", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        # Mencari kolom pendapatan
        target_col = next((c for c in df.columns if any(k in c for k in ['Penghasilan', 'Amount', 'Settlement'])), None)

        if target_col:
            omset = pd.to_numeric(df[target_col], errors='coerce').sum()
            orders = len(df)
            modal = orders * modal_fix
            profit = omset - modal
            bagi_hasil = profit / 3

            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Total Omset", f"Rp {omset:,.0f}")
            c1.metric("Total Order", f"{orders}")
            c2.metric("Total Modal", f"Rp {modal:,.0f}")
            c2.metric("Profit Bersih", f"Rp {profit:,.0f}")
            
            st.success(f"### 🤝 Jatah Per Orang: Rp {bagi_hasil:,.0f}")

            if st.button("Minta Saran AI"):
                if api_key:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = f"Bisnis TikTok: Omset {omset}, Profit {profit}. Berikan 1 tips sukses."
                    response = model.generate_content(prompt)
                    st.info(response.text)
                else:
                    st.error("Isi API Key di sidebar!")
        else:
            st.error("Kolom pendapatan tidak ditemukan!")
    except Exception as e:
        st.error(f"Error: {e}")
