import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("Анализ CSV-файла 📈")

# Загрузка файла
uploaded_file = st.file_uploader("Загрузите CSV-файл", type=["csv"])

if uploaded_file is not None:
    # Читаем файл в DataFrame
    df = pd.read_csv(uploaded_file)
    st.subheader("Первые 5 строк данных:")
    st.write(df.head())

    # Выбор колонок для графика
    columns = df.columns.tolist()
    x_col = st.selectbox("Выберите колонку для X", columns)
    y_col = st.selectbox("Выберите колонку для Y", columns)

    # Построение графика
    st.subheader(f"График: {y_col} от {x_col}")
    fig, ax = plt.subplots()
    ax.plot(df[x_col], df[y_col])
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.grid(True)
    st.pyplot(fig)
else:
    st.info("Пожалуйста, загрузите CSV-файл для начала анализа.")
