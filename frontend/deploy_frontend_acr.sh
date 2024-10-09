az acr login --name moneta.azurecr.io
docker build --tag abertaga27/moneta-ins-ai-frontend:v1.0.8 .
docker tag abertaga27/moneta-ins-ai-frontend:v1.0.8 moneta.azurecr.io/moneta-ins-ai-frontend:v1.0.8
docker push moneta.azurecr.io/moneta-ins-ai-frontend:v1.0.8