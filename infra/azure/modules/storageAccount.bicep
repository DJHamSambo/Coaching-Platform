param appName string
param environmentName string
param location string
param tags object

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: take(toLower(replace('st${appName}${environmentName}', '-', '')), 24)
  location: location
  tags: tags
  sku: { name: environmentName == 'prod' ? 'Standard_ZRS' : 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

output storageAccountName string = storage.name
