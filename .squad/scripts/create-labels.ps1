$ErrorActionPreference = 'Continue'
$repo = 'frdeange/verdecoraTest'

# Squad member labels
$squad = @(
  @{ name='squad'; color='0078d4'; desc='Untriaged squad work' }
  @{ name='squad:ripley'; color='107c10'; desc='Assigned to Ripley (Lead Architect)' }
  @{ name='squad:bishop'; color='107c10'; desc='Assigned to Bishop (AI Agent Dev)' }
  @{ name='squad:hicks'; color='107c10'; desc='Assigned to Hicks (DevOps Lead)' }
  @{ name='squad:dallas'; color='107c10'; desc='Assigned to Dallas (Azure Cloud)' }
  @{ name='squad:parker'; color='107c10'; desc='Assigned to Parker (Backend Dev)' }
  @{ name='squad:lambert'; color='107c10'; desc='Assigned to Lambert (Security)' }
  @{ name='squad:vasquez'; color='107c10'; desc='Assigned to Vasquez (QA)' }
  @{ name='squad:burke'; color='107c10'; desc='Assigned to Burke (BC/Dynamics)' }
  @{ name='squad:hudson'; color='107c10'; desc='Assigned to Hudson (Docs)' }
  @{ name='squad:ash'; color='107c10'; desc='Assigned to Ash (MAF Specialist)' }
  @{ name='squad:newt'; color='107c10'; desc='Assigned to Newt (MCP Analyst)' }
  @{ name='squad:call'; color='107c10'; desc='Assigned to Call (Foundry)' }
  @{ name='squad:brett'; color='107c10'; desc='Assigned to Brett (Private Net/CI)' }
)

# Type labels with emoji prefix in name
$types = @(
  @{ name="$([char]0xD83C)$([char]0xDFD7) architecture"; color='6f42c1'; desc='Architecture decisions' }
  @{ name="$([char]0xD83E)$([char]0xDD16) ai-agents"; color='ff8c00'; desc='AI agent development' }
  @{ name="$([char]0x2699) devops"; color='6e7681'; desc='CI/CD pipelines workflows' }
  @{ name="$([char]0x2601) infrastructure"; color='0dcaf0'; desc='Azure IaC Bicep' }
  @{ name="$([char]0xD83D)$([char]0xDD27) backend"; color='fbca04'; desc='Backend services webhooks' }
  @{ name="$([char]0xD83D)$([char]0xDD12) security"; color='d73a49'; desc='Security identity compliance' }
  @{ name="$([char]0xD83E)$([char]0xDDEA) testing"; color='0e8a16'; desc='Tests QA validation' }
  @{ name="$([char]0xD83D)$([char]0xDCCA) business-central"; color='0078d4'; desc='BC Dynamics integration' }
  @{ name="$([char]0xD83D)$([char]0xDCDD) documentation"; color='d4c5f9'; desc='Docs runbooks guides' }
  @{ name="$([char]0xD83D)$([char]0xDD2C) research"; color='6f42c1'; desc='Research PoC investigation' }
  @{ name="$([char]0xD83D)$([char]0xDD0C) mcp"; color='0e8a16'; desc='MCP server integration' }
  @{ name="$([char]0xD83E)$([char]0xDDE0) foundry"; color='ff8c00'; desc='Azure AI Foundry tasks' }
  @{ name="$([char]0xD83D)$([char]0xDCCA) observability"; color='1d76db'; desc='Monitoring dashboards alerts' }
)

# Priority labels
$priorities = @(
  @{ name='🔴 priority:critical'; color='d73a49'; desc='Must do NOW' }
  @{ name='🟠 priority:high'; color='ff8c00'; desc='Next up' }
  @{ name='🟡 priority:medium'; color='fbca04'; desc='Normal priority' }
  @{ name='⚪ priority:low'; color='6e7681'; desc='Backlog' }
)

# Phase labels
$phases = @(
  @{ name='📋 phase:analysis'; color='deecf9'; desc='Analysis phase' }
  @{ name='🏗 phase:foundation'; color='deecf9'; desc='Sprint 0 Foundation' }
  @{ name='💻 phase:implementation'; color='deecf9'; desc='Sprint 1-2 Core agents' }
  @{ name='📧 phase:hitl'; color='deecf9'; desc='Sprint 3 HITL Communication' }
  @{ name='🔒 phase:hardening'; color='deecf9'; desc='Sprint 4 Security Observability' }
  @{ name='🚀 phase:post-mvp'; color='deecf9'; desc='Post-MVP' }
)

# Parallelization labels
$parallel = @(
  @{ name='⚡ parallelizable'; color='0e8a16'; desc='Can run in parallel with other tasks' }
  @{ name='🔗 sequential'; color='d93f0b'; desc='Has dependencies must wait for blockers' }
  @{ name='🚫 blocked'; color='b60205'; desc='Blocked by another issue' }
  @{ name='🔬 poc'; color='c5def5'; desc='Proof of concept task' }
)

$all = $squad + $types + $priorities + $phases + $parallel

foreach ($l in $all) {
  $r = gh label create $l.name --repo $repo --color $l.color --description $l.desc --force 2>&1
  Write-Host "Label: $($l.name) -> $r"
}

Write-Host ""
Write-Host "Done! All labels created/updated." -ForegroundColor Green
