param appName string
param environmentName string
param location string
param tags object
param webAppName string
param postgresServerName string

// Stops non-prod compute outside business hours (19:00-07:00 + weekends) to
// avoid paying for idle environments. Start-up is via the 'spin-up' CLI
// command or the paired start schedule/runbook below.
resource automationAccount 'Microsoft.Automation/automationAccounts@2023-11-01' = {
  name: 'aa-${appName}-${environmentName}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'Basic' }
  }
  identity: { type: 'SystemAssigned' }
}

resource stopRunbook 'Microsoft.Automation/automationAccounts/runbooks@2023-11-01' = {
  parent: automationAccount
  name: 'Stop-NonProdCompute'
  location: location
  properties: {
    runbookType: 'PowerShell'
    logProgress: true
    logVerbose: false
    description: 'Stops the non-prod Web App and Postgres Flexible Server to save cost outside business hours.'
  }
}

resource stopSchedule 'Microsoft.Automation/automationAccounts/schedules@2023-11-01' = {
  parent: automationAccount
  name: 'nightly-stop'
  properties: {
    frequency: 'Day'
    interval: 1
    startTime: '2025-01-01T19:00:00+00:00'
  }
}
