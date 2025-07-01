import os
import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader

# Database Connection Manager
class DatabaseManager:
    def __init__(self, clinic_db_path: str, cob_db_path: str):
        self.clinic_db_path = clinic_db_path
        self.cob_db_path = cob_db_path
        self.init_databases()

    def init_databases(self):
        """Initialize database schemas if not exists"""
        # Clinic appointments schema
        with sqlite3.connect(self.clinic_db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                clinic_id TEXT,
                doctor_id TEXT,
                doctor_name TEXT,
                specialty TEXT,
                clinic_name TEXT,
                slot_datetime DATETIME,
                available BOOLEAN DEFAULT 1,
                appointment_id TEXT,
                patient_name TEXT,
                contact_email TEXT,
                PRIMARY KEY (clinic_id, doctor_id, slot_datetime)
            )
            """)

        # COB system schema
        with sqlite3.connect(self.cob_db_path) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS marketing_availability (
                marketer_id TEXT,
                marketer_name TEXT,
                slot_datetime DATETIME,
                available BOOLEAN DEFAULT 1,
                appointment_id TEXT,
                customer_id TEXT,
                PRIMARY KEY (marketer_id, slot_datetime)
            )
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                product_name TEXT,
                description TEXT,
                category TEXT
            )
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS escalation_tickets (
                ticket_id TEXT PRIMARY KEY,
                session_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'open',
                conversation_history TEXT
            )
            """)


    def get_clinic_connection(self):
        return sqlite3.connect(self.clinic_db_path)

    def get_cob_connection(self):
        return sqlite3.connect(self.cob_db_path)

    def save_escalation_ticket(self, ticket_id: str, session_id: str, history: str):
        """Save escalation ticket to database"""
        with sqlite3.connect(self.cob_db_path) as conn:
            conn.execute(
                "INSERT INTO escalation_tickets (ticket_id, session_id, conversation_history) VALUES (?, ?, ?)",
                (ticket_id, session_id, history)
            )
            conn.commit()

    def get_available_clinic_slots(self, date: str, specialty: str = None, doctor_name: str = None, start_time: str = None, end_time: str = None):
        """Get available clinic slots with time range filtering"""
        conn = self.get_clinic_connection()
        cursor = conn.cursor()

        query = """
        SELECT clinic_name, doctor_name, specialty, slot_datetime, clinic_id, doctor_id
        FROM appointments
        WHERE available = 'True' AND DATE(slot_datetime) = ?
        """

        date = datetime.strptime(date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        
        params = [date]

        if specialty:
            query += "AND LOWER(specialty) LIKE LOWER(?)"
            params.append(f"%{specialty}%")

        if doctor_name:
            query += "AND LOWER(doctor_name) LIKE LOWER(?)"
            params.append(f"%{doctor_name}%")

        if start_time and end_time:
            query += "AND TIME(slot_datetime) BETWEEN ? AND ?"
            params.extend([start_time, end_time])
        elif start_time:
            query += "AND TIME(slot_datetime) >= ?"
            params.append(start_time)
        elif end_time:
            query += "AND TIME(slot_datetime) <= ?"
            params.append(end_time)

        query += " ORDER BY slot_datetime"

        cursor.execute(query, params)
        result = cursor.fetchall()
        return result

    def get_available_marketing_slots(self, date: str, marketer_name: str = None, start_time: str = None, end_time: str = None):
        """Get available marketing slots with time range filtering"""
        conn = self.get_cob_connection()
        cursor = conn.cursor()

        query = """
        SELECT marketer_name, slot_datetime, marketer_id
        FROM marketing_availability
        WHERE available = 'True' AND DATE(slot_datetime) = ?
        """
        params = [date]
        if marketer_name:
            query += " AND LOWER(marketer_name) LIKE LOWER(?)"
            params.append(f"%{marketer_name}%")

        if start_time and end_time:
            query += " AND TIME(slot_datetime) BETWEEN ? AND ?"
            params.extend([start_time, end_time])
        elif start_time:
            query += " AND TIME(slot_datetime) >= ?"
            params.append(start_time)
        elif end_time:
            query += " AND TIME(slot_datetime) <= ?"
            params.append(end_time)

        query += "ORDER BY slot_datetime"
        cursor.execute(query, params)
        results = cursor.fetchall()
        return results
    

    def get_doctors_by_specialty(self, specialty: str = None):
        """Get doctors with optional specialty filter"""
        with sqlite3.connect(self.clinic_db_path) as conn:
            cursor = conn.cursor()
            if specialty:
                cursor.execute(
                    "SELECT DISTINCT doctor_name, specialty FROM appointments WHERE LOWER(specialty) LIKE LOWER(?)",
                    (f"%{specialty}%",))
            else:
                cursor.execute("SELECT DISTINCT doctor_name, specialty FROM appointments")
            return cursor.fetchall()

    def get_all_clinics(self):
        """Get all distinct clinic names"""
        with sqlite3.connect(self.clinic_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT clinic_name FROM appointments")
            return [row[0] for row in cursor.fetchall()]

    def get_clinic_details(self):
        """Get all clinics with their doctors and specialties"""
        with sqlite3.connect(self.clinic_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT clinic_name, doctor_name, specialty 
                FROM appointments
                ORDER BY clinic_name, doctor_name
            """)
            return cursor.fetchall()

    def get_earliest_available_slots(self, specialty: str = None, doctor_name: str = None, limit: int = 3):
        """Get earliest available slots for a specialty or doctor"""
        conn = self.get_clinic_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT clinic_name, doctor_name, specialty, slot_datetime
            FROM appointments
            WHERE available = 'True'
        """
        params = []
        
        if specialty:
            query += " AND LOWER(specialty) LIKE LOWER(?)"
            params.append(f"%{specialty}%")
            
        if doctor_name:
            query += " AND LOWER(doctor_name) LIKE LOWER(?)"
            params.append(f"%{doctor_name}%")
            
        query += " ORDER BY slot_datetime LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        return cursor.fetchall()
    

    def get_available_slots_around_time(self, date: str, target_time: str, specialty: str = None, 
                                    doctor_name: str = None, num_before=2, num_after=2):
        """Get available slots around a specific time with extended search"""
        try:
            # Convert to datetime objects
            target_dt = datetime.strptime(f"{date} {target_time}", "%Y-%m-%d %H:%M:%S")
            
            # First try: Search in a 4-hour window
            start_dt = target_dt - timedelta(hours=2)
            end_dt = target_dt + timedelta(hours=2)
            
            slots = self.get_available_clinic_slots(
                date, 
                specialty, 
                doctor_name,
                start_time=start_dt.strftime("%H:%M:%S"),
                end_time=end_dt.strftime("%H:%M:%S")
            )
            
            # If no slots found in window, try wider 8-hour window
            if not slots:
                start_dt = target_dt - timedelta(hours=4)
                end_dt = target_dt + timedelta(hours=4)
                slots = self.get_available_clinic_slots(
                    date, 
                    specialty, 
                    doctor_name,
                    start_time=start_dt.strftime("%H:%M:%S"),
                    end_time=end_dt.strftime("%H:%M:%S")
                )
            
            # If still no slots, search entire day
            if not slots:
                slots = self.get_available_clinic_slots(date, specialty, doctor_name)
            
            # If no slots found at all, return empty
            if not slots:
                return []
                
            # Convert to datetime objects and sort
            slot_objs = []
            for slot in slots:
                slot_dt = datetime.strptime(slot[3], "%Y-%m-%d %H:%M:%S")
                slot_objs.append({
                    "datetime": slot_dt,
                    "clinic_name": slot[0],
                    "doctor_name": slot[1],
                    "specialty": slot[2],
                    "clinic_id": slot[4],
                    "doctor_id": slot[5],
                    "time_difference": abs((slot_dt - target_dt).total_seconds())
                })
            
            # Sort by time difference
            slot_objs.sort(key=lambda x: x["time_difference"])
            
            # Return closest slots
            return slot_objs[:num_before + num_after]
            
        except Exception as e:
            print(f"Error getting slots around time: {e}")
            return []

    
    def get_available_marketing_slots_around_time(self, date: str, target_time: str, 
                                                 marketer_name: str = None, 
                                                 num_before=2, num_after=2):
        """Get available marketing slots around a specific time (searches entire day)"""
        try:
            # Get all available slots for the day
            all_slots = self.get_available_marketing_slots(date, marketer_name)
            if not all_slots or isinstance(all_slots, str):
                return []
                
            # Convert to datetime objects
            target_dt = datetime.strptime(f"{date} {target_time}", "%Y-%m-%d %H:%M:%S")
            slot_objs = []
            for slot in all_slots:
                slot_dt = datetime.strptime(slot[1], "%Y-%m-%d %H:%M:%S")
                slot_objs.append({
                    "datetime": slot_dt,
                    "marketer": slot[0],
                    "marketer_id": slot[2],
                    "time_diff": (slot_dt - target_dt).total_seconds()
                })
            
            # Separate before and after slots
            before = [s for s in slot_objs if s["time_diff"] < 0]
            after = [s for s in slot_objs if s["time_diff"] > 0]
            
            # Sort by proximity to target time
            before.sort(key=lambda x: abs(x["time_diff"]))
            after.sort(key=lambda x: abs(x["time_diff"]))
            
            # Select closest slots
            selected_before = before[:num_before] if before else []
            selected_after = after[:num_after] if after else []
            
            return selected_before + selected_after
            
        except Exception as e:
            print(f"Error getting marketing slots around time: {e}")
            return []

# Knowledge Base Manager with RAG
class KnowledgeBaseManager:
    def __init__(self, path: str):
        self.path = path
        self.vector_store = self._init_vector_store()

    def _init_vector_store(self):
        """Initialize FAISS vector store from knowledge base documents"""
        if not os.path.exists(self.path):
            os.makedirs(self.path)
            # Create sample knowledge files
            self._create_sample_knowledge()

        loader = DirectoryLoader(
            self.path,
            glob="**/*.txt",
            loader_cls=TextLoader,
            show_progress=False
        )
        docs = loader.load()

        if not docs:
            return None

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
        documents = text_splitter.split_documents(docs)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
        return FAISS.from_documents(documents, embeddings)

    def _create_sample_knowledge(self):
        """Create sample knowledge base files"""
        sample_files = {
            "products.txt": """
            COB Company Products:
            - Analytics Pro: Advanced data analytics platform with real-time dashboards and predictive capabilities.
            - Health Monitor: Wearable device that tracks vital signs and health metrics 24/7.
            - Cloud Secure: Enterprise-grade cloud security solution with threat detection and prevention.
            - AI Assistant: Conversational AI system for customer service and support automation.

            Pricing:
            - Analytics Pro: $99/month per user
            - Health Monitor: $199 one-time purchase
            - Cloud Secure: Custom pricing based on infrastructure size
            - AI Assistant: $499/month for basic plan

            Support:
            - Email: support@cobcompany.com
            - Phone: 1-800-COB-HELP
            - Hours: Mon-Fri 9AM-6PM EST
            """,

            "policies.txt": """
            COB Company Policies:
            - Return Policy: 30-day money-back guarantee on all products.
            - Warranty: Hardware products come with 1-year limited warranty.
            - Data Privacy: We comply with GDPR and CCPA regulations. All customer data is encrypted.
            - Service Level Agreement (SLA): 99.9% uptime guarantee for cloud services.

            Appointment Cancellation:
            - Clinical appointments: Cancel at least 24 hours in advance to avoid fees.
            - Marketing meetings: Cancel at least 2 hours in advance.
            """
        }

        for filename, content in sample_files.items():
            with open(os.path.join(self.path, filename), "w") as f:
                f.write(content)

    def query(self, question: str, k: int = 4) -> List[Document]:
        """Retrieve relevant documents for a query"""
        if not self.vector_store:
            print("No vector store available.")
            return []
        return self.vector_store.similarity_search(question, k=k)
