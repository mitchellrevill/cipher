param name string
param location string

@allowed([
  'LRS'
  'GRS'
])
param redundancy string

var skuName = redundancy == 'GRS' ? 'Standard_GRS' : 'Standard_LRS'

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: name
  location: location
  kind: 'StorageV2'
  sku: {
    name: skuName
  }
  properties: {
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource redactedJobsContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'redacted-jobs'
  properties: {
    publicAccess: 'None'
  }
}

output accountUrl string = storage.properties.primaryEndpoints.blob!
output resourceId string = storage.id
output name string = storage.name
