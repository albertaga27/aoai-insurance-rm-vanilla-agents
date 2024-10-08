# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.10-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.11

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    AzureWebJobsFeatureFlags=EnableWorkerIndexing

COPY requirements.txt /

RUN pip install -U pip
RUN pip install -r /requirements.txt

COPY . /home/site/wwwroot

RUN apt-get update
RUN apt-get install azure-functions-core-tools-4