import os
import re
import eventlet
import eventlet.tpool
from typing import Optional, Dict, List
from pypinyin import pinyin, Style


class DictionaryHandler:
    """Fast dictionary lookup service for CC-CEDICT"""
    
    def __init__(self, dict_path="../data/cc-cedict.txt"):
        self.simplified_index = {}  # simplified -> [entry1, entry2, ...]
        self.traditional_index = {}  # traditional -> [entry1, entry2, ...]
        self.compound_count = {}    # Track compound frequency per (word, pinyin)
        self._load_dictionary(dict_path)
        self._calculate_frequency_scores()
        
        # Translation model variable
        self.translator = None
        self.tokenizer = None
        self.unload_timer = None
        
        self.loading_lock = False
        
    def _get_translator(self):
        """Eventlet-safe lazy loading"""
        if self.loading_lock:
            eventlet.sleep(0.1)
            
        if self.translator is None:
            self.loading_lock = True
            
            try: 
                import ctranslate2
                import transformers
                
                current_dir = os.path.dirname(os.path.abspath(__file__))
                model_dir = os.path.join(current_dir, "../models/opus-mt-zh-en-ct2")
        
                print("🚀 Loading CTranslate2 (Eventlet-Safe Mode)...")
                self.translator = ctranslate2.Translator(model_dir, device="cuda")
                self.tokenizer = transformers.AutoTokenizer.from_pretrained("Helsinki-NLP/opus-mt-zh-en")
            finally:
                self.loading_lock = False
            
        if self.unload_timer:
            self.unload_timer.cancel()
        
        self.unload_timer = eventlet.spawn_after(300, self._unload_translation_model)
        
        return self.translator, self.tokenizer

    def _unload_translation_model(self):
        """Safe VRAM cleanup within the event loop"""
        print("💤 Inactivity detected: Offloading Translation Model...")
        self.translator = None
        self.tokenizer = None
        self.unload_timer = None
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _translate_phrase(self, text: str) -> str:
        return eventlet.tpool.execute(self._do_inference, text)
    
    def _do_inference(self, text: str) -> str:
        """The actual logic being offloaded to the thread pool"""
        translator, tokenizer = self._get_translator()
        
        source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(text, add_special_tokens=False))
        print(f"DEBUG - Input text: {text}")
        print(f"DEBUG - Source tokens: {source_tokens}")

        
        results = translator.translate_batch(
            [source_tokens],
            beam_size=2,
            max_decoding_length=12,
            length_penalty=1.2,
            repetition_penalty=2.3
        )

        target_tokens = results[0].hypotheses[0]
        print(f"DEBUG - Target tokens: {target_tokens}")
        
        translation = tokenizer.decode(tokenizer.convert_tokens_to_ids(target_tokens), skip_special_tokens=True)
        print(f"DEBUG - Decoded translation: '{translation}'")

        if '(' in translation:
            translation = translation.split('(')[0]
    
        translation = translation.split('.')[0].split('!')[0].split(';')[0]
        
        if ',' in translation:
            parts = translation.split(',')
            first_part = parts[0].strip()
            if len(first_part.split()) >= 2:
                translation = first_part
    
        final = translation.strip(".。!！, ")
        return final
    
    def _load_dictionary(self, path: str) -> None:
        """Load and index CC-CEDICT with multiple access patterns"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(current_dir, path)
        
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"Dictionary not found: {full_path}")
        
        print("Loading CC-CEDICT dictionary...")
        entry_count = 0
        
        with open(full_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or line.startswith('%') or not line.strip():
                    continue
                
                entry = self._parse_line(line)
                if entry:
                    self._index_entry(entry)
                    entry_count += 1
        
        print(f"✓ Dictionary loaded: {entry_count} entries indexed")
        print(f"  - Simplified index: {len(self.simplified_index)} keys")
        print(f"  - Traditional index: {len(self.traditional_index)} keys")
    
    def _parse_line(self, line: str) -> Optional[Dict]:
        """Parse a single CC-CEDICT line with classifier extraction"""
        try:
            bracket_start = line.find('[')
            bracket_end = line.find(']')
            if bracket_start == -1 or bracket_end == -1:
                return None
            
            parts = line[:bracket_start].strip().split()
            if len(parts) < 2:
                return None
            
            traditional = parts[0]
            simplified = parts[1]
            raw_pinyin = line[bracket_start+1:bracket_end].strip()
            pinyin = self._normalize_pinyin(raw_pinyin)
            
            # Parse definitions and extract classifier
            meanings_raw = line[bracket_end+1:].strip().strip('/')
            definitions = []
            classifier = None
            
            for meaning in meanings_raw.split('/'):
                meaning = meaning.strip()
                if not meaning:
                    continue
                
                # Extract classifier (e.g., "CL:名[ming2]")
                if meaning.startswith("CL:"):
                    cl_part = meaning[3:]  # remove 'CL:'
                    cl_matches = re.findall(
                        r'([\u4e00-\u9fff]+)(?:\[([\u4e00-\u9fff]+)\])?\[(.+?)\]',
                        cl_part
                    )
                    if cl_matches:
                        classifier = [
                            f"{trad}[{simp}][{pinyin}]" if simp else f"{trad}[{pinyin}]"
                            for trad, simp, pinyin in cl_matches
                        ]
                    continue

                definitions.append(meaning)
            
            # Determine if this is a single character or compound
            is_compound = len(simplified) > 1
            
            entry = {
                "is_generated": False,
                "simplified": simplified,
                "traditional": traditional,
                "pinyin": pinyin,
                "definitions": definitions,
                "classifier": classifier,
                "char_count": len(simplified),
                "is_compound": is_compound,
                "message": "Phrase found in dictionary",
            }
            
            return entry
            
        except Exception as e:
            return None
    
    def _index_entry(self, entry: Dict) -> None:
        """Index entry and track compound frequency"""
        simplified = entry["simplified"]
        traditional = entry["traditional"]
        pinyin = entry["pinyin"]
        
        # Store as lists to handle multiple entries per word
        if simplified not in self.simplified_index:
            self.simplified_index[simplified] = []
        self.simplified_index[simplified].append(entry)
        
        if traditional != simplified:
            if traditional not in self.traditional_index:
                self.traditional_index[traditional] = []
            self.traditional_index[traditional].append(entry)
        
        # Track compound frequency for single-character base words
        # e.g., "打電話" counts toward frequency of 打[da3]
        if entry["is_compound"]:
            base_char = simplified[0]  # First character
            key = (base_char, pinyin)
            if key not in self.compound_count:
                self.compound_count[key] = 0
            self.compound_count[key] += 1
    
    def _calculate_frequency_scores(self):
        """Calculate frequency scores for single-character entries based on compound count"""
        print("Calculating frequency scores...")
        
        for word, entries in self.simplified_index.items():
            if len(entries) <= 1:
                continue  # No ambiguity
            
            # Only score single-character words (where compounds matter)
            if len(word) > 1:
                continue
            
            for entry in entries:
                pinyin = entry["pinyin"]
                key = (word, pinyin)
                
                # Frequency = number of compound words using this pronunciation
                compound_freq = self.compound_count.get(key, 0)
                entry["frequency_score"] = compound_freq
        
        print("✓ Frequency scores calculated")
    
    def lookup(self, chinese_word: str, context: str = "") -> Dict:
        """
        Lookup a Chinese word - returns ALL matching entries, ordered by frequency
        
        Args:
            chinese_word: The Chinese text to lookup
            context: Not used currently, kept for API compatibility
        
        Returns:
            Dictionary with 'found' flag and 'entries' list (sorted by frequency)
        """
        if not self._is_chinese(chinese_word):
            return self._not_found(chinese_word)
        
        # Try exact match first
        entries = self._exact_lookup(chinese_word)
        if entries:
            # Sort by frequency score (highest first)
            sorted_entries = self._sort_by_frequency(entries, chinese_word)
            
            return {
                "found": True,
                "query": chinese_word,
                "entries": sorted_entries,
                "count": len(sorted_entries)
            }
        
        # Generate entry if not found
        if self._is_chinese(chinese_word):
            pinyin_list = pinyin(chinese_word, style=Style.TONE3)
            pinyin_str = " ".join([item[0] for item in pinyin_list])
            translation = self._translate_phrase(chinese_word)

            generated_entry = {
                "is_generated": True,
                "simplified": chinese_word,
                "traditional": chinese_word,
                "pinyin": pinyin_str,
                "definitions": [translation],
                "message": "Phrase not in dictionary; generated via OPUS-MT.",
                "confidence": "generated"
            }
            
            return {
                "found": True,
                "query": chinese_word,
                "entries": [generated_entry],
                "count": 1
            }
        
        return self._not_found(chinese_word)
    
    def _sort_by_frequency(self, entries: List[Dict], word: str) -> List[Dict]:
        """
        Sort entries by frequency score and add confidence labels
        """
        # Make copies to avoid modifying original entries
        sorted_entries = []
        
        for entry in entries:
            entry_copy = entry.copy()
            freq_score = entry_copy.get("frequency_score", 0)
            
            # Add metadata for frontend
            if len(word) == 1:  # Single character - use frequency
                entry_copy["sort_score"] = freq_score
            else:  # Multi-character - keep original order
                entry_copy["sort_score"] = 0
            
            sorted_entries.append(entry_copy)
        
        # Sort by frequency score (highest first)
        sorted_entries.sort(key=lambda x: x["sort_score"], reverse=True)
        
        # Add confidence labels
        if len(sorted_entries) > 1:
            # Mark the most common one
            max_score = sorted_entries[0]["sort_score"]
            if max_score > 0:
                sorted_entries[0]["confidence"] = "most common"
                for i in range(1, len(sorted_entries)):
                    sorted_entries[i]["confidence"] = "less common"
            else:
                # No frequency data, all equal
                for entry in sorted_entries:
                    entry["confidence"] = "see all meanings"
        else:
            sorted_entries[0]["confidence"] = "only meaning"
        
        return sorted_entries
    
    def _exact_lookup(self, word: str) -> Optional[List[Dict]]:
        """Exact dictionary lookup - returns all matching entries"""
        # Try simplified first
        if word in self.simplified_index:
            return self.simplified_index[word]
        
        # Try traditional
        if word in self.traditional_index:
            return self.traditional_index[word]
        
        return None  
    
    def _not_found(self, word: str) -> Dict:
        return {
            "found": False,
            "query": word,
            "entries": [],
            "count": 0,
            "message": "Term not found"
        }
  
    def _is_chinese(self, text: str) -> bool:
        """Check if the string contains at least one Chinese character"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))
    
    def _normalize_pinyin(self, pinyin: str) -> str:
        """Remove neutral tone marker (5) from CC-CEDICT pinyin"""
        return re.sub(r'(?<=[a-zA-ZüÜ])5\b', '', pinyin)


# Singleton instance
_dictionary_service = None

def get_dictionary_service() -> DictionaryHandler:
    """Get or create the singleton dictionary service"""
    global _dictionary_service
    if _dictionary_service is None:
        _dictionary_service = DictionaryHandler()
    return _dictionary_service