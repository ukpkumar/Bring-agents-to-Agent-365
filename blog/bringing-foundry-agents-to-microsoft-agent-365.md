---
title: "Lab Guide: Bringing Microsoft Foundry Agents to Microsoft Agent 365"
description: "A practical walkthrough for connecting Foundry-hosted agents to Microsoft Agent 365 using the Foundry-native data collection and observability path."
date: 2026-10-13
tags:
  - Microsoft Agent 365
  - Microsoft Foundry
  - Foundry Agent Service
  - Observability
  - Agent Governance
---

# Lab Guide: Bringing Microsoft Foundry Agents to Microsoft Agent 365

Microsoft Foundry Agent Service provides a managed platform for building, hosting, and running AI agents. When the agent is hosted by Foundry, the Agent 365 integration path is different from a fully custom third-party agent.

For a custom external agent, you typically register the agent with the Agent 365 CLI and add Microsoft OpenTelemetry/SDK instrumentation in your code.

For a **Foundry-hosted agent**, you usually start with the **Foundry-native Agent 365 integration**. This means configuring the Foundry resource to send agent activity data to Agent 365, then validating that the agent appears and emits activity in Agent 365.

## Why bring Foundry agents to Agent 365?

Foundry agents can become part of business-critical workflows. IT and security teams still need to answer enterprise questions:

- Which agents exist?
- Who owns them?
- Which Foundry resource hosts them?
- Are they active?
- What tools and actions are they using?
- Can security teams investigate activity?
- Can agent behavior be governed through Microsoft 365 and security admin processes?

Bringing Foundry agents into Agent 365 helps centralize visibility, governance, analytics, and security investigation across the agent estate.

## Foundry agent integration paths

Use this decision table before starting.

| Foundry scenario | Recommended Agent 365 path |
|---|---|
| Prompt agent hosted by Foundry | Use Foundry-native Agent 365 data collection |
| Voice-based prompt agent hosted by Foundry | Use Foundry-native Agent 365 data collection |
| Hosted agent using Foundry hosting libraries | Use Foundry-native data collection; grant observability app role if required |
| Hosted agent not using Foundry hosting libraries | May require explicit Agent 365 SDK/OpenTelemetry configuration in code |
| Code running outside Foundry but calling Foundry models/tools | Treat it as a custom external agent and use the Agent 365 CLI + SDK/OpenTelemetry path |

This guide focuses on the **Foundry-hosted** path.

## What this lab configures

This lab shows how to:

1. Identify the Foundry resource.
2. Enable Agent 365 data collection on that Foundry resource.
3. Check the Agent 365 data collection status.
4. Grant the Agent 365 observability app role for Hosted agents, if required.
5. Test the Foundry agent.
6. Validate activity in Agent 365.

## Important concept: resource-level setting

Agent 365 data collection for Foundry is configured at the **Foundry resource level**, not per individual agent.

The Azure resource type is:

```text
Microsoft.CognitiveServices/accounts
```

The key properties are:

| Property | Meaning |
|---|---|
| `a365LoggingEnabled` | User-controlled setting. `true` means this Foundry resource is allowed to send agent activity to Agent 365. |
| `a365Status` | Read-only status after licensing and consent checks. Values include `Enabled`, `Disabled`, and `NotLicensed`. |

Both conditions must be true for data to flow:

```text
a365LoggingEnabled = true
a365Status = Enabled
```

If `a365Status` is `NotLicensed`, the tenant/license/consent side is not ready.

## Prerequisites

You need:

- Azure subscription containing the Foundry resource
- Foundry resource name
- Resource group name
- Azure CLI installed
- Permission to update the Foundry resource, such as Owner or Contributor
- Agent 365 enabled in the Microsoft tenant
- Required Agent 365 licensing
- Tenant-level Agent 365 consent completed
- For Hosted agent observability app role assignment: Global Administrator or Application Administrator

Open **Windows PowerShell** or **Azure Cloud Shell**.

Verify Azure CLI:

```powershell
az --version
```

Sign in:

```powershell
az login
```

Select the subscription:

```powershell
az account set --subscription "<subscription-id>"
```

## Step 1: Identify the Foundry resource

You need three values:

```text
<subscription-id>
<resource-group>
<foundry-resource-name>
```

If you know the resource group, list Foundry/Azure AI resources:

```powershell
az resource list `
  --resource-group "<resource-group>" `
  --resource-type Microsoft.CognitiveServices/accounts `
  --output table
```

Find the Foundry resource name from the output.

## Step 2: Check current Agent 365 data collection status

Run:

```powershell
az resource show `
  --resource-group "<resource-group>" `
  --name "<foundry-resource-name>" `
  --resource-type Microsoft.CognitiveServices/accounts `
  --api-version 2026-03-15-preview `
  --query "properties.{a365LoggingEnabled:a365LoggingEnabled,a365Status:a365Status}"
```

Expected output after successful enablement should look like:

```json
{
  "a365LoggingEnabled": true,
  "a365Status": "Enabled"
}
```

## Step 3: Enable Agent 365 data collection

Run:

```powershell
az resource update `
  --resource-group "<resource-group>" `
  --name "<foundry-resource-name>" `
  --resource-type Microsoft.CognitiveServices/accounts `
  --api-version 2026-03-15-preview `
  --set properties.a365LoggingEnabled=true
```

This enables Agent 365 data collection for the Foundry resource.

Important: this setting applies to all projects and agents under that Foundry resource.

## Step 4: Confirm status again

Run:

```powershell
az resource show `
  --resource-group "<resource-group>" `
  --name "<foundry-resource-name>" `
  --resource-type Microsoft.CognitiveServices/accounts `
  --api-version 2026-03-15-preview `
  --query "properties.{a365LoggingEnabled:a365LoggingEnabled,a365Status:a365Status}"
```

Interpret the result:

| Result | Meaning |
|---|---|
| `a365LoggingEnabled: true`, `a365Status: Enabled` | Foundry resource is ready to send data to Agent 365 |
| `a365LoggingEnabled: true`, `a365Status: NotLicensed` | Logging is enabled, but license/tenant consent is missing |
| `a365LoggingEnabled: false` | Data collection is disabled for this Foundry resource |

## Step 5: For Hosted agents, grant observability permission if required

For Foundry Hosted agents, you may need to grant the hosted agent's Entra Agent Identity the Agent 365 observability app role:

```text
Agent365.Observability.OtelWrite
```

Skip this step for prompt agents unless your Foundry guidance says the agent identity needs this app role.

### 5.1 Get the hosted agent identity object ID

In the Azure portal:

1. Open the hosted agent application resource.
2. Open **Overview**.
3. Select **JSON View**.
4. Choose the latest API version.
5. Copy the `agentIdentityId` value.

Save it as:

```text
<AGENT_PRINCIPAL_ID>
```

### 5.2 Get the Agent365Observability service principal object ID

Run this in PowerShell:

```powershell
az rest --method GET `
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals?`$filter=displayName eq 'Agent365Observability'" `
  --query "value[0].id" `
  --output tsv
```

Save the output as:

```text
<AGENT365_OBSERVABILITY_SP_ID>
```

The app role ID is fixed:

```text
8f71190c-00c8-461d-a63b-f74abde9ba52
```

### 5.3 Create the role assignment body

Create a local file:

```powershell
notepad body.json
```

Paste:

```json
{
  "principalId": "<AGENT_PRINCIPAL_ID>",
  "resourceId": "<AGENT365_OBSERVABILITY_SP_ID>",
  "appRoleId": "8f71190c-00c8-461d-a63b-f74abde9ba52"
}
```

Replace:

- `<AGENT_PRINCIPAL_ID>`
- `<AGENT365_OBSERVABILITY_SP_ID>`

Save and close Notepad.

### 5.4 Assign the role

Run:

```powershell
az rest --method POST `
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/<AGENT_PRINCIPAL_ID>/appRoleAssignments" `
  --body "@body.json"
```

A successful request returns HTTP 201.

If you receive HTTP 409, the assignment may already exist.

### 5.5 Verify the role assignment

Run:

```powershell
az rest --method GET `
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/<AGENT_PRINCIPAL_ID>/appRoleAssignments" `
  --query "value[?appRoleId=='8f71190c-00c8-461d-a63b-f74abde9ba52']"
```

Confirm the response includes an assignment.

Role assignment propagation can take a few minutes.

## Step 6: Test the Foundry agent

Run a normal test interaction with the Foundry agent.

For a prompt agent:

1. Open the agent in Foundry.
2. Use the playground.
3. Send a test prompt.
4. Confirm the agent responds.

For a Hosted agent:

1. Invoke the hosted endpoint or test from your client application.
2. Confirm the hosted agent runs successfully.
3. Confirm there are no runtime or authentication errors.

## Step 7: Check Agent 365

Go to:

```text
https://admin.cloud.microsoft/#/agents/all
```

Look for Foundry agent activity.

Telemetry can take several minutes to appear.

## Troubleshooting

| Symptom | Likely cause | What to check |
|---|---|---|
| `a365Status` is `NotLicensed` | Agent 365 license or tenant consent is missing | Confirm Agent 365 is enabled and licensed |
| No telemetry appears | Data collection disabled or status not enabled | Check `a365LoggingEnabled` and `a365Status` |
| Hosted agent telemetry fails | Missing app role assignment | Assign `Agent365.Observability.OtelWrite` |
| `Agent365Observability` service principal not found | Agent 365 observability service not provisioned | Check tenant Agent 365 enablement |
| HTTP 403 assigning role | Insufficient permissions | Use Global Administrator or Application Administrator |
| Hosted agent identity not found | Agent not deployed or wrong resource | Recheck hosted agent resource JSON |
| Network/firewall blocks export | Outbound access restricted | Allow `agent365.svc.cloud.microsoft` on TCP 443 |

## What not to do

For a Foundry-hosted/platform-managed agent, do not start by running:

```powershell
a365 setup all
```

That command is for custom or external agent registration. Foundry-hosted agents usually use the Foundry-native integration path.

Only use the custom Agent 365 CLI + SDK path if:

- The agent code runs outside Foundry, or
- The hosted agent does not use Foundry hosting libraries and needs explicit SDK/OpenTelemetry instrumentation, or
- Microsoft guidance for your scenario says to use the SDK path.

## Summary

For Foundry-hosted agents:

```text
1. Identify the Foundry resource
2. Enable a365LoggingEnabled
3. Confirm a365Status is Enabled
4. For Hosted agents, grant observability app role if needed
5. Test the agent
6. Check Agent 365 activity
```

Foundry-native integration is the preferred starting point. Use manual Agent 365 SDK integration only when you own and run the agent code outside the Foundry-managed integration path.

