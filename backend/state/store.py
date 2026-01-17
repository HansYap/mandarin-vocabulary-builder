from backend.services.llm_handler import LLMHandler
from backend.services.feedback_gen import FeedbackGenerator

# Create singletons ONCE - shared across ALL modules
llm = LLMHandler()
feedback = FeedbackGenerator(llm)

# Shared state dictionaries (moved from store.py)
partial_transcripts = {}
transcripts = {}
conversation_histories = {}

print(f"✅ Shared instances created:")
print(f"   LLM Instance ID: {id(llm)}")
print(f"   Feedback Instance ID: {id(feedback)}")