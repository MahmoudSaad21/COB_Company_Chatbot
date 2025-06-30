from langchain.tools import BaseTool
from pydantic import Field
from ..database.manager import DatabaseManager
from typing import Optional

class MarketingAvailabilityTool(BaseTool):
    name: str = "marketing_availability_checker"  # Fixed name
    description: str = "Check available marketing meeting slots by date or marketer name"  # Fixed description
    db_manager: DatabaseManager = Field(...)

    def _run(self, date: str = None, marketer_name: str = None,
             start_time: str = None, end_time: str = None) -> str:
        try:
            if not date:
                return "Please specify a date to check availability."

            # Get slots with time range filtering
            results = self.db_manager.get_available_marketing_slots(
                date, marketer_name, start_time, end_time
            )
            if not results:
                time_range = ""
                if start_time and end_time:
                    time_range = f" between {start_time} and {end_time}"
                elif start_time:
                    time_range = f" after {start_time}"
                elif end_time:
                    time_range = f" before {end_time}"

                return f"No available marketing meeting slots found on {date}{time_range}."

            formatted_results = []
            for row in results:
                marketer_name, slot_datetime, marketer_id = row
                formatted_results.append({
                    "marketer": marketer_name,
                    "datetime": slot_datetime,
                    "marketer_id": marketer_id
                })

            return json.dumps(formatted_results, indent=2)

        except Exception as e:
            return f"Error checking marketing availability: {str(e)}"
        

class MarketingMeetingBookingTool(BaseTool):
    name: str = "marketing_meeting_booker"
    description: str = "Book a marketing meeting with specified details"
    db_manager: DatabaseManager = Field(...)

    def _run(self, marketer_id: str, slot_datetime: str, customer_name: str, contact_email: str) -> str:
        try:
            conn = self.db_manager.get_cob_connection()
            cursor = conn.cursor()

            # Generate appointment ID
            appointment_id = str(uuid4())
            customer_id = str(uuid4())

            # Update the marketing availability slot
            cursor.execute("""
                UPDATE marketing_availability
                SET available = 'False', appointment_id = ?, customer_id = ?
                WHERE marketer_id = ? AND slot_datetime = ? AND available = 'True'
            """, (appointment_id, customer_id, marketer_id, slot_datetime))
            if cursor.rowcount == 0:
                conn.close()
                return "Failed to book marketing meeting - slot may no longer be available."

            # Create customer record
            cursor.execute("""
                INSERT OR IGNORE INTO customers (customer_id, name, email)
                VALUES (?, ?, ?)
            """, (customer_id, customer_name, contact_email))

            conn.commit()
            conn.close()

            return f"Successfully booked marketing meeting with ID: {appointment_id}"

        except Exception as e:
            return f"Error booking marketing meeting: {str(e)}"