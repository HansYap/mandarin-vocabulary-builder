import os
import re
import eventlet
import eventlet.tpool
from typing import Optional, Dict
from pypinyin import pinyin, Style


class DictionaryHandler:
    """Fast dictionary lookup service for CC-CEDICT"""
    
    def __init__(self, dict_path="../data/cc-cedict.txt"):
        self.simplified_index = {}  # Primary: simplified -> entry
        self.traditional_index = {}  # Secondary: traditional -> entry
        self._load_dictionary(dict_path)
        
        # Translation model variable
        self.translator = None
        self.tokenizer = None
        self.unload_timer = None
        
        self.loading_lock = False
        
    def _get_translator(self):
        """Eventlet-safe lazy loading"""
        if self.loading_lock:
            # Wait a tiny bit if already loading
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
            
        # Manage VRAM with Eventlet Timer
        if self.unload_timer:
            self.unload_timer.cancel()
        
        # Schedule offloading after 5 mins of inactivity
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
        # Use eventlet.tpool.execute to run the heavy C++ translation 
        # outside the main green loop. This prevents recursion/freezing.
        return eventlet.tpool.execute(self._do_inference, text)
    
    
    def _do_inference(self, text: str) -> str:
        """The actual logic being offloaded to the thread pool"""
        translator, tokenizer = self._get_translator()
        
        # 1️⃣ Tokenize the input
        source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(text, add_special_tokens=False))
        print(f"DEBUG - Input text: {text}")
        print(f"DEBUG - Source tokens: {source_tokens}")

        # 2️⃣ Translate using CTranslate2
        results = translator.translate_batch(
            [source_tokens],
            beam_size=1,
            max_decoding_length=12,
            length_penalty=0.6,
            repetition_penalty=2.5
        )

        # 3️⃣ Decode translation
        target_tokens = results[0].hypotheses[0]
        print(f"DEBUG - Target tokens: {target_tokens}")
        
        translation = tokenizer.decode(tokenizer.convert_tokens_to_ids(target_tokens), skip_special_tokens=True)
        print(f"DEBUG - Decoded translation: '{translation}'")

        # 4️⃣ Clean punctuation
        if '(' in translation:
            translation = translation.split('(')[0]
    
        # Split on periods/exclamations but keep commas and "and"
        translation = translation.split('.')[0].split('!')[0].split(';')[0]
        
        if ',' in translation:
            parts = translation.split(',')
            first_part = parts[0].strip()
            # If first part has 2+ words, it's probably complete
            if len(first_part.split()) >= 2:
                translation = first_part
    
        final = translation.strip(".。!！, ")
        return final
    
    # MORE AGGRESIVE REPETITION PENALTY IF OPUS-MT GET TOO VERBOSE
    # def _do_inference(self, text: str) -> str:
    #     """The actual logic being offloaded to the thread pool"""
    #     translator, tokenizer = self._get_translator()
        
    #     source_tokens = tokenizer.convert_ids_to_tokens(
    #         tokenizer.encode(text, add_special_tokens=False)
    #     )

    #     results = translator.translate_batch(
    #         [source_tokens],
    #         beam_size=1,
    #         max_decoding_length=8,   # Shorter to avoid repetition
    #         length_penalty=0.8,       # Favor slightly longer but not too long
    #         repetition_penalty=3.0    # Heavy penalty on repetition
    #     )

    #     target_tokens = results[0].hypotheses[0]
    #     translation = tokenizer.decode(
    #         tokenizer.convert_tokens_to_ids(target_tokens),
    #         skip_special_tokens=True
    #     )

    #     # Stop at first comma or parenthesis
    #     for delimiter in [',', '(', ';', '.', '!']:
    #         if delimiter in translation:
    #             translation = translation.split(delimiter)[0]
    #             break
        
    #     return translation.strip(".。!！, ")
    
    
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
        """Parse a single CC-CEDICT line"""
        try:
            bracket_start = line.find('[')
            bracket_end = line.find(']')
            if bracket_start == -1 or bracket_end == -1:
                return None
            
            # Parse components
            parts = line[:bracket_start].strip().split()
            if len(parts) < 2:
                return None
            
            traditional = parts[0]
            simplified = parts[1]
            pinyin = line[bracket_start+1:bracket_end].strip()
            
            # Parse definitions
            meanings_raw = line[bracket_end+1:].strip().strip('/')
            definitions = [m.strip() for m in meanings_raw.split('/') if m.strip()]
            
            return {
                "is_generated": False,
                "simplified": simplified,
                "traditional": traditional,
                "pinyin": pinyin,
                "definitions": definitions,
                "char_count": len(simplified),
                "message": "Phrase found in dictionary",
            }
        except Exception as e:
            return None
    
    def _index_entry(self, entry: Dict) -> None:
        """Index entry by both simplified and traditional"""
        simplified = entry["simplified"]
        traditional = entry["traditional"]
        
        # Index by simplified (primary)
        if simplified not in self.simplified_index:
            self.simplified_index[simplified] = entry
        
        # Index by traditional (secondary)
        if traditional != simplified and traditional not in self.traditional_index:
            self.traditional_index[traditional] = entry
    
    def lookup(self, chinese_word: str, prefer_longer: bool = True) -> Optional[Dict]:
        """
        Lookup a Chinese word with intelligent matching
        
        Args:
            chinese_word: The Chinese text to lookup
            prefer_longer: If True, try to match longer phrases first
        
        Returns:
            Dictionary entry with simplified, traditional, pinyin, definitions
        """
        if not self._is_chinese(chinese_word):
            return self._not_found(chinese_word)
        
        # Try exact match first
        result = self._exact_lookup(chinese_word)
        if result:
            return {
                "found": True,
                **result
            }
        
        if self._is_chinese(chinese_word):
            pinyin_list = pinyin(chinese_word, style=Style.TONE3)
            pinyin_str = " ".join([item[0] for item in pinyin_list])
            translation = self._translate_phrase(chinese_word)

            return {
                "found": True,
                "is_generated": True,
                "simplified": chinese_word,
                "traditional": chinese_word,
                "pinyin": pinyin_str,
                "definitions": [translation],
                "message": "Phrase not in dictionary; generated via OPUS-MT."
            }
        
        return self._not_found(chinese_word)
    
    def _exact_lookup(self, word: str) -> Optional[Dict]:
        """Exact dictionary lookup"""
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
            "message": "Term not found"
        }
  
    def _is_chinese(self, text: str) -> bool:
        """Check if the string contains at least one Chinese character"""
        return bool(re.search(r'[\u4e00-\u9fff]', text))

# Singleton instance
_dictionary_service = None

def get_dictionary_service() -> DictionaryHandler:
    """Get or create the singleton dictionary service"""
    global _dictionary_service
    if _dictionary_service is None:
        _dictionary_service = DictionaryHandler()
    return _dictionary_service