param appName string
param environmentName string
param location string
param tags object
@secure()
param postgresAdminPassword string
@secure()
param djangoAdminPassword string
@secure()
param djangoSecretKey string
@secure()
param resendApiKey string

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

// The vault is the system of record for every application secret. The backend
// reads these through @Microsoft.KeyVault() app-setting references (see
// appServiceSettings.bicep) so no secret value is ever stored in site config.
resource postgresAdminPasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'postgres-admin-password'
  properties: { value: postgresAdminPassword }
}

resource djangoAdminPasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'django-admin-password'
  properties: { value: djangoAdminPassword }
}

// Signs Django sessions and JWTs. Without it the app falls back to the dev key
// committed in settings.py, i.e. tokens signed with a publicly known secret.
resource djangoSecretKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'django-secret-key'
  properties: { value: djangoSecretKey }
}

// Resend API key. Without it Django silently selects the console email backend
// and account-activation emails are written to the log instead of delivered.
resource resendApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name: 'resend-api-key'
  properties: { value: resendApiKey }
}

output vaultUri string = keyVault.properties.vaultUri
output vaultName string = keyVault.name
