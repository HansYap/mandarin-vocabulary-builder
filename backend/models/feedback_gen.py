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
        2. Correct sentences with English FIRST
        3. Resolve phrases using corrected sentences (Dictionary lookup)
        4. Return vocabulary + corrections
        
        Returns: JSON-serializable dict matching SessionFeedback schema
        """
        
        print("\n" + "="*60)
        print("[SMART FEEDBACK] Starting analysis...")
        print(f"[SMART FEEDBACK] Transcript has {len(transcript)} turns")
        print("="*60 + "\n")
        
        # 1. Identify English phrases & sentences to fix
        english_phrases = []
        sentences_to_fix = []
        
        for idx, turn in enumerate(transcript):
            if turn.get('role') == 'user':
                text = turn.get('content') or turn.get('text', '')
                print(f"[TURN {idx}] User: '{text}'")
                
                # Collect English phrases
                phrases = self._extract_english_phrases(text)
                print(f"[TURN {idx}] Extracted English: {phrases}")
                for p in phrases:
                    # Store the association between word and sentence
                    english_phrases.append((p, text))
                
                # If it has English or is mixed, collect for correction
                if phrases or self._has_mixed_language(text):
                    sentences_to_fix.append(text)

        print(f"\n[PHASE 1] Found {len(english_phrases)} English phrases")
        print(f"[PHASE 1] {len(sentences_to_fix)} sentences need correction\n")
        
        # 2. Correct all sentences FIRST (build mapping)
        corrections = []
        sentence_map = {}  # Original -> Corrected
        
        for sent in sentences_to_fix[-3:]:  # Last 3 to keep it fast
            print(f"[CORRECTION] Fixing: '{sent}'")
            correction_obj = self._fix_sentence_llm(sent)
            if correction_obj:
                corrections.append(correction_obj)
                sentence_map[sent] = correction_obj.corrected_sentence

        print(f"\n[PHASE 2] Generated {len(corrections)} corrections")
        print(f"[PHASE 2] Sentence map: {sentence_map}\n")

        # 3. Build Vocabulary Cards using corrected sentences
        vocab_cards = []
        seen_translations = set()  # Deduplicate by English word + Chinese translation
        
        for phrase, original_context in english_phrases:
            # Get the corrected version of this sentence
            corrected_context = sentence_map.get(original_context)
            
            if not corrected_context:
                print(f"[VOCAB] No correction found for '{original_context}', skipping")
                continue
            
            # Create a unique key: "english_word|corrected_sentence"
            # This allows same English word to have different translations in different contexts
            dedup_key = f"{phrase.lower()}|{corrected_context}"
            
            # Skip if we've already processed this exact combination
            if dedup_key in seen_translations:
                print(f"[VOCAB] Skipping duplicate '{phrase}' in same context")
                continue
            seen_translations.add(dedup_key)
            
            # Get the corrected version of this sentence (already retrieved above)
            print(f"[VOCAB] Resolving '{phrase}'")
            print(f"       Original: {original_context}")
            print(f"       Corrected: {corrected_context}")
            
            # Now call suggest_phrase with BOTH sentences
            card = self._resolve_phrase(phrase, original_context, corrected_context)
            if card:
                vocab_cards.append(card)

        print(f"\n[PHASE 3] Created {len(vocab_cards)} vocabulary cards\n")

        # 4. Annotate vocabulary cards that appear in corrections
        corrected_words = set()
        for sent in sentences_to_fix[-3:]:
            eng_words = self._extract_english_phrases(sent)
            for word in eng_words:
                corrected_words.add(word.lower())

        for card in vocab_cards:
            word_lower = card.original_text.lower()
            if word_lower in corrected_words:
                card.context_note = f"💡 在句子中更自然的说法请看下方「句子修正」"
                print(f"[ANNOTATE] '{card.original_text}' appears in corrections")

        # 5. Assemble Final Response
        feedback = SessionFeedback(
            vocabulary=vocab_cards,
            corrections=corrections,
            summary=f"Found {len(vocab_cards)} new words and {len(corrections)} grammar tips."
        )

        print("="*60)
        print("[SMART FEEDBACK COMPLETE]")
        print(f"Summary: {feedback.summary}")
        print("="*60 + "\n")

        return feedback.model_dump()  # Returns clean JSON dict

    # --- THE "HYBRID" RESOLVER (UPDATED) ---
    def _resolve_phrase(self, phrase: str, original_sentence: str, corrected_sentence: str) -> Optional[VocabCard]:
        """
        Delegates to LLMHandler's smart suggest_phrase.
        NOW passes both original and corrected sentences.
        """
        print(f"  [SMART] Resolving '{phrase}'...")
        
        try:
            # Call the updated method with 3 parameters
            result = self.llm.suggest_phrase(
                english_phrase=phrase,
                original_sentence=original_sentence,
                corrected_sentence=corrected_sentence
            )
            
            # Standardize source for the UI
            raw_source = result.get('source', 'llm')
            final_source = "dictionary" if "dictionary" in raw_source else "llm"
            
            return VocabCard(
                original_text=phrase,
                mandarin_text=result.get('translation', phrase),
                pinyin=result.get('pinyin', ''),
                example_sentence=result.get('example', ''),
                difficulty_level=result.get('source', 'LLM'),
                type='word',
                source=final_source
            )
        except Exception as e:
            print(f"  [ERROR] Resolve failed: {e}")
            return VocabCard(
                original_text=phrase,
                mandarin_text=phrase,
                pinyin="",
                example_sentence="Error resolving phrase",
                difficulty_level="Error",
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