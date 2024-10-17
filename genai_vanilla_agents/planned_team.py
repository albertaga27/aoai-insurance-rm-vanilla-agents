from typing import Callable
import json

from .conversation import Conversation
from .askable import Askable
from .llm import LLM

import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class PlannedTeam(Askable):
    def __init__(self, llm: LLM, description: str, id: str, members: list[Askable], stop_callback: Callable[[list[dict]], bool] = None):
        super().__init__(id, description)
        self.agents = members
        self.plan = None
        self.stop_callback = stop_callback
        
        self.current_agent = None
        self.agents_dict = {agent.id: agent for agent in members}
        
        self.llm = llm
        
        logger.debug("[PlannedTeam %s] initialized with agents: %s", self.id, self.agents_dict)

    def ask(self, conversation: Conversation, stream = False):
        
        if self.plan is None:
            self.plan = self._create_plan(conversation)
            logger.debug("[PlannedTeam %s] created plan: %s", self.id, self.plan)
        
        execution_result = None
        for step in self.plan:
            self.current_agent = self.agents_dict[step["agent_id"]]
            logger.debug("[PlannedTeam %s] current agent: %s", self.id, self.current_agent.id)
            
            # TODO check behavior
            conversation.messages.append({"role": "assistant", "name": self.id, "content": step["instructions"]})
            
            agent_result = self.current_agent.ask(conversation, stream=stream)
            logger.debug("[PlannedTeam %s] asked current agent with messages: %s", self.id, agent_result)
            
            if agent_result == "stop":
                logger.debug("[PlannedTeam %s] stop signal received, ending workflow.", self.id)
                execution_result = "agent-stop"
                break
            elif agent_result == "error":
                logger.error("[PlannedTeam %s] error signal received, ending workflow.", self.id)
                execution_result = "agent-error"
                break
            
            if self.stop_callback is not None and self.stop_callback(conversation.messages):
                logger.debug("[PlannedTeam %s] stop callback triggered, ending workflow.", self.id)
                execution_result = "callback-stop"
                break
            
        return execution_result

    def _create_plan(self, conversation: Conversation):
        system_prompt = """
You are a team orchestrator that must create a plan to solve the user inquiry by using the available agents.
Your task is to create a plan that includes only the agents suitable to help, based on their descriptions.
The plan must be a list of agent_id values, in the order they should be executed, along with the proper instructions for each agent.
The plan must be returned as JSON, with the following structure:

{{
    "plan": [
        {{
            "agent_id": "agent_id",
            "instructions": "instructions"
        }},
        ...
    ]
}}

You MUST return the plan in the format specified above. DO NOT return anything else.

# AVAILABLE AGENTS

{agents}

# INQUIRY

{inquiry}

BE SURE TO READ AGAIN THE INSTUCTIONS ABOVE BEFORE PROCEEDING.
"""
        local_messages = []
        agents_info = "\n".join([f"- agent_id: {agent.id}: {agent.description}\n" for agent in self.agents])
        inquiry = conversation.messages[-1]["content"] # TODO pick the first user message
        
        local_messages.append({"role": "system", "content": system_prompt.format(agents=agents_info, inquiry=inquiry)})
        local_messages.append({"role": "user", "content": "Define the plan based on the provided agents and the inquiry."})
        
        # logger.debug("[Team %s] messages for selecting next agent: %s", self.id, local_messages)
        
        result, usage = self.llm.ask(messages=local_messages)
        logger.debug("[PlannedTeam %s] result from Azure OpenAI: %s", self.id, result)
        
        if usage is not None:
            # Update conversation metrics with response usage
            conversation.metrics.total_tokens += usage["total_tokens"]
            conversation.metrics.prompt_tokens += usage["prompt_tokens"]
            conversation.metrics.completion_tokens += usage["completion_tokens"]
        
        content: str = result.content
        if "```json" in content:
            content = content.replace("```json", "").replace("```", "").strip()
        
        json_result = json.loads(content)
        
        return json_result["plan"]
