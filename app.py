import streamlit as st
import pandas as pd
import google.generativeai as genai

st.set_page_config(page_title="AI Business Manager", layout="centered", page_icon="📈")
st.title("📈 AI Business Manager")

# --- KONFIGURASI MODAL DARI SECRETS ---
try:
    daftar_modal = st.secrets["MODAL_PRODUK"]
except:
    daftar_modal = {"DEFAULT": 25000}

with st.sidebar:
    st.header("⚙️ Konfigurasi")
    modal_fix = st.number_input("Modal per Barang (Rp)", value=int(daftar_modal.get("DEFAULT", 25000)))
    st.divider()
    st.success("Mode Otomatis (Secrets) Aktif ✅")

uploaded_file = st.file_uploader("Upload CSV TikTok", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        keywords = ['Penghasilan', 'Amount', 'Settlement', 'Total']
        target_col = next((c for c in df.columns if any(k.lower() in c.lower() for k in keywords)), None)
        col_nama_produk = next((c for c in df.columns if any(k in c.lower() for k in ['product', 'nama', 'item'])), None)

        if target_col:
            def get_modal(row):
                if col_nama_produk:
                    nama_item = str(row[col_nama_produk]).lower()
                    for key, harga in daftar_modal.items():
                        if key.lower() in nama_item:
                            return harga * row.get('Quantity', 1)
                return modal_fix * row.get('Quantity', 1)

            df['Modal_Baris'] = df.apply(get_modal, axis=1)
            omset = pd.to_numeric(df[target_col], errors='coerce').sum()
            orders = len(df)
            total_modal = df['Modal_Baris'].sum()
            profit = omset - total_modal
            bagi_hasil = profit / 3

            # --- TAMPILAN METRIK ---
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Total Omset", f"Rp {omset:,.0f}")
            c1.metric("Total Order", f"{orders} Pesanan")
            c2.metric("Total Modal", f"Rp {total_modal:,.0f}")
            c2.metric("Profit Bersih", f"Rp {profit:,.0f}")
            st.success(f"### 🤝 Jatah Per Orang: Rp {bagi_hasil:,.0f}")

            # --- INPUT PROMPT MANUAL ---
            st.divider()
            st.subheader("🤖 Tanya Manajer AI")
            
            # User mengetik instruksi sendiri di sini
            user_instruction = st.text_area(
                "Apa yang ingin Anda tanyakan pada AI?", 
                placeholder="Contoh: Berikan saran strategi iklan dengan profit segini..."
            )
            
            if st.button("Kirim ke AI"):
                if user_instruction:
                    try:
                        api_key = st.secrets["GEMINI_API_KEY"]
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')

                        # Menggabungkan data angka dengan instruksi user
                        full_prompt = f"""
                        Data Bisnis Saya:
                        - Omset: Rp {omset:,.0f}
                        - Modal: Rp {total_modal:,.0f}
                        - Profit: Rp {profit:,.0f}
                        - Jumlah Order: {orders}

                        Pertanyaan/Instruksi User: 
                        {user_instruction}
                        """

                        with st.spinner('Menghubungi Manajer AI...'):
                            response = model.generate_content(full_prompt)
                            st.info(f"**Jawaban AI:**\n\n{response.text}")
                    except Exception as e:
                        st.error(f"Error AI: {e}")
                else:
                    st.warning("Silakan ketik pertanyaan Anda terlebih dahulu!")
        else:
            st.error("Kolom pendapatan tidak ditemukan!")
    except Exception as e:
        st.error(f"Error: {e}")
