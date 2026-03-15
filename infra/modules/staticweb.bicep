param name string
param location string

@allowed([
  'Free'
  'Standard'
])
param sku string

resource swa 'Microsoft.Web/staticSites@2024-04-01' = {
  name: name
  location: location
  sku: {
    name: sku
    tier: sku
  }
  properties: {}
}

output defaultHostname string = swa.properties.defaultHostname!
output resourceId string = swa.id
output name string = swa.name
