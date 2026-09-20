// Every app setting for the backend, applied after keyVaultAccess so that the
// @Microsoft.KeyVault() references below can be resolved by the site's managed
// identity. Keep this the single source of app settings -- see appService.bicep.
param webAppName string
param appInsightsConnectionString string
param keyVaultUri string
param staticWebAppHostname string
param postgresHost string
param postgresDatabase string
param postgresAdminLogin string
param defaultFromEmail string

resource webApp 'Microsoft.Web/sites@2023-01-01' existing = {
  name: webAppName
}

// vaultUri already carries a trailing slash. Omitting the secret version means
// the app always picks up the current value after a rotation.
var secretsUri = '${keyVaultUri}secrets'

resource appSettings 'Microsoft.Web/sites/config@2023-01-01' = {
  parent: webApp
  name: 'appsettings'
  properties: {
    APPLICATIONINSIGHTS_CONNECTION_STRING: appInsightsConnectionString
    KEY_VAULT_URI: keyVaultUri
    SCM_DO_BUILD_DURING_DEPLOYMENT: 'true'
    DJANGO_DEBUG: 'false'
    CORS_ALLOWED_ORIGINS: 'https://${staticWebAppHostname}'
    POSTGRES_HOST: postgresHost
    POSTGRES_DB: postgresDatabase
    POSTGRES_USER: postgresAdminLogin
    DJANGO_ADMIN_USERNAME: 'admin'
    // /home is App Service persistent storage; uploads survive restarts.
    MEDIA_ROOT: '/home/media'

    // Secrets, resolved from Key Vault by the site's managed identity.
    POSTGRES_PASSWORD: '@Microsoft.KeyVault(SecretUri=${secretsUri}/postgres-admin-password)'
    DJANGO_ADMIN_PASSWORD: '@Microsoft.KeyVault(SecretUri=${secretsUri}/django-admin-password)'
    DJANGO_SECRET_KEY: '@Microsoft.KeyVault(SecretUri=${secretsUri}/django-secret-key)'
    RESEND_API_KEY: '@Microsoft.KeyVault(SecretUri=${secretsUri}/resend-api-key)'

    // Email delivery. RESEND_API_KEY above selects the Resend backend in
    // settings.py; without it Django falls back to the console backend and
    // account-activation emails are never actually delivered. The sender domain
    // must be one verified in Resend or messages are rejected.
    DEFAULT_FROM_EMAIL: defaultFromEmail

    // Absolute links embedded in outbound email. These default to localhost,
    // which produced unusable invitations in every deployed environment.
    // NOTE: the SPA has no client-side router -- it reads ?token= off the root
    // URL (App.tsx) -- so the activation URL is the Static Web App root. Do not
    // use the '/activate' default; that path is not a real route.
    FRONTEND_BASE_URL: 'https://${staticWebAppHostname}'
    FRONTEND_LOGIN_URL: 'https://${staticWebAppHostname}'
    ACCOUNT_ACTIVATION_URL: 'https://${staticWebAppHostname}/'
  }
}
