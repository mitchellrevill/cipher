param name string
param projectName string
param location string
param modelName string
param modelVersion string
param modelCapacity int
param disableLocalAuth bool

resource aiFoundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: name
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: name
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: disableLocalAuth
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiFoundry
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiFoundry
  name: modelName
  sku: {
    name: 'DataZoneStandard'
    capacity: modelCapacity
  }
  properties: {
    model: {
      name: modelName
      format: 'OpenAI'
      version: modelVersion
    }
  }
}

output endpoint string = aiFoundry.properties.endpoint!
output openaiEndpoint string = 'https://${name}.openai.azure.com'
output docIntelEndpoint string = 'https://${name}.cognitiveservices.azure.com'
output languageEndpoint string = 'https://${name}.cognitiveservices.azure.com'
output resourceId string = aiFoundry.id
output name string = aiFoundry.name

@secure()
output accountKeySecretValue string = aiFoundry.listKeys().key1
