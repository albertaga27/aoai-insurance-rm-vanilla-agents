import streamlit as st
import requests
import logging
import os
from dotenv import load_dotenv
from msal import PublicClientApplication

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set page config
st.set_page_config(
    page_title="Moneta - Agentic Assistant for Insurance",
    initial_sidebar_state="expanded",
    layout="wide"
)

# Constants
CLIENT_ID = "99cf1386-bfc1-48f3-9a12-314b469c0091"
TENANT_ID = "72f988bf-86f1-41af-91ab-2d7cd011db47"
BACKEND_URL = os.getenv('FUNCTION_APP_URL')
REDIRECT_URI = os.getenv("WEB_REDIRECT_URI")

# Pre-defined questions
PREDEFINED_QUESTIONS = [
    "Please inform me about Ztravel international",
    "Provide information about my customer John Doe",
    "Please let me know the full claim procedure for accidents abroad"
]

# Updated Custom CSS
st.markdown("""
    <style>
    .big-font {
        font-size:30px !important;
        font-weight: bold;
    }
    .medium-font {
        font-size:20px !important;
    }
    .stButton>button {
        color: #4F8BF9;
        border-radius: 20px;
        height: 3em;
        width: 100%;
    }
    .stTextInput>div>div>input {
        color: #4F8BF9;
    }
    .login-container {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        background-image: url('insurance_logo.png');
        background-repeat: no-repeat;
        background-position: center;
        background-size: contain;
        background-attachment: fixed;
    }
    .login-box {
        background-color: rgba(255, 255, 255, 0.8);
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
    }
    </style>
    """, unsafe_allow_html=True)

def login():
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.markdown('<div class="login-box">', unsafe_allow_html=True)
    
    st.markdown('<p class="big-font">Welcome to Moneta</p>', unsafe_allow_html=True)
    st.markdown('<p class="medium-font">Your Agentic Assistant for Insurance</p>', unsafe_allow_html=True)
    st.write("Moneta is an AI-powered assistant designed to empower insurance advisors. "
             "Log in to access personalized insights, streamline your workflow, and enhance your client interactions.")
    
    app = initialize_msal_app()
    scopes = ["User.Read"]
    auth_url = app.get_authorization_request_url(scopes, redirect_uri=REDIRECT_URI)
    
    if st.button("Log in with Microsoft", key="login_button"):
        st.markdown(f"<meta http-equiv='refresh' content='0;url={auth_url}'>", unsafe_allow_html=True)
    
    st.write("By logging in, you agree to our Terms of Service and Privacy Policy.")
    
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    if "code" in st.query_params:
        with st.spinner("Authenticating..."):
            code = st.query_params["code"]
            token_result = acquire_token(app, code)
            if token_result:
                user_data = fetch_user_data(token_result["access_token"])
                st.session_state.authenticated = True
                st.session_state.user_id = user_data.get("id")
                st.session_state.display_name = user_data.get("displayName")
                st.rerun()
# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "conversations" not in st.session_state:
    st.session_state.conversations = []
if "current_conversation_index" not in st.session_state:
    st.session_state.current_conversation_index = None
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "display_name" not in st.session_state:
    st.session_state.display_name = None
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "last_selected_question" not in st.session_state:
    st.session_state.last_selected_question = None
    
def initialize_msal_app():
    authority_url = f"https://login.microsoftonline.com/{TENANT_ID}"
    return PublicClientApplication(CLIENT_ID, authority=authority_url)

def acquire_token(app, code):
    scopes = ["User.Read"]
    try:
        result = app.acquire_token_by_authorization_code(code, scopes=scopes, redirect_uri=REDIRECT_URI)
        if "access_token" in result:
            return result
        else:
            st.error("Failed to acquire token. Please try again.")
            return None
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None

def fetch_user_data(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    graph_api_endpoint = "https://graph.microsoft.com/v1.0/me"
    response = requests.get(graph_api_endpoint, headers=headers)
    return response.json()

def login():
    app = initialize_msal_app()
    if "code" in st.query_params:
        with st.spinner("Authenticating..."):
            code = st.query_params["code"]
            token_result = acquire_token(app, code)
            if token_result:
                user_data = fetch_user_data(token_result["access_token"])
                st.session_state.authenticated = True
                st.session_state.user_id = user_data.get("id")
                st.session_state.display_name = user_data.get("displayName")
                st.rerun()
    
    
    col1, col2, col3 = st.columns([1,6,1])
    with col2:
        
        st.markdown('<p class="big-font">Welcome to Moneta</p>', unsafe_allow_html=True)
        st.markdown('<p class="medium-font">Your Agentic Assistant for Insurance and Banking</p>', unsafe_allow_html=True)
        st.image('moneta_banner.webp')

        st.write("Moneta is an AI-powered assistant designed to empower insurance advisors. "
                 "Log in to access personalized insights, streamline your workflow, and enhance your client interactions.")
        
        
        scopes = ["User.Read"]
        auth_url = app.get_authorization_request_url(scopes, redirect_uri=REDIRECT_URI)
        
        if st.button("Log in with Microsoft", key="login_button"):
            st.markdown(f"<meta http-equiv='refresh' content='0;url={auth_url}'>", unsafe_allow_html=True)
        
    


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

def fetch_conversations():
    payload = {
        "user_id": st.session_state.user_id,
        "load_history": True
    }
    try:
        response = requests.post(f'https://{BACKEND_URL}/api/http_trigger', json=payload)
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching conversations: {e}")
        return []

def extract_assistant_messages(data):
    reply = data.get('reply', [])
    assistant_contents = [message.get('content') for message in reply if message.get('role') == 'assistant']
    return assistant_contents[0] if assistant_contents else 'Could not find any message...'

def start_new_conversation():
    st.session_state.conversations.append({
        'messages': []
    })
    st.session_state.current_conversation_index = len(st.session_state.conversations) - 1

def select_conversation(index):
    st.session_state.current_conversation_index = index

def display_sidebar():
    with st.sidebar:
        
        # st.image('insurance_logo.png', width=250)
        st.title("Moneta Assistant")
        st.write(f"Welcome, {st.session_state.display_name}!")
        if st.button("Start New Conversation", key="new_conv_button"):
            start_new_conversation()
        st.write("---")
        
        for idx, conv_dict in enumerate(st.session_state.conversations):
            messages = conv_dict.get('messages', [])
            
            # Get the first user message
            first_user_message = next((msg['content'] for msg in messages if msg['role'] == 'user'), "No messages yet")
            
            # Create a truncated version for the title
            title = (first_user_message[:30] + '...') if len(first_user_message) > 30 else first_user_message
            
            with st.expander(f"{title}"):
                # Display the full first message
                st.write(f"{first_user_message}")
                
                # Display the number of messages
                st.write(f"Number of messages: {len(messages)}")
                
                # Button to select this conversation
                if st.button("Open this conversation", key=f'open_conv_{idx}'):
                    select_conversation(idx)

        st.write("---")
        if st.button("Logout"):
            logout()


def display_chat():
    st.markdown("<h1 style='text-align: center;'>Empowering Advisors with AI</h1>", unsafe_allow_html=True)
    
    if st.session_state.current_conversation_index is None:
        st.write("Please start a new conversation or select an existing one from the sidebar.")
        return
    # Dropdown for pre-defined questions
    question_options = ["Select a predefined question or type your own below"] + PREDEFINED_QUESTIONS
    selected_question = st.selectbox("", question_options, key="question_selectbox")
                                     
    conversation_dict = st.session_state.conversations[st.session_state.current_conversation_index]
    messages = conversation_dict.get('messages', [])

    for message in messages:
        with st.chat_message(message['role'], avatar=get_avatar(message)):
            st.write(message['content'])


    
    if selected_question != "Select a predefined question or type your own below":
        if 'last_selected_question' not in st.session_state or st.session_state.last_selected_question != selected_question:
            st.session_state.last_selected_question = selected_question
            messages.append({'role': 'user', 'content': selected_question})
            with st.spinner('Moneta is thinking...'):
                assistant_response = send_message_to_backend(selected_question, conversation_dict)
                messages.append({'role': 'assistant', 'content': extract_assistant_messages(assistant_response)})
            st.rerun()

    # Custom input field
    user_input = st.chat_input("Ask Moneta anything...")
    if user_input:
        messages.append({'role': 'user', 'content': user_input})
        with st.spinner('Moneta is thinking...'):
            assistant_response = send_message_to_backend(user_input, conversation_dict)
            messages.append({'role': 'assistant', 'content': extract_assistant_messages(assistant_response)})
        st.rerun()

def get_avatar(message):
    if message['role'] == 'user':
        return None
    avatars = {
        'Planner': "avatars/planner_avatar.png",
        'CRM': "avatars/crm_avatar.png"
    }
    return avatars.get(message.get('name'), "avatars/search_avatar.png")

def send_message_to_backend(user_input, conversation_dict):
    payload = {
        "user_id": st.session_state.user_id,
        "message": user_input
    }
    if conversation_dict.get('name') != 'New Conversation':
        payload["chat_id"] = conversation_dict.get('name')
    
    try:
        response = requests.post(f'https://{BACKEND_URL}/api/http_trigger', json=payload)
        assistant_response = response.json()
        st.session_state.conversations[st.session_state.current_conversation_index]['name'] = assistant_response['chat_id']
        return assistant_response
    except requests.exceptions.RequestException as e:
        st.error(f"Error: {e}")
        return {"reply": [{"role": "assistant", "content": "Sorry, an error occurred while processing your request."}]}

def main():
    if not st.session_state.authenticated:
        login()
    else:
        if not st.session_state.conversations:
            st.session_state.conversations = fetch_conversations()
        
        display_sidebar()
        display_chat()

if __name__ == "__main__":
    main()