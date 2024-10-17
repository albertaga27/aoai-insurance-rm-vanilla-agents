from abc import abstractmethod
import asyncio
import contextlib
import gzip
import json
import logging
import time
from typing import Generator, Protocol

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn, threading, requests

from starlette_gzip_request import GZipRequestMiddleware

from ..conversation import AllMessagesStrategy, Conversation, ConversationMetrics, ConversationReadingStrategy
from ..askable import Askable

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class ConversationRequest(BaseModel):
    messages: list[dict]
    variables: dict

class ConversationResponse(BaseModel):
    messages: list[dict]
    variables: dict
    metrics: ConversationMetrics
    
class AskResponse(BaseModel):
    conversation: ConversationResponse
    result: str

class Connection(Protocol):
    @abstractmethod
    def send(target_id: str, self, operation: str, payload: any) -> dict:
        pass
    
    @abstractmethod
    def stream(target_id: str, self, operation: str, payload: any) -> dict:
        pass

class RESTConnection(Connection):
    def __init__(self, url: str):
        self.url = url
        logger.debug(f"RESTConnection initialized with URL: {self.url}")

    def send(self, target_id: str, operation: str, payload: any) -> dict:
        logger.debug(f"Sending payload to {self.url}/{operation}: {payload}")
        headers = {'Content-Encoding': 'gzip', 'Content-Type': 'application/json'}
        compressed_payload = gzip.compress(json.dumps(payload).encode('utf-8'))
        response = requests.post(f"{self.url}/{target_id}/{operation}", data=compressed_payload, headers=headers)
        response.raise_for_status()
        response = response.json()
        logger.debug(f"Received response: {response}")
        
        return response
    
    def stream(self, target_id: str, operation: str, payload: any):
        logger.debug(f"Streaming payload to {self.url}/{operation}: {payload}")
        headers = {'Content-Encoding': 'gzip', 'Content-Type': 'application/json'}
        compressed_payload = gzip.compress(json.dumps(payload).encode('utf-8'))
        response = requests.post(f"{self.url}/{target_id}/{operation}?stream=true", data=compressed_payload, headers=headers, stream=True)
        response.raise_for_status()
        result = None
        for line in response.iter_lines():
            if line:
                logger.debug(f"Received line: {line}")
                mark, content = json.loads(line)
                yield [mark, content]
                if mark == "result":
                    result = content
                    break
        
        return result

class RemoteAskable(Askable):
    def __init__(self, id: str, connection: Connection, reading_strategy: ConversationReadingStrategy = AllMessagesStrategy()):
        super().__init__("", "")
        self.connection = connection
        self.id = id
        self.reading_strategy = reading_strategy
        
        response = self.connection.send(self.id, "describe", {})
        self.description = response["description"]        
        
        logger.debug(f"RemoteAskable initialized with ID: {self.id}, Description: {self.description}")

    def ask(self, conversation: Conversation, stream = False):
        source_messages = self.reading_strategy.get_messages(conversation)
        payload = {"messages": source_messages, "variables": conversation.variables}
        logger.debug(f"Asking with payload: {payload}")
        
        result = None
        conv = None
        if not stream:
            response = self.connection.send(self.id, "ask", payload)
        else:
            gen = self.connection.stream(self.id, "ask", payload)         
            for mark, content in gen:
                conversation.update([mark, content])
                if mark == "result":
                    response = content
            
        result = response["result"]
        conv = response["conversation"]
        
        # Original metrics are not part of the payload, so we need to sum them
        conversation.metrics.completion_tokens += conv["metrics"]["completion_tokens"]
        conversation.metrics.prompt_tokens += conv["metrics"]["prompt_tokens"]
        conversation.metrics.total_tokens += conv["metrics"]["total_tokens"]
        # Update the conversation with the new messages
        conversation.messages += conv["messages"][len(source_messages):]
        # Update the conversation variables
        conversation.variables = conv["variables"]
        logger.debug(f"Updated conversation: {conversation}")
        
        return result

class AskableHost(Protocol):
    @abstractmethod
    def start(self):
        pass
    
    @abstractmethod
    def stop(self):
        pass
    
# Inspired by https://bugfactory.io/articles/starting-and-stopping-uvicorn-in-the-background/
class ThreadedServer(uvicorn.Server):
    @contextlib.contextmanager
    def run_in_thread(self) -> Generator:
        self.thread = threading.Thread(target=self.run)
        self.thread.start()
        logger.debug("Server thread started")
        while not self.started:
            time.sleep(0.001)
        yield
        logger.debug("Server running in thread")

class RESTHost(AskableHost):
    def __init__(self, askables: list[Askable], host: str, port: int, config: uvicorn.Config = None):
        self.askables = askables
        self.askables_dict = {askable.id: askable for askable in askables}
        self._build_app()
        self.config = config or uvicorn.Config(app=self.app, host=host, port=port)
        logger.debug(f"RESTHost initialized with host: {self.config.host}, port: {self.config.port}")

    def start(self):
        # Start the server
        self.server = ThreadedServer(config=self.config)
        with self.server.run_in_thread():
            logger.info(f"Askable server running at http://{self.config.host}:{self.config.port}")
            # Log a message with all available askables
            logger.info(f"Available askables: {', '.join([askable.id for askable in self.askables])}")
            
    def stop(self):
        logger.debug("Stopping server")
        self.server.should_exit = True
        self.server.thread.join()
        logger.debug("Server stopped")
        
    def _build_app(self):
        self.app = FastAPI()
        # Enable GZip compression for response
        self.app.add_middleware(GZipMiddleware, minimum_size=1000)
        self.app.add_middleware(GZipRequestMiddleware)
        
        @self.app.post("/{id}/describe")
        def describe(id: str):
            if id in self.askables_dict:
                askable = self.askables_dict[id]
                return {"id": askable.id, "description": askable.description}
            else:
                # Return 404 if the askable is not found
                return {"detail": "Askable not found"}, 404

        @self.app.post("/{id}/ask")
        async def ask(id: str, request: ConversationRequest, stream: bool = False):
            logger.debug(f"Received ask request: {request} for askable {id}")
            conv = Conversation(request.messages, request.variables)
            
            if id in self.askables_dict:
                askable = self.askables_dict[id]
                
                if stream:
                    loop = asyncio.get_event_loop()
                    res = loop.run_in_executor(None, askable.ask, conv, True)
                    async def _stream():
                        for mark, content in conv.stream():
                            json_string = json.dumps([mark, content])
                            # logger.debug(f"Streaming: {json_string}")
                            yield json_string + "\n" # NEW LINE DELIMITED JSON
                            if mark == "response":
                                break
                        
                        response = AskResponse(
                            conversation=ConversationResponse(messages=conv.messages, variables=conv.variables, metrics=conv.metrics), 
                            result=await res).model_dump()
                        yield json.dumps(["result", response])
                    response = StreamingResponse(_stream(), media_type="application/x-ndjson")
                else:                    
                    result = askable.ask(conv, stream=False)
                    response = AskResponse(
                        conversation=ConversationResponse(messages=conv.messages, variables=conv.variables, metrics=conv.metrics), 
                        result=result)
                
                    logger.debug(f"Returning response: {response}")
                
                return response
            else:
                # Return 404 if the askable is not found
                return {"detail": "Askable not found"}, 404
