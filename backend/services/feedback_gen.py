import json
import re
from typing import List, Dict
from backend.services.llm_handler import LLMHandler
from backend.services.schemas import SessionFeedback, VocabCard, SentenceCorrection


class FeedbackGenerator:
    def __init__(self, llm_handler: LLMHandler):
        self.llm = llm_handler
        # Re-use the dictionary from your LLMHandler
        # self.dictionary = getattr(llm_handler, 'dictionary', {})
        

    def analyze_session(self, transcript: List[Dict]) -> Dict:
        
        # 1. Identify sentences that need correction
        sentences_to_fix = []
        
        for idx, turn in enumerate(transcript):
            if turn.get('role') == 'user':
                text = turn.get('content') or turn.get('text', '')
                print(f"[TURN {idx}] User: '{text}'")
                
                # Collect any sentence that has English or mixed language
                if self._has_english(text) or self._has_mixed_language(text):
                    sentences_to_fix.append(text)

        print(f"\n[PHASE 1] {len(sentences_to_fix)} sentences need correction\n")
        
        corrections = []
        vocab_cards = []
        seen_vocab = set()
        
        # Process last 3 sentences for feedback
        for sent in sentences_to_fix:
            # 1. Get natural correction with highlights from LLM
            result_data = self.llm.correct_sentence(sent)
            
            corrected_text = result_data.get('corrected', sent)
            highlights = result_data.get('highlights', [])
            note = result_data.get('note', '')
            
            # === DEBUG OUTPUT ===
            print(f"\n{'='*70}")
            print(f"📝 Original:  {sent}")
            print(f"✅ Corrected: {corrected_text}")
            print(f"📚 Highlights ({len(highlights)} items):")
            for i, h in enumerate(highlights, 1):
                word = h.get('word', '?')
                meaning = h.get('meaning', '?')
                why = h.get('why', '')
                category = h.get('category', 'new_vocab')
                # Check if word exists in corrected text
                exists = '✓' if word in corrected_text else '✗ NOT IN TEXT'
                print(f"   {i}. '{word}' = {meaning} {exists}")
                print(f"      Why: {why} ({category})")
            if note:
                print(f"💬 Note: {note}")
            print(f"{'='*70}\n")
            # === END DEBUG ===

            # 2. Process highlights for vocab cards and text anchoring
            corrected_with_anchors = corrected_text
            
            for h in highlights:
                word = h.get('word', '')
                meaning = h.get('meaning', '')
                why = h.get('why', '')
                category = h.get('category', 'new_vocab')
                
                # Skip if word doesn't exist in corrected text (validation)
                if word not in corrected_text:
                    print(f"⚠️  Skipping '{word}' - not found in corrected text")
                    continue
                
                # Add [[anchors]] for UI highlighting (first occurrence only)
                # Check if this specific word is already anchored
                if word in corrected_with_anchors and f"[[{word}]]" not in corrected_with_anchors:
                    corrected_with_anchors = corrected_with_anchors.replace(
                        word, 
                        f"[[{word}]]", 
                        1  # Only first occurrence
                    )
                
                # Create vocab card with dictionary enrichment
                dict_entry = self.dictionary.get(word)
                
                # Use word itself as key
                vocab_key = word
                
                if vocab_key not in seen_vocab:
                    # Get pinyin from dictionary, fallback to guessing
                    if dict_entry:
                        pinyin = dict_entry.get('pinyin', '')
                        definitions = dict_entry.get('definitions', [meaning])
                        # Prefer dict definition if available, else use LLM meaning
                        full_meaning = definitions[0] if definitions else meaning
                    else:
                        pinyin = self._guess_pinyin(word)
                        full_meaning = meaning
                    
                    vocab_cards.append(VocabCard(
                        original_text=meaning,  # English meaning as "original"
                        mandarin_text=word,
                        pinyin=pinyin,
                        example_sentence=corrected_text,
                        difficulty_level=category,  # Use category as difficulty
                        type=category,  # new_vocab, measure_word, collocation, idiom
                        source='llm_highlight'
                    ))
                    seen_vocab.add(vocab_key)
                    
                    print(f"✅ Added vocab card: {word} ({pinyin}) = {full_meaning}")

            # 3. Store the correction (with anchors for UI)
            corrections.append(SentenceCorrection(
                original_sentence=sent,
                corrected_sentence=corrected_with_anchors,
                explanation=note,
                note=why if highlights else '',
                highlight_ranges=[]  # Not needed since we use [[anchors]]
            ))

        # Assemble final response
        return SessionFeedback(
            vocabulary=vocab_cards,
            corrections=corrections,
            summary=f"找到 {len(vocab_cards)} 个值得学习的词汇和 {len(corrections)} 个改进建议。"
        ).model_dump()

    # --- HELPER METHODS ---
    
    def _has_english(self, text: str) -> bool:
        """Check if text contains English"""
        return bool(re.search(r'[a-zA-Z]', text))
    
    def _has_mixed_language(self, text: str) -> bool:
        """Check if text contains both Chinese and English"""
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', text))
        has_english = bool(re.search(r'[a-zA-Z]', text))
        return has_chinese and has_english
    
    def _guess_pinyin(self, word: str) -> str:
        """
        Fallback: Generate approximate pinyin for words not in dictionary.
        Looks up individual characters if multi-character word.
        """
        pinyin_parts = []
        for char in word:
            entry = self.dictionary.get(char)
            if entry:
                # Extract syllable (remove tone numbers if needed)
                syllable = entry['pinyin'].split()[0] if entry['pinyin'] else char
                pinyin_parts.append(syllable)
            else:
                pinyin_parts.append(char)
        
        return ' '.join(pinyin_parts) if pinyin_parts else word