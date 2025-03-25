# === Импорты и базовая настройка ===
import asyncio
import csv
import os
import zipfile
from typing import List, Dict
import streamlit as st
from pydub import AudioSegment
from googletrans import Translator
from gtts import gTTS
from io import StringIO, BytesIO
import base64
from datetime import datetime
import pandas as pd
from collections import Counter

# === Пути к файлам и папкам ===
CSV_CACHE_FILE = "transcription_cache.csv"
LAST_SESSION_FOLDER = "sessions"
AUDIO_FOLDER = "audio_files"
os.makedirs(AUDIO_FOLDER, exist_ok=True)
os.makedirs(LAST_SESSION_FOLDER, exist_ok=True)

# === Нормализация отдельных слов (при необходимости) ===
NORMALIZATION_MAP = {
    'vinere': 'vineri'  # исправляем возможные варианты
}

# === Заменители для транскрипции румынского в IPA ===
IPA_REPLACEMENTS = [
    ('ce', 't͡ʃe'), ('ci', 't͡ʃi'), ('ge', 'd͡ʒe'), ('gi', 'd͡ʒi'),
    ('ch', 'k'), ('gh', 'g'), ('ă', 'ə'), ('â', 'ɨ'), ('î', 'ɨ'),
    ('ș', 'ʃ'), ('ţ', 't͡s'), ('ț', 't͡s')
]

# === Русская приближённая фонетика ===
RU_REPLACEMENTS = [
    ('ce', 'че'), ('ci', 'чи'), ('ge', 'дже'), ('gi', 'джи'),
    ('ch', 'к'), ('gh', 'г'), ('ă', 'э'), ('â', 'ы'), ('î', 'ы'),
    ('ș', 'ш'), ('ţ', 'ц'), ('ț', 'ц'), ('a', 'а'), ('e', 'е'),
    ('i', 'и'), ('o', 'о'), ('u', 'у'), ('b', 'б'), ('c', 'к'),
    ('d', 'д'), ('f', 'ф'), ('g', 'г'), ('h', 'х'), ('j', 'ж'),
    ('k', 'к'), ('l', 'л'), ('m', 'м'), ('n', 'н'), ('p', 'п'),
    ('q', 'к'), ('r', 'р'), ('s', 'с'), ('t', 'т'), ('v', 'в'),
    ('w', 'в'), ('x', 'кс'), ('y', 'и'), ('z', 'з')
]

# === Отображение флагов для языков ===
LANG_FLAGS = {
    "ru": "🇷🇺 Русский",
    "en": "🇬🇧 Английский",
    "ro": "🇷🇴 Румынский"
}

translator = Translator()

# === Перевод и обработка ===
async def translate_phrase(phrase: str, dest='ru') -> str:
    try:
        translation = await translator.translate(phrase, src='ro', dest=dest)
        return translation.text
    except Exception as e:
        return f"[ошибка перевода: {e}]"

def translate_ru_to_ro(phrase: str) -> str:
    try:
        return asyncio.run(translator.translate(phrase, src='ru', dest='ro')).text
    except Exception as e:
        return f"[ошибка перевода: {e}]"

def normalize(phrase: str) -> str:
    words = phrase.lower().split()
    return ' '.join(NORMALIZATION_MAP.get(w, w) for w in words)

def apply_replacements(phrase: str, rules: List[tuple]) -> str:
    result = phrase.lower()
    for orig, repl in rules:
        result = result.replace(orig, repl)
    return result

def speak(phrase: str, filename: str, lang='ro'):
    mp3_path = os.path.join(AUDIO_FOLDER, filename)
    if not os.path.exists(mp3_path):
        tts = gTTS(text=phrase, lang=lang)
        tts.save(mp3_path)
    return mp3_path

def load_csv_cache(csv_path: str) -> Dict[str, dict]:
    if not os.path.exists(csv_path):
        return {}
    existing_data = {}
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = dict(row)
            row.setdefault('known', '❌')
            row.setdefault('category', '')
            row.setdefault('date_added', '')
            row.setdefault('date_known', '')
            key = (row.get("normalized", "").strip(), row.get("lang", "").strip())
            if key:
                existing_data[key] = row
    return existing_data

def save_csv_file(data: List[dict], csv_path: str):
    with open(csv_path, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "original", "normalized", "ipa", "ru_phonetic", "translation",
                "lang", "known", "category", "date_added", "date_known"
            ]
        )
        writer.writeheader()
        writer.writerows(data)

async def process_phrases(phrases: List[str], cache: Dict[str, dict], lang='ru', study_lang_code='ro') -> List[dict]:
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
            'ipa': apply_replacements(normalized, IPA_REPLACEMENTS if study_lang_code == 'ro' else []),
            'ru_phonetic': apply_replacements(normalized, RU_REPLACEMENTS if study_lang_code == 'ro' else []),
            'translation': await translate_phrase(normalized, dest=lang if lang != study_lang_code else 'ru'),
            'lang': lang,
            'known': '❌',
            'category': st.session_state.get("category_input", "").strip(),
            'date_added': datetime.now().strftime('%Y-%m-%d'),
            'date_known': '',
        }
        cache[cache_key] = result
        results.append(result)
        speak(normalized, f"{normalized.replace(' ', '_')}_{study_lang_code}.mp3", lang=study_lang_code)
    return results

def make_zip_of_audio(phrases: List[str], results: List[dict], with_translation=False, lang='ru', study_lang_code='ro') -> BytesIO:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
        for row in results:
            normalized = row['normalized']
            base_name = normalized.replace(' ', '_')
            ro_file = f"{base_name}_{study_lang_code}.mp3"
            ro_path = speak(normalized, ro_file, lang=study_lang_code)
            zip_file.write(ro_path, arcname=ro_file)

            if with_translation:
                trans_text = row['translation']
                tr_file = f"{base_name}_{lang}.mp3"
                tr_path = speak(trans_text, tr_file, lang=lang)
                merged = AudioSegment.from_file(ro_path) + AudioSegment.silent(duration=500) + AudioSegment.from_file(tr_path)
                final_path = os.path.join(AUDIO_FOLDER, f"{base_name}_combo.mp3")
                merged.export(final_path, format="mp3")
                zip_file.write(final_path, arcname=f"{base_name}_combo.mp3")
    zip_buffer.seek(0)
    return zip_buffer


# === Streamlit UI ===
st.set_page_config(page_title="Romanian Transcriber", layout="wide")
st.title("📘 Transcriber & Translator")

study_lang = st.selectbox("🧠 Язык изучения:", ["Румынский (ro)", "Английский (en)"], index=0)
study_lang_code = "ro" if "ro" in study_lang else "en"

session_files = [f for f in os.listdir(LAST_SESSION_FOLDER) if f.endswith(".csv")]
load_session = st.selectbox("📂 Загрузить сессию:", ["(не выбрана)"] + session_files)

input_method = st.radio("Выберите способ ввода:", ["Ввод вручную", "Загрузка .txt файла"])
translation_lang = st.selectbox("Язык перевода:", [(LANG_FLAGS['ru'], "ru"), (LANG_FLAGS['en'], "en")])
save_last_session = st.checkbox("Сохранять текущую сессию отдельно", value=True)
append_to_current_session = st.checkbox("📎 Добавить к текущей загруженной сессии (если выбрана)", value=True)

phrases = []

if 'manual_input' not in st.session_state:
    st.session_state['manual_input'] = ""
if 'results' not in st.session_state:
    st.session_state['results'] = []

if load_session != "(не выбрана)":
    try:
        with open(os.path.join(LAST_SESSION_FOLDER, load_session), mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            st.session_state['results'] = list(reader)
        st.success(f"Сессия {load_session} загружена.")
    except Exception as e:
        st.warning(f"Ошибка загрузки сессии: {e}")

if input_method == "Ввод вручную":
    ru_input = st.text_input("✍️ Введите фразу (перевод на румынский будет добавлен):")
    category_input = st.text_input("🏷️ Категория (опционально):", key="category_input")
    if st.button("Добавить перевод", key="add_translation"):
        try:
            ro_phrase = asyncio.run(translator.translate(ru_input, src=translation_lang[1], dest=study_lang_code)).text
            st.session_state['manual_input'] += ("\n" if st.session_state['manual_input'] else "") + ro_phrase.strip()
        except Exception as e:
            st.warning(f"[ошибка перевода: {e}]")
    st.session_state['manual_input'] = st.text_area("📥 Введите фразы (по одной на строке):", value=st.session_state['manual_input'], height=200)
    if st.session_state['manual_input'].strip():
        phrases = [line.strip() for line in st.session_state['manual_input'].splitlines() if line.strip()]
else:
    uploaded_file = st.file_uploader("Загрузите .txt файл", type=["txt"])
    if uploaded_file:
        stringio = StringIO(uploaded_file.getvalue().decode("utf-8"))
        phrases = [line.strip() for line in stringio if line.strip()]

if phrases and st.button("▶️ Обработать"):
    with st.spinner("Обработка..."):
        cache = load_csv_cache(CSV_CACHE_FILE)
        results = asyncio.run(process_phrases(phrases, cache, lang=translation_lang[1], study_lang_code=study_lang_code))
        save_csv_file(list(cache.values()), CSV_CACHE_FILE)
        if save_last_session:
            if load_session != "(не выбрана)" and append_to_current_session:
                # 🔁 Добавляем к текущей сессии
                existing_path = os.path.join(LAST_SESSION_FOLDER, load_session)
                merged = load_csv_cache(existing_path)
                for r in results:
                    merged[(r['normalized'], r['lang'])] = r
                save_csv_file(list(merged.values()), existing_path)
                st.session_state['results'] = list(merged.values())

                st.success(f"Слова добавлены в сессию: {load_session}")
            else:
                # 🆕 Создаём новую сессию
                session_name = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                save_csv_file(results, os.path.join(LAST_SESSION_FOLDER, session_name))
                st.success(f"Создана новая сессия: {session_name}")
        if not (load_session != "(не выбрана)" and append_to_current_session):        
            st.session_state['results'] = results
        
    st.success("✅ Готово!")

if st.session_state['results']:
    filter_text = st.text_input("🔍 Фильтр по фразе или переводу:")
    filtered = [row for row in st.session_state['results'] if filter_text.lower() in row['original'].lower() or filter_text.lower() in row['translation'].lower()]

    st.download_button("📥 Скачать CSV", data=open(CSV_CACHE_FILE, "rb"), file_name="results.csv")

    audio_zip = make_zip_of_audio([row['original'] for row in filtered], filtered, lang=translation_lang[1], study_lang_code=study_lang_code)
    st.download_button("🔊 Скачать MP3 (архив)", data=audio_zip, file_name="audio_files.zip")

    st.subheader("📊 Результаты:")
    st.dataframe(filtered, use_container_width=True)

    st.subheader("🎧 Прослушать озвучку:")
    if st.button("▶️ Воспроизвести всё"):
        combined = AudioSegment.empty()
        for row in filtered:
            filename = f"{row['normalized'].replace(' ', '_')}_{study_lang_code}.mp3"
            path = speak(row['normalized'], filename, lang=study_lang_code)
            if os.path.exists(path):
                combined += AudioSegment.from_file(path) + AudioSegment.silent(duration=300)
        buffer = BytesIO()
        combined.export(buffer, format="mp3")
        buffer.seek(0)
        b64 = base64.b64encode(buffer.read()).decode()
        st.markdown(f"""
            <audio autoplay controls loop>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
        """, unsafe_allow_html=True)

    if st.checkbox("🔁 Включить двойную озвучку (фраза + перевод)"):
        combo_audio = AudioSegment.empty()
        for row in filtered:
            base = row['normalized'].replace(' ', '_')
            ro_path = speak(row['normalized'], f"{base}_{study_lang_code}.mp3", lang=study_lang_code)
            tr_path = speak(row['translation'], f"{base}_{translation_lang[1]}.mp3", lang=translation_lang[1])
            if os.path.exists(ro_path) and os.path.exists(tr_path):
                seg = AudioSegment.from_file(ro_path) + AudioSegment.silent(duration=500) + AudioSegment.from_file(tr_path)
                combo_audio += seg + AudioSegment.silent(duration=500)
        if len(combo_audio) > 0:
            combined_path = os.path.join(AUDIO_FOLDER, "all_combined.mp3")
            combo_audio.export(combined_path, format="mp3")
            st.audio(combined_path, format="audio/mp3")
            double_zip = make_zip_of_audio([row['original'] for row in filtered], filtered, with_translation=True, lang=translation_lang[1], study_lang_code=study_lang_code)
            st.download_button("📥 Скачать двойную озвучку (zip)", data=double_zip, file_name="combo_audio.zip")
            
# === Если есть результаты, показываем фильтр и вкладки ===
if st.session_state['results']:
    st.markdown("---")
    
    # 🎛️ Фильтрация перед вкладками
    col1, col2 = st.columns([3, 2])
    with col1:
        filter_text = st.text_input("🔍 Фильтр по фразе или переводу:", key="filter_text")
    with col2:
        show_only_unknown = st.checkbox("🔁 Только ❌ невыученные", key="filter_unknown")

    # Инициализируем known_map один раз
    if 'known_map' not in st.session_state:
        st.session_state['known_map'] = {}
        st.session_state['date_known_map'] = {}
        
    all_categories = sorted(set(r.get("category", "").strip() for r in st.session_state['results'] if r.get("category")))
    selected_category = st.selectbox("📂 Категория:", ["(все)"] + all_categories, index=0)

    # 🧠 Фильтрация и статус
    df_display = [
        r for r in st.session_state['results']
        if (not show_only_unknown or r.get("known") != '✅')
        and (selected_category == "(все)" or r.get("category", "") == selected_category)
        and (filter_text.lower() in r['original'].lower() or filter_text.lower() in r['translation'].lower())
    ]

    # === Вкладки ===
    tabs = st.tabs(["📋 Таблица", "🧠 Карточки (Flashcards)", "📊 Статистика"])

    # === Вкладка карточек ===
    with tabs[1]:
        st.subheader("🧠 Учим фразы")

        for idx, row in enumerate(df_display):
            normalized_key = row['normalized']
            lang_key = row['lang']

            # Загрузим статус known
            known_val = st.session_state['known_map'].get((normalized_key, lang_key), row.get('known', '❌'))
            row['known'] = known_val
            date_known_val = st.session_state['date_known_map'].get((normalized_key, lang_key), row.get('date_known', ''))
            row['date_known'] = date_known_val

            # Автооткрытие первой незнакомой карточки
            auto_open = True if show_only_unknown and known_val != '✅' and idx == 0 else False

            with st.expander(f"{row['original']} → {row['translation']}", expanded=auto_open):
                st.markdown(f"IPA: `{row.get('ipa', '')}`")
                st.markdown(f"Фонетика: `{row.get('ru_phonetic', '')}`")
                if row.get("category"):
                    st.markdown(f"🏷️ Категория: _{row['category']}_")

                audio_path = speak(
                    row['normalized'],
                    f"{row['normalized'].replace(' ', '_')}_{study_lang_code}.mp3",
                    lang=study_lang_code
                )
                st.audio(audio_path)

                # Цветной статус
                status_color = "green" if known_val == '✅' else "red"
                st.markdown(
                    f"**Текущий статус:** <span style='color:{status_color}'>{known_val}</span>",
                    unsafe_allow_html=True
                )

                # Кнопки
                col1, col2 = st.columns(2)
                if col1.button("✅ Знаю", key=f"know_{idx}"):
                    k = (normalized_key, lang_key)
                    st.session_state['known_map'][k] = '✅'
                    st.session_state['date_known_map'][k] = datetime.now().strftime('%Y-%m-%d')
                    row['known'] = '✅'
                    row['date_known'] = st.session_state['date_known_map'][k]
                if col2.button("❌ Не знаю", key=f"dontknow_{idx}"):
                    st.session_state['known_map'][k] = '❌'
                    st.session_state['date_known_map'][k] = ''
                    row['known'] = '❌'
                    row['date_known'] = ''

        if st.button("💾 Сохранить карточки", key="save_cards"):
            save_csv_file(st.session_state['results'], CSV_CACHE_FILE)
            # Если загружена сессия — обновим её тоже
            if load_session != "(не выбрана)":
                save_csv_file(st.session_state['results'], os.path.join(LAST_SESSION_FOLDER, load_session))
            st.success("Карточки сохранены!")

    # === Вкладка таблицы ===
    with tabs[0]:
        st.subheader("📊 Результаты:")

        total = len(df_display)
        known = sum(1 for row in df_display if row.get('known') == '✅')
        percent = int(100 * known / total) if total > 0 else 0
        st.markdown(f"📈 Прогресс: **{known} из {total}** ({percent}%)")
        st.progress(percent)
        for row in df_display:
            row.setdefault("date_added", "")
            row.setdefault("date_known", "")
            row.setdefault("category", "")
        st.dataframe(
            pd.DataFrame(df_display)[["original", "translation", "known", "category", "date_added", "date_known"]],
            use_container_width=True
        )

        if st.button("💾 Сохранить с прогрессом", key="save_known"):
            save_csv_file(st.session_state['results'], CSV_CACHE_FILE)
            
            # Если загружена сессия — обновим её тоже
            if load_session != "(не выбрана)":
                save_csv_file(st.session_state['results'], os.path.join(LAST_SESSION_FOLDER, load_session))
        
            st.success("Сохранено!")

    with tabs[2]:
        st.subheader("📊 Статистика изучения")
        # 🎯 Цель на день (по умолчанию 10)
        daily_goal = st.number_input("🎯 Цель на сегодня (фраз):", min_value=1, max_value=100, value=10, step=1)
        # Собираем все категории
        today_str = datetime.now().strftime('%Y-%m-%d')
        today_known = sum(
            1 for row in st.session_state['results']
            if row.get("known") == "✅" and row.get("date_known") == today_str
        )

        # 🎯 Прогресс выполнения цели
        percent_today = int((100 * today_known / daily_goal) if daily_goal > 0 else 0)
        st.markdown(f"📅 Сегодня выучено: **{today_known} из {daily_goal}** ({percent_today}%)")
        st.progress(percent_today)

        all_stats_categories = sorted(set(
            r.get("category", "").strip() for r in st.session_state['results'] if r.get("category")
        ))

        selected_stat_category = st.selectbox("📂 Фильтр по категории:", ["(все)"] + all_stats_categories, index=0)

        # Фильтруем фразы по категории
        filtered_results = [
            row for row in st.session_state['results']
            if selected_stat_category == "(все)" or row.get("category") == selected_stat_category
        ]
        st.code(selected_stat_category)
        st.json(filtered_results)
        # Считаем добавленные фразы
        added_dates = [row.get("date_added", "") for row in filtered_results if row.get("date_added")]
        added_counts = Counter(added_dates)

        # Считаем выученные фразы
        known_dates = [
            row.get("date_known", "")
            for row in filtered_results
            if row.get("known") == '✅' and row.get("date_known")
        ]
        known_counts = Counter(known_dates)


        # Объединяем все даты
        all_dates = sorted(set(added_counts.keys()) | set(known_counts.keys()))

        # Строим таблицу
        chart_df = pd.DataFrame({
            "Дата": all_dates,
            "Добавлено": [added_counts.get(date, 0) for date in all_dates],
            "Выучено": [known_counts.get(date, 0) for date in all_dates]
        }).set_index("Дата")

        if not chart_df.empty:
            st.bar_chart(chart_df)
        else:
            st.info("Пока нет данных для графика.")

            
    # === Служебная отладка ===
    with st.expander("📦 Отладка"):
        if df_display:
            st.code("Первый из отфильтрованных:")
            st.json(df_display[0])
        if st.session_state['results']:
            st.code("Первый из session_state['results']:")
            st.json(st.session_state['results'][0])

