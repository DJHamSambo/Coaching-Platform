param appName string
param environmentName string
param location string
param tags object

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: take('kv-${appName}-${environmentName}', 24)
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection: environmentName == 'prod' ? true : null
  }
}

output vaultUri string = keyVault.properties.vaultUri
