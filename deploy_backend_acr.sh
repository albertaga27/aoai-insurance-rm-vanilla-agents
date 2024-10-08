az acr login --name moneta.azurecr.io
docker build --tag abertaga27/moneta-ins-ai-backend:v1.0.23 .
docker tag abertaga27/moneta-ins-ai-backend:v1.0.23 moneta.azurecr.io/moneta-ins-ai-backend:v1.0.23
docker push moneta.azurecr.io/moneta-ins-ai-backend:v1.0.23