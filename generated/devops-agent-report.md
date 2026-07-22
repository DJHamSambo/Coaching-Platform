# DevOps Agent Plan - coaching-platform

Generated: 2026-07-22T19:56:06.165818+00:00

## Detected application
- **backend**: django (python), database=postgresql
- **frontend**: vite+react (typescript)

## Environment: nonprod
- Region: `uksouth`
- Resource group: `rg-coaching-platform-nonprod`

| Resource | Azure service | SKU | Purpose | Est. USD/month |
|---|---|---|---|---|
| asp-coaching-platform-backend-nonprod | Azure App Service (Linux, Python) | F1 | Hosts the Django/DRF API | 0.00 |
| psql-coaching-platform-nonprod | Azure Database for PostgreSQL - Flexible Server | B1ms | Primary application database | 12.41 |
| stcoachingplatformnonpro | Azure Storage Account (Blob) | LRS | Media/resource uploads + static assets | 2.00 |
| kv-coaching-platform-non | Azure Key Vault | Standard | Secrets/connection strings/API keys (no secrets in IaC or pipeline vars) | 0.75 |
| swa-coaching-platform-nonprod | Azure Static Web Apps | Free | Hosts the built React/Vite frontend via global CDN | 0.00 |
| appi-coaching-platform-nonprod | Application Insights + Log Analytics | Basic | Telemetry, logs, alerting | 5.00 |
| aa-coaching-platform-nonprod | Azure Automation Account (runbook + schedule) | Basic | Auto-stops non-prod compute outside business hours | 1.00 |
| budget-coaching-platform-nonprod | Azure Budget | Consumption | Alerts at 50%/80%/100% of monthly budget cap | 0.00 |
| ag-coaching-platform-cost-nonprod | Azure Monitor Action Group | Standard | Routes budget alerts to email/Teams | 0.00 |
| **Total** | | | | **21.16** |

Notes:
- Auto-shutdown schedule stops the App Service/Postgres server nightly and at weekends.
- Resource group can be fully deleted (`teardown`) and rebuilt from Bicep on demand; no manual click-ops resources exist outside this IaC.

## Environment: prod
- Region: `uksouth`
- Resource group: `rg-coaching-platform-prod`

| Resource | Azure service | SKU | Purpose | Est. USD/month |
|---|---|---|---|---|
| asp-coaching-platform-backend-prod | Azure App Service (Linux, Python) | P0v3 | Hosts the Django/DRF API | 51.10 |
| psql-coaching-platform-prod | Azure Database for PostgreSQL - Flexible Server | B2s | Primary application database | 24.82 |
| stcoachingplatformprod | Azure Storage Account (Blob) | ZRS | Media/resource uploads + static assets | 3.00 |
| kv-coaching-platform-pro | Azure Key Vault | Standard | Secrets/connection strings/API keys (no secrets in IaC or pipeline vars) | 0.75 |
| swa-coaching-platform-prod | Azure Static Web Apps | Standard | Hosts the built React/Vite frontend via global CDN | 9.00 |
| appi-coaching-platform-prod | Application Insights + Log Analytics | Prod | Telemetry, logs, alerting | 25.00 |
| budget-coaching-platform-prod | Azure Budget | Consumption | Alerts at 50%/80%/100% of monthly budget cap | 0.00 |
| ag-coaching-platform-cost-prod | Azure Monitor Action Group | Standard | Routes budget alerts to email/Teams | 0.00 |
| **Total** | | | | **113.67** |

Notes:
- Resource group can be fully deleted (`teardown`) and rebuilt from Bicep on demand; no manual click-ops resources exist outside this IaC.

## Grand total (both environments): ~US$134.83/month

> Estimates only, based on Pay-As-You-Go list pricing at time of writing. Confirm with the Azure Pricing Calculator / Cost Management before relying on these figures. Nothing will be built or changed in Azure until this plan is explicitly approved (`python agents/devops_agent.py approve --environment <env>`).

Plan hash: `64e18a14372a63585afee1373e987234ed33818a0420926ec6239dad88e5c075`
