import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- KUSTOMISASI DESAIN RETRO (CSS) ---
st.set_page_config(page_title="TikTok Money Magic", layout="centered", page_icon="🕹️")

st.markdown("""
    <style>
    /* Mengubah font dan background utama */
    @import url('https://fonts.googleapis.com/css2?family=Bungee&family=Space+Mono:wght@700&display=swap');
    
    .stApp {
        background: linear-gradient(135deg, #ff00ff 0%, #00ffff 100%);
    }

    /* Judul Utama Retro */
    h1 {
        font-family: 'Bungee', cursive;
        color: #ffff00;
        text-shadow: 4px 4px #ff007f;
        text-align: center;
        font-size: 3rem !important;
    }

    /* Container Box */
    .stMetric {
        background: rgba(255, 255, 255, 0.9);
        border: 4px solid #000;
        padding: 15px;
        border-radius: 0px;
        box-shadow: 8px 8px 0px #000;
    }

    /* Tombol Retro */
    .stButton>button {
        width: 100%;
        font-family: 'Bungee', cursive;
        background-color: #ff007f !important;
        color: white !important;
        border: 4px solid #000 !important;
        box-shadow: 5px 5px 0px #000;
        transition: 0.2s;
    }
    .stButton>button:hover {
        transform: translate(-2px, -2px);
        box-shadow: 7px 7px 0px #000;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #f0f0f0;
        border-right: 5px solid #000;
    }
    
    /* Sukses Message */
    .stAlert {
        background-color: #00ff00 !important;
        color: #000 !important;
        border: 4px solid #000;
        font-family: 'Space Mono', monospace;
    }
    </style>
    """, unsafe_allow_html=True)

# --- LOGIKA APLIKASI ---

st.title("🕹️ TIKTOK MONEY MAGIC")

# Ambil Daftar Modal dari Secrets
try:
    daftar_modal = st.secrets["MODAL_PRODUK"]
except:
    st.error("Konfigurasi MODAL_PRODUK tidak ditemukan di Secrets!")
    st.stop()

with st.sidebar:
    st.markdown("### 💾 SLAP DATA HERE")
    modal_fix = st.number_input("MODAL DEFAULT (Rp)", value=st.secrets.get("MODAL_DEFAULT", 25000))
    st.divider()
    st.write("Ready to crunch some numbers?")

uploaded_file = st.file_uploader("UPLOAD CSV TIKTOK DISINI", type=["csv"])

if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file)
        col_pendapatan = next((c for c in df.columns if any(k in c.lower() for k in ['penghasilan', 'amount', 'settlement'])), None)
        col_nama_produk = next((c for c in df.columns if any(k in c.lower() for k in ['product', 'nama', 'item'])), None)

        if col_pendapatan and col_nama_produk:
            # Hitung Modal per baris
            def hitung_modal(row):
                nama_item = str(row[col_nama_produk])
                for produk_key, harga in daftar_modal.items():
                    if produk_key.lower() in nama_item.lower():
                        return harga * row.get('Quantity', 1)
                return modal_fix * row.get('Quantity', 1)

            df['Modal Baris'] = df.apply(hitung_modal, axis=1)
            total_omset = pd.to_numeric(df[col_pendapatan], errors='coerce').sum()
            total_modal = df['Modal Baris'].sum()
            profit_bersih = total_omset - total_modal
            jatah = profit_bersih / 3

            # --- TAMPILAN METRIC GAYA RETRO ---
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.metric("TOTAL OMSET", f"Rp {total_omset:,.0f}")
                st.metric("ORDERAN", len(df))
            with c2:
                st.metric("TOTAL MODAL", f"Rp {total_modal:,.0f}")
                st.metric("PROFIT BERSERSIH", f"Rp {profit_bersih:,.0f}")
            
            st.markdown(f"""
                <div style="background-color:#ffff00; padding:20px; border:5px solid #000; text-align:center; box-shadow: 10px 10px 0px #ff007f;">
                    <h2 style="color:#000; font-family:'Bungee'; margin:0;">JATAH PER ORANG</h2>
                    <h1 style="color:#ff007f; margin:0;">Rp {jatah:,.0f}</h1>
                </div>
            """, unsafe_allow_html=True)

            # AI Analisis
            st.write("")
            if st.button("✨ MINTA SARAN AI"):
                try:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    prompt = f"Analisis bisnis TikTok: Omset {total_omset}, Profit {profit_bersih}. Berikan 1 saran gaya retro gaming."
                    response = model.generate_content(prompt)
                    st.info(response.text)
                except:
                    st.error("AI Error! Periksa API Key.")

        else:
            st.error("Kolom data tidak cocok!")
    except Exception as e:
        st.error(f"Error: {e}")
