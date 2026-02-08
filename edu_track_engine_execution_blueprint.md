# EduTrack Engine – Intern Execution Blueprint (Zero-Assumption Edition)

> **Constraint**: This is the bible for execution of this project 

---

## 0. Absolute Operating Rules (Non‑Negotiable)

1. **Never guess curriculum data**  
   If the system is unsure, it must ask the user or pause.

2. **Never block the UI**  
   All scraping, OCR, parsing, and embedding are background jobs.

3. **Never generate content without sources**  
   Every output must map to verified curriculum text.

4. **Never assume jurisdiction**  
   Jurisdiction must be inferred with confidence or clarified.

5. **When in doubt: stop, log, and escalate**  
   Silent failure is forbidden.

---

## 1. System Overview (What You Are Building)

EduTrack is a **curriculum intelligence engine**.

It:

- Accepts a user request for a curriculum
- Checks if it already exists
- If not, fetches and verifies it from official sources
- Stores it with provenance
- Generates structured educational outputs

It does **not**:

- Host copyrighted curricula verbatim without permission
- Guess missing information
- Run heavy computation in the UI

---

## 2. Core Architecture (Fixed)

```
[ Streamlit UI ]
      |
      v
[ Request Controller ]
      |
      v
[ Decision Engine ]  <-- this document defines its rules
      |
      +--> [ LangGraph Orchestrator ]
              |
              +--> Redis Queue
                      |
                      +--> Worker: Scout
                      +--> Worker: Gatekeeper
                      +--> Worker: Architect
                      +--> Worker: Embedder

[ Data Layer ]
  - Supabase Postgres
  - pgvector
  - Object Storage (PDF snapshots)
```

---

## 3. Canonical Data Models (Do Not Modify)

### 3.1 Curriculum Table

Required fields:

| Field                  | Description                 |
| ---------------------- | --------------------------- |
| id                     | UUID                        |
| country                | Human name                  |
| country_code           | ISO‑2                       |
| jurisdiction_level     | national / state / county   |
| jurisdiction_name      | nullable                    |
| parent_jurisdiction_id | nullable                    |
| grade                  | normalized                  |
| subject                | canonical                   |
| status                 | active / stale / conflicted |
| confidence_score       | 0.0 – 1.0                   |
| last_verified          | date                        |
| ttl_expiry             | date                        |

---

## 4. Request Handling (Step‑by‑Step)

### 4.1 Input Normalization (Always First)

Input example:

> "Grade 9 Biology curriculum for Nigeria"

Normalize:

- Country → ISO‑2
- Grade → canonical grade
- Subject → canonical subject

If normalization fails → reject request politely.

---

## 5. Jurisdiction Decision Framework (Critical Section)

### 5.1 Jurisdiction Ambiguity Score (JAS)

Compute JAS using the following signals:

| Signal                                | Weight |
| ------------------------------------- | ------ |
| Country has multiple active curricula | +0.4   |
| Subject managed below national level  | +0.3   |
| Multiple cached curricula exist       | +0.2   |
| Grade naming conflict                 | +0.1   |

**JAS Range:** 0.0 – 1.0

---

### 5.2 Jurisdiction Decision Thresholds

| JAS Score | Action                         |
| --------- | ------------------------------ |
| < 0.4     | Assume national silently       |
| 0.4 – 0.7 | Ask ONE clarification question |
| > 0.7     | Require explicit jurisdiction  |

---

### 5.3 Clarification Rules (Strict)

You may ask **only one question at a time**.

Allowed question:

> “Do you want the **National curriculum**, or a **State / County‑specific** one?”

Buttons:

- National (recommended)
- State / County

If user chooses State / County:

> “Which state or county?”

Never ask for:

- Authority name
- Education board
- Curriculum framework

---

## 6. Vault Lookup Logic

Query order:

1. Exact jurisdiction match
2. Parent jurisdiction
3. National

If found with confidence ≥ 0.8 → serve immediately.

If found but confidence < 0.8 → warn user + offer refresh.

If not found → enqueue cold‑start job.

---

## 7. Cold‑Start Agent Execution

### 7.1 Scout Agent (Search)

Rules:

- Max 5 queries
- Official domains first
- Headless browser only

Failure → retry once → then pause job.

---

### 7.2 Gatekeeper Agent (Validation)

Validation checklist:

- Official authority
- Current or explicitly valid
- License status known

Assign confidence score:

| Condition              | Score          |
| ---------------------- | -------------- |
| Official + current     | 0.9–1.0        |
| Official but ambiguous | 0.6–0.8        |
| Unofficial             | < 0.5 (reject) |

---

### 7.3 Architect Agent (Parsing)

Pipeline (mandatory order):

1. Structured extraction
2. Table parsing
3. OCR fallback
4. LLM structuring

Each competency gets its own confidence score.

If average < 0.75 → flag for human alert.

---

## 8. Legal & License Enforcement

### 8.1 License States

| License    | Output Allowed          |
| ---------- | ----------------------- |
| Permissive | Full structured content |
| Unclear    | Abstracted replica      |
| Restricted | Metadata + link only    |

Replica rules:

- No verbatim copying
- No paragraph‑level similarity
- Educational abstraction only

---

## 9. Generation Guardrails

Generation is allowed **only if**:

- Coverage ≥ 80% of requested competencies
- Every paragraph maps to ≥1 source

Otherwise → reject generation.

---

## 10. Human‑in‑the‑Loop (Minimal)

Humans are notified only when:

- User flags an error
- Confidence < threshold
- Legal ambiguity detected

Human actions:

- Confirm error → re‑scrape
- Dismiss → log reason
- Restrict output → enforce replica mode

---

## 11. What You Must NOT Do

- ❌ Guess jurisdiction
- ❌ Run OCR in Streamlit
- ❌ Store PDFs without metadata
- ❌ Generate lessons without citations
- ❌ Ignore confidence thresholds

---

## 12. Definition of “Done”

The system is correct when:

- Users get instant results for cached curricula
- Ambiguity triggers one clear question
- Errors are rare and traceable
- Humans intervene <5% of requests

---

## 13. Agent I/O JSON Schemas (Authoritative)

This section defines the **only allowed inputs and outputs** for every agent.  
If data does not match these schemas, **the agent must fail fast**.

---

## 13.1 Request Normalization Output (Controller → Decision Engine)

```json
{
  "request_id": "uuid",
  "raw_prompt": "string",
  "normalized": {
    "country": "string",
    "country_code": "ISO-2",
    "grade": "string",
    "subject": "string",
    "language": "string"
  },
  "confidence": 0.0,
  "timestamp": "ISO-8601"
}
```

**Validation rules**:

- confidence < 0.7 → reject request
- missing normalized fields → reject request

---

## 13.2 Jurisdiction Resolution Output (Decision Engine)

```json
{
  "request_id": "uuid",
  "jurisdiction": {
    "level": "national | state | county",
    "name": "string | null",
    "parent": "uuid | null"
  },
  "jas_score": 0.0,
  "assumption_type": "assumed | user_confirmed | explicit",
  "confidence": 0.0
}
```

**Rules**:

- jas_score > 0.7 AND assumption_type = assumed → INVALID
- confidence < 0.6 → must ask user

---

## 13.3 Vault Lookup Output (Controller)

```json
{
  "request_id": "uuid",
  "found": true,
  "curriculum_id": "uuid",
  "confidence": 0.0,
  "source": "cache | parent | national"
}
```

If `found = false`, enqueue cold-start job.

---

## 13.4 Scout Agent Output (Search)

```json
{
  "job_id": "uuid",
  "queries": ["string"],
  "candidate_urls": [
    {
      "url": "string",
      "domain": "string",
      "rank": 1,
      "authority_hint": "official | unknown"
    }
  ],
  "status": "success | failed"
}
```

**Rules**:

- queries.length ≤ 5
- candidate_urls.length ≥ 1 OR status = failed

---

## 13.5 Gatekeeper Agent Output (Validation)

```json
{
  "job_id": "uuid",
  "approved_sources": [
    {
      "url": "string",
      "authority": "string",
      "license": "permissive | unclear | restricted",
      "published_date": "YYYY-MM-DD",
      "confidence": 0.0
    }
  ],
  "rejected_sources": ["string"],
  "status": "approved | conflicted | failed"
}
```

**Rules**:

- approved_sources.length = 0 → failed
- status = conflicted → require human alert

---

## 13.6 Architect Agent Output (Parsing)

```json
{
  "job_id": "uuid",
  "curriculum_snapshot": {
    "file_path": "s3://...",
    "checksum": "sha256",
    "pages": 0
  },
  "competencies": [
    {
      "competency_id": "uuid",
      "title": "string",
      "description": "string",
      "learning_outcomes": ["string"],
      "page_range": "string",
      "confidence": 0.0
    }
  ],
  "average_confidence": 0.0,
  "status": "success | low_confidence | failed"
}
```

**Rules**:

- average_confidence < 0.75 → low_confidence
- competencies.length = 0 → failed

---

## 13.7 Embedder Output

```json
{
  "curriculum_id": "uuid",
  "embedded_chunks": 0,
  "embedding_model": "string",
  "status": "success | failed"
}
```

---

## 13.8 Generation Request Input

```json
{
  "curriculum_id": "uuid",
  "request_type": "lesson_plan | quiz | summary",
  "constraints": {
    "duration": "string",
    "offline_friendly": true
  }
}
```

---

## 13.9 Generation Output (Strictly Enforced)

```json
{
  "output_id": "uuid",
  "content": "string",
  "citations": [
    {
      "competency_id": "uuid",
      "page_range": "string"
    }
  ],
  "coverage": 0.0,
  "status": "approved | rejected"
}
```

**Rules**:

- coverage < 0.8 → rejected
- citations.length = 0 → rejected

---

## Final Instruction to Intern

If any agent output violates its schema:

1. Stop execution
2. Log the error
3. Escalate

**Schemas are law.**

---

## 14. LangGraph Node Diagram & State Machine (Authoritative)

This section defines the **exact execution graph**. No nodes may be skipped or reordered.

---

### 14.1 High-Level LangGraph Flow

```
[ START ]
    |
    v
[ NormalizeRequest ]
    |
    v
[ ResolveJurisdiction ]
    |
    v
[ VaultLookup ]
    |        \
    |         \
FOUND       NOT FOUND
    |             \
    v              v
[ Generate ]   [ EnqueueColdStart ]
                    |
                    v
              [ ScoutAgent ]
                    |
                    v
              [ GatekeeperAgent ]
                    |
          +---------+----------+
          |                    |
     APPROVED              CONFLICT / FAIL
          |                    |
          v                    v
   [ ArchitectAgent ]     [ HumanAlert ]
          |
          v
     [ Embedder ]
          |
          v
     [ VaultStore ]
          |
          v
     [ Generate ]
          |
          v
        [ END ]
```

---

### 14.2 Node-by-Node Responsibilities

#### NormalizeRequest

- Input: raw user prompt
- Output: normalized request schema (13.1)
- Failure → user-facing rejection

#### ResolveJurisdiction

- Computes JAS score
- May pause graph awaiting user clarification
- Output schema: 13.2

#### VaultLookup

- Queries Postgres in strict order
- Output schema: 13.3

#### EnqueueColdStart

- Creates job_id
- Pushes job to Redis
- Returns immediately to UI

#### ScoutAgent

- Runs asynchronously
- Output schema: 13.4

#### GatekeeperAgent

- Validates authority, freshness, license
- Output schema: 13.5

#### ArchitectAgent

- Parses curriculum into atomic competencies
- Output schema: 13.6

#### Embedder

- Creates vector embeddings
- Output schema: 13.7

#### VaultStore

- Writes Postgres + Vector + Object Storage
- Sets TTL + confidence

#### Generate

- Produces lesson / quiz / summary
- Enforces grounding rules
- Output schema: 13.9

---

### 14.3 State Transitions (Strict)

| From State          | To State            | Condition                         |
| ------------------- | ------------------- | --------------------------------- |
| NormalizeRequest    | ResolveJurisdiction | valid normalization               |
| ResolveJurisdiction | VaultLookup         | confidence ≥ 0.6                  |
| ResolveJurisdiction | WAIT_USER           | confidence < 0.6                  |
| VaultLookup         | Generate            | found = true AND confidence ≥ 0.8 |
| VaultLookup         | EnqueueColdStart    | found = false                     |
| ScoutAgent          | GatekeeperAgent     | urls found                        |
| GatekeeperAgent     | ArchitectAgent      | status = approved                 |
| GatekeeperAgent     | HumanAlert          | status = conflicted               |
| ArchitectAgent      | Embedder            | avg_confidence ≥ 0.75             |
| ArchitectAgent      | HumanAlert          | avg_confidence < 0.75             |
| Embedder            | VaultStore          | success                           |
| VaultStore          | Generate            | write successful                  |

Invalid transitions MUST throw errors.

---

## 15. Failure-Mode Playbook (Mandatory Reference)

This section defines **what breaks, how it is detected, and how the system recovers**.

---

### 15.1 Failure Classification

| Class  | Meaning                       |
| ------ | ----------------------------- |
| USER   | Bad or ambiguous input        |
| DATA   | Missing or invalid curriculum |
| AGENT  | Tool or model failure         |
| LEGAL  | License or copyright risk     |
| SYSTEM | Infra or service failure      |

---

### 15.2 Failure Modes & Recovery Actions

#### F1 — Ambiguous Jurisdiction

- Detected by: JAS ≥ 0.4
- Recovery: Ask one clarification question
- Human involved: ❌

---

#### F2 — No Official Source Found

- Detected by: Gatekeeper approved_sources = 0
- Recovery:
  - Pause job
  - Notify user
  - Allow manual link upload
- Human involved: ❌

---

#### F3 — Conflicting Official Sources

- Detected by: Gatekeeper status = conflicted
- Recovery:
  - Mark curriculum status = conflicted
  - Alert human reviewer
- Human involved: ✅

---

#### F4 — Low OCR / Parsing Confidence

- Detected by: avg_confidence < 0.75
- Recovery:
  - Store data as draft
  - Alert human
- Human involved: ✅

---

#### F5 — License Unclear or Restricted

- Detected by: license = unclear / restricted
- Recovery:
  - Enforce replica-only mode
  - Attach attribution link
- Human involved: ❌ (unless disputed)

---

#### F6 — Hallucination Risk

- Detected by: coverage < 0.8 OR missing citations
- Recovery:
  - Reject generation
  - Log error
- Human involved: ❌

---

#### F7 — Worker Crash / Timeout

- Detected by: missing heartbeat
- Recovery:
  - Retry once
  - If repeated → mark failed
- Human involved: ❌

---

#### F8 — User Reports Error

- Detected by: thumbs-down feedback
- Recovery:
  - Flag curriculum
  - Trigger re-verification
- Human involved: ✅ (review outcome only)

---

## Final Enforcement Rule

If a failure mode is not listed here:

1. Stop the graph
2. Log full state
3. Escalate

**Undefined behavior is a bug.**

---

## 15.1 Gemini API Configuration (Zero-Cost Stack)

This section defines the **exact API configuration** for the Gemini-based model stack.

---

### Primary Models

| Model | API Name | Use Case |
| ----- | -------- | -------- |
| Gemini 2.0 Flash | `gemini-2.0-flash` | Low/Medium complexity tasks |
| Gemini 1.5 Pro | `gemini-1.5-pro` | High/Critical complexity tasks |
| Gemini 2.0 Flash Vision | `gemini-2.0-flash` (with image) | PDF OCR fallback |

---

### Free Tier Rate Limits (Enforced)

| Model | RPM | TPM | Daily Limit |
| ----- | --- | --- | ----------- |
| Gemini 2.0 Flash | 15 | 1,000,000 | 1,500 requests |
| Gemini 1.5 Pro | 2 | 32,000 | 50 requests |

**Handling:**
- Implement request queuing with exponential backoff
- Cache-first design reduces actual API calls by 70%+
- If limits hit → degrade gracefully, never fail silently

---

### Structured Output Configuration (Mandatory)

All Gemini calls MUST use:

```python
generation_config = {
    "response_mime_type": "application/json",
    "response_schema": <PYDANTIC_MODEL>.model_json_schema()
}
```

**Rules:**
- Every agent output schema (Section 13) must be passed as `response_schema`
- If JSON parsing fails → retry once → then reject
- Never trust unvalidated output

---

### Prompt Engineering Guidelines (Gemini-Specific)

1. **Chain-of-Thought Required**: For complex tasks, include:
   > "Think step-by-step before providing your final answer."

2. **Explicit Schema Reference**: Always include:
   > "Your response MUST be valid JSON matching the following schema: ..."

3. **Single-Purpose Prompts**: Break complex multi-step instructions into atomic prompts

4. **Self-Verification**: For critical tasks, add:
   > "Before responding, verify that your answer is grounded in the provided sources."

---

### Vision API Configuration (PDF Fallback)

When using Gemini Vision for scanned PDFs:

```python
contents = [
    {"mime_type": "application/pdf", "data": base64_pdf_data},
    {"text": "Extract all competencies and learning outcomes..."}
]
```

**Rules:**
- Only use Vision when PyMuPDF + Marker fail to extract text
- Maximum 20 pages per request (split larger documents)
- Confidence threshold: 0.7 (lower than text-based parsing)

---

### API Key Management

- Store in environment variable: `GOOGLE_AI_API_KEY`
- Never log API keys
- Rotate keys if rate limited excessively

---

## 16. Operational Runbooks (Human-in-the-Loop, Minimal)

### 16.1 When Humans Are Notified (Strict Criteria Only)

Humans are **never** involved in normal flow. Notification is triggered **only** when:

| Trigger            | Condition                           | Action                        |
| ------------------ | ----------------------------------- | ----------------------------- |
| Curriculum dispute | User feedback confidence ≥ 0.85     | Send alert to Ops dashboard   |
| Source ambiguity   | ≥2 official sources conflict        | Pause auto-store, flag review |
| Legal risk         | License / copyright unclear         | Switch to replica-only mode   |
| Systemic failure   | Same failure occurs ≥3 times in 24h | Escalate infra review         |

Notification channels:

- Railway logs (primary)
- Slack / Email webhook (secondary)

No human may edit curriculum directly. All edits must go through re-ingestion.

---

## 17. Failure-Mode Playbooks (Actionable)

### 17.1 Search Failure

**Symptoms:**

- No qualifying domains found
- CAPTCHA blocks

**Recovery:**

1. Retry with reduced query count (≤3)
2. Switch to browser-based scraper
3. If still failing → ask user for link or upload

---

### 17.2 Validation Failure

**Symptoms:**

- Document too old
- Metadata missing

**Recovery:**

1. Cross-check “current” labels on official site
2. Lower freshness threshold ONLY if official confirmation exists
3. Else → reject ingestion

---

### 17.3 Parsing Failure

**Symptoms:**

- OCR confidence < 0.7
- Structural corruption

**Recovery:**

1. Retry with vision-based OCR
2. Segment pages manually (automated)
3. If still failing → reject + notify user

---

### 17.4 Generation Guard Failure

**Symptoms:**

- Output references unseen topic

**Recovery:**

1. Hard stop generation
2. Log hallucination attempt
3. Re-run with stricter context window

---

## 18. Test Matrix (Intern Must Implement All)

### 18.1 Unit Tests

| Component         | Test Case                    |
| ----------------- | ---------------------------- |
| Intent Classifier | Reject non-educational input |
| Scout             | Generates ≤5 queries         |
| Gatekeeper        | Rejects outdated docs        |
| Parser            | Produces valid JSON schema   |
| Generator         | Zero hallucinated topics     |

---

### 18.2 Integration Tests

| Scenario             | Expected Outcome           |
| -------------------- | -------------------------- |
| Cache hit            | Phase 2 skipped            |
| Cache miss           | Full swarm executed        |
| Partial failure      | Graceful user prompt       |
| County-level request | Correct jurisdiction match |

---

### 18.3 Adversarial / Edge Tests

- Fake .gov domain
- Watermarked scanned PDFs
- Conflicting state vs national curriculum
- User provides wrong jurisdiction

All must fail safely.

---

## 19. Telemetry, Metrics & Health Signals

### 19.1 Core Metrics

| Metric               | Healthy Threshold |
| -------------------- | ----------------- |
| Cache hit rate       | ≥ 70%             |
| OCR confidence avg   | ≥ 0.8             |
| User thumbs-up       | ≥ 85%             |
| Hallucination blocks | ≤ 1%              |

---

### 19.2 Logs (Mandatory Fields)

- curriculum_id
- jurisdiction_level
- source_domains
- verification_confidence
- failure_reason (if any)

---

### 19.3 Kill Switches

| Switch             | Effect                |
| ------------------ | --------------------- |
| Disable ingestion  | Serve cache only      |
| Disable generation | Data-only mode        |
| Disable replicas   | Source-only summaries |

---

## 20. Final Intern Rules (Non-Negotiable)

1. Never bypass schema validation
2. Never allow generation without retrieval
3. Never store copyrighted material verbatim
4. Never assume jurisdiction — always resolve
5. If unsure → system pauses, not guesses
6. **Never store replica content without hallucination verification**

---

## 20.1 Replica Hallucination Control Framework (Critical)

### Core Principle

A stored replica must be **provably derivable** from retrieved source material.
Anything not grounded is treated as contamination and rejected.

---

### Replica Construction Pipeline (Mandatory)

1. **Extraction Phase (Non-Generative)**
   
   - Use extract-only models or tools
   - Output: raw concepts, headings, objectives
   - No rewriting allowed

2. **Normalization Phase (Constrained Generation)**
   
   - Convert extracted items into atomic competencies
   - Strict schema enforcement
   - Max abstraction level predefined

3. **Grounding Verification Phase (Gatekeeper++)**
   Each atomic competency must:
   
   - Reference ≥1 source chunk ID
   - Pass semantic similarity threshold

---

### Hallucination Detection Checks

| Check                 | Method                       | Fail Action    |
| --------------------- | ---------------------------- | -------------- |
| Source coverage       | Every field cites source IDs | Reject replica |
| Semantic overlap      | Cosine similarity ≥ 0.75     | Reject item    |
| Novel token detection | New domain terms flagged     | Escalate       |
| Shadow diff           | Premium vs primary delta     | Rebuild        |

---

### Forbidden Replica Patterns

- Composite topics not explicitly stated
- Cross-grade extrapolation
- Pedagogical additions ("students should also learn")
- Reintroduced deprecated topics

Any detection → hard stop.

---

### Storage Guardrail

Replica is persisted **only if**:

- 100% of competencies grounded
- Zero forbidden patterns detected
- Confidence score = 1.0 (binary)

Otherwise:

- Replica is discarded
- System retries or pauses

---

## 21. Cost-Aware Model Routing + Fallback Ladder (Anti-Limbo Design)

### 21.1 Core Principle

Model selection is **task-weighted**. Cheap, fast models handle bounded, low-risk tasks. Expensive models are reserved **only** where accuracy, reasoning depth, or vision is critical.

Every node therefore has:

- A **primary model (cost-optimized)**
- A **high-accuracy escalation model**
- A **deterministic fallback**

This prevents cost bleed *and* limbo states.

---

### 21.2 Task → Model Assignment Matrix

| Task                         | Complexity | Risk     | Primary Model         | Escalation Model        | Deterministic Fallback |
| ---------------------------- | ---------- | -------- | --------------------- | ----------------------- | ---------------------- |
| Intent classification        | Low        | Low      | Gemini 2.0 Flash      | Gemini 1.5 Pro          | Rule-based             |
| Query generation             | Low        | Medium   | Gemini 2.0 Flash      | Gemini 1.5 Pro          | Template rules         |
| Jurisdiction resolution      | Medium     | High     | Gemini 2.0 Flash      | Gemini 1.5 Pro          | Lookup tables          |
| Source validation            | Medium     | High     | Gemini 2.0 Flash      | Gemini 1.5 Pro          | Heuristic rules        |
| PDF parsing                  | High       | High     | PyMuPDF + Marker      | Gemini 2.0 Flash Vision | Regex + layout         |
| Atomic competency extraction | High       | Critical | Gemini 1.5 Pro        | Gemini 1.5 Pro + retry  | Abort                  |
| Lesson / quiz generation     | High       | Critical | Gemini 1.5 Pro        | Gemini 1.5 Pro + retry  | Abort                  |

> [!NOTE]
> **Cost Strategy**: Gemini 2.0 Flash and Gemini 1.5 Pro both offer generous free tiers.
> - Gemini 2.0 Flash: 15 RPM, 1M tokens/min, 1500 requests/day (FREE)
> - Gemini 1.5 Pro: 50 requests/day, 32K tokens/request (FREE)
> - PDF parsing uses open-source tools first, Gemini Vision only as fallback

**Rule:** Any task marked *Critical* may not proceed without a high-confidence model.

---

### 21.3 Escalation Logic

Each node evaluates:

- Input complexity score
- Confidence score from primary model

If confidence < threshold → escalate to higher model.
If escalation fails → deterministic fallback or halt.

No task auto-escalates without justification.

---

### 21.4 Fallback Tiers (Enforced)

#### Tier 0 — Cost-Optimized Path

Default execution.

#### Tier 1 — Accuracy Escalation

Triggered by low confidence or partial failure.

#### Tier 2 — Deterministic Safe Mode

Triggered after 2 failures or timeout > X seconds.

**Tier 2 rules:**

- No generation
- No inference beyond extraction
- No storage of new curriculum

---

### 21.5 LangGraph Enforcement

Each LangGraph node must emit:

- `model_used`
- `confidence_score`
- `fallback_tier`

State transitions depend on these fields.

---

## 22. Synthetic Curriculum Simulators (Accuracy Booster)

### 22.1 Purpose

Synthetic curricula are **ground-truth-like test fixtures**, not real curricula.
They are used to:

- Stress-test parsers
- Validate hallucination guards
- Simulate edge jurisdictions

They are never shown to users.

---

### 22.2 Simulator Design

Each simulator generates:

- Fake country / state / county
- Official-looking metadata
- Realistic PDF layouts (tables, scans, watermarks)
- Controlled changes (topic removed, renamed, merged)

---

### 22.3 Simulator Schema

```json
{
  "synthetic_id": "SIM-KENYA-COUNTY-V1",
  "jurisdiction": "county",
  "structure_noise": 0.6,
  "ocr_noise": 0.4,
  "known_ground_truth": {
    "topics": ["Cell Division", "Genetics"],
    "removed_topics": ["Photosynthesis"]
  }
}
```

---

### 22.4 How Intern Uses Simulators

1. Run full ingestion pipeline
2. Compare output vs `known_ground_truth`
3. Measure:
   - Topic loss
   - Hallucination rate
   - Jurisdiction misclassification

Failing scores block deployment.

---

## 23. Confidence Threshold Table (Global)

| Stage                   | Minimum Confidence |
| ----------------------- | ------------------ |
| Intent classification   | 0.85               |
| Jurisdiction resolution | 0.8                |
| Source validation       | 0.9                |
| OCR parsing             | 0.7                |
| Generation grounding    | 1.0 (binary)       |

Anything below threshold → pause, retry, or ask user.

---

## 24. Cost Governance & Shadow Execution (Elite Safeguards)

### 24.1 Monthly Cost Budget Guards

Each LangGraph node must declare:

- `max_monthly_cost_usd`
- `cost_per_call_estimate`

Execution rule:

- If projected monthly spend > budget → node auto-downgrades to Tier 1
- If Tier 1 budget also exceeded → Tier 2 or halt

Budgets are enforced **before** execution, not after billing.

---

### 24.2 Shadow Execution Mode (Accuracy Drift Detection)

For *critical nodes only* (Parser, Architect, Generator):

- Run primary model
- Silently run secondary high-accuracy model
- Compare:
  - topic overlap
  - structure similarity
  - confidence delta

Shadow results:

- Never shown to user
- Logged for offline analysis

If drift exceeds threshold → escalate model permanently for that task.

---

## 25. Final System Audit (Brutal)

### 25.1 Architectural Soundness

| Area                  | Status | Notes                               |
| --------------------- | ------ | ----------------------------------- |
| Lazy loading          | PASS   | Cache-first logic airtight          |
| Jurisdiction handling | PASS   | Explicit resolution, no assumptions |
| Legal exposure        | PASS   | Replica-only, no verbatim storage   |
| Hallucination control | PASS   | Generation strictly retrieval-bound |
| Cost control          | PASS   | Budget + routing + fallback         |

No fatal design flaws found.

---

### 25.2 Identified Weak Points (Acceptable)

1. OCR on poor scans may still fail → correctly halts
2. Some countries lack digital curricula → user upload required
3. County-level coverage depends on source availability

All are **correctly handled** by pause-and-ask logic.

---

### 25.3 Explicit Non-Problems (Do Not Over-Engineer)

- Real-time curriculum updates
- Perfect OCR accuracy
- Universal jurisdiction coverage

Attempting these will reduce system reliability.

---

## 26. Execution Roadmap (Intern-Proof)

### Phase A — Foundations

1. Set up Supabase (DB + pgvector)
2. Define all schemas as Pydantic models
3. Implement schema validation middleware

---

### Phase B — LangGraph Core

1. Implement state machine exactly as specified
2. Enforce confidence gates and fallback tiers
3. Add cost guards to every node

---

### Phase C — Ingestion Swarm

1. Scout → Gatekeeper → Parser chain
2. Synthetic simulator tests must pass
3. No curriculum stored without verification

---

### Phase D — Generation Layer

1. Retrieval-only context
2. Shadow execution enabled
3. Hallucination guard enforced

---

### Phase E — Monitoring & Kill Switches

1. Logs wired to Railway
2. Alerts configured
3. Kill switches tested

---

### Phase F — Pre-Launch Checklist

- [ ] All tests passing
- [ ] Cost budgets respected
- [ ] Synthetic drift < threshold
- [ ] Human alerts verified
- [ ] Legal replica mode verified

Only then launch.

---



## 🚀 EXECUTION BEGINS — EXACT ORDER (DO NOT DEVIATE)

### **Phase 0 — Freeze the Spec**

- Treat the canvas document as **v1.0 frozen**

- No feature additions during build

- Only bug fixes allowed

This prevents scope creep and accidental invariants breakage.

---

### **Phase 1 — Hard Foundations (Week 1)**

**Goal:** Make it impossible to do the wrong thing.

1. Implement **all schemas as Pydantic models**

2. Add **schema validation middleware**

3. Add **binary confidence enforcement**

4. Add **replica storage gate (grounding = 1.0 or reject)**

✅ If this phase is wrong, everything else is pointless.

---

### **Phase 2 — LangGraph State Machine (Week 2)**

**Goal:** Deterministic flow, no limbo.

1. Implement nodes exactly as specified

2. Enforce:
   
   - fallback tiers
   
   - cost guards
   
   - confidence gates

3. Ensure **no node retries infinitely**

4. Ensure **halts are explicit states**

✅ At end of this phase, the system should *stop safely* under failure.

---

### **Phase 3 — Ingestion Swarm + Replica Control (Week 3)**

**Goal:** Clean data or no data.

1. Scout → Gatekeeper → Parser chain

2. Enforce:
   
   - no verbatim persistence
   
   - extraction ≠ generation separation

3. Implement:
   
   - semantic similarity checks
   
   - forbidden pattern detection

4. Reject partial replicas — always all-or-nothing

✅ This is where hallucinations die permanently.

---

### **Phase 4 — Synthetic Curriculum Simulators (Week 4)**

**Goal:** Prove correctness before real users.

1. Generate synthetic PDFs with:
   
   - OCR noise (blur, artifacts, watermarks)
   
   - structure corruption (missing tables, malformed headings)
   
   - jurisdiction ambiguity (conflicting metadata)

2. Run full pipeline

3. Measure with **semantic omission severity**:
   
   - Weighted topic loss (core vs peripheral)
   
   - hallucination rate
   
   - jurisdiction errors

---

#### 4.1 Topic Weighting System (Mandatory)

Not all topic losses are equal. Core concepts must be protected more strictly.

| Weight Class | Multiplier | Examples |
|--------------|------------|----------|
| FOUNDATIONAL | 1.0 | Prerequisites, core concepts |
| STANDARD | 0.7 | Regular curriculum topics |
| PERIPHERAL | 0.3 | Enrichment, optional content |

**Success Criteria:**

| Metric | Target | Blocking |
|--------|--------|----------|
| Weighted topic accuracy | ≥ 95% | ✅ Yes |
| Core topic accuracy (FOUNDATIONAL) | ≥ 99% | ✅ Yes |
| Peripheral topic accuracy | ≥ 85% | ❌ No |
| Hallucination rate | ≤ 1% | ✅ Yes |
| Jurisdiction accuracy | ≥ 98% | ✅ Yes |

---

#### 4.2 University Curriculum Governance (Binding)

> **University curriculum support is provisionally enabled.**

University syllabi differ from K-12 curricula:
- Professors omit, reorder, and personalize content
- Legal and reputational exposure is higher
- Pedagogical misalignment is possible even with correct extraction

**Governance Decisions:**

| Directive | Status |
|-----------|--------|
| Treat university curricula as "validated artifacts, not canonical truth" | POLICY |
| Do not expose higher-ed outputs publicly without visible provenance and disclaimers | BLOCKING |
| Use Phase 4 results to decide whether university support stays, narrows, or forks | PENDING |

**Required for University Outputs:**
- Visible provenance (source URL, extraction date, confidence)
- Disclaimer: "This is an extracted syllabus, not authoritative curriculum"
- Lower default confidence threshold (0.85 → 0.75)

---

🚫 Any failure in Phase 4 blocks production ingestion.

---

### **Phase 5 — Generation + Shadow Execution (Week 5)**

**Goal:** Safe personalization with temporal integrity.

1. Retrieval-only context

2. Shadow execution enabled for critical nodes

3. Drift logging only (no user impact)

4. Kill switch tested

---

#### 5.1 Replica Decay Controls (Mandatory)

Replicas must not become implicitly authoritative over time.

**Required metadata fields:**

| Field | Description |
|-------|-------------|
| `last_verified` | Date of last source validation |
| `use_count` | Number of times replica accessed |
| `age_days` | Days since creation |

**Confidence aging rule:**
```
confidence_score -= 0.01 per month since last_verified
```

**Soft revalidation triggers:**
- After 100 uses OR
- After 90 days since last verification
- On user flag/report

**Visual staleness indicators:**
- Yellow warning: >60 days since verification
- Red warning: >120 days since verification

---

### **Phase 6 — Pre-Launch Kill Test (Mandatory)**

**Goal:** If Phase 6 isn't brutal, it's theater.

---

#### 6.1 Failure Mode Tests (Original)

Run these **intentionally**:

- API outage

- OCR failure

- Conflicting curricula

- Budget exhaustion

- Low confidence everywhere

---

#### 6.2 Adversarial Input Tests (New — Mandatory)

| Attack Vector | Test Case |
|---------------|-----------|
| Malicious PDFs | Corrupted headers, embedded scripts, infinite loops |
| Prompt poisoning | Injected instructions in syllabus text |
| Contradictory syllabi | Same course, conflicting versions |
| Fake official domains | Spoofed .gov/.edu lookalikes |
| Watermarked scans | High OCR failure conditions |
| Encoding attacks | UTF-8 exploits, RTL injection |

---

#### 6.3 Expected Behavior (All Tests)

System must:

- Halt

- Ask user

- Or downgrade safely

**If it guesses → fail the build.**

**If adversarial inputs succeed → fail the build.**

---

## 🧠 FINAL INVARIANTS (NON-NEGOTIABLE)

If any of these are violated, stop execution immediately:

- ❌ No generation without retrieval

- ❌ No storage without grounding

- ❌ No verbatim persistence

- ❌ No confidence below threshold

- ❌ No silent fallback

- ❌ No jurisdiction assumptions

# 
