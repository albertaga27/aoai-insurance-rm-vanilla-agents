from openai import AzureOpenAI
from openai.types.chat import ChatCompletion
from abc import ABC, abstractmethod
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

import json
import logging

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class LLM(ABC):
    def __init__(self, config: dict):
        self.config = config
        
    @abstractmethod
    def ask(self, messages: list, tools: list = None, tools_function: dict[str, callable] = None):
        pass

class AzureOpenAILLM(LLM):
    def __init__(self, config: dict):
        super().__init__(config)
                
        api_key = self.config['api_key']
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
        ) if api_key is None or api_key == "" else None
        self.client = AzureOpenAI(
            azure_deployment=self.config['azure_deployment'], 
            api_key=self.config['api_key'], 
            azure_endpoint=self.config['azure_endpoint'], 
            api_version=self.config['api_version'],
            azure_ad_token_provider=token_provider)
        logger.debug("LLM initialized with AzureOpenAI client with %s", "api_key" if api_key else "token provider")
        
    def ask(self, messages: list, tools: list = None, tools_function: dict[str, callable] = None):
        # logger.debug("Received messages: %s", messages)
        
        response = self.client.chat.completions.create(
            messages=messages,
            model=self.config['azure_deployment'],
            tools=tools, 
            tool_choice="auto" if tools else None
        )
        
        response_message = response.choices[0].message
        logger.debug("Response message: %s", response_message)
        
        # Handle function calls (if any)
        if response_message.tool_calls:
            logger.debug("Tool calls detected: %s", response_message.tool_calls)
            messages.append(response.choices[0].message)
            for tool_call in response_message.tool_calls:
                function_args = json.loads(tool_call.function.arguments)
                logger.debug("Function arguments: %s", function_args)

                function_result = tools_function[tool_call.function.name](**function_args)
                logger.debug("Function result: %s", function_result)

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": function_result,
                })

            
            # logger.debug("Local messages prepared for API call: %s", messages)
            # Second API call: Get the final response from the model
            response:ChatCompletion = self.client.chat.completions.create(
                messages=messages,
                model=self.config['azure_deployment'],
            )
            response_message = response.choices[0].message
            logger.debug("Final response message: %s", response_message)
            
        # TODO what to do if more than one messages was generated via func calls? Or can they be skipped?
        
        return response_message
