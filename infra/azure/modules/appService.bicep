param appName string
param environmentName string
param location string
param tags object
param appInsightsConnectionString string
param keyVaultUri string

resource plan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: 'asp-${appName}-backend-${environmentName}'
  location: location
  tags: tags
  sku: { name: environmentName == 'prod' ? 'P0v3' : 'F1' }
  kind: 'linux'
  properties: { reserved: true }
}

resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: 'app-${appName}-backend-${environmentName}'
  location: location
  tags: tags
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.12'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'KEY_VAULT_URI', value: keyVaultUri }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
      ]
    }
  }
  identity: { type: 'SystemAssigned' }
}

output webAppName string = webApp.name
output defaultHostName string = webApp.properties.defaultHostName
