import streamlit as st
import requests  
import json
import logging
import os
from streamlit_msal import Msal
import msal

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Moneta - Agentic Assistant for Insurance",
    initial_sidebar_state="expanded",
  
)

backend_url = os.getenv('FUNCTION_APP_URL')

# Function to fetch conversations from the API
def fetch_conversations():
    
    # Prepare the payload for the API call
    payload = {
        "user_id": "rm10", 
        "load_history": True
    }
    
    try:
        response = requests.post(f'https://{backend_url}/api/http_trigger', json=payload)
        logging.info(f"Response fetch() = {response}")
        assistant_response = response.json()
        
    except requests.exceptions.RequestException as e:
        assistant_response = f"Error: {e}"
    except ValueError:
        assistant_response = "Error: Unable to parse the response from the server."
    
    return assistant_response


def extract_assistant_messages(data):
    """
    Extracts the 'content' of messages where 'role' is 'assistant' from the given data.

    Parameters:
        data (dict): The data containing 'reply' messages.

    Returns:
        List[str]: A list of 'content' strings from messages where 'role' == 'assistant'.
    """
    # Get the 'reply' field, which should be a list of messages
    reply = data.get('reply', [])
    # Extract the 'content' of messages where 'role' == 'assistant'
    assistant_contents = [message.get('content') for message in reply if message.get('role') == 'assistant']
    if assistant_contents:
        return assistant_contents[0]
    else:
        return 'Could not find any message...'
    


# Initialize session_state variables
if 'conversations' not in st.session_state:
    st.session_state.conversations = fetch_conversations()
    print(f"fetch conversation() reponse = {st.session_state.conversations}")
if 'current_conversation_index' not in st.session_state:
    st.session_state.current_conversation_index = None

def start_new_conversation():
    st.session_state.conversations.append({'name': 'New Conversation', 'messages': []})
    st.session_state.current_conversation_index = len(st.session_state.conversations) - 1

def select_conversation(index):
    st.session_state.current_conversation_index = index

# Sidebar for conversations
with st.sidebar:

    # auth_data = Msal.initialize_ui(
    #     client_id=os.getenv("AZ_REG_APP_CLIENT_ID"),
    #     authority=f"https://login.microsoftonline.com/{tenant_id}",
    #     scopes=scopes,
    #     # Customize (Default values):
    #     connecting_label="Connecting",
    #     disconnected_label="Disconnected",
    #     sign_in_label="Sign in",
    #     sign_out_label="Sign out",
    #     redirectUri=redirectUri
    # )

    # if not auth_data:
    #     st.write("Authenticate to access protected content")
    #     st.stop()

    # account = auth_data["account"]
    # name = account["name"]

    # st.write(f"Hello {name}!")
    
    #TODO: handle auth and display the rest only if authenticated

    st.title("Agentic Assistant")
    # Add the logo image at the top left
    st.image('insurance_logo.png', width=200)  # Adjust the image path and size as needed
    #st.title("Conversations")
    if st.button("Start New Conversation"):
        start_new_conversation()
    st.write("---")
    # List past conversations
    for idx, conv_dict in enumerate(st.session_state.conversations):
        #print(f"Past conversations: {conv_dict}")
        conv_name = conv_dict.get('name', f"Conversation {idx+1}")
        messages = conv_dict.get('messages', [])
        if messages:
            first_user_message = next(
                (msg['content'] for msg in messages if msg['role'] == 'user'), conv_name)
            title = first_user_message[:20]
        else:
            title = conv_name

        cols = st.columns([0.8, 0.2])
        with cols[0]:
            if st.button(title, key='conv_' + str(idx)):
                select_conversation(idx)
        with cols[1]:
            if st.button("⋮", key='options_' + str(idx)):
                st.session_state['show_options'] = idx  # Store the index of the conversation

    # Check if options need to be displayed
    if 'show_options' in st.session_state:
        idx = st.session_state['show_options']
        st.write(f"**Options for Conversation {idx + 1}:**")
        action = st.radio("Select an action", ('Rename', 'Save', 'Delete'), key='action_' + str(idx))
        if action == 'Rename':
            new_name = st.text_input("Enter new name", key='new_name_' + str(idx))
            if st.button("Confirm Rename", key='confirm_rename_' + str(idx)):
                # Implement rename logic
                st.session_state.conversations[idx]['name'] = new_name
                del st.session_state['show_options']
                st.experimental_rerun()
        elif action == 'Save':
            # Implement save logic
            if st.button("Confirm Save", key='confirm_save_' + str(idx)):
                # For demonstration, just show a success message
                st.success(f"Conversation {idx + 1} saved successfully!")
                del st.session_state['show_options']
                st.experimental_rerun()
        elif action == 'Delete':
            if st.button("Confirm Delete", key='confirm_delete_' + str(idx)):
                # Implement delete logic
                del st.session_state.conversations[idx]
                if st.session_state.current_conversation_index == idx:
                    st.session_state.current_conversation_index = None
                elif st.session_state.current_conversation_index > idx:
                    st.session_state.current_conversation_index -= 1
                del st.session_state['show_options']
                st.experimental_rerun()


# Azure AD configurations
CLIENT_ID = os.getenv("AZ_REG_APP_CLIENT_ID")
TENANT_ID = os.getenv("AZ_TENANT_ID")
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPE = ["User.Read"]
REDIRECT_URI = os.getenv("WEB_REDIRECT_URI")
REDIRECT_PATH = "/.auth/login/aad/callback"

# Initialize MSAL client
msal_instance = msal.ConfidentialClientApplication(
    CLIENT_ID,
    authority=AUTHORITY,
    client_credential=None
)

def get_auth_url():
    return msal_instance.get_authorization_request_url(
        SCOPE,
        redirect_uri=REDIRECT_URI+ REDIRECT_PATH
    )

def get_token_from_code(code):
    result = msal_instance.acquire_token_by_authorization_code(
        code,
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI + REDIRECT_PATH
    )
    return result


st.title("Streamlit Azure AD Authentication")

if "access_token" not in st.session_state:
    # Check if we're in the redirect flow
    if "code" in st.experimental_get_query_params():
        code = st.experimental_get_query_params()["code"][0]
        token_result = get_token_from_code(code)
        if "access_token" in token_result:
            st.session_state.access_token = token_result["access_token"]
        else:
            st.error("Failed to acquire token")
    else:
        # If not authenticated, show login button
        auth_url = get_auth_url()
        st.markdown(f'<a href="{auth_url}" target="_self">Login with Azure AD</a>', unsafe_allow_html=True)
else:
    # User is authenticated, fetch and display user info
    headers = {'Authorization': f'Bearer {st.session_state.access_token}'}
    user_info = requests.get('https://graph.microsoft.com/v1.0/me', headers=headers).json()
    st.write(f"Welcome, {user_info.get('displayName', 'User')}!")
    st.write("Your user information:")
    st.json(user_info)

# Main chat area
if st.session_state.current_conversation_index is None:
    st.write("Please start a new conversation or select an existing one from the sidebar.")
else:
    # Add the title centered in the middle of the chat interface component
    st.markdown("<h1 style='text-align: center;'>Empowering Advisors</h1>", unsafe_allow_html=True)

    # Retrieve the current conversation
    conversation_dict = st.session_state.conversations[st.session_state.current_conversation_index]
    messages = conversation_dict.get('messages', [])
    #print(f"\nMessages: {messages}")
    # Display chat messages
    for message in messages:
        if message['role'] == 'user':
            with st.chat_message("user"):
                st.write(message['content'])
        else:
            message_name = message.get('name', '')  # Returns '' if 'name' is not in message
            if message_name == 'Planner':
                with st.chat_message("assistant", avatar="avatars/planner_avatar.png"):
                    st.write(message['content'])
            elif message_name == 'CRM':
                with st.chat_message("assistant", avatar="avatars/crm_avatar.png"):
                    st.write(message['content']) 
            else:
                with st.chat_message("assistant", avatar="avatars/search_avatar.png"):
                    st.write(message['content'])       
    
    # Input field for the user to send a message
    user_input = st.chat_input("Your message")
    if user_input:
       # Append user's message to the conversation
        messages.append({'role': 'user', 'content': user_input})
        
        with st.spinner('Waiting for response...'):

            # Prepare the payload for the API call
            if conversation_dict.get('name') == 'New Conversation':
                print("payload without chat_id")
                payload = {
                    "user_id": "rm10",       
                    "message": user_input
                }
            else:
                payload = {
                    "user_id": "rm10", 
                    "chat_id": conversation_dict.get('name'),
                    "message": user_input
                }
                print(f"payload with chat_id = {conversation_dict.get('name')}")
            
            # Make the API call
            try:
                response = requests.post(f'https://{backend_url}/api/http_trigger', json=payload)
                assistant_response = response.json()
                #logging.info(f"api response: {assistant_response}")
            except requests.exceptions.RequestException as e:
                assistant_response = f"Error: {e}"
                logging.error(f"Error: {e}")
            except ValueError:
                assistant_response = "Error: Unable to parse the response from the server."
            
            #handle the chat_id to the session
            st.session_state.conversations[st.session_state.current_conversation_index]['name'] = assistant_response['chat_id']

            messages.append({'role': 'assistant', 'content': extract_assistant_messages(assistant_response)})
            
            # Refresh the app to display new messages
            st.experimental_rerun()
