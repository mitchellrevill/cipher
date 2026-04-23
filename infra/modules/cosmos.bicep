param name string
param location string
param dbName string = 'redactor'

resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: name
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
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    disableLocalAuth: false
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: dbName
  properties: {
    resource: {
      id: dbName
    }
  }
}

resource jobsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'jobs'
  properties: {
    resource: {
      id: 'jobs'
      partitionKey: {
        paths: [
          '/job_id'
        ]
        kind: 'Hash'
      }
    }
  }
}

resource workspacesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'workspaces'
  properties: {
    resource: {
      id: 'workspaces'
      partitionKey: {
        paths: [
          '/id'
        ]
        kind: 'Hash'
      }
    }
  }
}

resource workspaceRulesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'workspace_rules'
  properties: {
    resource: {
      id: 'workspace_rules'
      partitionKey: {
        paths: [
          '/workspace_id'
        ]
        kind: 'Hash'
      }
    }
  }
}

resource workspaceExclusionsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'workspace_exclusions'
  properties: {
    resource: {
      id: 'workspace_exclusions'
      partitionKey: {
        paths: [
          '/workspace_id'
        ]
        kind: 'Hash'
      }
    }
  }
}

output endpoint string = cosmos.properties.documentEndpoint!
output resourceId string = cosmos.id
output name string = cosmos.name
