# CRM Agent 
from pydantic import BaseModel, Field
import json
import os
import logging
from genai_vanilla_agents.agent import Agent
from agents.config import llm
from typing import List, Annotated, Optional
import requests
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient


product_agent = Agent(  
    id="Product",
    system_message="""You are an assistant that searches general information about insurance products.

        **Your Responsibilities:**
        - **Handle all user requests that do NOT include a client's name.**
        - Provide information about policies, prices, coverages, terms and conditions, etc., by using the provided function: 'search_product'.
        - Offer clear and helpful answers to the user's inquiries.

        **Important Guidelines:**
        - **If the user's request includes a client's name, you should not have been called, tell the manager to call other agents.**
        
    """,  
    llm=llm,  
    description="""Call this Agent if:
        - You need to retrieve generic policies details, terms and conditions or other offering related information
        DO NOT CALL THIS AGENT IF:  
        - You need to fetch specific client's data""",
    )  



def search(query: str):
    service_endpoint = os.getenv('AI_SEARCH_ENDPOINT')
    index_name = os.getenv('AI_SEARCH_INDEX_NAME')
    key = os.environ["AI_SEARCH_KEY"]

    search_client = SearchClient(service_endpoint, index_name, AzureKeyCredential(key))
    payload = json.dumps(
        {
            "search": query,
            "vectorQueries": [
                {
                "kind": "text",
                "text": query,
                "fields": "text_vector"
                }
            ],
            "queryType": "semantic",
            "semanticConfiguration": os.getenv('AI_SEARCH_SEMANTIC_CONFIGURATION'),
            "captions": "extractive",
            "answers": "extractive|count-3",
            "queryLanguage": "en-US"
        }
    )

    response = list(search_client.search(payload))

    output = []
    for result in response:
        result.pop("parent_id")
        result.pop("chunk_id")
        result.pop("text_vector")
        output.append(result)

    return output
    
    
@product_agent.register_tool(description="Load insured client data from the CRM")
def search_product(query: str) -> str:
    """
    Search general insurance product inforamtions regarding policies, coverages and terms and conditions by permorming a POST request to an Azure AI Search using the specified search body.

    Parameters:
    query

    Returns:
    dict: The search results in JSON format.
    """
    return search(query)