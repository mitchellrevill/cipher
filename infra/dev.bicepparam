using './main.bicep'

param environment = 'dev'
param appName = 'redactor'
param location = 'uksouth'
param aiLocation = 'swedencentral'
param staticWebLocation = 'westus2'
param resourceGroupName = 'rg-dev-redactor-uksouth'
param appServiceSku = 'B2'
param storageRedundancy = 'LRS'
param modelName = 'gpt-5.1'
param modelVersion = '2025-11-13'
param modelCapacity = 10
param disableLocalAuth = false
param openaiApiVersion = '2025-03-01-preview'
