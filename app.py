if st.button("Kirim ke AI"):
                if user_instruction:
                    try:
                        api_key = st.secrets["GEMINI_API_KEY"]
                        genai.configure(api_key=api_key)

                        # --- PERBAIKAN: DETEKSI MODEL OTOMATIS ---
                        available_models = [
                            m.name for m in genai.list_models() 
                            if 'generateContent' in m.supported_generation_methods
                        ]
                        
                        # Cari model flash, kalau tidak ada pakai yang pertama tersedia
                        model_name = next((m for m in available_models if 'gemini-1.5-flash' in m), None)
                        if not model_name:
                            model_name = available_models[0]
                        
                        model = genai.GenerativeModel(model_name)
                        # ---------------------------------------

                        full_prompt = f"""
                        Data Bisnis Saya:
                        - Omset: Rp {omset:,.0f}
                        - Modal: Rp {total_modal:,.0f}
                        - Profit: Rp {profit:,.0f}
                        - Jumlah Order: {orders}

                        Pertanyaan/Instruksi User: 
                        {user_instruction}
                        """

                        with st.spinner(f'Menghubungi {model_name}...'):
                            response = model.generate_content(full_prompt)
                            st.info(f"**Jawaban AI:**\n\n{response.text}")
                    except Exception as e:
                        st.error(f"Error AI: {e}")
                else:
                    st.warning("Silakan ketik pertanyaan Anda terlebih dahulu!")
