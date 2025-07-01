import os
import sys
import time
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
import sqlite3
import pandas as pd

# Load environment variables
load_dotenv()

# Add current directory to Python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import chatbot components
try:
    from chatbot.chatbot_system import COBCustomerCareSystem
except ImportError as e:
    st.error(f"Failed to import chatbot: {str(e)}")
    st.error("Make sure your chatbot system is properly structured")
    st.stop()



# Page configuration
st.set_page_config(
    page_title="COB Company Chatbot",
    page_icon=":robot_face:",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    
    /* Chat header */
    .chat-header {
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
        color: white;
        padding: 15px 20px;
        font-size: 1.2rem;
        font-weight: bold;
        text-align: center;
    }
    
    /* Messages container */
    .messages-container {
        flex: 1;
        padding: 20px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 15px;
    }
    
    /* Individual message bubbles */
    .user-message {
        align-self: flex-end;
        background-color: #d1e7ff;
        border-radius: 15px 15px 0 15px;
        padding: 12px 18px;
        max-width: 70%;
    }
    
    .bot-message {
        align-self: flex-start;
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 15px 15px 15px 0;
        padding: 12px 18px;
        max-width: 70%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Input area */
    .input-container {
        display: flex;
        padding: 15px;
        background-color: white;
        border-top: 1px solid #e0e0e0;
    }
    
    /* Animation for bot message */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .message-animation {
        animation: fadeIn 0.3s ease-out;
    }
    
    /* Timestamps */
    .message-timestamp {
        font-size: 0.7rem;
        color: #888;
        margin-top: 5px;
        text-align: right;
    }
    
    /* Reset Streamlit elements */
    .stTextInput > div > div > input {
        border-radius: 25px !important;
        padding: 12px 20px !important;
        border: 1px solid #ddd !important;
    }
    
    .stButton button {
        border-radius: 25px !important;
        padding: 8px 20px !important;
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%) !important;
        color: white !important;
        font-weight: bold !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'chatbot' not in st.session_state:
    st.session_state.chatbot = COBCustomerCareSystem(
        clinic_db_path="clinic_appointments_2.db",
        cob_db_path="cob_system_2.db",
        knowledge_base_path="knowledge_base/"
    )
    st.session_state.messages = []
    st.session_state.session_id = "streamlit_session"
    st.session_state.last_input = ""

# Sidebar for additional controls
with st.sidebar:
    st.image("https://via.placeholder.com/200x50?text=COB+Logo", width=200)
    st.title("COB Chatbot Controls")
    st.subheader("System Status")
    
    # Display database status
    st.markdown("**Database Status**")
    st.markdown(f"Clinic Database: {'✅ Connected' if os.path.exists('clinic_appointments_2.db') else '❌ Not Found'}")
    st.markdown(f"COB Database: {'✅ Connected' if os.path.exists('cob_system_2.db') else '❌ Not Found'}")
    
    st.divider()
    
    # Conversation controls
    st.subheader("Conversation Tools")
    if st.button("New Conversation"):
        st.session_state.chatbot.reset_session(st.session_state.session_id)
        st.session_state.messages = []
        st.rerun()
    
    if st.button("Generate Sample Data"):
        # This would need to be implemented
        st.info("Sample data generation would run here")
        time.sleep(1)
        st.rerun()
    
    st.divider()
    
    # Information about the system
    st.subheader("About")
    st.markdown("""
    **COB Company Chatbot**  
    This AI-powered assistant helps with:
    - Medical appointment scheduling
    - Marketing meeting booking
    - Product information
    - Company policy questions
    
    Version: 1.0.0
    """)

# Main chat interface
st.title("COB Company Chat Assistant")
st.caption("Your AI-powered customer service assistant")

# Chat container
st.markdown('<div class="chat-header">COB Virtual Assistant</div>', unsafe_allow_html=True)

# Messages display
st.markdown('<div class="messages-container">', unsafe_allow_html=True)
for message in st.session_state.messages:
    if message['role'] == 'user':
        st.markdown(
            f'<div class="user-message">'
            f'<div>👤 {message["content"]}</div>'
            f'<div class="message-timestamp">{message["time"]}</div>'
            f'</div>', 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="bot-message message-animation">'
            f'<div>🤖 {message["content"]}</div>'
            f'<div class="message-timestamp">{message["time"]}</div>'
            f'</div>', 
            unsafe_allow_html=True
        )
st.markdown('</div>', unsafe_allow_html=True)  # Close messages-container

# Input area
st.markdown('<div class="input-container">', unsafe_allow_html=True)
user_input = st.chat_input("Type your message here...", key="user_input")

if user_input and user_input != st.session_state.last_input:
    st.session_state.last_input = user_input
    
    # Add user message to history
    user_message = {
        'role': 'user',
        'content': user_input,
        'time': time.strftime("%H:%M:%S")
    }
    st.session_state.messages.append(user_message)
    
    # Get bot response
    bot_response = st.session_state.chatbot.process_message(
        user_input, 
        st.session_state.session_id
    )
    
    # Add bot response to history
    bot_message = {
        'role': 'bot',
        'content': bot_response,
        'time': time.strftime("%H:%M:%S")
    }
    st.session_state.messages.append(bot_message)
    
    # Rerun to update display
    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)  # Close input-container
st.markdown('</div>', unsafe_allow_html=True)  # Close chat-container    
