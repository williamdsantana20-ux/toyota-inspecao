import streamlit as st
#from tensorflow.keras.models import load_model
#from tensorflow.keras.preprocessing import image
import numpy as np

# carregar modelo
#model = load_model("modelo_ok_nok.h5")

st.title("Inspeção Visual Toyota 150D")

uploaded_file = st.file_uploader("Escolha a imagem da peça", type=["jpg","png","jpeg"])

if uploaded_file is not None:
    st.image(uploaded_file, caption="Imagem enviada", use_container_width=True)

    pred = model.predict(None)

    if pred[0][0] > 0.5:
        st.success("✅ Peça OK")
    else:
        st.error("❌ Peça NOK")
