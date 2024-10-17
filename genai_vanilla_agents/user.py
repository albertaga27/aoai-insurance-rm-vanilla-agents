from typing import Callable

from .conversation import Conversation


class User:
    def __init__(self, id = "user", mode = "interactive", description = "A human user that interacts with the system. Can provide input to the chat", interaction_function: Callable[[str], str] = None):
        self.id = id
        self.mode = mode
        self.description = description
        self.interaction_function = interaction_function or input
        
    def ask(self, conversation: Conversation, stream = False):
        if (self.mode == "interactive"):        
            # Get user input from command line prompt
            user_input = self.interaction_function(f"{self.id}: ")
            conversation.messages.append({"role": "user", "content": user_input, "name": self.id})
            return None
        elif (self.mode == "unattended"):
            return "stop"