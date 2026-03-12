import logging

logger = logging.getLogger(__name__)

class PolicyRAG:
    """
    Superlinked integration for hotel policies (pets, check-in times, etc.)
    For demo purposes, this mocks the Superlinked REST API interface.
    """
    def __init__(self):
        self.kb = [
            "Check-in time is 3:00 PM and check-out time is 11:00 AM.",
            "Pets are allowed for an additional fee of $50 per stay.",
            "Breakfast is served from 7:00 AM to 10:00 AM in the lobby.",
            "Cancellations must be made 24 hours in advance for a full refund."
        ]
        
    def query(self, question: str) -> str:
        """
        Mock similarity search using Superlinked.
        """
        logger.info(f"Querying Superlinked RAG for: {question}")
        question_lower = question.lower()
        if "pet" in question_lower or "dog" in question_lower or "cat" in question_lower:
            return self.kb[1]
        elif "breakfast" in question_lower or "food" in question_lower:
            return self.kb[2]
        elif "cancel" in question_lower or "refund" in question_lower:
            return self.kb[3]
        elif "time" in question_lower or "check-in" in question_lower or "check-out" in question_lower:
            return self.kb[0]
        return "I'm sorry, I don't have information on that policy."

# Singleton instance
rag = PolicyRAG()
