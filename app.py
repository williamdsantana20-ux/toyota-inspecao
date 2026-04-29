import streamlit as st
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import numpy as np
import os
import gdown

# baixar modelo automaticamente se não existir
if not os.path.exists("modelo_ok_nok.h5"):
    url = "https://drive.google.com/uc?id=1lMkbHSUai1P2aEes_0D-mx2MkUEavU2W"
    gdown.download(url, "modelo_ok_nok.h5", quiet=False)

# carregar modelo
model = load_model("modelo_ok_nok.h5")

# título
st.title("Inspeção Visual Toyota 150D")

# upload da imagem
uploaded_file = st.file_uploader(
    "Escolha a imagem da peça",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file is not None:
    # mostrar imagem
    st.image(uploaded_file, caption="Imagem enviada", use_container_width=True)

    # preprocessamento
    img = image.load_img(uploaded_file, target_size=(224, 224))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = img_array / 255.0

    # previsão
    pred = model.predict(img_array)

    # resultado
    if pred[0][0] > 0.5:
        st.success("✅ Peça OK")
    else:
        st.error("❌ Peça NOK")
