import asyncio
import json
import threading
from .remote import AskableHost, Connection
from ..conversation import Conversation
from ..askable import Askable
import grpc
from concurrent import futures
from .remote_pb2_grpc import RemoteServiceServicer, add_RemoteServiceServicer_to_server, RemoteServiceStub
from genai_vanilla_agents.remote import remote_pb2

import logging
logger = logging.getLogger(__name__)


class GRPCConnection(Connection):
    def __init__(self, url: str):
        self.channel = grpc.insecure_channel(url)
        self.stub = RemoteServiceStub(self.channel)

    def send(self, target_id: str, operation: str, payload: dict[str, any]) -> dict:
        if operation == "ask":
            request = remote_pb2.ConversationRequest(
                agent_id=target_id,
                messages=payload["messages"],
                variables=payload["variables"]
            )
            response = self.stub.Ask(request)
            return {
                "conversation": {
                    "messages": [{"role": message.role, "content": message.content, "name": message.name} for message in response.conversation.messages],
                    "variables": response.conversation.variables,
                    "metrics": {
                        "completion_tokens": response.conversation.metrics.completion_tokens,
                        "total_tokens": response.conversation.metrics.total_tokens,
                        "prompt_tokens": response.conversation.metrics.prompt_tokens
                    }
                },
                "result": response.result
            }
        elif operation == "describe":
            request = remote_pb2.DescribeRequest(agent_id=target_id)
            response = self.stub.Describe(request)
            
            return {"id": response.id, "description": response.description}
        else:
            raise Exception("Operation not supported")
        
    def stream(self, target_id: str, operation: str, payload: dict[str, any]):
        logger.debug(f"Streaming operation '{operation}' for target_id '{target_id}' with payload: {payload}")
        
        request = remote_pb2.ConversationRequest(
            agent_id=target_id,
            messages=[remote_pb2.Message(role=msg['role'], content=msg['content'], name=msg['name']) for msg in payload["messages"]],
            variables=payload["variables"]
        )
        
        result = None
        
        for response in self.stub.AskStream(request):
            mark = response.mark
            content = json.loads(response.content)
            logger.debug(f"Received stream response with mark '{mark}' and content: {content}")
            yield [mark, content]
            if mark == "result":
                result = content
                break
        
        logger.info(f"Streaming operation '{operation}' for target_id '{target_id}' completed with result: {result}")
        return result


class GRPCHost(AskableHost):
    def __init__(self, askables: list[Askable], host: str, port: int):
        self.askables = askables
        self.host = host.replace("http://", "")
        self.port = port

    def start(self):
        if hasattr(self, "server") and self.server is not None and self.server._state != 0:
            self.server.stop(grace=0)
            
        self.server = grpc.server(thread_pool=futures.ThreadPoolExecutor(max_workers=10))
        add_RemoteServiceServicer_to_server(
            GRPCServer(self.askables), self.server
        )
        self.server.add_insecure_port(f"{self.host}:{self.port}")
        self.server.start()
        logger.info(f"gRPC server running at {self.host}:{self.port}")
        # server.wait_for_termination()

    def stop(self):
        self.server.stop(grace=0)

class GRPCServer(RemoteServiceServicer):
    def __init__(self, askables: list[Askable]):
        self.askables = askables
        self.askables_dict = {askable.id: askable for askable in askables}

    def Ask(self, request: remote_pb2.ConversationRequest, context):
        if request.agent_id not in self.askables_dict:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Askable not found")
            return remote_pb2.Empty()
        
        askable = self.askables_dict[request.agent_id]
        conv = Conversation(
            messages=[{"role": message.role, "content": message.content, "name": message.name} for message in request.messages],
            variables=dict(request.variables))
        result = askable.ask(conv)
        
        return remote_pb2.AskResponse(
            conversation = remote_pb2.ConversationResponse(
                messages=[{"role": message["role"], "content": message["content"], "name": message["name"]} for message in conv.messages],
                variables=dict(conv.variables),
                metrics=remote_pb2.ConversationMetrics(
                    completion_tokens=conv.metrics.completion_tokens, 
                    total_tokens=conv.metrics.total_tokens, 
                    prompt_tokens=conv.metrics.prompt_tokens)
            ),
            result = result
        )
        
    def AskStream(self, request, context):
        agent_id = request.agent_id
        if agent_id not in self.askables_dict:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details('Agent not found')
            logger.error(f"Agent with id '{agent_id}' not found")
            return

        askable = self.askables_dict[agent_id]
        # Create a conversation object from the request
        # This is necessary because the request object typing is not compatible with the Conversation object
        conversation = Conversation(
            messages=[{"content": msg.content, "role": msg.role, "name": msg.name} for msg in request.messages],
            variables=dict(request.variables)
        )
        
        logger.debug(f"Received stream request for agent '{agent_id}' with messages: {conversation.messages}")
        
        # In order to stream the response, we need to run the askable.ask method in a separate thread
        # updates to the conversation object will be streamed back to the client below
        def ask_in_thread():
            try:
                return askable.ask(conversation, True)
            except Exception as e:
                logger.error("Error during askable.ask: %s", e, exc_info=True)
                conversation.update(["error", str(e)])
                return None
        
        thread = threading.Thread(target=ask_in_thread)
        thread.start()
        response = None
        # Stream the intermediate responses back to the client
        for mark, content in conversation.stream():
            logger.debug(f"Streaming response with mark '{mark}' and content: {content}")
            yield remote_pb2.AskStreamingResponse(
                mark=mark,
                content=json.dumps(content) # Convert the content to a JSON string, as the content must be a string for semplification
            )
            if mark == "response":
                # The stream is complete, break the loop
                res = thread.join()
                response = {
                    "conversation": conversation.to_dict(), 
                    "result": res
                }
                logger.info(f"Streaming operation completed with result: {response}")
                yield remote_pb2.AskStreamingResponse(
                    mark="result",
                    content=json.dumps(response)
                )
                break
            
        
    def Describe(self, request: remote_pb2.DescribeRequest, context):
        if request.agent_id in self.askables_dict:
            askable = self.askables_dict[request.agent_id]
            return remote_pb2.DescribeResponse(
                id=askable.id,
                description=askable.description
            )
        else:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Askable not found")
            return remote_pb2.Empty()