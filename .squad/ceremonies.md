# Ceremonies

> Team meetings that happen before or after work. Each squad configures their own.

## Design Review

| Field | Value |
|-------|-------|
| **Trigger** | auto |
| **When** | before |
| **Condition** | multi-agent task involving 2+ agents modifying shared systems |
| **Facilitator** | Ripley |
| **Participants** | all-relevant |
| **Time budget** | focused |
| **Enabled** | ✅ yes |

**Agenda:**
1. Review the task and requirements
2. Agree on interfaces and contracts between components
3. Identify risks and edge cases
4. Assign action items

---

## Retrospective

| Field | Value |
|-------|-------|
| **Trigger** | auto |
| **When** | after |
| **Condition** | build failure, test failure, or reviewer rejection |
| **Facilitator** | Ripley |
| **Participants** | all-involved |
| **Time budget** | focused |
| **Enabled** | ✅ yes |

**Agenda:**
1. What happened? (facts only)
2. Root cause analysis
3. What should change?
4. Action items for next iteration

---

## DevOps Gate

| Field | Value |
|-------|-------|
| **Trigger** | auto |
| **When** | before |
| **Condition** | any agent starting implementation work |
| **Facilitator** | Hicks |
| **Participants** | implementing agent |
| **Time budget** | minimal |
| **Enabled** | ✅ yes |

**Checklist:**
1. ✅ GitHub Issue exists with proper labels and emoji
2. ✅ Branch created from `main` with naming convention `squad/{issue}-{slug}`
3. ✅ Issue assigned to agent via `squad:{name}` label
4. Agent may proceed only after all checks pass

---

## PR Review Gate

| Field | Value |
|-------|-------|
| **Trigger** | auto |
| **When** | after |
| **Condition** | agent completes implementation and creates PR |
| **Facilitator** | Ripley |
| **Participants** | PR author + Vasquez (tests) |
| **Time budget** | focused |
| **Enabled** | ✅ yes |

**Checklist:**
1. ✅ All tests pass
2. ✅ PR description references issue with `Closes #N`
3. ✅ Code review approved by Ripley
4. ✅ No security concerns (Lambert consulted if needed)
5. Merge permitted only after all checks pass
