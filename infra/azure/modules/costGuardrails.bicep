param appName string
param environmentName string
param monthlyBudgetUsd int
param costAlertEmail string

@description('Start of the budget period. utcNow() is only valid as a parameter default in Bicep, so it cannot be inlined directly into the resource below.')
param budgetStartDate string = utcNow('yyyy-MM-01')

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-${appName}-cost-${environmentName}'
  location: 'global'
  properties: {
    groupShortName: take('cost${environmentName}', 12)
    enabled: true
    emailReceivers: [
      { name: 'cost-alert-email', emailAddress: costAlertEmail, useCommonAlertSchema: true }
    ]
  }
}

resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: 'budget-${appName}-${environmentName}'
  properties: {
    category: 'Cost'
    amount: monthlyBudgetUsd
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    notifications: {
      actual_50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        contactGroups: [actionGroup.id]
        thresholdType: 'Actual'
      }
      actual_80: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        contactGroups: [actionGroup.id]
        thresholdType: 'Actual'
      }
      forecasted_100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        contactGroups: [actionGroup.id]
        thresholdType: 'Forecasted'
      }
    }
  }
}
