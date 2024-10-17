from abc import ABC, abstractmethod
from queue import Queue
from typing import Any, Protocol

from pydantic import BaseModel

from .llm import LLM
import json

# a ConversationMetrics class with totalTokens, promptTokens and completionTokens
class ConversationMetrics(BaseModel):
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int

class Conversation():
    def __init__(self, messages: list[dict] = [], variables: dict[str, str] = {}):
        self.messages = messages
        self.variables = variables
        self.metrics = ConversationMetrics(total_tokens=0, prompt_tokens=0, completion_tokens=0)
        self.stream_queue = Queue()
        
    def stream(self):
        while True:
            mark, content = self.stream_queue.get()
            yield [mark, content]
            if mark == "response":
                break
        
    def update(self, delta):
        self.stream_queue.put_nowait(delta)
        
    def to_dict(self):
        return {
            "messages": self.messages,
            "variables": self.variables,
            "metrics": self.metrics.model_dump()
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            messages=data.get('messages', []),
            variables=data.get('variables', {})
        )
        
class ConversationReadingStrategy(ABC):
    @abstractmethod
    def get_messages(self, conversation: Conversation) -> list[dict]:
        pass
    
    def exclude_system_messages(self, messages: list[dict]) -> list[dict]:
        return [message for message in messages if message["role"] != "system"]
    
class LastNMessagesStrategy(ConversationReadingStrategy):
    def __init__(self, n: int):
        self.n = n
        
    def get_messages(self, conversation: Conversation) -> list[dict]:
        return self.exclude_system_messages(conversation.messages)[-self.n:]
    
class AllMessagesStrategy(ConversationReadingStrategy):
    def get_messages(self, conversation: Conversation) -> list[dict]:
        return self.exclude_system_messages(conversation.messages)
    
class TopKLastNMessagesStrategy(ConversationReadingStrategy):
    def __init__(self, k: int, n: int):
        self.k = k
        self.n = n
        
    def get_messages(self, conversation: Conversation) -> list[dict]:
        list = self.exclude_system_messages(conversation.messages)
        return list[:self.k] + list[-self.n:]
    
class SummarizeMessagesStrategy(ConversationReadingStrategy):
    def __init__(self, llm: LLM, system_prompt: str):
        super().__init__()
        self.llm = llm
        self.system_prompt = system_prompt
        
    def get_messages(self, conversation: Conversation) -> list[dict]:
        # Extract the conversation text from the messages        
        local_messages = [{"role": "system", "content": self.system_prompt}]
        local_messages += self.exclude_system_messages(conversation.messages)
        
        # Summarize the conversation text
        response, usage = self.llm.ask(messages=local_messages)
        response_message = response.model_dump()
        summarized_text = response_message["content"]
        
        return [{"role": "assistant", "name": "summarizer", "content": summarized_text}]

class PipelineConversationReadingStrategy(ConversationReadingStrategy):
    def __init__(self, strategies: list[ConversationReadingStrategy]):
        self.strategies = strategies
        
    def get_messages(self, conversation: Conversation) -> list[dict]:
        messages = conversation.messages
        for strategy in self.strategies:
            messages = strategy.get_messages(Conversation(messages=messages))
        return messages