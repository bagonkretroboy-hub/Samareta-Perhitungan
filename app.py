import streamlit as st
import pandas as pd
import google.generativeai as genai
import io

st.set_page_config(page_title="TikTok Profit Splitter", layout="centered")

st.title("💰 TikTok Profit Splitter")

with st.sidebar:
    st.header("Pengaturan")
    api_key = st.text_input("Masukkan Gemini API Key", type="password")
    modal_fix = st.number_input("Modal per Barang (Rp)", value=25000)

uploaded_file = st.file_uploader("Upload file CSV TikTok", type=["csv"])

if uploaded_file:
    if not api_key:
        st.warning("Silahkan masukkan API Key di sidebar sebelah kiri!")
    else:
        try:
            # Konfigurasi AI
            genai.configure(api_key=api_key)
            
            # Pengaturan Keamanan (Agar AI tidak gampang memblokir jawaban)
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            model = genai.GenerativeModel('gemini-1.5-flash', safety_settings=safety_settings)
            
            df = pd.read_csv(uploaded_file)
            target_col = next((col for col in df.columns if 'Penghasilan' in col or 'Amount' in col or 'Settlement' in col), None)
            
            if target_col:
                total_omset = df[target_col].sum()
                total_order = len(df)
                total_modal = total_order * modal_fix
                profit_bersih = total_omset - total_modal
                bagi_tiga = profit_bersih / 3
                
                st.divider()
                col1, col2 = st.columns(2)
                col1.metric("Total Omset", f"Rp {total_omset:,.0f}")
                col1.metric("Total Modal", f"Rp {total_modal:,.0f}")
                col2.metric("Profit Bersih", f"Rp {profit_bersih:,.0f}")
                st.success(f"### **Jatah Per Orang: Rp {bagi_tiga:,.0f}**")
                
                if st.button("Minta Analisis AI"):
                    with st.spinner('Sedang berpikir...'):
                        try:
                            prompt = f"Data bisnis TikTok: Omset Rp {total_omset:,.0f}, Modal Rp {total_modal:,.0f}, Profit Rp {profit_bersih:,.0f}. Berikan 2 saran singkat untuk meningkatkan profit."
                            response = model.generate_content(prompt)
                            st.info(response.text)
                        except Exception as e:
                            # Menampilkan error asli agar kita tahu masalahnya
                            st.error(f"AI Error: {str(e)}")
            else:
                st.error(f"Kolom pendapatan tidak ditemukan. Kolom yang ada: {list(df.columns)}")
                
        except Exception as e:
            st.error(f"Terjadi kesalahan sistem: {str(e)}")

st.caption("v1.1 - Samareta Perhitungan")
