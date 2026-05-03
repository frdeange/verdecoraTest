$ErrorActionPreference = 'Continue'
$repo = 'frdeange/verdecoraTest'

$labels = @(
  @{ name='squad:ash';     color='5319e7'; desc='Architecture Lead' },
  @{ name='squad:bishop';  color='5319e7'; desc='AI Agent Developer' },
  @{ name='squad:burke';   color='5319e7'; desc='BC/ERP Integration' },
  @{ name='squad:newt';    color='5319e7'; desc='Communications/HITL' },
  @{ name='squad:brett';   color='5319e7'; desc='Networking/Runners' },
  @{ name='squad:dallas';  color='5319e7'; desc='IaC/Bicep' },
  @{ name='squad:lambert'; color='5319e7'; desc='Identity/Security' },
  @{ name='squad:hicks';   color='5319e7'; desc='DevOps Lead' },
  @{ name='squad:vasquez'; color='5319e7'; desc='QA/Testing' },
  @{ name='squad:hudson';  color='5319e7'; desc='Tech Writer' },
  @{ name='squad:parker';  color='5319e7'; desc='MCP/Backend' },
  @{ name='priority:critical'; color='b60205'; desc='Critical priority' },
  @{ name='priority:high';     color='d93f0b'; desc='High priority' },
  @{ name='priority:medium';   color='fbca04'; desc='Medium priority' },
  @{ name='priority:low';      color='0e8a16'; desc='Low priority' },
  @{ name='phase:foundation';     color='1d76db'; desc='Sprint 0' },
  @{ name='phase:implementation'; color='1d76db'; desc='Sprint 1-2' },
  @{ name='phase:hitl';           color='1d76db'; desc='Sprint 3' },
  @{ name='phase:hardening';      color='1d76db'; desc='Sprint 4' },
  @{ name='phase:post-mvp';       color='1d76db'; desc='After MVP' },
  @{ name='ai-agents';     color='c5def5'; desc='AI agents' },
  @{ name='mcp';           color='c5def5'; desc='MCP servers' },
  @{ name='services';      color='c5def5'; desc='Backend services' },
  @{ name='infra';         color='c5def5'; desc='Infrastructure' },
  @{ name='security';      color='c5def5'; desc='Security' },
  @{ name='testing';       color='c5def5'; desc='Testing' },
  @{ name='docs';          color='c5def5'; desc='Documentation' },
  @{ name='observability'; color='c5def5'; desc='Monitoring' },
  @{ name='poc';           color='c5def5'; desc='Proof of concept' }
)

foreach ($l in $labels) {
  $r = gh label create $l.name --repo $repo --color $l.color --description $l.desc --force 2>&1
  Write-Host "Label: $($l.name) -> $r"
}
