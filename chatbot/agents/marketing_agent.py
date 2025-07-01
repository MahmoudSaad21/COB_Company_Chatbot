from langchain_google_genai import ChatGoogleGenerativeAI
from ..database.manager import DatabaseManager
from ..main_agent import MainOrchestratorAgent
from ..models.appointments import MarketingMeetingRequest
from ..tools.marketing_tools import MarketingAvailabilityTool, MarketingMeetingBookingTool
from typing import Dict, Tuple, Optional

class MarketingAgent:

    def __init__(self, llm: ChatGoogleGenerativeAI, db_manager: DatabaseManager, orchestrator: MainOrchestratorAgent):
        self.llm = llm
        self.db_manager = db_manager
        self.availability_tool = MarketingAvailabilityTool(db_manager=db_manager)
        self.booking_tool = MarketingMeetingBookingTool(db_manager=db_manager)
        self.orchestrator = orchestrator
        self.max_attempts = 3

    def handle_request(self, user_input: str, session_id: str, session_state: Dict) -> str:
        """Handle marketing requests with persistent session data"""
        # Get or create session data
        session_data = self.orchestrator.session_data.setdefault(session_id, {})
        request_data = session_data.get('marketing_request', {})
        request = MarketingMeetingRequest(**request_data)

        # Build context from properly ordered history
        context_str = self.orchestrator.get_conversation_context()

        # Extract time range if mentioned
        if "between" in user_input or "from" in user_input or "after" in user_input:
            start_time, end_time = self.extract_time_range(user_input)
            if start_time or end_time:
                # Update request with time range
                request.start_time = start_time
                request.end_time = end_time
                session_data['marketing_request'] = asdict(request)

            # Handle availability queries
            if "available" in user_input.lower() and request.date:
                # Use time range if provided
                availability = self.availability_tool._run(
                    date=request.date,
                    marketer_name=request.marketer_name,
                    start_time=request.start_time,
                    end_time=request.end_time
                )

                # Store updated request in session
                session_data['marketing_request'] = asdict(request)

                # Format availability results for better readability
                try:
                    slots = json.loads(availability)
                    if isinstance(slots, list):
                        slot_list = "\n".join([f"- {slot['marketer']} at {slot['datetime']}" for slot in slots])
                        return f"Available slots:\n{slot_list}"
                except:
                    pass
                return availability

        # Create prompt with context
        prompt = f"""
        Conversation Context:
        {context_str}

        Current User Input: "{user_input}"

        Extract ALL possible values for Marketing appointment:
        - customer_name
        - contact_email
        - date: string (in **ISO format**, i.e., YYYY-MM-DD, for example: "2025-07-01")
        - time (HH:MM:SS format)
        - product_interest

        ❗ Important Date Format Instructions:
        - Users might write dates like "1/7/2025", "July 1", or "01-07-2025".
        - Always assume **DD/MM/YYYY** if slashes or dashes are used.
        - Normalize all dates to the ISO standard format: **YYYY-MM-DD**, with **July 1st, 2025 → 2025-07-01**.
        - Do not return dates like "2025-01-07" for "1/7/2025" — that would be incorrect.

        Return JSON with extracted values. Use null for missing fields.
        """

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            cleaned_response = re.sub(r"^```(?:json)?|```$", "", response.content.strip(), flags=re.IGNORECASE).strip()
            extracted = json.loads(cleaned_response)
        except:
            extracted = {}

        # Update only fields with new values
        for key, value in extracted.items():
            if value is not None:  # Only update if not null
                setattr(request, key, value)

        # Save updated request to session
        session_data['marketing_request'] = asdict(request)
        self.orchestrator.session_data[session_id] = session_data

        # Check for completion
        if self.is_request_complete(request):
            return self.confirm_and_book(request, session_data)

        # Ask for missing information
        return self.request_missing_info(request)

    def extract_time_range(self, user_input: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract time range from user input using LLM"""
        prompt = f"""
        Extract time range information from the user input. Convert to 24-hour format (HH:MM).
        Handle both AM/PM formats and time ranges.

        Examples:
        - "between 2pm and 5pm" → ("14:00", "17:00")
        - "from 10am to 12pm" → ("10:00", "12:00")
        - "after 3:30 pm" → ("15:30", None)
        - "1 pm to 5 pm" → ("13:00", "17:00")

        User Input: "{user_input}"

        Return JSON format: {{"start_time": "HH:MM", "end_time": "HH:MM"}}
        """

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            # Handle different JSON formats
            cleaned_response = re.sub(r"^```(?:json)?|```$", "", response.content.strip(), flags=re.IGNORECASE).strip()

            # Handle case where LLM returns just a JSON object
            if cleaned_response.startswith('{'):
                result = json.loads(cleaned_response)
            # Handle case where LLM returns a code block with JSON
            else:
                result = json.loads(cleaned_response)

            return result.get("start_time"), result.get("end_time")
        except json.JSONDecodeError:
            print(f"JSON decode error in time extraction: {cleaned_response}")
            return None, None
        except Exception as e:
            print(f"Time extraction error: {e}")
            return None, None


    def is_request_complete(self, request: MarketingMeetingRequest) -> bool:
        """Check if all required fields are filled"""
        return all([
            request.customer_name,
            request.contact_email,
            request.date,
            request.time
        ])

    def confirm_and_book(self, request: MarketingMeetingRequest, session_data: Dict) -> str:
        """Confirm details and complete booking with alternative times"""
        # Check availability
        availability = self.availability_tool._run(
            date=request.date,
            start_time=request.start_time,
            end_time=request.end_time
        )

        if "No available" in availability:
            return f"No available marketing meetings on {request.date}. Please choose another date."

        try:
            # Parse availability to find matching slot
            slots = json.loads(availability)
            matching_slot = None
            for slot in slots:
                slot_time = slot['datetime'].split()[1][:8]  # Extract HH:MM:SS
                if slot_time == request.time:
                    matching_slot = slot
                    break

            if not matching_slot:
                # Get alternative times
                alternatives = self.db_manager.get_available_marketing_slots_around_time(
                    request.date,
                    request.time,
                    marketer_name=request.marketer_name
                )
                
                if alternatives:
                    # Format alternatives
                    alt_list = []
                    for alt in alternatives:
                        dt = alt["datetime"]
                        formatted_dt = dt.strftime("%I:%M %p")
                        alt_list.append(f"- {alt['marketer']} at {formatted_dt}")
                    
                    return (
                        f"Sorry, {request.time} is not available. Here are nearby options:\n" +
                        "\n".join(alt_list) + 
                        "\n\nPlease choose one by replying with the time (e.g., '09:30 AM')"
                    )
                else:
                    return f"No available times near {request.time}. Please choose another time."
            
            # Store slot details for booking
            request.marketer_id = matching_slot['marketer_id']
        except:
            return "Error processing availability. Please try again."

        # Format confirmation
        confirmation = (
            f"Please confirm your marketing meeting:\n"
            f"Name: {request.customer_name}\n"
            f"Email: {request.contact_email}\n"
            f"Date: {request.date} at {request.time}\n"
            f"Product Interest: {request.product_interest or 'General'}\n"
            f"Marketer: {matching_slot['marketer']}\n\n"
            "Reply 'YES' to confirm or 'NO' to make changes."
        )

        # Store in session for confirmation handling
        session_data['pending_confirmation'] = asdict(request)
        return confirmation

    def request_missing_info(self, request: MarketingMeetingRequest) -> str:
        """Generate prompt for missing information"""
        missing = []
        if not request.customer_name: missing.append("your name")
        if not request.contact_email: missing.append("your email")
        if not request.date: missing.append("a date")
        if not request.time: missing.append("a time")

        prompt = f"""
        I need more information to schedule your marketing meeting.
        Please provide: {', '.join(missing)}.

        You've already provided:
        {self._format_provided_info(request)}

        Ask for ONE piece of information at a time.
        """

        response = self.llm.invoke([HumanMessage(content=prompt)])
        return response.content

    def _format_provided_info(self, request: MarketingMeetingRequest) -> str:
        """Format provided information for context"""
        provided = []
        if request.customer_name: provided.append(f"Name: {request.customer_name}")
        if request.contact_email: provided.append(f"Email: {request.contact_email}")
        if request.date: provided.append(f"Date: {request.date}")
        if request.time: provided.append(f"Time: {request.time}")
        if request.product_interest: provided.append(f"Interest: {request.product_interest}")
        return "\n".join(provided) if provided else "Nothing yet"
