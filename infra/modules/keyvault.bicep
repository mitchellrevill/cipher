param name string
param location string

@secure()
param foundryAccountKey string

resource kv 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: name
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

resource foundryKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'foundry-account-key'
  properties: {
    value: foundryAccountKey
  }
}

output keyVaultUri string = kv.properties.vaultUri!
output secretUri string = '${kv.properties.vaultUri!}secrets/foundry-account-key'
output resourceId string = kv.id
output name string = kv.name
