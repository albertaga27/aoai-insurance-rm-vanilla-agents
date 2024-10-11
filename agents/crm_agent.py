# CRM Agent 
from pydantic import BaseModel, Field
import json
import os
import logging
from genai_vanilla_agents.agent import Agent
from agents.config import llm
from typing import List, Annotated, Optional
import requests


crm_agent = Agent(  
    id="CRM",
    system_message="""You are an assistant that interacts with CRM data.
        
        **Your Responsibilities:**
        - **Only respond to user requests that explicitly mention the name of a client.**
        - When the user's request includes the name of a client, retrieve information about the client and their policies, coverages, premiums by using the provided function: 'load_from_crm'.
        - Provide concise and accurate information based only on the CRM data. Don't come up with information that are not coming form the CRM.
    
    """,  
    llm=llm,  
    description="""Call this Agent if:
        - You need to retrieve specific client's data identified by the name of a client in the user request
        DO NOT CALL THIS AGENT IF:  
        - You need to fetch generic policies answers""",  
)  



@crm_agent.register_tool(description="Load insured client data from the CRM from the given full name")
def load_from_crm(full_name:Annotated[str,"The customer full name to search for"]) -> str:
    """
    Load an example file containing insured client data and policies into a pandas DataFrame.

    Parameters:
    file_path (str): Path to the  file

    Returns:
    pd.DataFrame: DataFrame containing the loaded data
    """
    try:
        # Open and read the JSON file
        with open('data/customer_insurance.json', 'r') as file:
            return json.load(file)
    except Exception as e:
        print(f"An unexpected error occurred: {e}") 