AI Agentic Framework Solution Accelerator for Insurance Advisors
Welcome to the AI Agentic Framework Solution Accelerator for Insurance Advisors. This repository contains a comprehensive solution that empowers insurance advisors by leveraging AI-driven agentic frameworks. The solution comprises a backend Azure Function app and a frontend Streamlit web application.

Overview
This solution provides an AI-powered assistant designed specifically for insurance advisors. It utilizes OpenAI's GPT-4 architecture to understand user queries, maintain conversation history, and deliver intelligent, context-aware responses. The assistant is capable of handling complex interactions, making it a valuable tool for advisors seeking to enhance client engagement.

Features
Intelligent Assistant: Offers context-aware and insightful responses to user inquiries.
Conversation Management: Stores and retrieves conversation history using Azure Cosmos DB.
Agentic Framework: Implements an agentic workflow to manage conversations and agent interactions.
User-Friendly Frontend: Streamlit web application provides an intuitive interface.
Scalable Backend: Azure Function app ensures reliable and scalable processing.
Customizable: Easily extendable to fit specific business requirements.
Architecture
The solution consists of two main components:

Backend: An Azure Function app (http_trigger) that handles HTTP requests, processes user messages, manages conversation history, and interacts with AI agents using the genai_vanilla_agents framework.

Frontend: A Streamlit web application that serves as the user interface, allowing insurance advisors to interact seamlessly with the AI assistant.

Prerequisites
Python 3.8+
Azure Account: For deploying the Azure Function app and using Azure Cosmos DB.
OpenAI API Key: Access to GPT-4 functionalities.
Azure Cosmos DB: For storing conversation histories.
Azure Functions Core Tools: For local development and deployment.
Git: Version control system

Azure resources:
Azure Function App: To host your backend function.
Azure Cosmos DB Account: With a database and container to store conversation histories.
Storage Account: Required for the Function App.
Application Insights: For monitoring.
Managed Identity: So the Function App can securely access Cosmos DB using DefaultAzureCredential.
App Service Plan: For the Streamlit app if you plan to deploy it to Azure (optional).