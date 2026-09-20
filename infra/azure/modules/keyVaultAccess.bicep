// Grants the backend App Service's system-assigned identity read access to the
// Key Vault secrets it resolves at startup. Split into its own module because
// the role assignment needs the site's principalId, which only exists after the
// site is created -- declaring it on the keyVault module would be circular.
param keyVaultName string
param principalId string

// Built-in 'Key Vault Secrets User' role: get/list on secret values, nothing else.
var keyVaultSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e6'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource secretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: keyVault
  // Deterministic name so redeploys update in place instead of conflicting.
  name: guid(keyVault.id, principalId, keyVaultSecretsUserRoleId)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUserRoleId)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}

output roleAssignmentId string = secretsUser.id
