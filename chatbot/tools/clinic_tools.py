from langchain.tools import BaseTool
from pydantic import Field
import json
from datetime import datetime
from uuid import uuid4
from ..database.manager import DatabaseManager
from typing import Optional

# Tools for Database Operations
class ClinicAvailabilityTool(BaseTool):
    name: str = "clinic_availability_checker"
    description: str = "Check available appointment slots for clinical appointments by date, specialty, or doctor"
    db_manager: DatabaseManager = Field(...)

    def _run(self, date: str = None, specialty: str = None,
             doctor_name: str = None, start_time: str = None,
             end_time: str = None) -> str:
        try:
            if not date:
                return "Please specify a date to check availability."

            # Get slots with time range filtering
            results = self.db_manager.get_available_clinic_slots(
                date, specialty, doctor_name, start_time, end_time
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


            # Format results
            formatted_results = []
            for row in results:
                clinic_name, doctor_name, specialty, slot_datetime, clinic_id, doctor_id = row
                formatted_results.append({
                    "clinic": clinic_name,
                    "doctor": doctor_name,
                    "specialty": specialty,
                    "datetime": slot_datetime,
                    "clinic_id": clinic_id,
                    "doctor_id": doctor_id
                })

            return json.dumps(formatted_results, indent=2)

        except Exception as e:
            return f"Error checking availability: {str(e)}"

class AppointmentBookingTool(BaseTool):
    name: str = "appointment_booker"
    description: str = "Book a clinical appointment with specified details"
    db_manager: DatabaseManager = Field(...)

    def _run(self, clinic_id: str, doctor_name: str, slot_datetime: str,
             patient_name: str, contact_email: str) -> str:
        try:
            conn = self.db_manager.get_clinic_connection()
            cursor = conn.cursor()

            # Generate appointment ID
            appointment_id = str(uuid4())

            # Update the appointment slot
            cursor.execute("""
                UPDATE appointments
                SET available = 'False', appointment_id = ?, patient_name = ?, contact_email = ?
                WHERE doctor_name = ? AND slot_datetime = ? AND available = 'True'
            """, (appointment_id, patient_name, contact_email, doctor_name, slot_datetime))
            if cursor.rowcount == 0:
                conn.close()
                return "Failed to book appointment - slot may no longer be available."

            conn.commit()
            conn.close()

            return f"Successfully booked appointment with ID: {appointment_id}"

        except Exception as e:
            return f"Error booking appointment: {str(e)}"

# New Tools for Clinic Information
class ClinicInfoTool(BaseTool):
    name: str = "clinic_info_fetcher"
    description: str = "Retrieve information about clinics, doctors, and specialties"
    db_manager: DatabaseManager = Field(...)

    def _run(self, query: str = None) -> str:
        try:
            # Get all clinic details
            details = self.db_manager.get_clinic_details()
            if not details:
                return "No clinic information available."
            
            # Organize by clinic
            clinic_map = {}
            for clinic, doctor, specialty in details:
                if clinic not in clinic_map:
                    clinic_map[clinic] = []
                clinic_map[clinic].append((doctor, specialty))
            
            # Format response
            response = []
            for clinic, doctors in clinic_map.items():
                doctor_list = "\n    ".join([f"- {doc} ({spec})" for doc, spec in doctors])
                response.append(f"{clinic}:\n    {doctor_list}")
            return "Here are our clinics with doctors and their specialties:\n" + "\n\n".join(response)
            
        except Exception as e:
            return f"Error retrieving clinic info: {str(e)}"
        

class DoctorAvailabilityTool(BaseTool):
    name: str = "doctor_availability_checker"
    description: str = "Check available appointment times for specific doctors or specialties across all dates"
    db_manager: DatabaseManager = Field(...)

    def _run(self, doctor_name: str = None, specialty: str = None, date: str = None) -> str:
        try:
            # If no date specified, get earliest available slots across all dates
            if not date:
                slots = self.db_manager.get_earliest_available_slots(specialty, doctor_name, limit=10)
                
                if not slots:
                    return f"No available appointments found for {doctor_name or specialty}."
                
                # Format results by date
                date_map = {}
                for row in slots:
                    clinic, doctor, spec, datetime_str = row
                    slot_dt = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
                    date_str = slot_dt.strftime("%Y-%m-%d")
                    time_str = slot_dt.strftime("%I:%M %p")
                    
                    if date_str not in date_map:
                        date_map[date_str] = []
                    
                    date_map[date_str].append(f"- Dr. {doctor} at {time_str} ({clinic})")
                
                # Format response
                response = [f"Earliest available appointments for {doctor_name or specialty}:"]
                for date_str, times in date_map.items():
                    response.append(f"\n{date_str}:")
                    response.extend(times)
                
                return "\n".join(response)
                
            # If date is specified, get slots for that date
            results = self.db_manager.get_available_clinic_slots(
                date, 
                specialty, 
                doctor_name
            )
            
            if not results or isinstance(results, str):
                return f"No available appointments found for {doctor_name or specialty} on {date}."
                
            # Format results
            slot_list = []
            for row in results:
                clinic_name, doctor_name, specialty, slot_datetime, clinic_id, doctor_id = row
                dt = datetime.strptime(slot_datetime, "%Y-%m-%d %H:%M:%S")
                time_str = dt.strftime("%I:%M %p")
                slot_list.append(f"- Dr. {doctor_name} at {time_str} ({clinic_name})")
                
            return f"Available slots on {date}:\n" + "\n".join(slot_list)
            
        except Exception as e:
            return f"Error checking availability: {str(e)}"
