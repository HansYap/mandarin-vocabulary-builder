import requests
import json
import re
import os


class LLMHandler:
    def __init__(self, dict_path="../data/cc-cedict.txt"):
        # 1. Load Dictionary (Fast & Deterministic)
        # Path is relative to backend/models/ directory
        self.dictionary = self._load_cedict(dict_path)
        
        # 2. LLM Config
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen2.5:1.5b"

    # -------------------------------------------------------
    # DICTIONARY LOADING (From Version 1)
    # -------------------------------------------------------
    def _load_cedict(self, path):
        # Resolve path relative to this file's location
        current_dir = os.path.dirname(os.path.abspath(__file__))
        full_path = os.path.join(current_dir, path)
        
        if not os.path.exists(full_path):
            print(f"Warning: Dictionary file {full_path} not found. Running in LLM-only mode.")
            return {}
            
        print("Loading Dictionary... (takes ~1s)")
        cedict = {}
        with open(full_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Skip comments (lines starting with #) and empty lines
                if line.startswith('#') or line.startswith('%') or not line.strip(): 
                    continue
                
                # Line format: Traditional Simplified [pin1 yin1] /meaning1/meaning2/
                # Example: 你好 你好 [ni3 hao3] /hello/hi/how are you/
                try:
                    # Find the bracket positions first
                    bracket_start = line.find('[')
                    bracket_end = line.find(']')
                    
                    if bracket_start == -1 or bracket_end == -1:
                        continue
                    
                    # Extract parts before brackets (Traditional and Simplified)
                    before_bracket = line[:bracket_start].strip().split()
                    if len(before_bracket) < 2:
                        continue
                    
                    traditional = before_bracket[0]
                    simplified = before_bracket[1]
                    
                    # Extract Pinyin (between brackets)
                    pinyin = line[bracket_start+1:bracket_end].strip()
                    
                    # Extract English meanings (after bracket, between /)
                    after_bracket = line[bracket_end+1:].strip()
                    if not after_bracket.startswith('/'):
                        continue
                    
                    meanings_raw = after_bracket.strip('/')
                    meanings = [m.strip() for m in meanings_raw.split('/') if m.strip()]
                    
                    # Map English words/phrases to Chinese info
                    for m in meanings:
                        clean_key = m.lower().strip()
                        # Only save if not already there (keep most common/first entry)
                        if clean_key and clean_key not in cedict:
                            cedict[clean_key] = {
                                "word": clean_key,
                                "translation": simplified,
                                "pinyin": pinyin,
                                "alternatives": [traditional] if traditional != simplified else [],
                                "example": ""
                            }
                except Exception as e:
                    # Silently skip malformed lines
                    continue
        
        print(f"Dictionary loaded: {len(cedict)} entries.")
        return cedict

    # -------------------------------------------------------
    # PUBLIC: Get Response (From Version 2 - Better Prompts)
    # -------------------------------------------------------
    def get_response(self, user_message, conversation_history):
        try:
            # Build formatted conversation history
            context = self._build_context(conversation_history)

            # System prompt optimized for Qwen 2.5 (Version 2)
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

            # Final formatted prompt for Qwen
            prompt = (
                f"{system_prompt}\n"
                f"<conversation>\n"
                f"{context}\n"
                f"<user>{user_message}</user>\n"
                f"<assistant>"
            )

            # Call Ollama
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": 0.6,   # Version 2's setting
                    "top_p": 0.9,
                    "stream": False
                }
            )

            if response.status_code != 200:
                return "抱歉，我好像遇到一点问题，你可以再说一次吗？"

            # Parse Ollama response safely (Version 2)
            result_text = self._safe_parse_response(response).strip()

            # Ensure Chinese-only output
            if not self._looks_like_mandarin(result_text):
                result_text = "我再说一遍：" + result_text

            return result_text

        except Exception as e:
            print(f"LLM Error: {e}")
            return "系统好像连不上，你可以再试一次吗？"

    # -------------------------------------------------------
    # PUBLIC: Suggest Phrase (Hybrid: Dictionary First, Then LLM)
    # -------------------------------------------------------
    def suggest_phrase(self, english_phrase, sentence_context):
        """
        HYBRID APPROACH:
        1. Check Dictionary (Instant, 100% Correct)
        2. If not found, ask LLM (Slower, Creative)
        """
        clean_phrase = english_phrase.lower().strip()
        
        # --- PATH A: Dictionary (Fast & Deterministic) ---
        if clean_phrase in self.dictionary:
            result = self.dictionary[clean_phrase].copy()
            result["source"] = "dictionary"
            
            # Print dictionary lookup info
            print(f"[DICT] '{english_phrase}' → {result['translation']} [{result['pinyin']}]")
            
            # Dictionary doesn't have examples, but we can keep it simple
            # or optionally ask LLM just for an example (commented out for speed)
            return result

        # --- PATH B: LLM Fallback (Creative, handles slang/context) ---
        print(f"[LLM] '{english_phrase}' not in dictionary, using LLM...")
        return self._suggest_phrase_llm(english_phrase, sentence_context)

    def _suggest_phrase_llm(self, english_phrase, sentence_context):
        """
        Use Version 2's improved prompt for LLM suggestions.
        """
        prompt = f"""You are a concise professional Chinese teacher. For the given English phrase and sentence context,
output a single JSON object ONLY (no extra text). The JSON keys must be exactly:
- "word": the original english phrase,
- "translation": a short, natural Mandarin word/phrase (max 4 chars if single word),
- "alternatives": an array of up to 2 simpler/colloquial alternatives (can be empty []),
- "example": one short example sentence (MAX 12 Chinese characters preferred) showing usage.

User sentence: "{sentence_context}"
English phrase: "{english_phrase}"

Rules:
- Output JSON only, no explanation or extra text.
- Keep fields short and natural.
- Prefer modern, commonly used Mandarin (avoid archaic words).
- If you cannot confidently translate, put empty strings or [].

Return the single JSON object."""

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
        parsed = self._parse_json_or_fallback(raw)
        parsed["source"] = "llm"
        return parsed

    # -------------------------------------------------------
    # PUBLIC: Correct Sentence (New from Version 2)
    # -------------------------------------------------------
    def correct_sentence(self, broken_sentence):
        """
        Ask Qwen to rewrite the full sentence into natural Mandarin.
        Return a JSON object:
        { "corrected": "我只喜欢喝冰水。", "note": "minor word order" }
        """
        prompt = f"""You are a professional Chinese tutor. Rewrite the following user sentence into one concise, correct Mandarin sentence.
Output a single JSON object ONLY with keys:
- "corrected": the corrected Mandarin sentence (one sentence, concise),
- "note": a one-line note (in Chinese) explaining the main fix (or "" if none).

User sentence: "{broken_sentence}"

Rules:
- Output JSON only.
- Keep corrected sentence short and natural.
- Note should be 1 short phrase at most."""

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
        parsed = self._parse_json_or_fallback(raw)
        return parsed

    # -------------------------------------------------------
    # HELPERS (Improved from Version 2)
    # -------------------------------------------------------
    def _build_context(self, history):
        """
        Converts conversation history into XML-tag structure.
        Qwen 2.5 performs best with <user> and <assistant> tags.
        """
        formatted = []
        for msg in history[-8:]:  # Keep last 8 messages
            if msg["role"] == "user":
                formatted.append(f"<user>{msg['content']}</user>")
            else:
                formatted.append(f"<assistant>{msg['content']}</assistant>")
        return "\n".join(formatted)

    def _safe_parse_response(self, response):
        """
        Correctly handle Ollama's NDJSON output format.
        Extracts ALL 'response' fields and joins them.
        """
        text = response.text.strip()
        final_chunks = []

        # Iterate line by line because Ollama returns NDJSON style
        for line in text.split("\n"):
            try:
                obj = json.loads(line)
                if "response" in obj:
                    final_chunks.append(obj["response"])
            except json.JSONDecodeError:
                continue

        return "".join(final_chunks).replace("</assistant>", "")

    def _looks_like_mandarin(self, text):
        """
        Basic check: does output contain Chinese characters?
        """
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    def _parse_json_or_fallback(self, text):
        """
        Try to parse JSON from model output, with fallback.
        """
        text = text.strip()
        # Clean up Markdown code blocks if LLM adds them
        text = text.replace("```json", "").replace("```", "")
        
        try:
            return json.loads(text)
        except:
            # Attempt to extract a JSON-looking substring
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
            # Ultimate Fallback
            return {
                "word": "Error",
                "translation": "",
                "alternatives": [],
                "example": text
            }