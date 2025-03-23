import asyncio
import csv
import os
import argparse
from typing import List, Set, Dict
from googletrans import Translator
from gtts import gTTS

# Устаревшие формы
NORMALIZATION_MAP = {
    'vinere': 'vineri'
}

# Транскрипционные замены
IPA_REPLACEMENTS = [
    ('ce', 't͡ʃe'), ('ci', 't͡ʃi'), ('ge', 'd͡ʒe'), ('gi', 'd͡ʒi'),
    ('ch', 'k'), ('gh', 'g'),
    ('ă', 'ə'), ('â', 'ɨ'), ('î', 'ɨ'),
    ('ș', 'ʃ'), ('ţ', 't͡s'), ('ț', 't͡s')
]

RU_REPLACEMENTS = [
    ('ce', 'че'), ('ci', 'чи'), ('ge', 'дже'), ('gi', 'джи'),
    ('ch', 'к'), ('gh', 'г'),
    ('ă', 'э'), ('â', 'ы'), ('î', 'ы'),
    ('ș', 'ш'), ('ţ', 'ц'), ('ț', 'ц'),
    ('a', 'а'), ('e', 'е'), ('i', 'и'), ('o', 'о'), ('u', 'у'),
    ('b', 'б'), ('c', 'к'), ('d', 'д'), ('f', 'ф'), ('g', 'г'),
    ('h', 'х'), ('j', 'ж'), ('k', 'к'), ('l', 'л'), ('m', 'м'),
    ('n', 'н'), ('p', 'п'), ('q', 'к'), ('r', 'р'), ('s', 'с'),
    ('t', 'т'), ('v', 'в'), ('w', 'в'), ('x', 'кс'), ('y', 'и'), ('z', 'з')
]

translator = Translator()

def normalize(phrase: str) -> str:
    words = phrase.lower().split()
    return ' '.join(NORMALIZATION_MAP.get(w, w) for w in words)

def apply_replacements(phrase: str, rules: List[tuple]) -> str:
    result = phrase.lower()
    for orig, repl in rules:
        result = result.replace(orig, repl)
    return result

async def translate_phrase(phrase: str, src='ro', dest='ru') -> str:
    try:
        translation = await translator.translate(phrase, src=src, dest=dest)
        return translation.text
    except Exception as e:
        return f"[ошибка перевода: {e}]"

def speak(phrase: str, lang='ro', filename='audio'):
    filename_mp3 = f"{filename}.mp3"
    tts = gTTS(text=phrase, lang=lang)
    tts.save(filename_mp3)

def read_existing_csv(csv_path: str) -> Dict[str, dict]:
    if not os.path.exists(csv_path):
        return {}

    existing_data = {}
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = row.get("normalized", "").strip()
            if key:
                existing_data[key] = row
    return existing_data

async def transcribe(phrase: str, cache: Dict[str, dict]) -> dict:
    normalized = normalize(phrase)

    if normalized in cache:
        result = cache[normalized]
        print(f"{result['original']} (→ {result['normalized']}):")
        print(f"  IPA: {result['ipa']}")
        print(f"  Рус: {result['ru_phonetic']}")
        print(f"  Перевод: {result['translation']} ✅ (из кэша)")
        return result

    result = {
        'original': phrase,
        'normalized': normalized,
        'ipa': apply_replacements(normalized, IPA_REPLACEMENTS),
        'ru_phonetic': apply_replacements(normalized, RU_REPLACEMENTS),
        'translation': await translate_phrase(normalized)
    }
    return result

async def save_to_csv(data: List[dict], filename="transcription_results.csv"):
    with open(filename, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["original", "normalized", "ipa", "ru_phonetic", "translation"])
        writer.writeheader()
        writer.writerows(data)

def read_phrases_from_txt(file_path: str) -> List[str]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")
    with open(file_path, encoding='utf-8') as f:
        phrases = [line.strip() for line in f if line.strip()]
    return phrases

async def main():
    parser = argparse.ArgumentParser(description="Romanian Transcriber CLI (with cache and phrases)")
    parser.add_argument('--words', nargs='+', help='Фразы через пробел')
    parser.add_argument('--txt', help='Путь к .txt файлу с фразами')
    parser.add_argument('--csv', default='transcription_results.csv', help='Файл CSV для чтения и записи')
    parser.add_argument('--audio_dir', default='audio', help='Папка для сохранения mp3')
    args = parser.parse_args()

    os.makedirs(args.audio_dir, exist_ok=True)
    input_items = args.words if args.words else []

    if args.txt:
        input_items += read_phrases_from_txt(args.txt)

    if not input_items:
        print("❗ Укажите фразы через --words или --txt путь_к_файлу.txt")
        return

    # Удаляем повторы
    unique_phrases: Set[str] = set(input_items)

    # Загружаем кэш из CSV
    cache = read_existing_csv(args.csv)
    results = list(cache.values())  # уже сохранённые записи

    normalized_in_cache = set(cache.keys())

    for phrase in unique_phrases:
        result = await transcribe(phrase, cache)
        results.append(result)
        speak(result['normalized'], filename=os.path.join(args.audio_dir, result['normalized'].replace(' ', '_')))
        print()

    await save_to_csv(results, filename=args.csv)

if __name__ == "__main__":
    asyncio.run(main())
