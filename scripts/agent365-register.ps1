param(
    [string]$ManifestPath = ".\agent365-manifest.json",
    [string]$AgentName = "external-it-helpdesk-agent"
)

if (-not (Test-Path $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}

Write-Host "Agent 365 registration preparation"
Write-Host "Agent name: $AgentName"
Write-Host "Manifest: $((Resolve-Path $ManifestPath).Path)"
Write-Host ""
Write-Host "When the Agent 365 CLI is installed, register this external agent using the CLI command documented by your SDK package."
Write-Host "Use this manifest as the agent metadata and tool inventory source."
Write-Host ""
Write-Host "After registration, set these environment variables before running the agent:"
Write-Host '$env:AGENT365_ENABLED = "true"'
Write-Host '$env:AGENT365_AGENT_ID = "<agent-id-from-registration>"'
Write-Host '$env:AGENT365_TENANT_ID = "<customer-tenant-id>"'

