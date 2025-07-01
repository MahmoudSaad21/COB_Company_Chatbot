import os
import time
from dotenv import load_dotenv
from .main_agent import MainOrchestratorAgent
from .agents import ClinicalAgent, MarketingAgent, KnowledgeAgent
from .database.manager import DatabaseManager
from .knowledge_base.manager import KnowledgeBaseManager
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Dict
from .models.appointments import AppointmentRequest, MarketingMeetingRequest 

# Load environment variables from .env file
load_dotenv()

class COBCustomerCareSystem:
    def __init__(self, clinic_db_path: str = "clinic_appointments_2.db",
                 cob_db_path: str = "cob_system_2.db",
                 knowledge_base_path: str = "knowledge_base/"):
        # Get API key from environment
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=google_api_key,
            temperature=0.3
        )
        
        self.db_manager = DatabaseManager(clinic_db_path, cob_db_path)
        self.kb_manager = KnowledgeBaseManager(knowledge_base_path)
        
        self.orchestrator = MainOrchestratorAgent(
            self.llm, 
            self.db_manager,
            self.kb_manager
        )
        
        # Initialize sub-agents
        self.orchestrator.clinical_agent = ClinicalAgent(
            self.llm,
            self.db_manager,
            self.orchestrator
        )
        
        self.orchestrator.marketing_agent = MarketingAgent(
            self.llm,
            self.db_manager,
            self.orchestrator
        )
        
        self.orchestrator.knowledge_agent = KnowledgeAgent(
            self.llm,
            self.kb_manager,
            self.orchestrator
        )
        
        self.session_data = {}

    def process_message(self, user_input: str, session_id: str = "default") -> str:
        # Implementation of message processing
        pass

    def reset_session(self, session_id: str = "default"):
        if session_id in self.session_data:
            del self.session_data[session_id]

def run_demo():
    system = COBCustomerCareSystem(
        clinic_db_path="clinic_appointments_2.db",
        cob_db_path="cob_system_2.db",
        knowledge_base_path="knowledge_base/"
    )
    
    print("COB Customer Care AI System")
    print("=" * 50)
    print("Type 'exit' to quit or 'reset' to start new session\n")
    
    session_id = "demo_session"
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break
        if user_input.lower() == 'reset':
            system.reset_session(session_id)
            print("\nSession reset. New conversation started.\n")
            continue
            
        response = system.process_message(user_input, session_id)
        print(f"\nBot: {response}\n")
