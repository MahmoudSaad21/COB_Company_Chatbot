import os
import time
from dotenv import load_dotenv
from .main_agent import MainOrchestratorAgent
from .agents import ClinicalAgent, MarketingAgent, KnowledgeAgent
from .database.manager import DatabaseManager
from .knowledge_base.manager import KnowledgeBaseManager
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from typing import Dict
from .models.appointments import AppointmentRequest, MarketingMeetingRequest 

# Load environment variables from .env file
load_dotenv()

KNOWLEDGE_BASE_PATH = "knowledge_base/"

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
        """Process message with enhanced session management"""
        # Initialize session
        if session_id not in self.session_data:
            self.session_data[session_id] = {
                "history": [],
                "state": {},
                "failure_count": 0
            }

        session = self.session_data[session_id]

        # Store session ID in orchestrator
        self.orchestrator.current_session = session_id
        self.orchestrator.session_data = self.session_data

        # Handle confirmation responses FIRST
        if 'pending_confirmation' in self.orchestrator.session_data.get(session_id, {}):
            if user_input.lower().strip() in ['yes', 'y']:
                # Complete booking and clear state
                response = self._complete_booking(session_id)
                # FIXED: Clear from orchestrator.session_data
                if session_id in self.orchestrator.session_data:
                    self.orchestrator.session_data[session_id].pop('pending_confirmation', None)
                return response
            elif user_input.lower().strip() in ['no', 'n']:
                # FIXED: Clear from orchestrator.session_data
                if session_id in self.orchestrator.session_data:
                    self.orchestrator.session_data[session_id].pop('pending_confirmation', None)
                return "Let's make changes. What would you like to change?"

        # Process message
        response, escalated = self.orchestrator.process_message(
            user_input,
            session_id,
            session['state']
        )

        # Update session history
        session['history'].append({"user": user_input, "bot": response})

        # Handle escalation
        if escalated:
            session['state']['escalated'] = True
            session['failure_count'] = 0

        return response


    def _complete_booking(self, session_id: str) -> str:
        """Complete pending booking"""
        session_data = self.orchestrator.session_data.get(session_id, {})
        request_data = session_data.get('pending_confirmation')
        

        if not request_data:
            return "Error: No pending booking found."

        # Determine booking type based on the request data content
        if "clinical_request" in session_data:
            # Clinical appointment
            clinical_request = session_data.get('clinical_request', {})
            tool = self.orchestrator.clinical_agent.tools["appointment_booker"]
            result = tool._run(
                clinic_id=clinical_request['clinic_id'],
                doctor_name=clinical_request['doctor_name'],
                slot_datetime=f"{clinical_request['date']} {clinical_request['time']}",
                patient_name=clinical_request['customer_name'],
                contact_email=clinical_request['contact_email']
            )
        else:
            # Marketing meeting
            marketing_request = session_data.get('marketing_request', {})
            availability = self.orchestrator.marketing_agent.availability_tool._run(date=marketing_request['date'])
            try:
                import json
                slots = json.loads(availability)
                if slots and isinstance(slots, list):
                    # Find a slot that matches the requested time
                    matching_slot = None
                    request_time = marketing_request['time']
                    for slot in slots:
                        slot_time = slot['datetime'].split()[1][:8]  # Extract HH:MM
                        if slot_time == request_time:
                            matching_slot = slot
                            break

                    if matching_slot:
                        marketer_id = matching_slot['marketer_id']
                    else:
                        marketer_id = slots[0]['marketer_id']  # Use first available
                else:
                    marketer_id = 'marketer-0'  # Default fallback
            except:
                marketer_id = 'marketer-0'  # Default fallback
            tool = self.orchestrator.marketing_agent.booking_tool
            result = tool._run(
                marketer_id=marketer_id,
                slot_datetime=f"{marketing_request['date']} {marketing_request['time']}",
                customer_name=marketing_request['customer_name'],
                contact_email=marketing_request['contact_email']
            )

        return result if "Successfully" in result else f"Booking failed: {result}"

    def reset_session(self, session_id: str = "default"):
        """Reset session data"""
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
