targetScope = 'subscription'

@allowed([
  'dev'
  'prod'
])
param environment string

param appName string = 'redactor'
param location string = 'uksouth'
param aiLocation string = 'swedencentral'
param staticWebLocation string = 'westus2'
param resourceGroupName string = 'rg-${environment}-${appName}-${location}'

@allowed([
  'B2'
  'P2v3'
])
param appServiceSku string

@allowed([
  'LRS'
  'GRS'
])
param storageRedundancy string

param modelName string = 'gpt-5.1'
param modelVersion string = '2025-04-14'
param modelCapacity int = 10
param disableLocalAuth bool = false
param openaiApiVersion string = '2025-03-01-preview'

var regionAbbrev = location == 'uksouth' ? 'uks' : location
var aiRegionAbbrev = aiLocation == 'swedencentral' ? 'swec' : aiLocation

var normalizedAppName = toLower(replace(appName, '-', ''))
var rgName = resourceGroupName
var storageName = 'st${normalizedAppName}${environment}${regionAbbrev}'
var cosmosName = 'cosmos-${appName}-${environment}-${regionAbbrev}'
var foundryName = 'ai-${appName}-${environment}-${aiRegionAbbrev}'
var projectName = '${appName}-proj-${environment}'
var kvName = 'kv-${appName}-${environment}-${regionAbbrev}'
var aspName = 'asp-${appName}-${environment}-${regionAbbrev}'
var apiName = 'app-${appName}-${environment}-${regionAbbrev}'
var swaName = 'stapp-${appName}-${environment}-${regionAbbrev}'

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: rgName
  location: location
}

module storage 'modules/storage.bicep' = {
  scope: rg
  name: 'storage'
  params: {
    name: storageName
    location: location
    redundancy: storageRedundancy
  }
}

module cosmos 'modules/cosmos.bicep' = {
  scope: rg
  name: 'cosmos'
  params: {
    name: cosmosName
    location: location
  }
}

module foundry 'modules/foundry.bicep' = {
  scope: rg
  name: 'foundry'
  params: {
    name: foundryName
    projectName: projectName
    location: aiLocation
    modelName: modelName
    modelVersion: modelVersion
    modelCapacity: modelCapacity
    disableLocalAuth: disableLocalAuth
  }
}

module keyvault 'modules/keyvault.bicep' = {
  scope: rg
  name: 'keyvault'
  params: {
    name: kvName
    location: location
    foundryAccountKey: foundry.outputs.accountKeySecretValue
  }
}

module swa 'modules/staticweb.bicep' = {
  scope: rg
  name: 'swa'
  params: {
    name: swaName
    location: staticWebLocation
    sku: environment == 'prod' ? 'Standard' : 'Free'
  }
}

var corsOrigins = '["https://${swa.outputs.defaultHostname}"]'
var startupCommand = 'gunicorn --bind 0.0.0.0:8000 --workers 2 --worker-class uvicorn.workers.UvicornWorker app.main:app'

module appservice 'modules/appservice.bicep' = {
  scope: rg
  name: 'appservice'
  params: {
    planName: aspName
    appName: apiName
    location: location
    sku: appServiceSku
    pythonVersion: '3.12'
    cosmosEndpoint: cosmos.outputs.endpoint
    cosmosDbName: 'redactor'
    storageAccountUrl: storage.outputs.accountUrl
    foundryOpenaiEndpoint: foundry.outputs.openaiEndpoint
    docIntelEndpoint: foundry.outputs.docIntelEndpoint
    languageEndpoint: foundry.outputs.languageEndpoint
    openaiDeployment: modelName
    openaiApiVersion: openaiApiVersion
    foundryKeySecretUri: keyvault.outputs.secretUri
    corsOrigins: corsOrigins
    startupCommand: startupCommand
  }
}

module roles 'modules/roles.bicep' = {
  scope: rg
  name: 'roles'
  params: {
    appServicePrincipalId: appservice.outputs.principalId
    storageAccountName: storage.outputs.name
    cosmosAccountName: cosmos.outputs.name
    foundryAccountName: foundry.outputs.name
    keyVaultName: keyvault.outputs.name
  }
}

output resourceGroupName string = rg.name
output appServiceUrl string = 'https://${appservice.outputs.defaultHostname}'
output swaUrl string = 'https://${swa.outputs.defaultHostname}'
// ACR removed from infra
output cosmosEndpoint string = cosmos.outputs.endpoint
output foundryEndpoint string = foundry.outputs.endpoint
