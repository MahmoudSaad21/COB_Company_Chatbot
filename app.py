import os
import sys
import time
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv
import sqlite3
import pandas as pd


# Add current directory to Python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

# Import chatbot components
try:
    from chatbot.chatbot_system import COBCustomerCareSystem
except ImportError as e:
    st.error(f"Failed to import chatbot: {str(e)}")
    st.error("Make sure your chatbot system is properly structured")
    st.stop()

# Define the path to the .env file
ENV_FILE_PATH = "./.env"


# Load environment variables
if os.path.exists(ENV_FILE_PATH):
    load_dotenv(dotenv_path=ENV_FILE_PATH, override=True)
else:
    load_dotenv()
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
    # Check if API key is valid before initializing chatbot
    api_key = os.getenv("GOOGLE_API_KEY")
    valid_api_key = False
    
    if api_key:
        try:
            # Try a simple validation (we'll actually validate when we try to use it)
            if len(api_key) > 30 and api_key.startswith("AIza"):
                valid_api_key = True
        except:
            valid_api_key = False
    
    if valid_api_key:
        try:
            # Import and initialize only if we have a potentially valid key
            from chatbot.chatbot_system import COBCustomerCareSystem
            st.session_state.chatbot = COBCustomerCareSystem(
                clinic_db_path="clinic_appointments_2.db",
                cob_db_path="cob_system_2.db",
                knowledge_base_path="knowledge_base/"
            )
        except ImportError as e:
            st.error(f"Failed to import chatbot: {str(e)}")
            st.error("Make sure your chatbot system is properly structured")
            st.session_state.chatbot = None
        except Exception as e:
            st.error(f"Chatbot initialization failed: {str(e)}")
            st.session_state.chatbot = None
    else:
        st.session_state.chatbot = None
    
    st.session_state.messages = []
    st.session_state.session_id = "streamlit_session"
    st.session_state.last_input = ""
    st.session_state.api_key_valid = valid_api_key

# Sidebar for additional controls
with st.sidebar:
    st.title("COB Chatbot Controls")
    st.subheader("System Status")
    
    # Display database status
    st.markdown("**Database Status**")
    st.markdown(f"Clinic Database: {'✅ Connected' if os.path.exists('clinic_appointments_2.db') else '❌ Not Found'}")
    st.markdown(f"COB Database: {'✅ Connected' if os.path.exists('cob_system_2.db') else '❌ Not Found'}")
    
    # API Key Configuration Section
    st.divider()
    st.subheader("API Key Configuration")
    
    current_api_key = os.getenv("GOOGLE_API_KEY", "")
    api_key_status = st.empty()
    
    if current_api_key:
        api_key_status.success("✅ API Key is configured")
        if st.button("Show API Key"):
            st.code(f"Current API Key: {current_api_key[:4]}...{current_api_key[-4:]}")
    else:
        api_key_status.warning("⚠️ API Key not configured")
    
    # API Key input form
    with st.form("api_key_form"):
        new_api_key = st.text_input("Enter Google API Key", type="password", value="", help="Get your API key from Google Cloud Console")
        submitted = st.form_submit_button("Update API Key")
        
        if submitted:
            if new_api_key:
                try:
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(ENV_FILE_PATH), exist_ok=True)
                    
                    # Update the .env file
                    with open(ENV_FILE_PATH, "w") as f:
                        f.write(f"GOOGLE_API_KEY={new_api_key}\n")

                    # Update environment variable
                    os.environ["GOOGLE_API_KEY"] = new_api_key
                    
                    # Update session state
                    st.session_state.api_key_valid = True

                    # Reset chatbot to force reinitialization
                    if 'chatbot' in st.session_state:
                        del st.session_state['chatbot']
                    
                    st.success("✅ API Key updated successfully! Please wait...")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update API key: {str(e)}")
            else:
                st.warning("Please enter a valid API key")

    st.divider()
    
    # Conversation controls
    st.subheader("Conversation Tools")
    if st.button("New Conversation"):
        if 'chatbot' in st.session_state and st.session_state.chatbot:
            st.session_state.chatbot.reset_session(st.session_state.session_id)
        st.session_state.messages = []
        st.rerun()
    
    if st.button("Generate Sample Data"):
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
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
st.markdown('<div class="chat-header">COB Virtual Assistant</div>', unsafe_allow_html=True)

# Messages display
st.markdown('<div class="messages-container">', unsafe_allow_html=True)

# Show warning if API key is invalid or missing
if not st.session_state.api_key_valid or not st.session_state.chatbot:
    st.warning("⚠️ API key is missing or invalid. Please configure a valid Google API key in the sidebar to use the chatbot.")
    st.info("Get an API key from Google Cloud Console: https://cloud.google.com/generative-ai/documentation/api-keys")

# Display chat messages
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

# Input area (disabled if no valid API key)
st.markdown('<div class="input-container">', unsafe_allow_html=True)
user_input = st.chat_input(
    "Type your message here..." if st.session_state.api_key_valid and st.session_state.chatbot else "Configure API key to enable chat",
    disabled=not (st.session_state.api_key_valid and st.session_state.chatbot),
    key="user_input"
)

if user_input and user_input != st.session_state.last_input and st.session_state.chatbot:
    st.session_state.last_input = user_input
    
    # Add user message to history
    user_message = {
        'role': 'user',
        'content': user_input,
        'time': datetime.now().strftime("%H:%M")
    }
    st.session_state.messages.append(user_message)
    
    try:
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
    except Exception as e:
        error_msg = f"Error processing your request: {str(e)}"
        bot_message = {
            'role': 'bot',
            'content': error_msg,
            'time': datetime.now().strftime("%H:%M")
        }
        st.session_state.messages.append(bot_message)
        st.error(f"Chatbot error: {str(e)}")
    
    # Rerun to update display
    st.rerun()

st.markdown('</div>', unsafe_allow_html=True)  # Close input-container
st.markdown('</div>', unsafe_allow_html=True)  # Close chat-container
