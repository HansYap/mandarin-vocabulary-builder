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
    # PUBLIC: Correct Sentence (NEW APPROACH)
    # -------------------------------------------------------
    def correct_sentence(self, broken_sentence):
        """
        NEW: Natural correction with smart highlighting.
        
        Returns: {
            "corrected": "自然的中文句子",
            "highlights": [
                {
                    "word": "中文词",
                    "meaning": "English meaning",
                    "why": "为什么值得学习",
                    "category": "new_vocab|measure_word|collocation|idiom"
                }
            ],
            "note": "整体评价（可选）"
        }
        """
        
        # Extract English words to hint to the LLM
        english_words = re.findall(r'[a-zA-Z]+', broken_sentence)
        english_hint = f"\n注意：用户用英文说了这些词：{', '.join(english_words)}" if english_words else ""
        
        # Build the new prompt
        prompt = f"""你是经验丰富的中文老师。学生（中级水平，HSK 3-4）说了：

"{broken_sentence}"{english_hint}

任务：
1. 改成母语者会说的自然句子
2. 标注值得学习的词汇（新词、搭配、量词、习语等）

规则：
- 不要逐字翻译！要说母语者真正会说的话
- 仔细理解句子结构和语境（注意一词多义、同形异义词）
- 习语、问候语要用地道表达（例如："hello people" → "大家好"，不是"你好人们"）
- 高亮所有值得注意的词汇：
  * 用户用英文说的词（说明他们不知道中文怎么说）
  * 中高级词汇（HSK 3+）
  * 量词、搭配、习语
  * 不要标注"我"、"的"、"是"这种最基础的词
- 量词如果用错，要标注正确的量词
- 如果句子已经很自然，corrected 可以跟原句相同

输出JSON（无其他文字）：
{{
  "corrected": "自然流畅的中文句子",
  "highlights": [
    {{
      "word": "高亮的中文词",
      "meaning": "英文含义",
      "why": "为什么值得学习（例如：常用搭配、正式用语、量词等）",
      "category": "new_vocab|collocation|measure_word|idiom"
    }}
  ],
  "note": "整体评价（可选，如果句子改动较大才写）"
}}

示例1 - 混合中英文：
输入: "我想book一个restaurant，你有recommendation吗？"
输出: {{
  "corrected": "我想预订一家餐厅，你有推荐的吗？",
  "highlights": [
    {{"word": "预订", "meaning": "to reserve/book", "why": "正式场合用词", "category": "new_vocab"}},
    {{"word": "一家餐厅", "meaning": "a restaurant", "why": "餐厅的量词是'家'", "category": "measure_word"}},
    {{"word": "推荐", "meaning": "recommend", "why": "常用动词", "category": "new_vocab"}}
  ],
  "note": ""
}}

示例2 - 语法/语序错误：
输入: "我昨天去了商店很多人"
输出: {{
  "corrected": "我昨天去了商店，人很多",
  "highlights": [
    {{"word": "人很多", "meaning": "very crowded (lit: people very many)", "why": "正确语序：主语+很+形容词", "category": "collocation"}}
  ],
  "note": "需要用逗号分隔两个信息"
}}

示例3 - 已经很自然：
输入: "我今天很累，想早点睡觉"
输出: {{
  "corrected": "我今天很累，想早点睡觉",
  "highlights": [],
  "note": "说得很自然！"
}}

示例4 - 纯英文（习语表达）：
输入: "hello people"
输出: {{
  "corrected": "大家好",
  "highlights": [
    {{"word": "大家好", "meaning": "hello everyone (idiomatic greeting)", "why": "习惯用语，比'你好人们'更自然", "category": "idiom"}}
  ],
  "note": ""
}}

示例5 - 纯英文（直接翻译）：
输入: "I want to learn Chinese"
输出: {{
  "corrected": "我想学中文",
  "highlights": [
    {{"word": "学", "meaning": "to learn/study", "why": "基础动词", "category": "new_vocab"}},
    {{"word": "中文", "meaning": "Chinese language", "why": "与'汉语'同义，更口语化", "category": "new_vocab"}}
  ],
  "note": ""
}}

示例6 - 纯英文（注意一词多义）：
输入: "I hit a bat with a bat"
输出: {{
  "corrected": "我用球棒打了一只蝙蝠",
  "highlights": [
    {{"word": "球棒", "meaning": "baseball bat (sports equipment)", "why": "运动器材", "category": "new_vocab"}},
    {{"word": "蝙蝠", "meaning": "bat (animal)", "why": "动物名称", "category": "new_vocab"}},
    {{"word": "用...打", "meaning": "to hit with (using...)", "why": "常用结构", "category": "collocation"}}
  ],
  "note": "注意：bat 有两个意思（球棒/蝙蝠）"
}}

现在处理：
"{broken_sentence}"

输出JSON："""

        try:
            # Unload chat model, load feedback model
            requests.post(self.ollama_url, json={"model": self.chat_model, "keep_alive": 0})
            print("→ Loading 3B Feedback Model...")
            
            response = self._call_ollama(self.feedback_model, prompt, 0.3, 0.9, 0)
            raw = self._safe_parse_response(response).strip()
            
            # Clean and parse JSON
            parsed = self._parse_json_or_fallback(raw)
            
            # Validate structure
            if not parsed.get('corrected'):
                parsed['corrected'] = broken_sentence
            if 'highlights' not in parsed:
                parsed['highlights'] = []
            if 'note' not in parsed:
                parsed['note'] = ''
            
            print(f"✅ Corrected: {parsed['corrected']}")
            print(f"📚 Highlights: {len(parsed['highlights'])} items")
            
            return parsed
            
        except Exception as e:
            print(f"[ERROR] Correction failed: {e}")
            return {
                "corrected": broken_sentence,
                "highlights": [],
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
                "highlights": [],
                "note": "解析错误"
            }
            
    def _call_ollama(self, model, prompt, temperature=0.2, top_p=0.9, keep_alive="5m"):
        """Unified caller to handle VRAM memory swap."""
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {
                "num_ctx": 2048,
                "temperature": temperature,
                "top_p": top_p,
            }
        }
        return requests.post(self.ollama_url, json=payload)