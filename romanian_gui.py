import asyncio
import csv
import os
import zipfile
from typing import List, Dict
import streamlit as st
from googletrans import Translator
from gtts import gTTS
from io import StringIO, BytesIO

# === Конфигурация ===
CSV_CACHE_FILE = "transcription_cache.csv"
LAST_SESSION_FILE = "last_session.csv"
AUDIO_FOLDER = "audio_files"
os.makedirs(AUDIO_FOLDER, exist_ok=True)

NORMALIZATION_MAP = {
    'vinere': 'vineri'
}

IPA_REPLACEMENTS = [
    ('ce', 't͡ʃe'), ('ci', 't͡ʃi'), ('ge', 'd͡ʒe'), ('gi', 'd͡ʒi'),
    ('ch', 'k'), ('gh', 'g'), ('ă', 'ə'), ('â', 'ɨ'), ('î', 'ɨ'),
    ('ș', 'ʃ'), ('ţ', 't͡s'), ('ț', 't͡s')
]

RU_REPLACEMENTS = [
    ('ce', 'че'), ('ci', 'чи'), ('ge', 'дже'), ('gi', 'джи'),
    ('ch', 'к'), ('gh', 'г'), ('ă', 'э'), ('â', 'ы'), ('î', 'ы'),
    ('ș', 'ш'), ('ţ', 'ц'), ('ț', 'ц'), ('a', 'а'), ('e', 'е'),
    ('i', 'и'), ('o', 'о'), ('u', 'у'), ('b', 'б'), ('c', 'к'), ('d', 'д'),
    ('f', 'ф'), ('g', 'г'), ('h', 'х'), ('j', 'ж'), ('k', 'к'), ('l', 'л'),
    ('m', 'м'), ('n', 'н'), ('p', 'п'), ('q', 'к'), ('r', 'р'), ('s', 'с'),
    ('t', 'т'), ('v', 'в'), ('w', 'в'), ('x', 'кс'), ('y', 'и'), ('z', 'з')
]

LANG_FLAGS = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 Английский"
}

translator = Translator()

def normalize(phrase: str) -> str:
    words = phrase.lower().split()
    return ' '.join(NORMALIZATION_MAP.get(w, w) for w in words)

def apply_replacements(phrase: str, rules: List[tuple]) -> str:
    result = phrase.lower()
    for orig, repl in rules:
        result = result.replace(orig, repl)
    return result

async def translate_phrase(phrase: str, dest='ru') -> str:
    try:
        translation = await translator.translate(phrase, src='ro', dest=dest)
        return translation.text
    except Exception as e:
        return f"[ошибка перевода: {e}]"

def speak(phrase: str, filename: str):
    mp3_path = os.path.join(AUDIO_FOLDER, filename)
    if not os.path.exists(mp3_path):
        tts = gTTS(text=phrase, lang='ro')
        tts.save(mp3_path)
    return mp3_path

def load_csv_cache(csv_path: str) -> Dict[str, dict]:
    if not os.path.exists(csv_path):
        return {}
    existing_data = {}
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row.get("normalized", "").strip(), row.get("lang", "").strip())
            if key:
                existing_data[key] = row
    return existing_data

def save_csv_file(data: List[dict], csv_path: str):
    with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["original", "normalized", "ipa", "ru_phonetic", "translation", "lang"])
        writer.writeheader()
        writer.writerows(data)

async def process_phrases(phrases: List[str], cache: Dict[str, dict], lang='ru') -> List[dict]:
    results = []
    for phrase in set(phrases):
        normalized = normalize(phrase)
        cache_key = (normalized, lang)
        if cache_key in cache:
            results.append(cache[cache_key])
            continue
        result = {
            'original': phrase,
            'normalized': normalized,
            'ipa': apply_replacements(normalized, IPA_REPLACEMENTS),
            'ru_phonetic': apply_replacements(normalized, RU_REPLACEMENTS),
            'translation': await translate_phrase(normalized, dest=lang),
            'lang': lang
        }
        cache[cache_key] = result
        results.append(result)
        speak(normalized, f"{normalized.replace(' ', '_')}.mp3")
    return results

def make_zip_of_audio(phrases: List[str]) -> BytesIO:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for phrase in phrases:
            normalized = normalize(phrase)
            filename = f"{normalized.replace(' ', '_')}.mp3"
            path = os.path.join(AUDIO_FOLDER, filename)
            if os.path.exists(path):
                zip_file.write(path, arcname=filename)
    zip_buffer.seek(0)
    return zip_buffer

# === Streamlit UI ===
st.set_page_config(page_title="Romanian Transcriber", layout="wide")
st.title("📘 Romanian Transcriber & Translator")

input_method = st.radio("Выберите способ ввода:", ["Ввод вручную", "Загрузка .txt файла"])
translation_lang = st.selectbox("Язык перевода:", [("🇷🇺 Русский", "ru"), ("🇬🇧 Английский", "en")])
save_last_session = st.checkbox("Сохранять текущую сессию отдельно", value=True)
if st.button("🧹 Очистить кэш и сессию"):
    if os.path.exists(CSV_CACHE_FILE):
        os.remove(CSV_CACHE_FILE)
    if os.path.exists(LAST_SESSION_FILE):
        os.remove(LAST_SESSION_FILE)
    st.session_state["results"] = []
    st.success("Кэш и сессия очищены.")

phrases = []

if input_method == "Ввод вручную":
    text_input = st.text_area("Введите фразы (по одной на строку):", height=200)
    if text_input.strip():
        phrases = [line.strip() for line in text_input.splitlines() if line.strip()]
else:
    uploaded_file = st.file_uploader("Загрузите .txt файл", type=["txt"])
    if uploaded_file:
        stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
        phrases = [line.strip() for line in stringio if line.strip()]

if 'results' not in st.session_state:
    st.session_state['results'] = []

if phrases:
    if st.button("▶️ Обработать"):
        with st.spinner("Обработка..."):
            cache = load_csv_cache(CSV_CACHE_FILE)
            results = asyncio.run(process_phrases(phrases, cache, lang=translation_lang[1]))
            save_csv_file(list(cache.values()), CSV_CACHE_FILE)
            if save_last_session:
                save_csv_file(results, LAST_SESSION_FILE)
            st.session_state['results'] = results
        st.success("✅ Готово!")

if st.session_state['results']:
    col1, col2 = st.columns([3, 1])
    with col1:
        filter_text = st.text_input("🔍 Фильтр по фразе или переводу:")
    with col2:
        lang_filter = st.selectbox("🌍 Язык:", ["Все", "ru", "en"], format_func=lambda x: LANG_FLAGS.get(x, "🌐 Все") if x != "Все" else "🌐 Все")

    filtered = []
    for row in st.session_state['results']:
        if (not filter_text or (
            filter_text.lower() in row['original'].lower()
            or filter_text.lower() in row['translation'].lower()
        )) and (lang_filter == "Все" or row['lang'] == lang_filter):
            filtered.append(row)

    st.download_button("📅 Скачать CSV", data=open(LAST_SESSION_FILE if save_last_session else CSV_CACHE_FILE, "rb"), file_name="results.csv")

    audio_zip = make_zip_of_audio([row['original'] for row in filtered])
    st.download_button("🔊 Скачать MP3 (архив)", data=audio_zip, file_name="audio_files.zip")

    st.subheader("📊 Результаты:")
    st.dataframe(filtered, use_container_width=True)

    st.subheader("🎵 Прослушать озвучку:")
    for row in filtered:
        normalized = row['normalized']
        filename = f"{normalized.replace(' ', '_')}.mp3"
        path = os.path.join(AUDIO_FOLDER, filename)
        if os.path.exists(path):
            st.markdown(f"**{row['original']}**")
            st.audio(path, format="audio/mp3")
else:
    st.info("Введите или загрузите хотя бы одну фразу для обработки.")
