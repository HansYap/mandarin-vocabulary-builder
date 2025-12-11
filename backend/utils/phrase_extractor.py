import re

class PhraseExtractor:
    """
    Extracts English words and multi-word phrases using simple NP/VB patterns.
    Lightweight alternative to spaCy (no large models).
    """

    # Match English words
    WORD_RE = re.compile(r"[A-Za-z]+(?:-[A-Za-z]+)?")

    # Match common multi-word phrases (adj+noun, verb+noun, noun+noun, phrasal verbs)
    PHRASE_RE = re.compile(
        r"""
        (?:
            [A-Za-z]+(?:-[A-Za-z]+)?\s+[A-Za-z]+(?:-[A-Za-z]+)?   # two-word phrase
        )
        """,
        re.VERBOSE
    )

    @staticmethod
    def extract_phrases(text):
        """
        Returns:
            list of unique English tokens and phrases.
        """
        phrases = []

        # Extract multi-word sequences first
        for match in PhraseExtractor.PHRASE_RE.finditer(text):
            phrase = match.group().lower().strip()
            phrases.append(phrase)

        # Extract single English words
        for match in PhraseExtractor.WORD_RE.finditer(text):
            word = match.group().lower().strip()
            phrases.append(word)

        # Remove duplicates while keeping order
        final = []
        for p in phrases:
            if p not in final:
                final.append(p)

        return final

