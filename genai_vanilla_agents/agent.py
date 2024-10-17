import logging
from typing import Annotated, Callable, Optional
import json

from .conversation import AllMessagesStrategy, Conversation, ConversationReadingStrategy

from .askable import Askable
from .function_utils import get_function_schema, wrap_function, F
from .llm import LLM

# Configure logging
logger = logging.getLogger(__name__)

class Agent(Askable):
    def __init__(self, description: str, id: str, system_message: str, llm: LLM,
                 reading_strategy: ConversationReadingStrategy = AllMessagesStrategy()):
        super().__init__(id, description)
        self.tools = []
        self.tools_function = {}
        self.llm = llm
        self.system_message = system_message
        self.reading_strategy = reading_strategy
        
        logger.debug(f"Agent initialized with ID: {self.id}, Description: {self.description}")

    def ask(self, conversation: Conversation, stream = False):
        logger.debug(f"[Agent ID: {self.id}] Received messages: %s", conversation.messages)
        
        local_messages = self._prepare_llm_input(conversation)
        local_tools, local_tools_function = self._prepare_llm_tools(conversation=conversation)

        try:
            if not stream:
                response, usage = self.llm.ask(
                    messages=local_messages,
                    tools=local_tools,
                    tools_function=local_tools_function
                )
                logger.debug(f"[Agent ID: {self.id}] API response received: %s", response)
                response_message = response.model_dump()
            else:
                gen = self.llm.ask_stream(
                    messages=local_messages,
                    tools=local_tools,
                    tools_function=local_tools_function
                )
                # logger.debug(f"[Agent ID: {self.id}] Stream started")
                response_message = None
                usage = None
                for mark, content in gen:
                    if mark == "start" or mark == "end":
                        content = self.id
                    if mark == "response" and content is not None:
                        response_message, usage = content
                    
                    conversation.update([mark, content])
            
            if usage is not None:
                # Update conversation metrics with response usage
                conversation.metrics.total_tokens += usage["total_tokens"]
                conversation.metrics.prompt_tokens += usage["prompt_tokens"]
                conversation.metrics.completion_tokens += usage["completion_tokens"]
        except Exception as e:
            logger.error(f"[Agent ID: {self.id}] Error during LLM call: %s", e)
            return "error"
        
        response_message['name'] = self.id
        conversation.messages.append(response_message)
        logger.debug(f"[Agent ID: {self.id}] Response message: %s", response_message)
        
        return "done"

    def _prepare_llm_tools(self, conversation: Conversation):
        
        # Closure function to update a conversation variable
        def update_conversation_variable(
            variableName: Annotated[str, "The variable name to update"], 
            variableValue: Annotated[str, "The new value of the variable"]) -> Annotated[str, "Confirmation that the variable was updated"]:
            conversation.variables[variableName] = variableValue
            return f"Variable {variableName} updated to {variableValue}"
        
        s = get_function_schema(update_conversation_variable, name="update_conversation_variable", description="update a conversation or context variable")
        local_tools = self.tools + [s]
        local_tools_function = {**self.tools_function, "update_conversation_variable": wrap_function(update_conversation_variable)}
        return local_tools,local_tools_function

    def _prepare_llm_input(self, conversation):
        local_messages = []
        local_messages.append({"role": "system", "content": self.system_message.replace("__context__", json.dumps(conversation.variables))})
        local_messages.extend(self.reading_strategy.get_messages(conversation))
        logger.debug(f"[Agent ID: {self.id}] Local messages prepared for API call (last 3): %s", local_messages[-3:])
        return local_messages
    
    def register_tool(
        self,
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Callable[[F], F]:

        def _decorator(func: F) -> F:
            """Decorator for registering a function to be used by an agent.

            Args:
                func: the function to be registered.

            Returns:
                The function to be registered, with the _description attribute set to the function description.

            Raises:
                ValueError: if the function description is not provided and not propagated by a previous decorator.
                RuntimeError: if the LLM config is not set up before registering a function.

            """
            # name can be overwritten by the parameter, by default it is the same as function name
            if name:
                func._name = name
            elif not hasattr(func, "_name"):
                func._name = func.__name__

            # description is propagated from the previous decorator, but it is mandatory for the first one
            if description:
                func._description = description
            else:
                if not hasattr(func, "_description"):
                    raise ValueError("Function description is required, none found.")

            # get JSON schema for the function
            f = get_function_schema(func, name=func._name, description=func._description)

            logger.debug(f"[Agent ID: {self.id}] Registering tool: %s with description: %s", func._name, func._description)
            if not self.tools:
                self.tools = []
                self.tools_function = {}
            self.tools.append(f)
            self.tools_function[func._name] = wrap_function(func)
            logger.debug(f"[Agent ID: {self.id}] Tool registered successfully: %s", func._name)

            return func

        return _decorator