import streamlit as st
import pandas as pd
import google.generativeai as genai
import io

st.set_page_config(page_title="TikTok Profit Splitter", layout="centered")

st.title("💰 TikTok Profit Splitter")

# Sidebar untuk Input Rahasia
with st.sidebar:
    st.header("Pengaturan")
    api_key = st.text_input("Masukkan Gemini API Key", type="password")
    modal_fix = st.number_input("Modal per Barang (Rp)", value=25000)

uploaded_file = st.file_uploader("Upload file CSV TikTok", type=["csv"])

if uploaded_file:
    if not api_key:
        st.warning("Silahkan masukkan API Key di sidebar sebelah kiri!")
    else:
        # Konfigurasi AI
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Baca Data
        df = pd.read_csv(uploaded_file)
        
        # Cari kolom uang
        target_col = next((col for col in df.columns if 'Penghasilan' in col or 'Amount' in col), None)
        
        if target_col:
            total_omset = df[target_col].sum()
            total_order = len(df)
            total_modal = total_order * modal_fix
            profit_bersih = total_omset - total_modal
            bagi_tiga = profit_bersih / 3
            
            # Tampilan
            st.divider()
            col1, col2 = st.columns(2)
            col1.metric("Total Omset", f"Rp {total_omset:,.0f}")
            col1.metric("Total Modal", f"Rp {total_modal:,.0f}")
            col2.metric("Profit Bersih", f"Rp {profit_bersih:,.0f}")
            col2.success(f"**Jatah Per Orang: Rp {bagi_tiga:,.0f}**")
            
            if st.button("Minta Analisis AI"):
                try:
                    prompt = f"Bisnis TikTok untung Rp {profit_bersih:,.0f} dari {total_order} order. Berikan 1 saran singkat."
                    response = model.generate_content(prompt)
                    st.info(response.text)
                except:
                    st.error("Gagal memanggil AI. Cek kembali API Key Anda.")
        else:
            st.error("Kolom pendapatan tidak ditemukan di CSV!")

st.caption("Dibuat untuk memudahkan bagi hasil 3 orang.")
