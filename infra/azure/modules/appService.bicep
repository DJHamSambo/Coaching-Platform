param appName string
param environmentName string
param location string
param tags object

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
      // Apply migrations and seed the initial staff user before serving.
      appCommandLine: 'python manage.py migrate --noinput && python manage.py ensure_admin && gunicorn --bind=0.0.0.0:8000 --timeout 600 coaching_backend.wsgi'
      // App settings are deliberately NOT declared here. They live in
      // appServiceSettings.bicep, which runs after the Key Vault role
      // assignment so that @Microsoft.KeyVault() references can resolve.
      // Declaring them in both places makes the two overwrite each other.
    }
  }
  identity: { type: 'SystemAssigned' }
}

output webAppName string = webApp.name
output defaultHostName string = webApp.properties.defaultHostName
// Consumed by keyVaultAccess.bicep to grant this site read access to secrets.
output principalId string = webApp.identity.principalId
