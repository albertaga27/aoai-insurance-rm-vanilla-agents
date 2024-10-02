from typing import Any, Protocol

class Conversation():
    def __init__(self, messages: list[dict] = [], variables: dict[str, str] = {}):
        self.messages = messages
        self.variables = variables

    def to_dict(self):
        return {
            'messages': self.messages,
            'variables': self.variables
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            messages=data.get('messages', []),
            variables=data.get('variables', {})
        )