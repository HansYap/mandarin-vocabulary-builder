from backend.utils.phrase_extractor import PhraseExtractor
from backend.models.llm_handler import LLMHandler
import re
from typing import List, Dict, Any


class FeedbackGenerator:
    def __init__(self, llm_handler: LLMHandler):
        self.llm = llm_handler
        # small in-memory cache to avoid repeated LLM calls in a single run
        self._cache = {}

    # --- helpers ---
    def _is_english_phrase(self, token: str) -> bool:
        """
        Return True if token contains at least one ASCII letter and
        does NOT contain CJK characters. Allows hyphens and spaces.
        """
        # contains any CJK? if yes -> not english phrase
        if re.search(r'[\u4e00-\u9fff]', token):
            print("YWH======", token)
            return False
        # must contain at least one ascii letter
        print("HELLOOOOOOO", bool(re.search(r'[A-Za-z]', token)))
        return bool(re.search(r'[A-Za-z]', token))

    def _normalize_phrase(self, phrase: str) -> str:
        return phrase.strip().lower()

    def _cached_suggest(self, phrase: str, context: str) -> Dict[str, Any]:
        key = ("sug", self._normalize_phrase(phrase), context)
        if key in self._cache:
            return self._cache[key]
        res = self.llm.suggest_phrase(english_phrase=phrase, sentence_context=context)
        # normalize fallback shapes: ensure dict keys exist
        if isinstance(res, dict) and "raw" in res:
            out = {
                "word": phrase,
                "translation": res.get("raw", "")[:120],
                "alternatives": [],
                "example": ""
            }
        elif isinstance(res, dict):
            out = {
                "word": res.get("word", phrase),
                "translation": res.get("translation", "") or "",
                "alternatives": res.get("alternatives", []) or [],
                "example": (res.get("example", "") or "")[:120]
            }
        else:
            out = {
                "word": phrase,
                "translation": str(res)[:120],
                "alternatives": [],
                "example": ""
            }
        self._cache[key] = out
        return out

    def _cached_correct(self, sentence: str) -> Dict[str, str]:
        key = ("corr", sentence)
        if key in self._cache:
            return self._cache[key]
        res = self.llm.correct_sentence(broken_sentence=sentence)
        if isinstance(res, dict) and "corrected" in res:
            out = {"corrected": res.get("corrected", ""), "note": res.get("note", "")}
        elif isinstance(res, dict) and "raw" in res:
            out = {"corrected": res.get("raw", ""), "note": ""}
        else:
            out = {"corrected": str(res), "note": ""}
        self._cache[key] = out
        return out

    # --- main API ---
    def analyze_session(self, transcript: List[Dict[str, str]]) -> Dict[str, Any]:
        print("YWH=====1====")
        """
        Returns:
        {
            "per_word": [
                {
                  "english": "good",
                  "translation": "好",
                  "alternatives": ["不错"],
                  "example": "今天很好。",
                  "sentence_index": 0
                }, ...
            ],
            "per_sentence": [
                {
                  "original": "今天很 good，我想 drink tea.",
                  "corrected": "今天很好，我想喝茶。",
                  "words_needing_feedback": ["good", "drink tea"]
                }, ...
            ],
            "summary": "Analyzed N turns; M words flagged."
        }
        """
        print("YWH=====22====")
        self._cache.clear()
        per_word = []
        sentence_to_words = {}  # idx -> list of phrases
        sentence_texts = {}     # idx -> original text
        total_words_flagged = 0
        
        print("YWH=====333====")

        # 1) collect English candidate phrases and map them to sentence indices
        for idx, turn in enumerate(transcript):
            print("YWH=====4444====")
            if turn.get("role") != "user":
                continue
            text = turn.get("text", "")
            sentence_texts[idx] = text

            tokens = PhraseExtractor.extract_phrases(text)

            # Keep only English phrases (skip Chinese tokens)
            english_tokens = [t for t in tokens if self._is_english_phrase(t)]
            print(english_tokens)

            # prioritize multi-word phrases and avoid overlapping words
            tokens_sorted = sorted(english_tokens, key=lambda t: -len(t.split()))
            seen = set()
            selected = []
            for t in tokens_sorted:
                words = [w.lower() for w in t.split()]
                if any(w in seen for w in words):
                    continue
                selected.append(t)
                for w in words:
                    seen.add(w)

            if selected:
                sentence_to_words[idx] = selected

        # 2) For each sentence, call suggest_phrase for each selected word/phrase
        for sent_idx, phrases in sentence_to_words.items():
            sent_text = sentence_texts.get(sent_idx, "")
            for phrase in phrases:
                if len(phrase.strip()) < 1:
                    continue
                suggestion = self._cached_suggest(phrase, sent_text)
                per_word.append({
                    "english": phrase,
                    "translation": suggestion.get("translation", ""),
                    "alternatives": suggestion.get("alternatives", []),
                    "example": suggestion.get("example", ""),
                    "sentence_index": sent_idx
                })
                total_words_flagged += 1

        # 3) After per-word loop, produce corrected sentences for sentences that had flagged words
        per_sentence = []
        for sent_idx, phrases in sentence_to_words.items():
            original = sentence_texts.get(sent_idx, "")
            corrected_info = self._cached_correct(original)
            per_sentence.append({
                "original": original,
                "corrected": corrected_info.get("corrected", ""),
                "note": corrected_info.get("note", ""),
                "words_needing_feedback": phrases
            })

        summary = f"Analyzed {len(sentence_texts)} turns; flagged {total_words_flagged} words/phrases across {len(per_sentence)} sentences."

        return {
            "per_word": per_word,
            "per_sentence": per_sentence,
            "summary": summary
        }



# if __name__ == "__main__":
#     from unittest.mock import MagicMock

#     # --- Mock LLMHandler ---
#     mock_llm = LLMHandler()
    
#     # Mock suggest_phrase
#     def mock_suggest(english_phrase, sentence_context):
#         mapping = {
#             "good": {"word": "good", "translation": "好", "alternatives": ["不错"], "example": "今天很好。"},
#             "drink tea": {"word": "drink tea", "translation": "喝茶", "alternatives": [], "example": "我想喝茶。"},
#             "like very": {"word": "like very", "translation": "很喜欢", "alternatives": ["喜欢"], "example": "我很喜欢喝水。"},
#             "cold water": {"word": "cold water", "translation": "冰水", "alternatives": ["冷饮"], "example": "我喜欢冰水。"}
#         }
#         return mapping.get(english_phrase, {"word": english_phrase, "translation": english_phrase, "alternatives": [], "example": ""})

#     # Mock correct_sentence
#     def mock_correct(broken_sentence, **kwargs):
#         mapping = {
#             "今天很 good，我想 drink tea.": {"corrected": "今天很好，我想喝茶。", "note": "词汇替换"},
#             "I only like very cold water.": {"corrected": "我只喜欢冰水。", "note": "词序调整"}
#         }
#         return mapping.get(broken_sentence, {"corrected": broken_sentence, "note": ""})


#     mock_llm.suggest_phrase = MagicMock(side_effect=mock_suggest)
#     mock_llm.correct_sentence = MagicMock(side_effect=mock_correct)

#     # --- Create FeedbackGenerator ---
#     fgen = FeedbackGenerator(mock_llm)

#     # --- Sample transcript ---
#     transcript = [
#         {"role": "assistant", "text": "你好，今天天气怎么样？"},
#         {"role": "user", "text": "今天很 good，我想 drink tea."},
#         {"role": "assistant", "text": "听起来不错。"},
#         {"role": "user", "text": "I only like very cold water."}
#     ]

#     # --- Analyze ---
#     feedback = fgen.analyze_session(transcript)

#     # --- Print per-word feedback ---
#     print("\n--- PER WORD FEEDBACK ---")
#     for word in feedback["per_word"]:
#         print(f"Sentence #{word['sentence_index']}: '{word['english']}'")
#         print(f"  Translation: {word['translation']}")
#         print(f"  Alternatives: {word['alternatives']}")
#         print(f"  Example: {word['example']}")

#     # --- Print per-sentence corrections ---
#     print("\n--- PER SENTENCE CORRECTIONS ---")
#     for sent in feedback["per_sentence"]:
#         print(f"Original: {sent['original']}")
#         print(f"Corrected: {sent['corrected']}")
#         print(f"Words needing feedback: {sent['words_needing_feedback']}")
#         print(f"Note: {sent.get('note','')}")
    
#     # --- Print summary ---
#     print("\n--- SUMMARY ---")
#     print(feedback["summary"])














# #import jieba
# # from backend.utils.dictionary import Dictionary
# from backend.utils.phrase_extractor import PhraseExtractor
# from backend.models.llm_handler import LLMHandler
# from pathlib import Path

# class FeedbackGenerator:
#     def __init__(self, llm_handler):
#         self.llm = llm_handler
#         # self.dictionary = Dictionary()
        
#     def analyze_session(self, transcript):
#         """
#         For each user turn:
#         1. extract phrases (multi-word first)
#         2. call LLM.suggest_phrase for each chosen phrase
#         3. call LLM.correct_sentence once per user sentence
#         Returns: {
#             "suggestions": [ { "english": "...", "translation": "...", "alternatives": [...], "example": "..." }, ... ],
#             "corrected_sentence": "...",
#             "summary": "..."
#         }
#         """
#         feedback = {
#             "suggestions": [],
#             "corrected_sentence": None,
#             "summary": ""
#         }

#         for turn in transcript:
#             if turn["role"] != "user":
#                 continue
#             text = turn["text"]

#             # Extract phrases
#             tokens = PhraseExtractor.extract_phrases(text)

#             # Process multi-word phrases first and avoid duplicates of their words
#             tokens_sorted = sorted(tokens, key=lambda t: -len(t.split()))
#             seen_words = set()
#             selected = []
#             for t in tokens_sorted:
#                 words = [w.lower() for w in t.split()]
#                 # skip if all words already covered by a multi-word we selected
#                 if any(w in seen_words for w in words):
#                     continue
#                 selected.append(t)
#                 for w in words:
#                     seen_words.add(w)

#             # Request suggestion for each selected phrase
#             for phrase in selected:
#                 if len(phrase) < 2:
#                     continue
#                 llm_json = self.llm.suggest_phrase(english_phrase=phrase, sentence_context=text)
#                 # Normalize parsed result to expected dict
#                 if isinstance(llm_json, dict) and "raw" in llm_json:
#                     # fallback: put raw text under example
#                     suggestion = {
#                         "english": phrase,
#                         "translation": llm_json.get("raw", "")[:80],
#                         "alternatives": [],
#                         "example": ""
#                     }
#                 else:
#                     suggestion = {
#                         "english": llm_json.get("word", phrase) if isinstance(llm_json, dict) else phrase,
#                         "translation": llm_json.get("translation", "") if isinstance(llm_json, dict) else "",
#                         "alternatives": llm_json.get("alternatives", []) if isinstance(llm_json, dict) else [],
#                         "example": llm_json.get("example", "") if isinstance(llm_json, dict) else ""
#                     }
#                 feedback["suggestions"].append(suggestion)

#             # After all phrase suggestions, request corrected full sentence
#             corrected = self.llm.correct_sentence(broken_sentence=text)
#             if isinstance(corrected, dict) and "corrected" in corrected:
#                 feedback["corrected_sentence"] = corrected["corrected"]
#             else:
#                 # fallback: use raw text if LLM failed
#                 feedback["corrected_sentence"] = corrected.get("raw", "") if isinstance(corrected, dict) else str(corrected)

#         feedback["summary"] = f"Analyzed {len(transcript)} turns. Generated {len(feedback['suggestions'])} suggestions."
#         return feedback



#     def _is_english(self, word):
#         return word.replace("-", "").isalpha() and word.isascii()
    
#     # def _load_hsk(self):
#     #     """Load HSK characters + words for a given level."""

#     #     base_dir = Path(__file__).resolve().parent.parent  # backend/
#     #     # Two different files
#     #     char_file = base_dir / 'data' / f'hsk3.0_char.txt'
#     #     word_file = base_dir / 'data' / f'hsk3.0_word.txt'

#     #     hsk = set()

#     #     # Load chars
#     #     if char_file.exists():
#     #         with open(char_file, 'r', encoding='utf-8') as f:
#     #             for line in f:
#     #                 w = line.strip()
#     #                 if w:
#     #                     hsk.add(w)

#     #     # Load words
#     #     if word_file.exists():
#     #         with open(word_file, 'r', encoding='utf-8') as f:
#     #             for line in f:
#     #                 w = line.strip()
#     #                 if w:
#     #                     hsk.add(w)

#     #     if not hsk:
#     #         print(f"Warning: No HSK files found.")

#     #     return hsk
    

# if __name__ == '__main__':
    
#     llm = LLMHandler()

#     class TestableFeedbackGenerator(FeedbackGenerator):
#         def __init__(self):
#             super().__init__(llm_handler=llm)
#             # manually set dictionary path if needed
#             # base_dir = Path(__file__).resolve().parent.parent
#             # cedict_path = base_dir / 'data' / 'cc-cedict.txt'
#             # self.dictionary = Dictionary(cedict_path=str(cedict_path))

#     simulated_transcript = [
#         {'role': 'assistant', 'text': '你好，今天天气怎么样？'},
#         {'role': 'user', 'text': '今天很 good，我想 drink tea.'},
#         {'role': 'assistant', 'text': '听起来不错。你喜欢喝什么茶？'},
#         {'role': 'user', 'text': 'I only like very cold water.'}
#     ]

#     print("Initializing Feedback Generator...")
#     fgen = TestableFeedbackGenerator()

#     print("\nAnalyzing simulated transcript...")
#     feedback_report = fgen.analyze_session(simulated_transcript)

#     # printing
#     print("\n--- Feedback Report ---")
#     print(feedback_report['summary'])
#     print(f"Total Suggestions Found: {len(feedback_report['per_word'])}")

#     for item in feedback_report['per_word']:
#         print(f"- English: {item['english']}")
#         print(f"  Translation: {item['translation']}")
#         print(f"  Alternatives: {item['alternatives']}")
#         print(f"  Example: {item['example']}")

#     print("-----------------------")

