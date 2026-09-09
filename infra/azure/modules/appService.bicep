param appName string
param environmentName string
param location string
param tags object
param appInsightsConnectionString string
param keyVaultUri string
param staticWebAppHostname string
param postgresHost string
param postgresDatabase string
param postgresAdminLogin string
@secure()
param postgresAdminPassword string
@secure()
param djangoAdminPassword string

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
      appSettings: [
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'KEY_VAULT_URI', value: keyVaultUri }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'DJANGO_DEBUG', value: 'false' }
        { name: 'CORS_ALLOWED_ORIGINS', value: 'https://${staticWebAppHostname}' }
        { name: 'POSTGRES_HOST', value: postgresHost }
        { name: 'POSTGRES_DB', value: postgresDatabase }
        { name: 'POSTGRES_USER', value: postgresAdminLogin }
        { name: 'POSTGRES_PASSWORD', value: postgresAdminPassword }
        { name: 'DJANGO_ADMIN_USERNAME', value: 'admin' }
        { name: 'DJANGO_ADMIN_PASSWORD', value: djangoAdminPassword }
      ]
    }
  }
  identity: { type: 'SystemAssigned' }
}

output webAppName string = webApp.name
output defaultHostName string = webApp.properties.defaultHostName
