# Code Review Report

| Field | Value |
|---|---|
| Mode | chat (interactive review, no external model called) |
| Commit | `feature/fix-coachee-invitation-emails` |
| Base | `main` |
| Timestamp | 2026-09-20T19:47:23.131542+00:00 |
| Diff hash | `4425dfb83bcca9d6106f7fcf0b673cd1903d96622dd457f8317875f47c977ea4` |
| Quality score | **8.0/10** |
| Verdict | **pass** |
| Findings | critical=0, high=0, medium=0, low=4 |
| Files reviewed | 22 |

## Files reviewed

- `agents/devops_agent.py`
- `docs/coaching-platform-requirements.md`
- `docs/devops-agent.md`
- `generated/backend-app/.env.example`
- `generated/backend-app/api/account_provisioning.py`
- `generated/backend-app/api/administration_serializers.py`
- `generated/backend-app/api/coachees_serializers.py`
- `generated/backend-app/api/tests/test_account_provisioning.py`
- `generated/backend-app/coaching_backend/settings.py`
- `generated/devops-agent-report.md`
- `generated/frontend-app/src/api.ts`
- `generated/frontend-app/src/components/AdministrationPanel.tsx`
- `generated/frontend-app/src/types.ts`
- `infra/azure/envs/nonprod.bicepparam`
- `infra/azure/envs/prod.bicepparam`
- `infra/azure/main.bicep`
- `infra/azure/modules/appService.bicep`
- `infra/azure/modules/appServiceSettings.bicep`
- `infra/azure/modules/keyVault.bicep`
- `infra/azure/modules/keyVaultAccess.bicep`
- `pipelines/templates/deploy.yml`
- `pipelines/templates/infra-plan.yml`

## Summary

Fixes a real defect (no email config in Azure meant Django silently used the console backend) at the right layer: IaC edits are made in agents/devops_agent.py and regenerated, honouring the 'edit the agent, not this file' contract. Secrets move from plaintext app settings into Key Vault behind managed identity, and the module split (keyVaultAccess, appServiceSettings) correctly resolves the principalId/RBAC ordering cycle rather than papering over it. Verified rather than asserted: bicep build compiles clean, 16/16 backend tests pass including new first-ever coverage of the invitation path, and frontend typechecks. Four low-severity items, none merge-blocking: (1) on a first deploy the site is created before its app settings exist, so it may boot once unconfigured and need the subsequent restart; (2) Key Vault RBAC propagation can lag, so references may briefly show unresolved on a brand-new environment - both are documented in docs/devops-agent.md with the restart remedy; (3) send_activation_email returns False for a user with no email address, conflating 'not due' with 'failed', though that path is unreachable for coachees and guarded by serializer validation for coaches; (4) no re-send-invitation endpoint exists, a pre-existing gap this change makes more visible - the admin warning was reworded so it no longer promises an action the product cannot perform. Note for the record: this review was produced by the same agent that wrote the change, so it is a self-review and should not substitute for a human pass on the security-sensitive Key Vault and RBAC wiring.
