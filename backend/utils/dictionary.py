import re
import os
from collections import defaultdict
from typing import List, Dict, Set

STOPWORDS = {
    "a", "an", "the", "to", "of", "in", "on", "for", "by", "with", "and",
    "or", "from", "as", "at", "is", "are", "be", "was", "were", "that",
    "this", "these", "those", "it", "its", "which", "also", "used", "use"
}

class Dictionary:
    def __init__(self, cedict_path: str = "data/cc-cedict.txt"):
        # maps english-term -> set(simplified-chinese)
        self.eng_to_cn: Dict[str, Set[str]] = defaultdict(set)
        self.cn_info: Dict[str, Dict] = {}  # simplified -> {traditional, pinyin, defs}
        self._load_cedict(cedict_path)

    def _parse_cedict_line(self, line: str):
        """
        Robust parse for lines that match:
          traditional simplified [pinyin] /def1/def2/...
        Returns (traditional, simplified, pinyin, list_of_definitions) or None
        """
        if not line or line.startswith("#"):
            return None

        m = re.match(r'^\s*(\S+)\s+(\S+)\s+\[(.+?)\]\s+/(.+)/\s*$', line)
        if m:
            traditional, simplified, pinyin, defs = m.groups()
            definitions = [d for d in defs.split('/') if d.strip()]
            return traditional, simplified, pinyin.strip(), definitions

        # tolerant fallback parse
        try:
            before_pinyin, after = line.split('[', 1)
            pinyin, defs_part = after.split(']', 1)
            chinese_forms = before_pinyin.strip().split()
            if len(chinese_forms) >= 2:
                traditional = chinese_forms[0]
                simplified = chinese_forms[1]
            else:
                traditional = chinese_forms[0]
                simplified = chinese_forms[0]
            definitions = [d for d in defs_part.strip().split('/') if d.strip()]
            return traditional, simplified, pinyin.strip(), definitions
        except Exception:
            return None

    def _split_def_into_phrases(self, definition: str) -> List[str]:
        """
        Turn a definition string into cleaned English phrase candidates.
        We split on common separators but avoid over-tokenizing.
        """
        # split on semicolon, comma, " or ", " and " etc.
        parts = re.split(r'\s*(?:;|,|\bor\b|\band\b|\bto\b|\b\/\b)\s*', definition)
        cleaned = []
        for p in parts:
            p = p.strip().lower()
            if not p:
                continue
            # remove any trailing parenthetical notes
            p = re.sub(r'\s*\(.*\)$', '', p).strip()
            if p:
                cleaned.append(p)
        return cleaned

    def _load_cedict(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    parsed = self._parse_cedict_line(line.strip())
                    if not parsed:
                        continue
                    traditional, simplified, pinyin, definitions = parsed

                    # store info for simplified form
                    if simplified not in self.cn_info:
                        self.cn_info[simplified] = {
                            "traditional": traditional,
                            "pinyin": pinyin,
                            "definitions": []
                        }

                    # Add all parsed definitions to cn_info for reference
                    for d in definitions:
                        # cc-cedict sometimes contains slashes inside defs; keep raw defs in list
                        if d not in self.cn_info[simplified]["definitions"]:
                            self.cn_info[simplified]["definitions"].append(d)

                    # Index English -> Chinese:
                    for d in definitions:
                        phrases = self._split_def_into_phrases(d)
                        for phrase in phrases:
                            # index the full phrase
                            self.eng_to_cn[phrase].add(simplified)

                            # if the phrase is exactly a single word (alphabetic), index it as a single-word token
                            words = re.findall(r"[a-zA-Z]+", phrase)
                            if len(words) == 1:
                                word = words[0].lower()
                                if len(word) > 2 and word not in STOPWORDS:
                                    self.eng_to_cn[word].add(simplified)

        except FileNotFoundError:
            print(f"Warning: CC-CEDICT file not found at {path}. Dictionary will be empty.")
        except Exception as ex:
            print(f"Error loading CC-CEDICT: {ex}")

    def lookup(self, english_word: str, max_results: int = 6) -> List[str]:
        """
        Lookup english_word and return a list of Chinese simplified words.
        Strategy:
          1. Exact normalized phrase match.
          2. Exact single-word match (if indexed).
          3. Whole-word match inside indexed keys (safe fuzzy).
        """
        if not english_word or not english_word.strip():
            return []

        q = english_word.strip().lower()

        results = []
        seen = set()

        # 1) exact phrase match
        if q in self.eng_to_cn:
            for cn in self.eng_to_cn[q]:
                if cn not in seen:
                    results.append(cn); seen.add(cn)
                    if len(results) >= max_results:
                        return results

        # 2) exact single-word match (we only indexed single words that were standalone defs)
        if re.fullmatch(r"[a-zA-Z]+", q) and q not in STOPWORDS:
            if q in self.eng_to_cn:
                for cn in self.eng_to_cn[q]:
                    if cn not in seen:
                        results.append(cn); seen.add(cn)
                        if len(results) >= max_results:
                            return results

        # 3) safe fuzzy: look for keys where the query appears as a whole word
        #    this will match "cold" -> "cold water" but avoid partial inside unrelated tokens
        pattern = re.compile(r'\b' + re.escape(q) + r'\b')
        for key in sorted(self.eng_to_cn.keys(), key=lambda s: (len(s.split()), len(s))):
            if pattern.search(key):
                for cn in self.eng_to_cn[key]:
                    if cn not in seen:
                        results.append(cn); seen.add(cn)
                        if len(results) >= max_results:
                            return results

        return results

    def get_info(self, simplified_word: str):
        """Return stored info about a Chinese simplified word (pinyin, definitions)."""
        return self.cn_info.get(simplified_word, None)






