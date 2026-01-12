from pydantic import BaseModel, Field
from typing import List, Optional

# This maps 1:1 to a "Vocab Card" component in your UI
class VocabCard(BaseModel):
    original_text: str = Field(..., description="The English phrase the user said")
    mandarin_text: str = Field(..., description="The correct Mandarin translation")
    pinyin: str = Field(..., description="Pinyin with tone marks, e.g., 'nǐ hǎo'")
    example_sentence: str = Field(..., description="A short, natural sentence using the word")
    difficulty_level: str = Field("HSK1", description="Estimated HSK level")
    type: str = Field("word", description="'word' or 'phrase'")
    source: str = Field("llm", description="'dictionary' or 'llm'")
    context_note: str = Field("", description="Note about contextual usage if word appears in corrections")

# This maps 1:1 to a "Correction Bubble" component
class SentenceCorrection(BaseModel):
    original_sentence: str
    corrected_sentence: str
    explanation: str = Field(..., description="Very brief explanation of the fix")
    note: str = Field("", description="Additional note from LLM")
    highlight_ranges: List[List[int]] = Field(default_factory=list, description="Indices [start, end] of changed words for UI highlighting")

# The full JSON response your API will return
class SessionFeedback(BaseModel):
    vocabulary: List[VocabCard] = Field(default_factory=list)
    corrections: List[SentenceCorrection] = Field(default_factory=list)
    summary: str