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
        padding: 18px 25px;
        font-size: 1.3rem;
        font-weight: 600;
        text-align: center;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
    }
    
    /* Messages container */
    .messages-container {
        flex: 1;
        padding: 25px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 20px;
        background-color: #f9fbfd;
    }
    
    /* Individual message bubbles */
    .user-message {
        align-self: flex-end;
        background: linear-gradient(135deg, #2575fc 0%, #6a11cb 100%);
        color: white;
        border-radius: 18px 18px 0 18px;
        padding: 15px 20px;
        max-width: 75%;
        margin-left: 25%;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.08);
        position: relative;
    }
    
    .bot-message {
        align-self: flex-start;
        background-color: #ffffff;
        border: 1px solid #e6e9ef;
        border-radius: 18px 18px 18px 0;
        padding: 15px 20px;
        max-width: 75%;
        margin-right: 25%;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
        position: relative;
    }
    
    /* Message content styling */
    .message-content {
        font-size: 1.05rem;
        line-height: 1.5;
    }
    
    /* Input area */
    .input-container {
        display: flex;
        padding: 20px;
        background-color: white;
        border-top: 1px solid #e6e9ef;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.03);
    }
    
    /* Animation for bot message */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .message-animation {
        animation: fadeIn 0.35s ease-out;
    }
    
    /* Timestamps */
    .message-timestamp {
        font-size: 0.75rem;
        color: rgba(255, 255, 255, 0.7);
        margin-top: 8px;
        text-align: right;
    }
    
    .bot-message .message-timestamp {
        color: #888;
    }
    
    /* Message indicators */
    .user-indicator {
        position: absolute;
        bottom: -8px;
        right: 0;
        width: 0;
        height: 0;
        border-left: 10px solid transparent;
        border-top: 10px solid #2575fc;
    }
    
    .bot-indicator {
        position: absolute;
        bottom: -8px;
        left: 0;
        width: 0;
        height: 0;
        border-right: 10px solid transparent;
        border-top: 10px solid #ffffff;
    }
    
    /* Reset Streamlit elements */
    .stTextInput > div > div > input {
        border-radius: 25px !important;
        padding: 14px 24px !important;
        border: 1px solid #ddd !important;
        font-size: 1.05rem !important;
    }
    
    .stButton button {
        border-radius: 25px !important;
        padding: 10px 25px !important;
        background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%) !important;
        color: white !important;
        font-weight: 600 !important;
        border: none !important;
        font-size: 1.05rem !important;
        margin-left: 12px !important;
    }
    
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #a8a8a8;
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

# Chat container with improved structure
st.markdown('<div class="chat-header">COB Virtual Assistant</div>', unsafe_allow_html=True)

# Messages display
st.markdown('<div class="messages-container">', unsafe_allow_html=True)
for message in st.session_state.messages:
    if message['role'] == 'user':
        st.markdown(
            f'<div class="user-message">'
            f'<div class="message-content">{message["content"]}</div>'
            f'<div class="message-timestamp">{message["time"]}</div>'
            f'<div class="user-indicator"></div>'
            f'</div>', 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f'<div class="bot-message message-animation">'
            f'<div class="message-content">{message["content"]}</div>'
            f'<div class="message-timestamp">{message["time"]}</div>'
            f'<div class="bot-indicator"></div>'
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
        'time': datetime.now().strftime("%H:%M")
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
        'time': datetime.now().strftime("%H:%M")
    }
    st.session_state.messages.append(bot_message)
    
    # Rerun to update display
    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)  # Close input-container
st.markdown('</div>', unsafe_allow_html=True)  # Close chat-container
