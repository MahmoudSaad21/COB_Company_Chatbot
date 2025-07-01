import json
import re
import time
from collections import deque
from uuid import uuid4
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from .database.manager import DatabaseManager
from .knowledge_base.manager import KnowledgeBaseManager
from typing import Dict, Tuple, Deque

MAX_HISTORY = 5

# Agent Classes
class MainOrchestratorAgent:
    """Main agent that routes conversations to appropriate sub-agents"""

    def __init__(self, llm: ChatGoogleGenerativeAI, db_manager: DatabaseManager, kb_manager: KnowledgeBaseManager):
        self.llm = llm
        self.db_manager = db_manager
        self.kb_manager = kb_manager

        # Unified conversation history with chronological ordering
        self.conversation_history = deque(maxlen=MAX_HISTORY * 4)  # Increased capacity
        self.session_data = {}  # Central session storage

        # Initialize sub-agents
        self.knowledge_agent = None
        self.marketing_agent = None
        self.clinical_agent = None

        # Failure counts per session
        self.failure_counts = {}
    def add_to_history(self, role: str, content: str):
        """Add message to conversation history with timestamp"""
        self.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

    def get_conversation_context(self) -> str:
        """Get properly ordered conversation context"""
        # Sort by timestamp to ensure chronological order
        sorted_history = sorted(self.conversation_history, key=lambda x: x['timestamp'])
        return "\n".join(f"{msg['role']}: {msg['content']}" for msg in sorted_history)



        # Failure counts per session
        self.failure_counts = {}

    def classify_intent(self, user_input: str, session_id: str) -> str:
        """Enhanced intent classification using conversation context"""
        # Create context from last 3 messages
        context_str = self.get_conversation_context()

        # FIXED: Check for pending confirmation BEFORE classification
        session_data = self.session_data.get(session_id, {})
        if 'pending_confirmation' in session_data:
            if user_input.lower().strip() in ['yes', 'y', 'no', 'n']:
                return "CONFIRMATION"

        # Check for escalation triggers
        if self._requires_escalation(user_input, session_id):
            return "ESCALATE"
        classification_prompt = f"""
        Analyze the conversation context and current user input to classify intent:

        Conversation Context:
        {context_str}

        Current User Input: "{user_input}"

        Classify into one of:
        1. KNOWLEDGE - Questions about products, services, company info
        2. MARKETING - Marketing meeting requests
        3. CLINICAL - Medical appointment requests
        4. GENERAL - General conversation

        Also consider:
        - Ongoing conversations (e.g., if we're in the middle of booking)
        - User's explicit requests

        Respond in JSON format: {{"intent": "...", "requires_escalation": boolean}}
        """
        try:
            response = self.llm.invoke([HumanMessage(content=classification_prompt)])
            cleaned_response = re.sub(r"^```(?:json)?|```$", "", response.content.strip(), flags=re.IGNORECASE).strip()
            result = json.loads(cleaned_response)
            intent = result.get("intent", "GENERAL").upper()
            print(intent)

            # Track failures for escalation
            if intent == "GENERAL" and "?" in user_input:
                self.failure_counts[session_id] = self.failure_counts.get(session_id, 0) + 1

            return intent
        except:
            return "GENERAL"


    def _requires_escalation(self, user_input: str, session_id: str) -> bool:
        """Determine if conversation requires human escalation"""
        # Check explicit requests
        if any(phrase in user_input.lower() for phrase in ["human", "agent", "representative", "talk to person"]):
            return True

        # Check frustration indicators
        if any(word in user_input.lower() for word in ["frustrated", "angry", "annoyed", "not helping", "useless"]):
            return True

        # Check repeated failures
        if self.failure_counts.get(session_id, 0) >= 3:
            return True

        return False

    def process_message(self, user_input: str, session_id: str, session_state: Dict) -> Tuple[str, bool]:
        """Process message with enhanced routing and context"""
        # Add user input to history
        self.add_to_history("user", user_input)

        # Classify intent with conversation context
        intent = self.classify_intent(user_input, session_id)

        # FIXED: Handle confirmation responses
        if intent == "CONFIRMATION":
            return "Confirmation response received.", False

        # Handle escalation
        if intent == "ESCALATE":
            response = self.handle_escalation(session_id)
            self.add_to_history("assistant", response)
            return response, True

        # Route to appropriate agent and get response
        if intent == "KNOWLEDGE":
            response = self.knowledge_agent.handle_query(user_input)
        elif intent == "MARKETING":
            response = self.marketing_agent.handle_request(user_input, session_id, session_state)
        elif intent == "CLINICAL":
            response = self.clinical_agent.handle_request(user_input, session_id, session_state)
        else:  # GENERAL
            response = self.handle_general_conversation(user_input)

        # Add response to history
        self.add_to_history("assistant", response)
        return response, False

    def handle_escalation(self, session_id: str) -> str:
        """Handle escalation to human agent"""
        # Reset failure count
        self.failure_counts[session_id] = 0

        # Create support ticket
        ticket_id = f"TKT-{str(uuid4())[:8].upper()}"

        # Format conversation history
        history = "\n".join(
            f"{msg['role'].capitalize()}: {msg['content']}"
            for msg in self.conversation_history
        )

        # Save to database
        self.db_manager.save_escalation_ticket(ticket_id, session_id, history)

        return (
            "I'm transferring you to a human agent who can better assist you. "
            f"Your support ticket ID is {ticket_id}. "
            "An agent will contact you shortly. Is there anything else I can help with in the meantime?"
        )

    def handle_general_conversation(self, user_input: str) -> str:
        """Handle general conversation with improved UX"""
        prompt = f"""
        You're a customer service assistant for COB Company. Respond to:
        "{user_input}"

        Guidelines:
        - Be friendly and professional
        - Keep responses concise (1-2 sentences)
        - Offer help with: products, marketing meetings, clinical appointments
        - If unclear, ask clarifying questions
        """
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content
