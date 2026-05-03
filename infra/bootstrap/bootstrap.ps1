[CmdletBinding()]
param(
    [string]$SubscriptionId = '0acbc8a1-0f3e-498e-b86b-6fa5468730e2',
    [string]$Location = 'swedencentral',
    [string]$Environment = 'dev',
    [string]$ResourceGroupName = 'rg-verdecoratest-dev',
    [string]$RepoUrl = 'https://github.com/frdeange/verdecoraTest',
    [string]$RunnerNamePrefix = 'verdecora',
    [string]$RunnerImage = 'ghcr.io/actions/actions-runner:latest',
    [Parameter(Mandatory = $true)]
    [SecureString]$GitHubPat
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-PlainText {
    param([SecureString]$SecureValue)

    return [pscredential]::new('unused', $SecureValue).GetNetworkCredential().Password
}

function Get-RepoParts {
    param([string]$RepositoryUrl)

    $normalized = $RepositoryUrl.Replace('https://github.com/', '').Replace('http://github.com/', '').Replace('.git', '').Trim('/')
    $segments = $normalized.Split('/')

    if ($segments.Count -lt 2) {
        throw "RepoUrl '$RepositoryUrl' must look like https://github.com/<owner>/<repo>."
    }

    return @{
        Owner = $segments[0]
        Repo = $segments[1]
    }
}

$repo = Get-RepoParts -RepositoryUrl $RepoUrl
$gitHubPatPlain = Get-PlainText -SecureValue $GitHubPat
$deploymentName = 'bootstrap-' + (Get-Date -Format 'yyyyMMddHHmmss')
$bootstrapTemplate = Join-Path $PSScriptRoot 'bootstrap.bicep'

Write-Host "Using subscription $SubscriptionId in Sweden Central for bootstrap." -ForegroundColor Cyan
az account set --subscription $SubscriptionId | Out-Null
$account = az account show --query '{subscription:id,user:user.name,tenant:tenantId}' --output json | ConvertFrom-Json
Write-Host "Azure CLI context: $($account.user) -> $($account.subscription)" -ForegroundColor DarkGray

Write-Host 'Step 1/5 - Ensuring the bootstrap resource group exists.' -ForegroundColor Cyan
az group create --name $ResourceGroupName --location $Location --output none

Write-Host 'Step 2/5 - Deploying VNet, Key Vault, runner ACA environment, and runner job.' -ForegroundColor Cyan
$deployment = az deployment sub create `
    --name $deploymentName `
    --location $Location `
    --template-file $bootstrapTemplate `
    --parameters environment=$Environment location=$Location resourceGroupName=$ResourceGroupName repoUrl=$RepoUrl runnerNamePrefix=$RunnerNamePrefix runnerImage=$RunnerImage githubPat=$gitHubPatPlain `
    --output json | ConvertFrom-Json

$runnerJobName = $deployment.properties.outputs.runnerJobName.value
$runnerEnvironmentName = $deployment.properties.outputs.runnerEnvironmentName.value
$keyVaultName = $deployment.properties.outputs.keyVaultName.value

Write-Host 'Step 3/5 - Validating Azure resources exist.' -ForegroundColor Cyan
az containerapp env show --name $runnerEnvironmentName --resource-group $ResourceGroupName --output none
az containerapp job show --name $runnerJobName --resource-group $ResourceGroupName --output none
Write-Host "Validated ACA environment '$runnerEnvironmentName', job '$runnerJobName', and Key Vault '$keyVaultName'." -ForegroundColor Green

Write-Host 'Step 4/5 - Starting one manual runner execution for GitHub registration verification.' -ForegroundColor Cyan
az containerapp job start --name $runnerJobName --resource-group $ResourceGroupName --output none

$headers = @{
    Authorization = "Bearer $gitHubPatPlain"
    Accept = 'application/vnd.github+json'
    'X-GitHub-Api-Version' = '2022-11-28'
}
$runnerApiUrl = "https://api.github.com/repos/$($repo.Owner)/$($repo.Repo)/actions/runners"
$registeredRunner = $null

for ($attempt = 1; $attempt -le 12 -and -not $registeredRunner; $attempt++) {
    Start-Sleep -Seconds 15
    $response = Invoke-RestMethod -Method Get -Uri $runnerApiUrl -Headers $headers
    $registeredRunner = $response.runners | Where-Object { $_.name -like "$RunnerNamePrefix*" } | Select-Object -First 1
    Write-Host "  Poll $attempt/12 - runner registered: $([bool]$registeredRunner)" -ForegroundColor DarkGray
}

if (-not $registeredRunner) {
    throw "Runner registration was not observed in GitHub. Inspect 'az containerapp job execution list --name $runnerJobName --resource-group $ResourceGroupName' and the GitHub repository runner page."
}

Write-Host 'Step 5/5 - Bootstrap verification succeeded.' -ForegroundColor Green
Write-Host "Runner '$($registeredRunner.name)' is visible in GitHub with status '$($registeredRunner.status)'." -ForegroundColor Green
Write-Host 'Phase 0 is complete. All subsequent deployments should now run through the self-hosted ACA runner pool.' -ForegroundColor Yellow
Write-Host 'Next hardening step: add private endpoints/private DNS, then remove temporary public access from Key Vault and the rest of the private data plane.' -ForegroundColor Yellow

$gitHubPatPlain = $null
