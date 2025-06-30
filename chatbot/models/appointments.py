from dataclasses import dataclass
from typing import Optional

@dataclass
class AppointmentRequest:
    customer_name: Optional[str] = None
    contact_email: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    specialty: Optional[str] = None
    doctor_name: Optional[str] = None
    clinic_name: Optional[str] = None
    clinic_id: Optional[str] = None
    doctor_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

@dataclass
class MarketingMeetingRequest:
    customer_name: Optional[str] = None
    contact_email: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    product_interest: Optional[str] = None
    marketer_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None