using './main.bicep'

param environment = 'prod'
param appName = 'redactor'
param location = 'uksouth'
param aiLocation = 'swedencentral'
param appServiceSku = 'P2v3'
param acrSku = 'Standard'
param storageRedundancy = 'GRS'
param modelName = 'gpt-5.1'
param modelVersion = '2025-04-14'
param modelCapacity = 50
param disableLocalAuth = true
param openaiApiVersion = '2025-03-01-preview'
