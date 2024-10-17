from .agent import Agent
from .askable import Askable
from .llm import LLM

import logging
logger = logging.getLogger(__name__)

class Sequence(Askable):
    def __init__(self, llm: LLM, description: str, id: str, steps: list[Askable], system_prompt: str = ""):
        super().__init__(id, description)
        self.steps = steps
        self.system_prompt = system_prompt
        
        self.llm = llm
        
        logger.debug("[Sequence %s] initialized with agents: %s", self.id, [step.id for step in self.steps])

    def ask(self, messages: list[dict], stream = False):
        
        execution_result = None
        for step in self.steps:            
            agent_result = step.ask(messages, stream=stream)
            logger.debug("[Sequence %s] asked step '%s' with messages: %s", self.id, step.id, agent_result)
            
            if agent_result == "stop":
                logger.debug("[Sequence %s] stop signal received, ending workflow.", self.id)
                execution_result = "agent-stop"
                break
            elif agent_result == "error":
                logger.error("[Sequence %s] error signal received, ending workflow.", self.id)
                execution_result = "agent-error"
                break
            
        return execution_result