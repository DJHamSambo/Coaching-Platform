param appName string
param environmentName string
param location string
param tags object
param logAnalyticsWorkspaceId string

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'appi-${appName}-${environmentName}'
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceId
    SamplingPercentage: environmentName == 'prod' ? 20 : 100
  }
}

output connectionString string = appInsights.properties.ConnectionString
