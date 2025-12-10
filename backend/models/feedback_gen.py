import json
import re
from typing import List, Dict, Optional
from backend.models.llm_handler import LLMHandler
from backend.models.schemas import SessionFeedback, VocabCard, SentenceCorrection

class FeedbackGenerator:
    def __init__(self, llm_handler: LLMHandler):
        self.llm = llm_handler
        # Re-use the dictionary from your LLMHandler
        self.dictionary = getattr(llm_handler, 'dictionary', {})

    def analyze_session(self, transcript: List[Dict]) -> Dict:
        """
        Orchestrates the analysis pipeline:
        1. Extract English phrases
        2. Resolve phrases (Dictionary First -> LLM Fallback)
        3. Correct full sentences
        
        Returns: JSON-serializable dict matching SessionFeedback schema
        """
        
        print("\n" + "="*60)
        print("[SMART FEEDBACK] Starting analysis...")
        print(f"[SMART FEEDBACK] Transcript has {len(transcript)} turns")
        print("="*60 + "\n")
        
        # 1. Identify English phrases & sentences to fix
        english_phrases = set()
        sentences_to_fix = []
        
        for idx, turn in enumerate(transcript):
            if turn.get('role') == 'user':
                text = turn.get('content') or turn.get('text', '')
                print(f"[TURN {idx}] User: '{text}'")
                
                # Collect English phrases
                phrases = self._extract_english_phrases(text)
                print(f"[TURN {idx}] Extracted English: {phrases}")
                english_phrases.update(phrases)
                
                # If it has English or is mixed, collect for correction
                if phrases or self._has_mixed_language(text):
                    sentences_to_fix.append(text)

        print(f"\n[PHASE 1] Found {len(english_phrases)} unique English phrases")
        print(f"[PHASE 1] {len(sentences_to_fix)} sentences need correction\n")

        # 2. Build Vocabulary Cards (The Hybrid Engine)
        vocab_cards = []
        for phrase in sorted(english_phrases):  # Sort for consistent output
            print(f"[VOCAB] Resolving '{phrase}'...")
            card = self._resolve_phrase(phrase)
            vocab_cards.append(card)

        print(f"\n[PHASE 2] Created {len(vocab_cards)} vocabulary cards\n")

        # 3. Correct Sentences (last 3 to keep it fast)
        corrections = []
        corrected_words = {}  # Map: word -> corrected translation in sentence
        
        for sent in sentences_to_fix[-3:]:
            print(f"[CORRECTION] Fixing: '{sent}'")
            correction = self._fix_sentence_llm(sent)
            if correction:
                corrections.append(correction)
                # Extract English words and their contextual Chinese equivalents
                eng_words = self._extract_english_phrases(sent)
                for word in eng_words:
                    corrected_words[word.lower()] = sent  # Store which sentence it appeared in

        print(f"\n[PHASE 3] Generated {len(corrections)} corrections\n")
        
        # Annotate vocabulary cards that also appear in corrections
        for card in vocab_cards:
            word_lower = card.original_text.lower()
            if word_lower in corrected_words:
                # Add context note to vocabulary card
                card.context_note = f"💡 在句子中更自然的说法请看下方「句子修正」"
                print(f"[ANNOTATE] '{card.original_text}' appears in both - adding context note")

        print(f"[FILTER] Annotated {sum(1 for c in vocab_cards if c.context_note)} cards with context notes")

        # 4. Assemble Final Response
        feedback = SessionFeedback(
            vocabulary=vocab_cards,  # Keep all cards, but annotated
            corrections=corrections,
            summary=f"Found {len(vocab_cards)} new words and {len(corrections)} grammar tips."
        )

        print("="*60)
        print("[SMART FEEDBACK COMPLETE]")
        print(f"Summary: {feedback.summary}")
        print("="*60 + "\n")

        return feedback.model_dump()  # Returns clean JSON dict

    # --- THE "HYBRID" RESOLVER ---
    def _resolve_phrase(self, phrase: str) -> VocabCard:
        """
        Resolves a phrase using Dictionary First, then LLM fallback.
        """
        clean_phrase = phrase.lower().strip()
        
        # PATH A: Dictionary Lookup (Instant & Accurate)
        if clean_phrase in self.dictionary:
            entry = self.dictionary[clean_phrase]
            print(f"  [DICT] ✅ Found in dictionary: {entry['translation']} [{entry['pinyin']}]")
            
            return VocabCard(
                original_text=phrase,
                mandarin_text=entry['translation'],
                pinyin=entry['pinyin'],
                example_sentence=f"例句：{entry['translation']}",  # Dictionary lacks examples
                difficulty_level="Dictionary",
                type="word",
                source="dictionary"
            )

        # PATH B: LLM Generation (Creative & Context-Aware)
        print(f"  [LLM] ⚠️  Not in dictionary, calling LLM...")
        
        # Use existing suggest_phrase method from LLMHandler
        try:
            result = self.llm.suggest_phrase(english_phrase=phrase, sentence_context="")
            
            print(f"  [LLM] ✅ Got: {result.get('translation', '')} [{result.get('pinyin', '')}]")
            
            return VocabCard(
                original_text=phrase,
                mandarin_text=result.get('translation', phrase),
                pinyin=result.get('pinyin', ''),
                example_sentence=result.get('example', ''),
                difficulty_level='Unknown',  # LLM doesn't provide this
                type='phrase',
                source=result.get('source', 'llm')
            )
        except Exception as e:
            print(f"  [LLM] ❌ Failed: {e}")
            # Fallback Card
            return VocabCard(
                original_text=phrase,
                mandarin_text="[Not Found]",
                pinyin="",
                example_sentence="",
                difficulty_level="Unknown",
                type="unknown",
                source="error"
            )

    def _fix_sentence_llm(self, sentence: str) -> Optional[SentenceCorrection]:
        """
        Corrects a sentence using LLM's existing correct_sentence method.
        """
        try:
            result = self.llm.correct_sentence(broken_sentence=sentence)
            
            print(f"  [CORRECTION] ✅ Corrected to: {result.get('corrected', '')}")
            
            return SentenceCorrection(
                original_sentence=sentence,
                corrected_sentence=result.get('corrected', sentence),
                explanation=result.get('note', ''),
                note='',
                highlight_ranges=[]  # TODO: Implement word-level diff if needed
            )
        except Exception as e:
            print(f"  [CORRECTION] ❌ Failed: {e}")
            return None

    # --- HELPER METHODS ---
    def _extract_english_phrases(self, text: str) -> List[str]:
        """
        Improved Regex: Captures multi-word phrases like "ice cream".
        Ignores pure punctuation.
        """
        # Match sequences of letters with optional spaces/hyphens
        candidates = re.findall(r'[a-zA-Z][a-zA-Z\s\-]*[a-zA-Z]|[a-zA-Z]', text)
        return [c.strip() for c in candidates if len(c.strip()) > 0]

    def _has_mixed_language(self, text: str) -> bool:
        """
        Check if text contains both Chinese and English.
        """
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        has_english = bool(re.search(r'[a-zA-Z]', text))
        return has_chinese and has_english

    def _clean_and_parse_json(self, text: str) -> dict:
        """
        Robust JSON parser for LLM output.
        Handles markdown code blocks and extra text.
        """
        # Remove markdown code blocks
        text = text.replace("```json", "").replace("```", "").strip()
        
        try:
            return json.loads(text)
        except:
            # Find first { and last }
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end > start:
                return json.loads(text[start:end])
            raise ValueError(f"No valid JSON found in: {text[:100]}...")