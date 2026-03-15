param planName string
param appName string
param location string
param sku string
param acrLoginServer string
param cosmosEndpoint string
param cosmosDbName string
param storageAccountUrl string
param foundryEndpoint string
param foundryOpenaiEndpoint string
param openaiDeployment string
param openaiApiVersion string
param foundryKeySecretUri string
param corsOrigins string

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: planName
  location: location
  kind: 'linux'
  sku: {
    name: sku
  }
  properties: {
    reserved: true
  }
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux,container'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOCKER|${acrLoginServer}/redactor-api:latest'
      acrUseManagedIdentityCreds: true
      appSettings: [
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${acrLoginServer}'
        }
        {
          name: 'AZURE_ENV'
          value: 'production'
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: foundryOpenaiEndpoint
        }
        {
          name: 'AZURE_OPENAI_DEPLOYMENT'
          value: openaiDeployment
        }
        {
          name: 'AZURE_OPENAI_API_VERSION'
          value: openaiApiVersion
        }
        {
          name: 'AZURE_DOC_INTEL_ENDPOINT'
          value: foundryEndpoint
        }
        {
          name: 'AZURE_DOC_INTEL_KEY'
          value: '@Microsoft.KeyVault(SecretUri=${foundryKeySecretUri})'
        }
        {
          name: 'AZURE_LANGUAGE_ENDPOINT'
          value: foundryEndpoint
        }
        {
          name: 'AZURE_LANGUAGE_KEY'
          value: '@Microsoft.KeyVault(SecretUri=${foundryKeySecretUri})'
        }
        {
          name: 'AZURE_STORAGE_ACCOUNT_URL'
          value: storageAccountUrl
        }
        {
          name: 'AZURE_STORAGE_CONTAINER'
          value: 'redacted-jobs'
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosEndpoint
        }
        {
          name: 'COSMOS_DB_NAME'
          value: cosmosDbName
        }
        {
          name: 'CORS_ORIGINS'
          value: corsOrigins
        }
        {
          name: 'ENABLE_PII_SERVICE'
          value: 'true'
        }
      ]
    }
  }
}

output principalId string = app.identity.principalId!
output defaultHostname string = app.properties.defaultHostName!
output resourceId string = app.id
output name string = app.name
