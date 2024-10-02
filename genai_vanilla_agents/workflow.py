from typing import Union
from .askable import Askable
from .conversation import Conversation

import logging
logger = logging.getLogger(__name__)

import base64

class WorkflowInput:
    def __init__(self, text: str, images: list[str] = []):
        self.text = text
        self.images = images
        
    # Function to encode the image
    def _encode_image(self, image_path: str):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
        
    def add_image_file(self, image_path: str):
        base64_image = self._encode_image(image_path)
        url = f"data:image/jpeg;base64,{base64_image}"
        self.images.append(url)
        
    def to_message(self):
        # See https://platform.openai.com/docs/guides/vision
        content = [{"text": self.text, "type": "text"}]
        content.extend([{"image_url": {"url": image}, "type": "image_url"} for image in self.images])
        return {"role": "user", "content": content}
        

class Workflow():
    def __init__(self, askable: Askable, conversation: Conversation = None, system_prompt: str = ""):
        self.askable = askable
        self.conversation = conversation or Conversation(messages=[], variables={})
        self.system_prompt = system_prompt
        
        logger.debug("Workflow initialized")

    def run(self, workflow_input: Union[str, WorkflowInput]):
        logger.debug("Running workflow with input: %s", workflow_input)
        
        logger.debug("Conversation length: %s", len(self.conversation.messages))
        if len(self.conversation.messages) == 0:
            self.conversation.messages.append({"role": "system", "content": self.system_prompt})
            logger.debug("Added system prompt to messages: %s", self.system_prompt)
            
        if isinstance(workflow_input, WorkflowInput):
            self.conversation.messages.append(workflow_input.to_message())
            logger.debug("Added user input to messages: %s", workflow_input.text)
        elif isinstance(workflow_input, str):
            self.conversation.messages.append({"role": "user", "content": workflow_input})
        logger.debug("Added user input to messages: %s", workflow_input)
        
        execution_result = self.askable.ask(self.conversation)
            
        return execution_result
    
    def restart(self):        
        self.conversation = Conversation(messages=[], variables={})
        logger.debug("Conversation length: %s", len(self.conversation.messages))
        logger.debug("Restarted workflow, cleared conversation.")
        