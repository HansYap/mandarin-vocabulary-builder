import requests
import json
import re
import os


class LLMHandler:
    def __init__(self, dict_path="../data/cc-cedict.txt"):
        # 1. Load Dictionary (Fast & Deterministic)
        self.dictionary = self._load_cedict(dict_path)
        
        # 2. LLM Config
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen2.5:1.5b"

    # -------------------------------------------------------
    # DICTIONARY LOADING
    # -------------------------------------------------------
    def _load_cedict(self, path):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(current_dir, path)
        
        if not os.path.exists(full_path):
            print(f"Warning: Dictionary file {full_path} not found. Running in LLM-only mode.")
            return {}
            
        print("Loading Dictionary... (takes ~1s)")
        cedict = {}
        with open(full_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or line.startswith('%') or not line.strip(): 
                    continue
                
                try:
                    bracket_start = line.find('[')
                    bracket_end = line.find(']')
                    if bracket_start == -1 or bracket_end == -1: 
                        continue
                    
                    parts = line[:bracket_start].strip().split()
                    if len(parts) < 2: 
                        continue
                    
                    traditional = parts[0]
                    simplified = parts[1]
                    pinyin = line[bracket_start+1:bracket_end].strip()
                    
                    meanings_raw = line[bracket_end+1:].strip().strip('/')
                    meanings = [m.strip() for m in meanings_raw.split('/') if m.strip()]
                    
                    entry = {
                        "simplified": simplified,
                        "traditional": traditional,
                        "pinyin": pinyin,
                        "definitions": meanings
                    }

                    # Index by simplified Chinese (primary key)
                    if simplified not in cedict:
                        cedict[simplified] = entry
                    
                    # Also index by traditional (for lookup flexibility)
                    if traditional != simplified and traditional not in cedict:
                        cedict[traditional] = entry

                except Exception:
                    continue
        
        print(f"Dictionary loaded: {len(cedict)} entries.")
        return cedict

    # -------------------------------------------------------
    # PUBLIC: Get Response (Conversation)
    # -------------------------------------------------------
    def get_response(self, user_message, conversation_history):
        try:
            context = self._build_context(conversation_history)

            system_prompt = (
                "<system>"
                "你是一位温柔、友善的中文会话老师。"
                "你要使用非常自然的中文（类似日常对话，HSK2-4 的难度）。"
                "你的任务是帮助使用者练习中文口语。\n"
                "规则：\n"
                "1. 永远只用中文回答。\n"
                "2. 如果用户的中文不自然，你的回答中给出自然、正确的表达，但不要直接指出错误。\n"
                "3. 如果用户混合英文，你可以自然地给出中文对应词。\n"
                "4. 每次回复保持简短但自然，并提出一个简单的追问。\n"
                "5. 不要解释语法，除非用户明确要求。\n"
                "</system>"
            )

            prompt = (
                f"{system_prompt}\n"
                f"<conversation>\n"
                f"{context}\n"
                f"<user>{user_message}</user>\n"
                f"<assistant>"
            )

            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": 0.6,
                    "top_p": 0.9,
                    "stream": False
                }
            )

            if response.status_code != 200:
                return "抱歉，我好像遇到一点问题，你可以再说一次吗？"

            result_text = self._safe_parse_response(response).strip()

            if not self._looks_like_mandarin(result_text):
                result_text = "我再说一遍：" + result_text

            return result_text

        except Exception as e:
            print(f"LLM Error: {e}")
            return "系统好像连不上，你可以再试一次吗？"

    # -------------------------------------------------------
    # PUBLIC: Suggest Phrase (FIXED VERSION)
    # -------------------------------------------------------
    def suggest_phrase(self, english_phrase, original_sentence, corrected_sentence):
        """
        IMPROVED PIPELINE (Context-First Approach):
        1. Use the ALREADY corrected sentence (from feedback_gen.py)
        2. Extract which Chinese word corresponds to the English phrase
        3. Look up that Chinese word in dictionary for accurate pinyin/definitions
        4. Fallback to LLM-only if dictionary lookup fails
        
        Args:
            english_phrase: The English word to translate (e.g., "book")
            original_sentence: The mixed sentence (e.g., "我想book一间房")
            corrected_sentence: The fully Chinese sentence (e.g., "我想预订一间房")
        """
        print(f"\n{'='*60}")
        print(f"[VOCAB] Analyzing '{english_phrase}'")
        print(f"[VOCAB] Original: '{original_sentence}'")
        print(f"[VOCAB] Corrected: '{corrected_sentence}'")
        print(f"{'='*60}")

        # Step 1: Identify which Chinese word replaced the English phrase
        chinese_term = self._extract_chinese_equivalent(
            english_phrase, 
            original_sentence, 
            corrected_sentence
        )
        
        if not chinese_term:
            print(f"[WARN] Could not identify Chinese equivalent for '{english_phrase}'")
            return self._generate_llm_only_fallback(english_phrase, corrected_sentence)
        
        print(f"[EXTRACTED] '{english_phrase}' → '{chinese_term}'")
        
        # Step 2: Dictionary lookup for pinyin and definitions
        dict_entry = self.dictionary.get(chinese_term)
        
        if dict_entry:
            print(f"[DICT] ✅ Found '{chinese_term}' in dictionary")
            return self._format_dictionary_entry(
                english_phrase, 
                dict_entry, 
                corrected_sentence,
                source="hybrid"
            )
        
        # Step 3: Fallback - use LLM translation but note it's less reliable
        print(f"[FALLBACK] '{chinese_term}' not in dictionary, using LLM-only")
        return {
            "word": english_phrase,
            "translation": chinese_term,
            "pinyin": "(推测发音)",
            "alternatives": "",
            "example": f"在这句话中: {corrected_sentence}",
            "chinese_term": chinese_term,
            "source": "llm_fallback"
        }

    def _extract_chinese_equivalent(self, english_word, original_sentence, corrected_sentence):
        """
        Identifies which Chinese word in the corrected sentence corresponds 
        to the English word in the original sentence.
        
        Strategy: 
        1. Find position of English word in original
        2. Find what changed NEAR that position (the "local diff")
        3. The new Chinese characters near that position are the translation
        """
        # Find position of English word in original
        eng_pos = original_sentence.lower().find(english_word.lower())
        if eng_pos == -1:
            print(f"[WARN] English word '{english_word}' not found in original sentence")
            return self._extract_via_llm(english_word, corrected_sentence)
        
        eng_end = eng_pos + len(english_word)
        
        print(f"[EXTRACT] English word '{english_word}' at position {eng_pos}-{eng_end}")
        
        # Get Chinese characters before the English word
        prefix = original_sentence[:eng_pos]
        chinese_chars_before = sum(1 for c in prefix if '\u4e00' <= c <= '\u9fff')
        
        # Get Chinese characters after the English word (for range calculation)
        suffix = original_sentence[eng_end:]
        chinese_chars_after = sum(1 for c in suffix if '\u4e00' <= c <= '\u9fff')
        
        print(f"[EXTRACT] Chinese chars: {chinese_chars_before} before, {chinese_chars_after} after")
        
        # Strategy 1: Find the "local diff" - what's new NEAR the English word position?
        original_chars = [c for c in original_sentence if '\u4e00' <= c <= '\u9fff']
        corrected_chars = [c for c in corrected_sentence if '\u4e00' <= c <= '\u9fff']
        
        print(f"[EXTRACT] Original Chinese: {original_chars}")
        print(f"[EXTRACT] Corrected Chinese: {corrected_chars}")
        
        # Calculate expected position range in corrected sentence
        # (The translation should appear around where the English word was)
        expected_start = max(0, chinese_chars_before - 1)  # Allow 1 char before
        expected_end = min(len(corrected_chars), chinese_chars_before + 4)  # Allow up to 4 chars
        
        print(f"[EXTRACT] Expected translation position: {expected_start}-{expected_end}")
        
        # Find new characters in that range
        new_chars_in_range = []
        used_original_indices = set()
        
        for i in range(expected_start, expected_end):
            if i >= len(corrected_chars):
                break
                
            corrected_char = corrected_chars[i]
            
            # Check if this char existed in original at roughly the same position
            found_in_original = False
            search_range = range(max(0, i - 2), min(len(original_chars), i + 3))
            
            for j in search_range:
                if j in used_original_indices:
                    continue
                if j < len(original_chars) and corrected_char == original_chars[j]:
                    used_original_indices.add(j)
                    found_in_original = True
                    break
            
            if not found_in_original:
                new_chars_in_range.append(corrected_char)
        
        print(f"[EXTRACT] New characters in range: {new_chars_in_range}")
        
        # Build candidate from new characters in range
        if new_chars_in_range:
            candidate = ''.join(new_chars_in_range)
            print(f"[EXTRACT] Local diff candidate: '{candidate}'")
            
            # Verify it exists in corrected sentence
            if candidate in corrected_sentence:
                # Strategy: Try different substrings, PRIORITIZING LONGER MATCHES
                # This handles cases like "柴来点" where we want "火柴" not just "柴"
                
                best_match = None
                best_length = 0
                
                # First, try to find matches in the corrected sentence near this position
                # Look for 2-4 character words that include our candidate chars
                for window_size in [4, 3, 2]:
                    for i in range(len(corrected_chars) - window_size + 1):
                        window = ''.join(corrected_chars[i:i+window_size])
                        
                        # Count how many of our new chars are in this window
                        chars_in_window = sum(1 for c in new_chars_in_range if c in window)
                        coverage = chars_in_window / len(new_chars_in_range)
                        
                        # Require at least 70% coverage (for 3 chars, need at least 2)
                        # AND the window must be in dictionary
                        if coverage >= 0.7 and window in self.dictionary:
                            # Prefer longer matches with better coverage
                            score = len(window) * coverage
                            if score > best_length:
                                best_match = window
                                best_length = score
                                print(f"[EXTRACT] Found candidate: '{window}' (size={len(window)}, coverage={coverage:.1%}, score={score:.1f})")
                
                if best_match:
                    print(f"[EXTRACT] ✅ Best match from context: '{best_match}'")
                    return best_match
                
                # Fallback: Try substrings of the candidate itself
                # But still prioritize longer matches
                for length in range(len(candidate), 0, -1):  # Longest to shortest
                    for start_pos in range(len(candidate) - length + 1):
                        substring = candidate[start_pos:start_pos + length]
                        if substring in self.dictionary:
                            # Additional check: prefer 2+ char words over single chars
                            if len(substring) >= 2 or best_length == 0:
                                print(f"[EXTRACT] ✅ Found substring in dict: '{substring}' (from '{candidate}')")
                                return substring
                
                # If no dictionary match found, return the full candidate if reasonable length
                if 1 <= len(candidate) <= 3:
                    print(f"[EXTRACT] ⚠️  Not in dict but reasonable: '{candidate}'")
                    return candidate
        
        # Strategy 2: Position-based lookup with dictionary validation
        print(f"[EXTRACT] Trying position-based lookup at {chinese_chars_before}")
        
        if 0 <= chinese_chars_before < len(corrected_chars):
            # Try multi-character words first (prefer dictionary matches)
            for length in [3, 2, 1]:
                if chinese_chars_before + length <= len(corrected_chars):
                    candidate = ''.join(corrected_chars[chinese_chars_before:chinese_chars_before + length])
                    if candidate in self.dictionary:
                        print(f"[EXTRACT] ✅ Position-based match in dict: '{candidate}'")
                        return candidate
            
            # Single character fallback
            candidate = corrected_chars[chinese_chars_before]
            if candidate in self.dictionary:
                print(f"[EXTRACT] ✅ Single char in dict: '{candidate}'")
                return candidate
            else:
                print(f"[EXTRACT] ⚠️  Single char not in dict: '{candidate}'")
                return candidate
        
        # Strategy 3: Ask LLM
        print("[EXTRACT] All heuristics failed, asking LLM...")
        return self._extract_via_llm(english_word, corrected_sentence)

    def _extract_via_llm(self, english_word, corrected_sentence):
        """
        Ask LLM directly: "Which Chinese word in this sentence means [english_word]?"
        This is more reliable than position heuristics for complex cases.
        """
        print(f"[LLM-EXTRACT] Asking LLM to identify '{english_word}' in '{corrected_sentence}'")
        
        prompt = f"""Task: Identify the Chinese word that means "{english_word}"

Chinese Sentence: {corrected_sentence}
English Word: {english_word}

Output ONLY the base Chinese word (without grammar particles like 了/的/吗).
Examples:
- If asked for "book" in "我想预订一间房", output: 预订
- If asked for "book" in "我想读一本书", output: 书
- If asked for "fine" in "因为违停被罚款了", output: 罚款 (not 罚款了)"""

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": 0.1,
                    "stream": False
                }
            )
            
            raw = self._safe_parse_response(response).strip()
            # Extract only Chinese characters
            cleaned = re.sub(r'[^\u4e00-\u9fff]', '', raw)
            
            # Sanity check: should be 1-4 characters typically
            if cleaned and 1 <= len(cleaned) <= 5:
                # Remove common grammar particles if present
                grammar_particles = ['了', '的', '吗', '呢', '啊', '吧']
                for particle in grammar_particles:
                    if cleaned.endswith(particle) and len(cleaned) > 1:
                        cleaned_without = cleaned[:-1]
                        # Check if the version without particle is in dictionary
                        if cleaned_without in self.dictionary:
                            print(f"[LLM-EXTRACT] ✅ Removed particle '{particle}': '{cleaned_without}'")
                            return cleaned_without
                
                print(f"[LLM-EXTRACT] ✅ Identified: '{cleaned}'")
                return cleaned
            
            print(f"[LLM-EXTRACT] ❌ Invalid result: '{raw}'")
            return None
            
        except Exception as e:
            print(f"[LLM-EXTRACT] ❌ Error: {e}")
            return None

    def _format_dictionary_entry(self, original_word, dict_entry, context_sentence, source):
        """
        Formats a dictionary entry into the expected VocabCard structure.
        """
        definitions = dict_entry.get('definitions', [])
        definition_text = " / ".join(definitions[:3])  # Limit to top 3 definitions
        
        return {
            "word": original_word,
            "translation": dict_entry['simplified'],
            "pinyin": dict_entry['pinyin'],
            "alternatives": dict_entry.get('traditional', dict_entry['simplified']),
            "example": f"释义: {definition_text}\n例句: {context_sentence}",
            "chinese_term": dict_entry['simplified'],
            "source": source
        }

    def _generate_llm_only_fallback(self, english_word, context):
        """
        Pure LLM fallback when all else fails.
        Used for slang, proper nouns, or when extraction fails.
        """
        print(f"[FALLBACK] Generating pure LLM explanation for '{english_word}'")
        
        prompt = f"""Translate this word into Chinese based on the context:

Context: {context}
Word: {english_word}

Output format (JSON only):
{{"chinese": "中文翻译", "pinyin": "pin yin", "note": "simple explanation"}}"""

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": 0.2,
                    "stream": False
                }
            )
            
            raw = self._safe_parse_response(response).strip()
            result = self._parse_json_or_fallback(raw)
            
            return {
                "word": english_word,
                "translation": result.get("chinese", english_word),
                "pinyin": result.get("pinyin", "(未知)"),
                "alternatives": "",
                "example": result.get("note", "LLM生成的翻译"),
                "chinese_term": result.get("chinese", english_word),
                "source": "llm_fallback"
            }
            
        except Exception as e:
            print(f"[FALLBACK] ❌ Error: {e}")
            return {
                "word": english_word,
                "translation": english_word,
                "pinyin": "(错误)",
                "alternatives": "",
                "example": "无法翻译此词",
                "chinese_term": english_word,
                "source": "error"
            }

    # -------------------------------------------------------
    # PUBLIC: Correct Sentence
    # -------------------------------------------------------
    def correct_sentence(self, broken_sentence):
        """
        Ask Qwen to rewrite the sentence into natural Mandarin.
        Returns: { "corrected": "...", "note": "..." }
        """
        prompt = f"""You are a professional Chinese tutor. Rewrite this sentence into natural Mandarin.

CRITICAL RULES:
1. Understand context to choose correct translation for ambiguous words
2. Keep measure words (一根/一本/一个) - they indicate object type  
3. Translate compound phrases as complete units
4. Output ONLY JSON: {{"corrected": "...", "note": "..."}}

EXAMPLES OF CONTEXT-DEPENDENT TRANSLATION:
Input: "我需要一根 match 点火"
Output: {{"corrected": "我需要一根火柴点火", "note": ""}}
Why: 一根 + 点火 → stick for lighting → 火柴 (matchstick)

Input: "昨晚的 match 太精彩了"
Output: {{"corrected": "昨晚的比赛太精彩了", "note": ""}}
Why: 昨晚 + 精彩 → sports event → 比赛 (match/game)

Input: "他在 chemical plant 工作"
Output: {{"corrected": "他在化工厂工作", "note": ""}}
Why: compound phrase "chemical plant" = 化工厂 (complete unit)

Input: "我是周杰伦的忠实 fan"
Output: {{"corrected": "我是周杰伦的忠实粉丝", "note": ""}}
Why: person's fan → 粉丝

Input: "房间太热，打开 fan"
Output: {{"corrected": "房间太热，打开风扇", "note": ""}}
Why: cooling device → 风扇 (electric fan)

NOW CORRECT (use context clues):
"{broken_sentence}"

Output (JSON only):"""

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "stream": False
                }
            )

            raw = self._safe_parse_response(response).strip()
            
            # More aggressive cleaning for JSON output
            # Remove all whitespace/newlines that might break JSON
            raw = ' '.join(raw.split())
            
            parsed = self._parse_json_or_fallback(raw)
            
            # Additional validation: ensure we got actual content, not JSON structure
            if isinstance(parsed.get('corrected'), str):
                # Check if the correction contains JSON artifacts
                corrected = parsed['corrected']
                if '{' in corrected or '"corrected"' in corrected:
                    print(f"[WARN] Detected JSON in correction, extracting...")
                    # Try to extract just the corrected sentence
                    # Pattern: look for Chinese content between quotes
                    match = re.search(r'[""]([^"""]+)[""]', corrected)
                    if match:
                        corrected = match.group(1)
                        parsed['corrected'] = corrected
                        print(f"[WARN] Extracted: '{corrected}'")
            
            return parsed
            
        except Exception as e:
            print(f"[ERROR] Correction failed: {e}")
            return {
                "corrected": broken_sentence,
                "note": f"Error: {str(e)}"
            }

    # -------------------------------------------------------
    # HELPERS
    # -------------------------------------------------------
    def _build_context(self, history):
        """Converts conversation history into XML-tag structure."""
        formatted = []
        for msg in history[-8:]:
            if msg["role"] == "user":
                formatted.append(f"<user>{msg['content']}</user>")
            else:
                formatted.append(f"<assistant>{msg['content']}</assistant>")
        return "\n".join(formatted)

    def _safe_parse_response(self, response):
        """Handles Ollama's NDJSON output format."""
        text = response.text.strip()
        final_chunks = []

        for line in text.split("\n"):
            try:
                obj = json.loads(line)
                if "response" in obj:
                    final_chunks.append(obj["response"])
            except json.JSONDecodeError:
                continue

        return "".join(final_chunks).replace("</assistant>", "")

    def _looks_like_mandarin(self, text):
        """Check if output contains Chinese characters."""
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    def _parse_json_or_fallback(self, text):
        """Try to parse JSON from model output, with fallback."""
        text = text.strip()
        text = text.replace("```json", "").replace("```", "")
        
        try:
            return json.loads(text)
        except:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
            return {
                "corrected": text,
                "note": "解析错误"
            }