$ErrorActionPreference = 'Continue'
$repo = 'frdeange/verdecoraTest'

$labels = @(
  # Squad member labels (green family)
  @{ name='squad';           color='0078d4'; desc='🔵 Untriaged squad work — inbox for Lead triage' },
  @{ name='squad:ripley';    color='107c10'; desc='🏗️ Assigned to Ripley (Lead Architect)' },
  @{ name='squad:bishop';    color='107c10'; desc='🤖 Assigned to Bishop (AI Agent Dev)' },
  @{ name='squad:hicks';     color='107c10'; desc='⚙️ Assigned to Hicks (DevOps Lead)' },
  @{ name='squad:dallas';    color='107c10'; desc='☁️ Assigned to Dallas (Azure Cloud)' },
  @{ name='squad:parker';    color='107c10'; desc='🔧 Assigned to Parker (Backend Dev)' },
  @{ name='squad:lambert';   color='107c10'; desc='🔒 Assigned to Lambert (Security)' },
  @{ name='squad:vasquez';   color='107c10'; desc='🧪 Assigned to Vasquez (QA)' },
  @{ name='squad:burke';     color='107c10'; desc='📊 Assigned to Burke (BC/Dynamics)' },
  @{ name='squad:hudson';    color='107c10'; desc='📝 Assigned to Hudson (Docs)' },
  @{ name='squad:ash';       color='107c10'; desc='🔬 Assigned to Ash (MAF Specialist)' },
  @{ name='squad:newt';      color='107c10'; desc='🔌 Assigned to Newt (MCP Analyst)' },
  @{ name='squad:call';      color='107c10'; desc='🧠 Assigned to Call (Foundry)' },
  @{ name='squad:brett';     color='107c10'; desc='🔐 Assigned to Brett (Private Net/CI)' },

  # Type labels (with emojis)
  @{ name='🏗️ architecture';    color='6f42c1'; desc='Architecture decisions and design' },
  @{ name='🤖 ai-agents';       color='ff8c00'; desc='AI agent development' },
  @{ name='⚙️ devops';           color='6e7681'; desc='CI/CD, pipelines, workflows' },
  @{ name='☁️ infrastructure';   color='0dcaf0'; desc='Azure IaC (Bicep)' },
  @{ name='🔧 backend';         color='fbca04'; desc='Backend services, webhooks' },
  @{ name='🔒 security';        color='d73a49'; desc='Security, identity, compliance' },
  @{ name='🧪 testing';         color='0e8a16'; desc='Tests, QA, validation' },
  @{ name='📊 business-central'; color='0078d4'; desc='BC/Dynamics integration' },
  @{ name='📝 documentation';   color='d4c5f9'; desc='Docs, runbooks, guides' },
  @{ name='🔬 research';        color='6f42c1'; desc='Research, PoC, investigation' },
  @{ name='🔌 mcp';             color='0e8a16'; desc='MCP server integration' },
  @{ name='🧠 foundry';         color='ff8c00'; desc='Azure AI Foundry tasks' },
  @{ name='📊 observability';   color='1d76db'; desc='Monitoring, dashboards, alerts' },

  # Priority labels
  @{ name='priority:critical';  color='d73a49'; desc='🔴 Must do NOW' },
  @{ name='priority:high';      color='ff8c00'; desc='🟠 Next up' },
  @{ name='priority:medium';    color='fbca04'; desc='🟡 Normal priority' },
  @{ name='priority:low';       color='6e7681'; desc='⚪ Backlog' },

  # Phase labels
  @{ name='phase:analysis';        color='deecf9'; desc='📋 Analysis phase' },
  @{ name='phase:foundation';      color='deecf9'; desc='🏗️ Sprint 0 — Foundation' },
  @{ name='phase:implementation';  color='deecf9'; desc='💻 Sprint 1-2 — Core agents' },
  @{ name='phase:hitl';            color='deecf9'; desc='📧 Sprint 3 — HITL/Communication' },
  @{ name='phase:hardening';       color='deecf9'; desc='🔒 Sprint 4 — Security/Observability' },
  @{ name='phase:post-mvp';        color='deecf9'; desc='🚀 Post-MVP' },

  # Parallelization labels (NEW — Kiko requested)
  @{ name='⚡ parallelizable';     color='0e8a16'; desc='Can run in parallel with other tasks' },
  @{ name='🔗 sequential';         color='d93f0b'; desc='Has dependencies — must wait for blockers' },
  @{ name='🚫 blocked';            color='b60205'; desc='Blocked by another issue' },

  # PoC label
  @{ name='🔬 poc';               color='c5def5'; desc='Proof of concept task' }
)

foreach ($l in $labels) {
  $r = gh label create $l.name --repo $repo --color $l.color --description $l.desc --force 2>&1
  Write-Host "Label: $($l.name) -> $r"
}

Write-Host "`n✅ All labels created/updated." -ForegroundColor Green
