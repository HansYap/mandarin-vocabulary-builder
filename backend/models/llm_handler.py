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
        self.chat_model = "qwen2.5:1.5b"
        self.feedback_model = "qwen2.5:3b"

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

            response = self._call_ollama(self.chat_model, prompt, 0.9, 0.9, keep_alive="5m")

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
    # PUBLIC: Correct Sentence
    # -------------------------------------------------------
    def correct_sentence(self, broken_sentence):
        """
        Returns: { "corrected": "...", "mappings": [{"english": "...", "chinese": "..."}], "note": "..." }
        """
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', broken_sentence))
    
        if has_chinese:
        # Mixed sentence - need detailed mappings
            prompt = f"""你是专业中文老师。
            任务：把学生的混合句子改成自然的中文，并标注哪些英文词被替换了。

            严格规则：
            1. 把所有英文词替换成对应的中文词
            2. **只替换英文词，保持原有中文不变**
            3. 同音异义：如果同一个英文词出现多次但意思不同（例如 "book" 作为动词"预订"和名词"书"），必须用不同的中文词
            4. 完整词汇：mappings 必须是完整的词，不要只映射语气助词（例如 "people" → "人们"，不是 "们"）
            5. mappings 里的中文词必须在 corrected 句子中真实存在
            6. 只输出 JSON 格式

            示例：
            输入: "我想要book一间房，因为我想读一本book"
            输出: {{
                "corrected": "我想要预订一间房，因为我想读一本书",
                "mappings": [
                    {{"english": "book", "chinese": "预订"}},
                    {{"english": "book", "chinese": "书"}}
                ],
                "note": "第一个 book 是动词（预订），第二个是名词（书）"
            }}

            现在处理：
            "{broken_sentence}"

            输出（只输出JSON）："""

        else:
            # Pure English - just translate, no mappings needed
            prompt = f"""你是专业中文老师。
            任务：把学生的英文句子翻译成自然的中文（HSK 2-4 水平）。

            规则：
            1. 翻译成母语者会说的自然表达
            2. 不要逐字翻译
            3. 保持原意
            4. 只输出 JSON 格式
            5. **不需要 mappings 字段**（因为是整句翻译）

            示例：
            输入: "hello people"
            输出: {{"corrected": "大家好", "note": ""}}

            输入: "how are you"
            输出: {{"corrected": "你好吗", "note": ""}}

            输入: "I want to book a room"
            输出: {{"corrected": "我想订一间房", "note": ""}}

            现在处理：
            "{broken_sentence}"

            输出（只输出JSON）："""

        try:
            requests.post(self.ollama_url, json={"model": self.chat_model, "keep_alive": 0})
            print("1.5B Unloaded. Loading 3B Feedback Model...")
            
            response = self._call_ollama(self.feedback_model, prompt, 0.25, 0.9, 0)

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
        """Modified for non-streaming JSON mode"""
        try:
            # Since stream=False, the entire body is one JSON object
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            print(f"Parsing error: {e}")
            return ""

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
            
    def _call_ollama(self, model, prompt, temperature=0.2, top_p=0.9, keep_alive="5m"):
        """Unified caller to handle VRAM memory swap."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            #"format": "json",
            "keep_alive": keep_alive, # How long it stays in GPU
            "options": {
                "num_ctx": 2048,      # IMPORTANT: Limits RAM usage to ~500MB
                "temperature": temperature,
                "top_p": top_p,
            }
        }
        return requests.post(self.ollama_url, json=payload)
            
