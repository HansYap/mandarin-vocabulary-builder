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
        print(f"[DEBUG] Checking if '{token}' is English phrase...")
        
        # contains any CJK? if yes -> not english phrase
        if re.search(r'[\u4e00-\u9fff]', token):
            print(f"[DEBUG] ❌ '{token}' contains Chinese characters - NOT English")
            return False
        
        # must contain at least one ascii letter
        has_letter = bool(re.search(r'[A-Za-z]', token))
        print(f"[DEBUG] {'✅' if has_letter else '❌'} '{token}' is {'English' if has_letter else 'NOT English'}")
        return has_letter

    def _normalize_phrase(self, phrase: str) -> str:
        return phrase.strip().lower()

    def _cached_suggest(self, phrase: str, context: str) -> Dict[str, Any]:
        key = ("sug", self._normalize_phrase(phrase), context)
        if key in self._cache:
            print(f"[CACHE HIT] Using cached suggestion for '{phrase}'")
            return self._cache[key]
        
        print(f"[CACHE MISS] Calling LLM suggest_phrase for '{phrase}'...")
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
            print(f"[CACHE HIT] Using cached correction for sentence")
            return self._cache[key]
        
        print(f"[CACHE MISS] Calling LLM correct_sentence...")
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
        print("\n" + "="*60)
        print("[ANALYZE SESSION] Starting analysis...")
        print(f"[ANALYZE SESSION] Transcript has {len(transcript)} turns")
        print("="*60 + "\n")
        
        self._cache.clear()
        per_word = []
        sentence_to_words = {}  # idx -> list of phrases
        sentence_texts = {}     # idx -> original text
        total_words_flagged = 0

        # 1) collect English candidate phrases and map them to sentence indices
        for idx, turn in enumerate(transcript):
            print(f"\n[TURN {idx}] Role: {turn.get('role')}")
            
            if turn.get("role") != "user":
                print(f"[TURN {idx}] ⏭️  Skipping (not user turn)")
                continue
            
            text = turn.get("text", "")
            print(f"[TURN {idx}] User said: '{text}'")
            sentence_texts[idx] = text

            # Extract phrases
            print(f"[TURN {idx}] Extracting phrases...")
            tokens = PhraseExtractor.extract_phrases(text)
            print(f"[TURN {idx}] Extracted tokens: {tokens}")

            # Keep only English phrases (skip Chinese tokens)
            english_tokens = [t for t in tokens if self._is_english_phrase(t)]
            print(f"[TURN {idx}] English tokens after filtering: {english_tokens}")

            if not english_tokens:
                print(f"[TURN {idx}] ⚠️  No English phrases found")
                continue

            # prioritize multi-word phrases and avoid overlapping words
            tokens_sorted = sorted(english_tokens, key=lambda t: -len(t.split()))
            print(f"[TURN {idx}] Sorted by length (longest first): {tokens_sorted}")
            
            seen = set()
            selected = []
            for t in tokens_sorted:
                words = [w.lower() for w in t.split()]
                if any(w in seen for w in words):
                    print(f"[TURN {idx}]   ⏭️  Skipping '{t}' (overlaps with already selected)")
                    continue
                selected.append(t)
                print(f"[TURN {idx}]   ✅ Selected '{t}'")
                for w in words:
                    seen.add(w)

            if selected:
                sentence_to_words[idx] = selected
                print(f"[TURN {idx}] Final selected phrases: {selected}")

        print(f"\n{'='*60}")
        print(f"[PHASE 1 COMPLETE] Found {len(sentence_to_words)} sentences with English phrases")
        print(f"{'='*60}\n")

        # 2) For each sentence, call suggest_phrase for each selected word/phrase
        for sent_idx, phrases in sentence_to_words.items():
            sent_text = sentence_texts.get(sent_idx, "")
            print(f"\n[SENTENCE {sent_idx}] Processing {len(phrases)} phrases...")
            
            for phrase in phrases:
                if len(phrase.strip()) < 1:
                    continue
                
                print(f"[SENTENCE {sent_idx}] Getting suggestion for '{phrase}'...")
                suggestion = self._cached_suggest(phrase, sent_text)
                
                per_word.append({
                    "english": phrase,
                    "translation": suggestion.get("translation", ""),
                    "alternatives": suggestion.get("alternatives", []),
                    "example": suggestion.get("example", ""),
                    "sentence_index": sent_idx
                })
                total_words_flagged += 1
                print(f"[SENTENCE {sent_idx}]   → Translation: {suggestion.get('translation', '')}")

        print(f"\n{'='*60}")
        print(f"[PHASE 2 COMPLETE] Generated {total_words_flagged} word suggestions")
        print(f"{'='*60}\n")

        # 3) After per-word loop, produce corrected sentences for sentences that had flagged words
        per_sentence = []
        for sent_idx, phrases in sentence_to_words.items():
            original = sentence_texts.get(sent_idx, "")
            print(f"\n[CORRECTION {sent_idx}] Correcting: '{original}'")
            
            corrected_info = self._cached_correct(original)
            per_sentence.append({
                "original": original,
                "corrected": corrected_info.get("corrected", ""),
                "note": corrected_info.get("note", ""),
                "words_needing_feedback": phrases
            })
            print(f"[CORRECTION {sent_idx}]   → Corrected: {corrected_info.get('corrected', '')}")

        summary = f"Analyzed {len(sentence_texts)} turns; flagged {total_words_flagged} words/phrases across {len(per_sentence)} sentences."

        print(f"\n{'='*60}")
        print(f"[ANALYSIS COMPLETE]")
        print(f"{summary}")
        print(f"{'='*60}\n")

        return {
            "per_word": per_word,
            "per_sentence": per_sentence,
            "summary": summary
        }