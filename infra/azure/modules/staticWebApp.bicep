param appName string
param environmentName string
param location string
param tags object

resource staticWebApp 'Microsoft.Web/staticSites@2023-01-01' = {
  name: 'swa-${appName}-${environmentName}'
  location: location
  tags: tags
  sku: {
    name: environmentName == 'prod' ? 'Standard' : 'Free'
    tier: environmentName == 'prod' ? 'Standard' : 'Free'
  }
  properties: {
    buildProperties: {
      appLocation: '/generated/frontend-app'
      outputLocation: 'dist'
    }
  }
}

output defaultHostName string = staticWebApp.properties.defaultHostname
