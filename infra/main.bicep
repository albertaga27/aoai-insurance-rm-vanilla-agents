// main.bicep

param functionAppDockerImage string = 'DOCKER|moneta.azurecr.io/moneta-ins-ai-backend:v1.0.0'
param webappAppDockerImage string = 'DOCKER|moneta.azurecr.io/moneta-ins-ai-frontend:v1.0.0'

@description('Name of the Resource Group')
param resourceGroupName string = resourceGroup().name

@description('Location for all resources')
param location string = resourceGroup().location

@description('Name prefix for all resources')
param namePrefix string = 'moneta'

@description('Name of the Cosmos DB account')
param cosmosDbAccountName string = toLower('cdb${uniqueString(resourceGroup().id)}')

@description('Name of the Cosmos DB database')
param cosmosDbDatabaseName string = 'ConversationDB'

@description('Name of the Cosmos DB container')
param cosmosDbContainerName string = 'Conversations'

@description('Name of the Function App')
param functionAppName string = toLower('func${uniqueString(resourceGroup().id)}')

@description('Application Insights Location')
param appInsightsLocation string = location

// New parameters for Azure OpenAI
@description('Azure OpenAI Endpoint')
@secure()
param AZURE_OPENAI_ENDPOINT string

@description('Azure OpenAI Key')
@secure()
param AZURE_OPENAI_KEY string

@description('Azure OpenAI Model')
param AZURE_OPENAI_MODEL string

@description('Azure OpenAI API Version')
param AZURE_OPENAI_API_VERSION string = '2024-05-01-preview'

// New parameters for AI Search
@description('AI Search Endpoint')
@secure()
param AI_SEARCH_ENDPOINT string

@description('AI Search Key')
@secure()
param AI_SEARCH_KEY string

@description('AI Search Index Name')
param AI_SEARCH_INDEX_NAME string

@description('AI Search Semantic Configuration')
param AI_SEARCH_SEMANTIC_CONFIGURATION string


// Define common tags  
var commonTags = {  
  solution: 'moneta-ins-gbb-ai-1.0'    
}


// Create an Application Insights instance
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${functionAppName}-ai'
  location: appInsightsLocation
  kind: 'web'
  properties: {
    Application_Type: 'web'
  }
}

// Create a Cosmos DB Account
resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2022-08-15' = {
  name: cosmosDbAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    capabilities: []
    ipRules: []
    isVirtualNetworkFilterEnabled: false
    enableAutomaticFailover: false
    enableFreeTier: false
    enableAnalyticalStorage: false
    cors: []
  }
  tags: commonTags
}

// Create the Cosmos DB Database
resource cosmosDbDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2022-05-15' = {
  parent: cosmosDbAccount
  name: cosmosDbDatabaseName
  properties: {
    resource: {
      id: cosmosDbDatabaseName
    }
    options: {}
  }
  tags: commonTags
}

// Create the Cosmos DB Container
resource cosmosDbContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2022-05-15' = {
  parent: cosmosDbDatabase
  name: cosmosDbContainerName
  properties: {
    resource: {
      id: cosmosDbContainerName
      partitionKey: {
        paths: ['/userId']
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: []
      }
    }
    options: {}
  }
  tags: commonTags
}

// Create a Service Plan for Function App
resource servicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: '${functionAppName}-plan'
  location: location
  kind: 'Linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true
  }
  tags: commonTags
}

// Create the Function App with Managed Identity
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: servicePlan.id
    siteConfig: {
      pythonVersion: '3.10'
      linuxFxVersion: functionAppDockerImage
      alwaysOn: true
      appSettings: [ 
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://index.docker.io'
        }              
        {
          name: 'COSMOSDB_ENDPOINT'
          value: cosmosDbAccount.properties.documentEndpoint
        }
        {
          name: 'COSMOSDB_DATABASE_NAME'
          value: cosmosDbDatabaseName
        }
        {
          name: 'COSMOSDB_CONTAINER_USER_NAME'
          value: cosmosDbContainerName
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: AZURE_OPENAI_ENDPOINT
        }
        {
          name: 'AZURE_OPENAI_KEY'
          value: AZURE_OPENAI_KEY
        }
        {
          name: 'AZURE_OPENAI_MODEL'
          value: AZURE_OPENAI_MODEL
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: AZURE_OPENAI_API_VERSION
        }
        {
          name: 'AI_SEARCH_ENDPOINT'
          value: AI_SEARCH_ENDPOINT
        }
        {
          name: 'AI_SEARCH_KEY'
          value: AI_SEARCH_KEY
        }
        {
          name: 'AI_SEARCH_INDEX_NAME'
          value: AI_SEARCH_INDEX_NAME
        }
        {
          name: 'AI_SEARCH_SEMANTIC_CONFIGURATION'
          value: AI_SEARCH_SEMANTIC_CONFIGURATION
        }
      ]
    }
  }
  dependsOn: [
    servicePlan
    cosmosDbAccount
  ]
  tags: commonTags
}

// Grant Cosmos DB access to the Function App's Managed Identity
resource cosmosDbRoleDefinition 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: cosmosDbAccount
  name: 'b24988ac-6180-42a0-ab88-20f7382dd24c' // Built-in role: Cosmos DB Account Reader Role
}

resource cosmosDbRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(subscription().id, cosmosDbAccount.id, functionApp.id, cosmosDbRoleDefinition.id)
  scope: cosmosDbAccount
  properties: {
    principalId: functionApp.identity.principalId
    roleDefinitionId: cosmosDbRoleDefinition.id
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    functionApp
  ]
}



@description('Name of the App Service Plan for Streamlit')
param appServicePlanName string = '${namePrefix}-streamlit-plan'

@description('Name of the Web App for Streamlit')
param webAppName string = '${namePrefix}-streamlit-app'

// Create an App Service Plan
resource streamlitServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: appServicePlanName
  location: location
  kind: 'Linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true
  }
  tags: commonTags
}

// Create the Web App
resource streamlitWebApp 'Microsoft.Web/sites@2022-03-01' = {
  name: webAppName
  location: location
  properties: {
    serverFarmId: streamlitServicePlan.id
    siteConfig: {
      linuxFxVersion: webappAppDockerImage
      appSettings: [
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'FUNCTION_APP_URL'
          value: functionApp.properties.defaultHostName
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://index.docker.io'
        }  
        // Add other environment variables as needed
      ]
    }
    httpsOnly: true
  }
  kind: 'app,linux'
  tags: commonTags
}

