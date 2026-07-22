param appName string
param environmentName string
param location string
param tags object
param administratorLogin string
@secure()
param administratorPassword string

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: 'psql-${appName}-${environmentName}'
  location: location
  tags: tags
  sku: {
    name: environmentName == 'prod' ? 'Standard_B2s' : 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    version: '16'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    storage: { storageSizeGB: environmentName == 'prod' ? 64 : 32 }
    backup: {
      backupRetentionDays: environmentName == 'prod' ? 14 : 7
      geoRedundantBackup: environmentName == 'prod' ? 'Enabled' : 'Disabled'
    }
    highAvailability: { mode: 'Disabled' }
  }
}

output serverName string = postgres.name
