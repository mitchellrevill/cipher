param staticSiteName string
param backendResourceId string
param backendRegion string
param linkedBackendName string = 'appservice'

resource staticSite 'Microsoft.Web/staticSites@2024-04-01' existing = {
  name: staticSiteName
}

resource linkedBackend 'Microsoft.Web/staticSites/linkedBackends@2025-03-01' = {
  parent: staticSite
  name: linkedBackendName
  properties: {
    backendResourceId: backendResourceId
    region: backendRegion
  }
}

output name string = linkedBackend.name