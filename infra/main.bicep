// main.bicep

param functionAppDockerImage string = 'DOCKER|moneta.azurecr.io/moneta-ins-ai-backend:v1.0.23'
param webappAppDockerImage string = 'DOCKER|moneta.azurecr.io/moneta-ins-ai-frontend:v1.0.8'

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

// Define the storage account name
param storageAccountName string = 'sa${uniqueString(resourceGroup().id)}'

@description('Name of the Function App')
param functionAppName string = toLower('func${uniqueString(resourceGroup().id)}')

@description('Application Insights Location')
param appInsightsLocation string = location

// New parameters for Azure OpenAI
@description('Azure OpenAI Endpoint')
param AZURE_OPENAI_ENDPOINT string

@description('Azure OpenAI Key')
@secure()
param AZURE_OPENAI_KEY string

@description('Azure OpenAI Model')
param AZURE_OPENAI_MODEL string

@description('Azure OpenAI API Version')
param AZURE_OPENAI_API_VERSION string

// New parameters for AI Search
@description('AI Search Endpoint')
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

// Define the storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
  tags: commonTags
}

// Define the blob service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-05-01' = {
  parent: storageAccount
  name: 'default'
}

// Create the Function App with Managed Identity
resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'functionapp'
  properties: {
    serverFarmId: servicePlan.id
    httpsOnly: true
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: functionAppDockerImage
      alwaysOn: true
      appSettings: [ 
        {
          name: 'AzureWebJobsStorage__credential'
          value: 'managedidentity'  
        } 
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsFeatureFlags'
          value: 'EnableWorkerIndexing'
        }
        {
          name: 'AzureWebJobsStorage__serviceUri'
          value: 'https://${storageAccount.name}.blob.core.windows.net'  
        }  
        {
          name: 'AzureWebJobsStorage__blobServiceUri'
          value: 'https://${storageAccount.name}.blob.core.windows.net'  
        }
        {
          name: 'AzureWebJobsStorage__queueServiceUri'
          value: 'https://${storageAccount.name}.queue.core.windows.net'  
        }
        {
          name: 'AzureWebJobsStorage__tableServiceUri'
          value: 'https://${storageAccount.name}.table.core.windows.net'  
        }              
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_WORKER_PROCESS_COUNT'
          value: '1'
        }
        {
          name: 'WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT'
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
  
  tags: commonTags
}

// Role assignments for the Function App's managed identity
resource functionAppStorageBlobDataContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource functionAppStorageBlobDataOwnerRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageBlobDataOwner')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b') // Storage Blob Data Owner
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource functionAppStorageQueueDataContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageQueueDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88') // Storage Queue Data Contributor
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource functionAppStorageAccountContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageAccountContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '17d1049b-9a84-46fb-8f53-869881c3d3ab') // Storage Account Contributor
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
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

// Cosmos DB role assignment
resource cosmosDBDataContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2021-04-15' existing = {
  parent: cosmosDbAccount
  name: '00000000-0000-0000-0000-000000000002' // Built-in Data Contributor Role
}

resource cosmosDBRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2021-04-15' = {
  parent: cosmosDbAccount
  name: guid(cosmosDbAccount.id, functionApp.id, cosmosDBDataContributorRoleDefinition.id)
  properties: {
    roleDefinitionId: cosmosDBDataContributorRoleDefinition.id
    principalId: functionApp.identity.principalId
    scope: cosmosDbAccount.id
  }
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

