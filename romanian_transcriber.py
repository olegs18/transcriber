import asyncio
import csv
import os
import argparse
from typing import List
from googletrans import Translator
from gtts import gTTS

# Автоматическая замена устаревших/специфических слов
NORMALIZATION_MAP = {
    'vinere': 'vineri'
}

# Заменяемые звуки для транскрипции
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

def normalize(word: str) -> str:
    return NORMALIZATION_MAP.get(word.lower(), word)

def apply_replacements(word: str, rules: List[tuple]) -> str:
    word = word.lower()
    for orig, repl in rules:
        word = word.replace(orig, repl)
    return word

async def translate_word(word: str, src='ro', dest='ru') -> str:
    try:
        translation = await translator.translate(word, src=src, dest=dest)
        return translation.text
    except Exception as e:
        return f"[ошибка перевода: {e}]"

def speak(word: str, lang='ro', filename='audio'):
    filename_mp3 = f"{filename}.mp3"
    tts = gTTS(text=word, lang=lang)
    tts.save(filename_mp3)

async def transcribe(word: str) -> dict:
    normalized = normalize(word)
    return {
        'original': word,
        'normalized': normalized,
        'ipa': apply_replacements(normalized, IPA_REPLACEMENTS),
        'ru_phonetic': apply_replacements(normalized, RU_REPLACEMENTS),
        'translation': await translate_word(normalized)
    }

async def save_to_csv(data: List[dict], filename="transcription_results.csv"):
    with open(filename, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["original", "normalized", "ipa", "ru_phonetic", "translation"])
        writer.writeheader()
        writer.writerows(data)

async def main():
    parser = argparse.ArgumentParser(description="Romanian Transcriber CLI")
    parser.add_argument('--words', nargs='+', required=True, help='Список слов на румынском')
    parser.add_argument('--csv', default='transcription_results.csv', help='Файл для экспорта CSV')
    parser.add_argument('--audio_dir', default='audio', help='Папка для сохранения mp3')
    args = parser.parse_args()

    os.makedirs(args.audio_dir, exist_ok=True)
    results = []

    for word in args.words:
        result = await transcribe(word)
        results.append(result)
        print(f"{result['original']} (→ {result['normalized']}):")
        print(f"  IPA: {result['ipa']}")
        print(f"  Рус: {result['ru_phonetic']}")
        print(f"  Перевод: {result['translation']}")
        speak(result['normalized'], filename=os.path.join(args.audio_dir, result['normalized']))
        print()

    await save_to_csv(results, filename=args.csv)

if __name__ == "__main__":
    asyncio.run(main())
