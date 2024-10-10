az acr login --name moneta.azurecr.io
docker build --tag abertaga27/moneta-ins-ai-frontend:v1.0.9 .
docker tag abertaga27/moneta-ins-ai-frontend:v1.0.9 moneta.azurecr.io/moneta-ins-ai-frontend:v1.0.9
docker push moneta.azurecr.io/moneta-ins-ai-frontend:v1.0.9