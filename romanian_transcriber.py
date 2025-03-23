import asyncio
import csv
from typing import List
from googletrans import Translator
from gtts import gTTS
import os

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
    return {
        'original': word,
        'ipa': apply_replacements(word, IPA_REPLACEMENTS),
        'ru_phonetic': apply_replacements(word, RU_REPLACEMENTS),
        'translation': await translate_word(word)
    }

async def save_to_csv(data: List[dict], filename="transcription_results.csv"):
    with open(filename, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["original", "ipa", "ru_phonetic", "translation"])
        writer.writeheader()
        writer.writerows(data)

async def main():
    words = ["sâmbătă", "vinere", "miercuri", "gheață", "înțelegere"]
    results = []
    os.makedirs("audio", exist_ok=True)

    for word in words:
        result = await transcribe(word)
        results.append(result)
        print(f"{result['original']}:")
        print(f"  IPA: {result['ipa']}")
        print(f"  Рус: {result['ru_phonetic']}")
        print(f"  Перевод: {result['translation']}")
        speak(result['original'], filename=os.path.join("audio", result['original']))
        print()

    await save_to_csv(results)

asyncio.run(main())
