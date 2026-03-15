param name string
param location string

@allowed([
  'Basic'
  'Standard'
])
param sku string

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: false
  }
}

output loginServer string = acr.properties.loginServer!
output resourceId string = acr.id
output name string = acr.name
