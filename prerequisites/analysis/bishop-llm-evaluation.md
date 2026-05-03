# Bishop — LLM Model Evaluation & OCR Strategy

_Date: 2026-05-03_

## 1. Current Azure OpenAI Model Landscape

The PRD references `gpt-4o` / `gpt-4.1`. Those models are still available, but they are no longer the best default starting point for a new production build.

### 1.1 Current Azure-hosted model families relevant to this project

| Family | Status in May 2026 | Relevant strengths | Recommendation for this project |
| --- | --- | --- | --- |
| GPT-5.5 | GA | Best current general model for reasoning, tools, structured outputs, image processing, long context | Use for the hardest validation/orchestration steps |
| GPT-5.4 / GPT-5 / GPT-5-mini | GA | Same modern capability set with much better cost profile than GPT-5.5 | Best default family for new production work |
| GPT-4.1 / 4.1-mini | GA | Good vision, strong coding/instruction following, structured outputs, vision fine-tuning support | Acceptable fallback, but not the best long-term default |
| o3 / o4-mini | GA | Strong reasoning, structured outputs, tool use | Good specialist options, but weaker lifecycle outlook than GPT-5 family |
| GPT-4o / 4o-mini | GA | Mature multimodal models, easy migration path from older designs | Do not start new architecture on them unless compatibility forces it |
| Claude in Foundry | Preview | Very strong reasoning/vision options, especially Opus/Sonnet | Interesting evaluation path, but not my primary production recommendation while still preview |

### 1.2 Lifecycle impact

For a new implementation, lifecycle matters almost as much as capability:

- `gpt-4o` retires on **2026-10-01**.
- `gpt-4.1`, `gpt-4.1-mini`, and `gpt-4.1-nano` retire on **2026-10-14**.
- `o3` and `o4-mini` retire on **2026-10-16**.
- GPT-5 family models extend into **2027** (for example `gpt-5.5` retires on **2027-04-23**).

**Conclusion:** even if GPT-4.x/o-series are still usable, a net-new production design should prefer **GPT-5 family models** unless there is a hard pricing or regional availability constraint.

### 1.3 Practical takeaways

- `gpt-4o` is now a migration/compatibility model, not the best future-facing default.
- `gpt-4.1` remains solid, especially where vision fine-tuning matters, but it still has a 2026 retirement horizon.
- `o3` is still attractive for reasoning-heavy tasks, but GPT-5.5 gives a better long-term platform choice.
- Claude Opus 4.7 / Sonnet 4.6 are worth keeping on the benchmark list, but because they are **preview in Foundry**, I would not make them the day-1 production baseline.

## 2. Model Recommendations per Agent (with justification)

### 2.1 Recommendation summary

| Agent | Recommended model | Why | Secondary / escalation |
| --- | --- | --- | --- |
| Agent 1 — Extraction | `gpt-5-mini` | Modern multimodal model, structured outputs, tool calling, much cheaper than flagship models; good fit when OCR is handled separately | Escalate difficult docs to `gpt-5.5`; fallback to `gpt-4.1` if GPT-5 is not yet approved in target region |
| Agent 2 — Validation | `gpt-5.5` | Best current option for comparison logic, ambiguity resolution, policy-heavy reasoning, and reliable structured decisions | `o3` if you want a reasoning-specialist benchmark; `gpt-5.4` if you need lower flagship cost |
| Agent 3 — Inventory | `gpt-5-mini` | Strong tool calling + structured output + low cost; ideal for deterministic orchestration around BC/Cosmos state | `gpt-5.4-mini` if you want more headroom; `gpt-4.1-mini` only as a temporary fallback |

### 2.2 Agent-by-agent rationale

#### Agent 1 — Extraction

This agent is **not pure OCR**. Its job is: read document context, normalize fields, resolve ambiguities, and emit a strict schema.

Why I recommend `gpt-5-mini` instead of `gpt-5.5` as the default:

- OCR should be delegated to a document-native OCR layer, not paid for twice with the most expensive LLM.
- GPT-5 mini still supports:
  - text + image processing,
  - structured outputs,
  - functions/tools,
  - parallel tool calling,
  - large context.
- For the minority of hard documents, create an **escalation path** to `gpt-5.5` instead of paying flagship rates on every albarán.

#### Agent 2 — Validation

This is the most reasoning-sensitive step:

- compare extracted fields vs Business Central order data,
- detect mismatches,
- decide whether the variance is acceptable,
- explain the result cleanly,
- produce a structured decision object.

This is where I would spend the money. `gpt-5.5` is the best fit because it combines:

- strongest current reasoning,
- structured outputs,
- tools/function calling,
- image support if needed for audit/recheck,
- the longest useful runway among the Azure OpenAI options considered here.

`o3` is still a valid benchmark candidate, but for a new production system I would pick GPT-5.5 over o3 because the platform direction is clearly moving toward GPT-5.x.

#### Agent 3 — Inventory

This agent should behave more like a **strict workflow controller** than a creative assistant.

The main requirements are:

- reliable tool invocation,
- deterministic schema output,
- idempotency awareness,
- cheap high-volume operation.

That profile fits `gpt-5-mini` very well. Agent 3 should rely more on:

- application-level idempotency keys,
- state checks in Cosmos/BC,
- explicit allowed transitions,
- schema-locked outputs,

than on “smarter” reasoning. A smaller modern model is the right default here.

### 2.3 Models I would **not** choose as the default baseline

- **`gpt-4o`**: too close to retirement for a fresh production start.
- **`gpt-4o-mini`**: cheap, but same lifecycle problem and weaker long-term posture.
- **`gpt-4.1` / `4.1-mini`**: still respectable, but GPT-5 family is the better starting point for a project beginning now.
- **`o3-mini`**: already deprecated, not appropriate for new build decisions.
- **Claude as primary prod default**: preview in Foundry, so better for benchmarking than for baseline architecture.

## 3. Document Intelligence vs LLM-Only OCR Analysis

## 3.1 Is Document Intelligence still the best OCR base for delivery notes?

**Yes — for production, yes.**

The strongest official signal from Microsoft is still in favor of a document-native OCR layer:

- Document Intelligence is described as the **trusted choice** for document-centric scenarios.
- It provides **industry-leading OCR**, table/layout extraction, confidence scores, and source grounding.
- Microsoft’s own comparison says Azure OpenAI-only approaches require preprocessing and do **not** provide built-in confidence or grounding.

That is exactly why it is still the safer base for albaranes.

## 3.2 Important correction to the PRD

The PRD assumes **Document Intelligence prebuilt invoice** will cover most delivery notes.

I would not lock onto that assumption yet.

Why:

- an **albarán is not an invoice**;
- vendor layouts can resemble invoices, but business semantics differ;
- Document Intelligence’s older general-document path is being replaced by **Layout + keyValuePairs** for generic structured documents.

### Recommended OCR baseline

Start with:

1. **Document Intelligence Read/Layout** as the universal OCR + structure extractor.
2. Use tables, key-value pairs, lines, and raw text as the grounded source.
3. Add **supplier-specific custom extraction only after error analysis proves it is necessary**.

In other words: **Read/Layout first, custom only where justified.**

## 3.3 Could a multimodal LLM do everything in one pass?

**Technically yes. Architecturally no (for production STP).**

An LLM-only approach is tempting because it simplifies the pipeline, but it creates problems that matter here:

- weaker grounding,
- weaker confidence semantics,
- more output variance,
- harder auditability,
- more expensive OCR for easy documents,
- less predictable straight-through processing.

I would only use LLM-only extraction for:

- prototypes,
- low-volume manual review workflows,
- or exceptional suppliers where the classic OCR path repeatedly fails.

## 3.4 What about GPT-4.1 / GPT-5 vision capabilities?

They absolutely help, but they do **not** remove the value of Document Intelligence.

Current multimodal models are excellent for:

- resolving ambiguous headers,
- understanding weird supplier-specific wording,
- mapping OCR text into canonical business fields,
- spotting obvious OCR misses,
- normalizing final JSON.

They are still not the best primitive for primary OCR confidence and grounded extraction.

## 3.5 Is the PRD’s “double pass” still justified?

**Yes, but not as an unconditional double pass.**

The original PRD proposes:

- Pass 1: Document Intelligence OCR
- Pass 2: multimodal LLM verifies/completes

That idea is still sound, but I would change the implementation to a **selective hybrid pipeline**:

### Recommended production strategy

**Stage A — Always run**
- Document Intelligence Read/Layout
- deterministic normalization layer
- rule-based confidence scoring

**Stage B — Only escalate when needed**
- low OCR confidence,
- missing mandatory fields,
- conflicting totals/quantities,
- unusual supplier format,
- table parsing anomalies,
- business-rule mismatch.

**Stage C — LLM reconciliation**
- use `gpt-5-mini` by default,
- escalate to `gpt-5.5` for the hardest documents.

So the answer is:

- **hybrid? yes**
- **always double-pass? no**
- **LLM-only? no, not for production baseline**

## 3.6 Alternative worth tracking

Azure **Content Understanding** is strategically interesting because it combines OCR + extraction + reasoning more natively, but Microsoft still marks key API versions/features as **preview** and explicitly says preview is **not recommended for production workloads**.

So for this release:

- **Do not replace Document Intelligence with Content Understanding yet.**
- Re-evaluate it later as a phase-2 optimization track.

## 4. Structured Output Strategy

## 4.1 Do current models support structured JSON output natively?

**Yes.** Azure OpenAI structured outputs are now the right default.

Supported current models include `gpt-4o`, `gpt-4.1`, `gpt-4.1-mini`, `o3`, `o4-mini`, and newer families.

## 4.2 Best approach

### Use this order of preference

1. **Structured Outputs with JSON Schema** (`response_format = json_schema`, `strict: true`) for final agent responses.
2. **Function/tool calling with `strict: true`** for external actions.
3. Use old **JSON mode** only as a legacy fallback.

### Why

Structured outputs give us:

- exact schema adherence,
- fewer parser failures,
- less prompt fragility,
- easier downstream validation,
- safer retries and replays.

## 4.3 Important implementation constraints

Microsoft explicitly notes:

- structured outputs are **not supported with parallel tool calls**;
- set `parallel_tool_calls = false` when schema fidelity matters;
- structured outputs are **not supported in Assistants / Foundry Agents Service**.

### Practical implication for our agents

For schema-critical steps, the agents should call Azure OpenAI **directly** through the SDK/API (Responses API or Chat Completions), not rely on Assistants/Agents abstractions.

## 4.4 Recommended implementation pattern

For each agent:

- define a versioned JSON Schema,
- use strict structured outputs,
- validate again in Python with `pydantic` or equivalent,
- reject unknown fields,
- persist both raw model response metadata and normalized domain object,
- include retry rules only for transient failures, not semantic mismatches.

### Suggested split

- **Agent 1:** strict schema output for extracted albarán payload.
- **Agent 2:** strict schema output for validation decision (`approved`, `needs_review`, `rejected`) plus machine-readable reasons.
- **Agent 3:** strict schema output for intended inventory action plan before executing tools.

## 5. Cost Estimates

## 5.1 Assumptions

These are **engineering estimates**, not billing guarantees.

Assumptions used:

- 500 albaranes/day
- 30 days/month = **15,000 albaranes/month**
- average 1 page per albarán for token estimates (OCR page costs scale separately)
- Agent 1 uses **selective LLM escalation** on ~35% of documents
- Agent 2 runs on every document
- Agent 3 runs on every document

### Estimated average token profile

| Agent | Model | Estimated average input tokens / albarán | Estimated average output tokens / albarán | Notes |
| --- | --- | ---: | ---: | --- |
| Agent 1 | `gpt-5-mini` | 1,050 | 315 | Amortized average after selective escalation; assumes OCR text + key fields, not raw full-page image on every doc |
| Agent 2 | `gpt-5.5` | 2,000 | 600 | Extraction JSON + BC order lines + validation instructions |
| Agent 3 | `gpt-5-mini` | 1,200 | 300 | Tool-planning + state check + normalized output |

## 5.2 Approximate model prices used

> These token prices are indicative estimates from current market references and should be revalidated in the Azure pricing calculator before commit.

| Model | Input / 1K tokens | Output / 1K tokens |
| --- | ---: | ---: |
| `gpt-5.5` | $0.00500 | $0.03000 |
| `gpt-5-mini` | $0.00025 | $0.00200 |
| `gpt-5.4-mini` | $0.00075 | $0.00450 |
| `gpt-4.1` | $0.00200 | $0.00800 |
| `gpt-4.1-mini` | $0.00040 | $0.00160 |
| `gpt-4o` | $0.00250 | $0.01000 |

## 5.3 Monthly estimate for the recommended setup

### Agent 1 — `gpt-5-mini`

- Input: 15,000 × 1,050 = **15.75M** tokens → **$3.94**
- Output: 15,000 × 315 = **4.725M** tokens → **$9.45**
- **Estimated monthly total: $13.39**

### Agent 2 — `gpt-5.5`

- Input: 15,000 × 2,000 = **30M** tokens → **$150.00**
- Output: 15,000 × 600 = **9M** tokens → **$270.00**
- **Estimated monthly total: $420.00**

### Agent 3 — `gpt-5-mini`

- Input: 15,000 × 1,200 = **18M** tokens → **$4.50**
- Output: 15,000 × 300 = **4.5M** tokens → **$9.00**
- **Estimated monthly total: $13.50**

### Total estimated Azure OpenAI spend

- **Approximate monthly total: $446.89**

## 5.4 OCR cost note

Document Intelligence is billed per page, so its cost profile is usually much more stable than the LLM layer.

Indicative external references place:

- Read OCR at roughly **$1.50 / 1,000 pages**,
- Prebuilt models around **$10 / 1,000 pages**,
- Custom extraction around **$30 / 1,000 pages**.

Implication:

- if we stay mostly in **Read/Layout**, OCR cost is modest;
- if we force **custom extraction for every supplier/page**, OCR can become a meaningful cost driver;
- the cheapest architecture is usually **Read/Layout + selective LLM escalation**, not unconditional custom extraction and not unconditional LLM-only OCR.

## 6. Recommendations

## Final recommendation set

1. **Do not keep GPT-4o / GPT-4.1 as the primary production baseline.**
   - They are still usable, but they are no longer the best starting point for a project beginning now.

2. **Adopt GPT-5 family as the default architecture baseline.**
   - Agent 1: `gpt-5-mini`
   - Agent 2: `gpt-5.5`
   - Agent 3: `gpt-5-mini`

3. **Keep Document Intelligence as the OCR foundation.**
   - For this problem, it is still the best production base because of OCR quality, confidence, and grounding.

4. **Change the PRD from unconditional double-pass to selective hybrid escalation.**
   - Always OCR first.
   - Call the LLM only when confidence/rules justify it.

5. **Do not assume prebuilt invoice is enough for albaranes.**
   - Start with Read/Layout.
   - Add supplier-specific custom extraction only after observing real error patterns.

6. **Use strict structured outputs everywhere.**
   - Prefer JSON Schema structured outputs over JSON mode.
   - Use strict function schemas for tool calls.
   - Set `parallel_tool_calls = false` for schema-critical steps.

7. **Treat Claude as a benchmark candidate, not the baseline.**
   - Claude Opus 4.7 and Sonnet 4.6 are worth evaluating later, but preview status in Foundry makes them a phase-2 experiment, not the day-1 choice.

## Suggested next action

Run a short bake-off on 100 real albaranes:

- **Pipeline A:** Document Intelligence Read/Layout only
- **Pipeline B:** Read/Layout + `gpt-5-mini` selective reconciliation
- **Pipeline C:** Read/Layout + `gpt-5.5` on low-confidence subset only

Measure:

- field-level F1,
- straight-through rate,
- human-review rate,
- average latency,
- total cost per document.

That will validate the architecture with production-like evidence before locking implementation.

## Sources

- Azure OpenAI model catalog: https://learn.microsoft.com/azure/ai-foundry/openai/concepts/models
- Foundry model retirement schedule: https://learn.microsoft.com/azure/foundry/openai/concepts/model-retirement-schedule
- Structured outputs: https://learn.microsoft.com/azure/ai-foundry/openai/how-to/structured-outputs
- Function calling: https://learn.microsoft.com/azure/foundry/openai/how-to/function-calling
- Reasoning models: https://learn.microsoft.com/azure/foundry/openai/how-to/reasoning
- Vision-enabled chat: https://learn.microsoft.com/azure/ai-foundry/openai/how-to/gpt-with-vision
- Document Intelligence Read model: https://learn.microsoft.com/azure/ai-services/document-intelligence/prebuilt/read?view=doc-intel-4.0.0
- Choosing the right Azure document tool: https://learn.microsoft.com/azure/ai-services/content-understanding/choosing-right-ai-tool
- Claude in Foundry: https://learn.microsoft.com/azure/foundry/foundry-models/how-to/use-foundry-models-claude
- Supplemental market/pricing checks used only for rough estimates: Azure/OpenAI/Claude pricing trackers and vendor pricing pages searched on 2026-05-03
