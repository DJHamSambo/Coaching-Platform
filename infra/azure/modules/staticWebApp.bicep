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
  // No buildProperties: they only apply to repo-linked Static Web Apps and
  // make ARM preflight/what-if fail with an internal 404 on updates. The
  // frontend is deployed by the pipeline's AzureStaticWebApp task instead.
  properties: {}
}

output defaultHostName string = staticWebApp.properties.defaultHostname
