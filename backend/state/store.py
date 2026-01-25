from backend.services.llm_handler import LLMHandler
from backend.services.feedback_gen import FeedbackGenerator

# Create singletons ONCE - shared across ALL modules
llm = LLMHandler()
feedback = FeedbackGenerator(llm)

# Shared state dictionaries (moved from store.py)
transcripts = {}
conversation_histories = {}
