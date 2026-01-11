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
        
        #1. Identify English phrases & sentences to fix
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
        
        corrections = []
        vocab_cards = []
        seen_vocab = set()
        
        for sent in sentences_to_fix[-3:]:
            # 1. Get correction and mappings in ONE call
            result_data = self.llm.correct_sentence(sent) 
            corrected_text = result_data.get('corrected', sent)
            mappings = result_data.get('mappings', [])
            
            # === DEBUG OUTPUT ===
            print(f"\n{'='*70}")
            print(f"📝 Original:  {sent}")
            print(f"✅ Corrected: {corrected_text}")
            print(f"📋 Mappings from LLM:")
            for i, m in enumerate(mappings, 1):
                en = m.get('english', '?')
                cn = m.get('chinese', '?')
                # Check if the Chinese word actually exists in corrected text
                exists = '✓' if cn in corrected_text else '✗ NOT IN TEXT'
                print(f"   {i}. '{en}' → '{cn}' {exists}")
            print(f"{'='*70}\n")
            # === END DEBUG ===

            # 2. Process Mappings for Anchors and Vocab Cards
            for item in mappings:
                en_word = item.get('english')
                cn_word = item.get('chinese')

                # Create the Inline Anchor in the text
                # This turns "预订" into "[[预订]]" for your UI to highlight
                corrected_text = corrected_text.replace(cn_word, f"[[{cn_word}]]")

                # Create Vocab Card using the dictionary for pinyin/definitions
                # This ensures 100% accuracy and consistency
                dict_entry = self.dictionary.get(cn_word)
                
                vocab_key = f"{en_word}|{cn_word}"
                if dict_entry and vocab_key not in seen_vocab:
                    vocab_cards.append(VocabCard(
                        original_text=en_word,
                        mandarin_text=cn_word,
                        pinyin=dict_entry.get('pinyin', ''),
                        example_sentence=f"Context: {corrected_text.replace('[[', '').replace(']]', '')}",
                        difficulty_level="New",
                        type='word',
                        source='dictionary'
                    ))
                    seen_vocab.add(vocab_key)

            # 3. Store the correction (with anchors)
            corrections.append(SentenceCorrection(
                original_sentence=sent,
                corrected_sentence=corrected_text,
                explanation=result_data.get('note', ''),
                note='',
                highlight_ranges=[] 
            ))

        # Assemble Final Response (Matches SessionFeedback schema)
        return SessionFeedback(
            vocabulary=vocab_cards,
            corrections=corrections,
            summary=f"Found {len(vocab_cards)} new words and {len(corrections)} grammar tips."
        ).model_dump()


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

    