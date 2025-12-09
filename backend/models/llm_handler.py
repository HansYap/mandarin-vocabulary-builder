import requests
import json
import re


class LLMHandler:
    def __init__(self):
        # Qwen 2.5 model (best Mandarin model available for Ollama)
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "qwen2.5:1.5b"

    # -------------------------------------------------------
    # PUBLIC: Get response from LLM
    # -------------------------------------------------------
    def get_response(self, user_message, conversation_history):
        try:
            # Build formatted conversation history
            context = self._build_context(conversation_history)

            # System prompt optimized for Qwen 2.5
            # (Qwen responds BEST to natural language + XML tags)
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
                    "temperature": 0.6,   # Qwen is already creative, keep lower
                    "top_p": 0.9,
                    "stream": False
                }
            )

            if response.status_code != 200:
                return "抱歉，我好像遇到一点问题，你可以再说一次吗？"

            # Parse Ollama response safely
            result_text = self._safe_parse_response(response).strip()

            # Ensure Chinese-only output
            if not self._looks_like_mandarin(result_text):
                result_text = "我再说一遍：" + result_text

            return result_text

        except Exception as e:
            print(f"LLM Error: {e}")
            return "系统好像连不上，你可以再试一次吗？"

    # -------------------------------------------------------
    # BUILD CONTEXT FOR PROMPT
    # -------------------------------------------------------
    def _build_context(self, history):
        """
        Converts conversation history into XML-tag structure.
        Qwen 2.5 performs best with <user> and <assistant> tags.
        """
        formatted = []
        for msg in history[-8:]:  # Qwen can handle slightly more context
            if msg["role"] == "user":
                formatted.append(f"<user>{msg['content']}</user>")
            else:
                formatted.append(f"<assistant>{msg['content']}</assistant>")

        return "\n".join(formatted)

    # -------------------------------------------------------
    # SAFELY PARSE OLLAMA RESPONSE
    # -------------------------------------------------------
    def _safe_parse_response(self, response):
        """
        Correctly handle Ollama stream=false and stream=true outputs.
        For stream=false: Ollama still returns multiple JSON lines.
        This function extracts ALL 'response' fields and joins them.
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
                print("Json decoding error")
                continue
            

        return "".join(final_chunks).replace("</assistant>", "")


    # -------------------------------------------------------
    # SIMPLE CHINESE DETECTION
    # -------------------------------------------------------
    def _looks_like_mandarin(self, text):
        """
        Basic check: does output contain Chinese characters?
        """
        return bool(re.search(r"[\u4e00-\u9fff]", text))
    
    # suggest mandarin words and phrases
    def _parse_json_or_fallback(self, text):
        """Try to parse JSON from model output, otherwise return raw text as fallback."""
        text = text.strip()
        # try to find JSON object in the output
        try:
            return json.loads(text)
        except Exception:
            # attempt to extract a JSON-looking substring
            m = re.search(r'(\{.*\})', text, flags=re.S)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    pass
            return {"raw": text}

    def suggest_phrase(self, english_phrase, sentence_context):
        """
        Ask Qwen for a concise JSON containing:
        { "word": "...", "translation": "...", "alternatives": [...], "example": "..." }
        """
        prompt = f"""
    You are a concise professional Chinese teacher. For the given English phrase and sentence context,
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

    Return the single JSON object.
    """

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


    def correct_sentence(self, broken_sentence, brief=True):
        """
        Ask Qwen to rewrite the full (possibly-mixed) sentence into natural Mandarin.
        Return a JSON object:
        { "corrected": "我只喜欢喝冰水。", "note": "minor word order" }  (note optional)
        """
        prompt = f"""
    You are a professional Chinese tutor. Rewrite the following user sentence into one concise, correct Mandarin sentence.
    Output a single JSON object ONLY with keys:
    - "corrected": the corrected Mandarin sentence (one sentence, concise),
    - "note": a one-line note (in Chinese) explaining the main fix (or "" if none).

    User sentence: "{broken_sentence}"

    Rules:
    - Output JSON only.
    - Keep corrected sentence short and natural.
    - Note should be 1 short phrase at most.
    """

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
    
# if __name__ == '__main__':
#     llm_tester = LLMHandler()

#     # Simulate history
#     history = [
#         {'role': 'user', 'content': '我今天很不开心。'},
#         {'role': 'assistant', 'content': '怎么了？发生什么事了？跟我说说吧。'}
#     ]

#     user_message = "I want to eat pizza." # Testing the English/Chinese mix rule
#     print(f"User Input: {user_message}")

#     print("\nGetting LLM Response...")
#     response = llm_tester.get_response(user_message, history)

#     print("--- LLM Response ---")
#     print(response)
#     print("--------------------")

    # The response should be in Chinese, possibly suggesting "比萨" or "披萨"
