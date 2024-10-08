import azure.functions as func
from azure.identity import DefaultAzureCredential
import json
import logging
import openai
import os
import sys
import requests

from pydantic import BaseModel, Field

from dotenv import load_dotenv
load_dotenv()

from conversation_store import ConversationStore
from genai_vanilla_agents.workflow import Workflow
from genai_vanilla_agents.conversation import Conversation
from agents.group_chat import create_group_chat



app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="http_trigger")
def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    Example usage
    {"user_id":"rm3","message":"What policy is best to travel to Canada?"}

    """
    logging.info('Empowering RMs - HTTP trigger function processed a request.')

    try:
        req_body = req.get_json()
    except ValueError as e:
        logging.error(f"Invalid JSON: {e}")
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON format"}),
            status_code=400,
            mimetype="application/json"
        )

    user_id = req_body.get('user_id')
    chat_id = req_body.get('chat_id')  # None if starting a new chat
    user_message = req_body.get('message')
    load_history = req_body.get('load_history')

    if not user_id:
        return func.HttpResponse(
            json.dumps({"error": "<user_id and message> are required!"}),
            status_code=400,
            mimetype="application/json"
        )

    # A helper class that store and retrieve messages by conversation from an Azure Cosmos DB
    key = DefaultAzureCredential()
    db = ConversationStore(
        url=os.getenv("COSMOSDB_ENDPOINT"),
        key=key,
        database_name=os.getenv("COSMOSDB_DATABASE_NAME"),
        container_name=os.getenv("COSMOSDB_CONTAINER_USER_NAME")
    )

    if not db.read_user_info(user_id):
        user_data = {'chat_histories': {} }
        db.create_user(user_id, user_data)

    user_data = db.read_user_info(user_id)
    #logging.info(f"user history: {user_data.get('chat_histories')}")

    conversation_history = Conversation(messages=[], variables={})

    #if the API was called with load_history, return that and terminate
    if load_history is True:
        conversation_list = []
        chat_histories = user_data.get('chat_histories')
        if chat_histories:
            logging.info(list(chat_histories.keys()))
            for chat_id, conversation_history in chat_histories.items():
                conversation_object = {
                    "name": chat_id,
                    "messages": Conversation.from_dict(conversation_history).messages
                }
                conversation_list.append(conversation_object)
        logging.info(f"user history: {json.dumps(conversation_list)}")
        return func.HttpResponse(
            json.dumps(conversation_list),
            status_code=200,
            mimetype="application/json"
        )
    
    #if the API was called with a message, initiate chat
    if chat_id:
        # Continue existing chat
        conversation_data = user_data.get('chat_histories', {}).get(chat_id)
        if conversation_data:
            conversation_history = Conversation.from_dict(conversation_data)
        else:
            return func.HttpResponse(
                json.dumps({"error": "chat_id not found"}),
                status_code=404,
                mimetype="application/json"
            )
    else:
        # Start a new chat
        chat_id = db.generate_chat_id()
        conversation_history = Conversation(messages=[], variables={})
        user_data.setdefault('chat_histories', {})
        user_data['chat_histories'][chat_id] = conversation_history.to_dict()
        db.update_user_info(user_id, user_data)

    
    # See https://microsoft.github.io/autogen/docs/topics/groupchat/resuming_groupchat
    team = create_group_chat()
    
    history_count = len(conversation_history.messages)
     
    workflow = Workflow(askable=team, conversation=conversation_history)
    workflow.run(user_message)
    
    previous_history = user_data['chat_histories'].get(chat_id)
    #logging.info(f"\nPrevious history = user_data['chat_histories'][chat_id]: {previous_history}\n")

    merged_history = {**previous_history, **workflow.conversation.to_dict()} 
    user_data['chat_histories'][chat_id] = merged_history
    
    #logging.info(f"\nAfter merging history = user_data['chat_histories'][chat_id]: {merged_history}\n")
    db.update_user_info(user_id, user_data)
    
    delta = len(workflow.conversation.messages) - history_count
    
    new_messages = workflow.conversation.messages[-delta:]

    # Return the chat_id and reply to the client
    return func.HttpResponse(
        json.dumps({"chat_id": chat_id, "reply": new_messages}),
        status_code=200,
        mimetype="application/json"
    )
    