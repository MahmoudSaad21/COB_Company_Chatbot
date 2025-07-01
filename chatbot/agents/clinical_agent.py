from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from ..database.manager import DatabaseManager
from ..main_agent import MainOrchestratorAgent
from ..models.appointments import AppointmentRequest
from ..tools.clinic_tools import (  # ADD THIS IMPORT
    ClinicAvailabilityTool, 
    AppointmentBookingTool,
    ClinicInfoTool,
    DoctorAvailabilityTool
)
from ..tools.knowledge_tools import KnowledgeRetrievalTool 
from ..knowledge_base.manager import KnowledgeBaseManager 
from typing import Dict
import json
from datetime import datetime
from dataclasses import asdict

KNOWLEDGE_BASE_PATH = "knowledge_base/"

class ClinicalAgent:
    def __init__(self, llm: ChatGoogleGenerativeAI, db_manager: DatabaseManager, orchestrator: MainOrchestratorAgent):
        self.llm = llm
        self.db_manager = db_manager
        self.orchestrator = orchestrator
        self.max_attempts = 3
        
        # Initialize all clinical tools
        self.tools = {
            "availability_checker": ClinicAvailabilityTool(db_manager=db_manager),
            "appointment_booker": AppointmentBookingTool(db_manager=db_manager),
            "clinic_info": ClinicInfoTool(db_manager=db_manager),
            "doctor_availability": DoctorAvailabilityTool(db_manager=db_manager),
            "knowledge_retriever": KnowledgeRetrievalTool(kb_manager=KnowledgeBaseManager(KNOWLEDGE_BASE_PATH))
        }
        
        # Tool selection prompt template
        self.tool_selection_prompt = """
        You are a clinical assistant. Based on the conversation context and user input, select the most appropriate tool from the following options:

        Available Tools:
        1. availability_checker - Check available appointment slots (use when user asks about availability)
        2. appointment_booker - Book an appointment (use when user provides all booking details)
        3. clinic_info - Get information about clinics and doctors (use when user asks "list clinics" or "what doctors are available")
        4. doctor_availability - Check available times for specific doctors (use when user asks about a specific doctor's availability)
        5. knowledge_retriever - Retrieve general knowledge (use for other informational questions)

        Conversation Context:
        {context}

        User Input: "{input}"

        Respond ONLY with the tool name in JSON format: {{"tool": "tool_name"}}
        """

    def handle_request(self, user_input: str, session_id: str, session_state: Dict) -> str:
        """Handle clinical requests with unified parameter extraction"""
        session_data = self.orchestrator.session_data.setdefault(session_id, {})
        request_data = session_data.get('clinical_request', {})
        request = AppointmentRequest(**request_data)
        
        # Get conversation context
        context_str = self.orchestrator.get_conversation_context()
        
        # Check for pending confirmation first
        if 'pending_confirmation' in session_data:
            if user_input.lower() in ['yes', 'y']:
                return self._complete_booking(request, session_data)
            elif user_input.lower() in ['no', 'n']:
                session_data.pop('pending_confirmation', None)
                return "Let's make changes. What would you like to change?"
        
        # Extract all clinical parameters from user input
        extracted_params = self._extract_clinical_parameters(user_input)
        
        # Update request with extracted parameters
        for key, value in extracted_params.items():
            if value is not None:  # Only update if not null
                setattr(request, key, value)
        
        # Save updated request
        session_data['clinical_request'] = asdict(request)
        
        # Select tool using LLM
        selected_tool = self._select_tool(user_input, context_str)
        print(selected_tool)
        # Handle tool-specific logic with extracted parameters
        if selected_tool == "availability_checker":
            return self._handle_availability(request, session_data)
        elif selected_tool == "appointment_booker":
            return self._handle_booking(request, session_data)
        elif selected_tool == "clinic_info":
            return self.tools["clinic_info"]._run()
        elif selected_tool == "doctor_availability":
            return self.tools["doctor_availability"]._run(
                doctor_name=request.doctor_name,
                specialty=request.specialty,
                date=request.date
            )
        elif selected_tool == "knowledge_retriever":
            return self.tools["knowledge_retriever"]._run(user_input)
        else:
            return "I'm not sure how to handle that request. Could you please rephrase?"


    def _extract_clinical_parameters(self, user_input: str) -> dict:
        """Extract all possible clinical parameters from user input"""

        # Build context from properly ordered history
        context_str = self.orchestrator.get_conversation_context()

        prompt = f"""
        Conversation Context:
        {context_str}

        Current User Input: "{user_input}"

        Extract ALL possible values for:
        - customer_name
        - contact_email
        - date (YYYY-MM-DD format)
        - time (HH:MM:SS format)
        - specialty
        - doctor_name (without title)
        - start_time (for time ranges)
        - end_time (for time ranges)

        Return JSON with extracted values. Use null for missing fields.
        """
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            cleaned = re.sub(r"^```(?:json)?|```$", "", response.content.strip(), flags=re.IGNORECASE).strip()
            return json.loads(cleaned)
        except:
            return {}


    def _select_tool(self, user_input: str, context: str) -> str:
        """Use LLM to select the appropriate tool"""
        prompt = self.tool_selection_prompt.format(
            context=context,
            input=user_input
        )
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            cleaned = re.sub(r"^```(?:json)?|```$", "", response.content.strip(), flags=re.IGNORECASE).strip()
            result = json.loads(cleaned)
            return result.get("tool", "")
        except:
            return ""


    def _handle_availability(self, request: AppointmentRequest, session_data: Dict) -> str:
        """Handle availability requests using pre-extracted parameters"""
        # Check if we have date
        if not request.date:
            return "Please specify a date to check availability."
        
        # Get availability using extracted parameters
        return self._check_availability(request, session_data)


    def _check_availability(self, request: AppointmentRequest, session_data: Dict) -> str:
        """Check availability and provide alternatives if needed"""
        # Get availability for requested time/range
        availability = self.tools["availability_checker"]._run(
            date=request.date,
            specialty=request.specialty,
            doctor_name=request.doctor_name,
            start_time=request.start_time,
            end_time=request.end_time
        )
        
        try:
            slots = json.loads(availability)
            if isinstance(slots, list) and slots:
                # If specific time was requested, look for exact match
                if request.time:
                    for slot in slots:
                        slot_time = slot['datetime'].split()[1][:8]  # Extract HH:MM:SS
                        if slot_time == request.time:
                            # Store for potential booking
                            request.clinic_id = slot['clinic_id']
                            request.doctor_id = slot['doctor_id']
                            session_data['clinical_request'] = asdict(request)
                            
                            return (
                                f"Slot available! Dr. {slot['doctor']} at {slot_time} in {slot['clinic']}.\n"
                                "Would you like to book this appointment? (yes/no)"
                            )
                    
                    # If exact time not found, get alternative times
                    return self._get_alternative_times(request)
                
                # If no specific time requested - just return all available slots
                return self._format_availability_response(request, slots)
        except:
            pass
        
        # If we get here, either no slots or error
        return availability

    def _get_alternative_times(self, request: AppointmentRequest) -> str:
        """Find and format alternative time suggestions"""
        # Get alternative slots around the requested time
        alternative_slots = self.db_manager.get_available_slots_around_time(
            request.date,
            request.time,
            specialty=request.specialty,
            doctor_name=request.doctor_name
        )
        
        if alternative_slots:
            # Format response with alternatives
            response = [f"Sorry, {request.time} is not available. Here are nearby options:"]
            for slot in alternative_slots:
                dt = slot["datetime"]
                time_str = dt.strftime("%I:%M %p")
                response.append(f"- Dr. {slot['doctor_name']} at {time_str} in {slot['clinic_name']}")
            return "\n".join(response)
        else:
            # Try to find any available slots for that day
            any_slots = self.db_manager.get_available_clinic_slots(
                date=request.date,
                specialty=request.specialty,
                doctor_name=request.doctor_name
            )
            
            if any_slots:
                response = [f"No slots near {request.time}, but here are other available times:"]
                for slot in any_slots:
                    slot_time = slot[3].split()[1][:5]  # HH:MM
                    response.append(f"- Dr. {slot[1]} at {slot_time} in {slot[0]}")
                return "\n".join(response)
            else:
                return f"No available appointments found for Dr. {request.doctor_name} on {request.date}."


    def _format_availability_response(self, request: AppointmentRequest, all_slots: list) -> str:
        """Format availability response with alternative suggestions"""
        # If time range was requested, just return the slots in range
        if request.start_time or request.end_time:
            response = ["Available slots in your requested range:"]
            for slot in all_slots:
                slot_time = slot['datetime'].split()[1][:5]  # HH:MM
                response.append(f"- Dr. {slot['doctor']} at {slot_time} in {slot['clinic']}")
            return "\n".join(response)
        
        # If specific time was requested but not available, find alternatives
        if request.time:
            return self._get_alternative_times(request, all_slots)
        
        # No specific time requested - just return all available slots
        response = [f"Available slots on {request.date}:"]
        for slot in all_slots:
            slot_time = slot['datetime'].split()[1][:5]  # HH:MM
            response.append(f"- Dr. {slot['doctor']} at {slot_time} in {slot['clinic']}")
        return "\n".join(response)

    def _get_alternative_times(self, request: AppointmentRequest, all_slots: list) -> str:
        """Find and format alternative time suggestions"""
        # Convert to datetime objects
        target_dt = datetime.strptime(f"{request.date} {request.time}", "%Y-%m-%d %H:%M:%S")
        slot_objs = []
        for slot in all_slots:
            slot_dt = datetime.strptime(slot['datetime'], "%Y-%m-%d %H:%M:%S")
            slot_objs.append({
                "datetime": slot_dt,
                "clinic": slot['clinic'],
                "doctor": slot['doctor'],
                "difference": abs((slot_dt - target_dt).total_seconds())
            })
        
        # Sort by time proximity to requested time
        slot_objs.sort(key=lambda x: x["difference"])
        
        # Get closest alternatives (2 before, 2 after)
        before = [s for s in slot_objs if s["datetime"] < target_dt]
        after = [s for s in slot_objs if s["datetime"] > target_dt]
        
        alternatives = before[-2:] + after[:2]  # 2 closest before + 2 closest after
        
        # Format response
        response = [f"Sorry, {request.time} is not available. Here are nearby options:"]
        for alt in alternatives:
            time_str = alt["datetime"].strftime("%I:%M %p")
            response.append(f"- Dr. {alt['doctor']} at {time_str} in {alt['clinic']}")
        
        response.append("\nPlease choose a time or say 'book <time>' to select one.")
        return "\n".join(response)

    def _handle_booking(self, request: AppointmentRequest, session_data: Dict) -> str:
        """Handle booking using pre-extracted parameters"""
        # Check if we have enough information to book
        if request.customer_name and request.contact_email and request.date and request.time:
            # Get clinic/doctor details from availability
            availability = self.tools["availability_checker"]._run(
                date=request.date,
                specialty=request.specialty,
                doctor_name=request.doctor_name,
                start_time=request.start_time,
                end_time=request.end_time
            )
            
            try:
                slots = json.loads(availability)
                if isinstance(slots, list) and slots:
                    for slot in slots:
                        slot_time = slot['datetime'].split()[1][:8]
                        if slot_time == request.time:
                            request.clinic_id = slot['clinic_id']
                            request.doctor_id = slot['doctor_id']
                            break
            except:
                pass
            
            # Confirm before booking
            session_data['pending_confirmation'] = True
            return (
                f"Please confirm your appointment:\n"
                f"Name: {request.customer_name}\n"
                f"Email: {request.contact_email}\n"
                f"Date: {request.date}\n"
                f"Time: {request.time}\n"
                f"Doctor: {request.doctor_name or 'Any available'}\n\n"
                "Reply 'YES' to confirm or 'NO' to make changes."
            )
        
        return self._request_missing_info(request)

    def _complete_booking(self, request: AppointmentRequest, session_data: Dict) -> str:
        """Complete the booking process with alternative suggestions"""
        if not all([request.doctor_name, request.date, request.time]):
            return "Missing information for booking. Please start over."
        
        # Format datetime for booking
        slot_datetime = f"{request.date} {request.time}"
        
        # First try to book the exact time
        result = self.tools["appointment_booker"]._run(
            clinic_id=request.clinic_id or "",
            doctor_name=request.doctor_name,
            slot_datetime=slot_datetime,
            patient_name=request.customer_name,
            contact_email=request.contact_email
        )
        
        # If booking succeeded, clear session
        if "Successfully" in result:
            session_data.pop('clinical_request', None)
            session_data.pop('pending_confirmation', None)
            return result
        
        # If booking failed, get alternative times
        alternative_slots = self.db_manager.get_available_slots_around_time(
            request.date,
            request.time,
            specialty=request.specialty,
            doctor_name=request.doctor_name
        )
        
        if alternative_slots:
            # Format alternatives
            response = ["Sorry, that time is not available. Here are nearby options:"]
            for slot in alternative_slots:
                dt = slot["datetime"]
                time_str = dt.strftime("%I:%M %p")
                response.append(f"- Dr. {slot['doctor_name']} at {time_str} in {slot['clinic_name']}")
            
            # Store alternatives in session for next booking attempt
            session_data['alternative_slots'] = alternative_slots
            return "\n".join(response)
        
        # If no alternatives, return error
        return "Booking failed and no alternative times available. Please try another time."


    def _request_missing_info(self, request: AppointmentRequest) -> str:
        """Generate prompt for missing booking information"""
        missing = []
        if not request.customer_name: missing.append("your name")
        if not request.contact_email: missing.append("your email")
        if not request.date: missing.append("a date")
        if not request.time: missing.append("a time")
        
        return f"I need more information to book your appointment. Please provide: {', '.join(missing)}."
