from typing import Callable

from .conversation import AllMessagesStrategy, Conversation, ConversationReadingStrategy

from .agent import Agent
from .askable import Askable
from .llm import LLM

import logging
logger = logging.getLogger(__name__)

class Team(Askable):
    def __init__(self, llm: LLM, description: str, id: str, 
                 members: list[Askable], 
                 system_prompt: str = "", 
                 stop_callback: Callable[[list[dict]], bool] = None, 
                 allowed_transitions: dict[Agent, list[Agent]] = None,
                 reading_strategy: ConversationReadingStrategy = AllMessagesStrategy()):
        super().__init__(id, description)
        self.agents = members
        self.system_prompt = system_prompt
        self.stop_callback = stop_callback
        self.allowed_transitions = allowed_transitions
        self.allowed_transitions_str_dict = {tr.id: [agent.id for agent in members] for tr in self.allowed_transitions for agent in self.allowed_transitions[tr]} if self.allowed_transitions else None
        
        self.current_agent = None
        self.agents_dict = {agent.id: agent for agent in members}
        
        self.llm = llm
        self.reading_strategy = reading_strategy
        
        logger.debug("[Team %s] initialized with agents: %s", self.id, self.agents_dict)

    def ask(self, conversation: Conversation, stream = False):
        
        execution_result = None
        while True:
            next_agent_id = self._select_next_agent(conversation)
            logger.debug("[Team %s] selected next agent ID: %s", self.id, next_agent_id)
            
            self.current_agent = self.agents_dict[next_agent_id]
            logger.debug("[Team %s] current agent: '%s'", self.id, self.current_agent.id)
            
            agent_result = self.current_agent.ask(conversation, stream=stream)
            logger.debug("[Team %s] asked current agent with messages: %s", self.id, agent_result)
            
            if agent_result == "stop":
                logger.debug("[Team %s] stop signal received, ending workflow.", self.id)
                execution_result = "agent-stop"
                break
            elif agent_result == "error":
                logger.error("[Team %s] error signal received, ending workflow.", self.id)
                execution_result = "agent-error"
                break
            
            if self.stop_callback(conversation.messages):
                logger.debug("[Team %s] stop callback triggered, ending workflow.", self.id)
                execution_result = "callback-stop"
                break
            
        return execution_result

    def _select_next_agent(self, conversation: Conversation):
        system_prompt = """
You are a team orchestrator that uses a chat history to determine the next best speaker in the conversation. 
Your task is to return the agent_id of the speaker that is best suited to proceed based on the context provided in the chat history and the description of the agents.
You MUST return the agent_id and nothing else.
You MUST return agent_id value from the list of available agents.
The names are case-sensitive and should not be abbreviated or changed.
When a user input is expected, you MUST select an agent capable of handling the user input.

# AVAILABLE AGENTS

{agents}

# CHAT HISTORY

{history}

BE SURE TO READ AGAIN THE INSTUCTIONS ABOVE BEFORE PROCEEDING.
"""
        local_messages = []
        agents_info = "\n".join([f"- agent_id: {agent.id}: {agent.description}\n" for agent in self.agents])
        selected_messages = self.reading_strategy.get_messages(conversation)
        history = "\n".join([f"{message['role']}: {message['content']}" for message in selected_messages])
        
        local_messages.append({"role": "system", "content": system_prompt.format(agents=agents_info, history=history)})
        local_messages.append({"role": "user", "content": "Read the conversation and provide the agent_id of the next speaker."})
        
        # logger.debug("[Team %s] messages for selecting next agent: %s", self.id, local_messages)
        
        result, usage = self.llm.ask(messages=local_messages, temperature=0)
        logger.debug("[Team %s] result from Azure OpenAI: %s", self.id, result)
        
        if usage is not None:
            # Update conversation metrics with response usage
            conversation.metrics.total_tokens += usage["total_tokens"]
            conversation.metrics.prompt_tokens += usage["prompt_tokens"]
            conversation.metrics.completion_tokens += usage["completion_tokens"]
        
        key = result.content.split(" ")[-1].strip()
        
        if key not in self.agents_dict:
            logger.error("[Team %s] invalid agent_id selected: %s", self.id, key)
            return self._select_next_agent(conversation)
        
        if self.allowed_transitions_str_dict is not None and self.current_agent is not None:
            if key not in self.allowed_transitions_str_dict[self.current_agent.id]:
                logger.error("[Team %s] invalid agent_id selected: %s", self.id, key)
                return self._select_next_agent(conversation)
        
        return key
