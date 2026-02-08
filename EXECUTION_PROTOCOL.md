# EduTrack Engine — Agent Execution Protocol

> **Status**: MANDATORY — This protocol governs all execution of this project.  
> **Deviation**: Forbidden without explicit user approval.

---

## 0. Core Principles (Non-Negotiable)

1. **Incremental execution** — Build small, test immediately, verify before proceeding
2. **Schema-first** — Define data structures before implementation
3. **No assumptions** — Ask when unclear, never guess
4. **Fail fast** — Stop at first sign of error, do not proceed with broken state
5. **User approval at boundaries** — Major phases require explicit sign-off

---

## 1. Pre-Execution Checklist

Before writing any code, confirm:

- [ ] Blueprint reviewed and understood
- [ ] This protocol acknowledged
- [ ] Development environment verified
- [ ] Phase order understood

---

## 2. Development Cycle (Enforced)

```
┌─────────────┐
│   DEFINE    │  ← Schema/interface first
└──────┬──────┘
       ▼
┌─────────────┐
│  IMPLEMENT  │  ← Write code
└──────┬──────┘
       ▼
┌─────────────┐
│    TEST     │  ← Run tests, verify output
└──────┬──────┘
       ▼
┌─────────────┐
│   REVIEW    │  ← Show user, get approval
└──────┬──────┘
       ▼
┌─────────────┐
│   COMMIT    │  ← Only then proceed
└─────────────┘
```

**Every component follows this cycle. No exceptions.**

---

## 3. Phase Execution Rules

### 3.1 Phase Order (Strict)

| Phase | Name | Dependency |
|-------|------|------------|
| 1 | Schemas + Validation | None |
| 2 | LangGraph State Machine | Phase 1 |
| 3 | Ingestion Swarm | Phase 2 |
| 4 | Synthetic Simulators | Phase 3 |
| 5 | Generation Layer | Phase 4 |
| 6 | Kill Tests + Launch Prep | Phase 5 |

**Rule:** Phase N cannot begin until Phase N-1 is approved by user.

### 3.2 Phase Boundary Protocol

At the end of each phase:

1. **Summarize** — List all components built
2. **Evidence** — Show passing tests
3. **Review** — Request user approval
4. **Wait** — Do not proceed without explicit "approved" or equivalent

---

## 4. Error Handling Rules

### 4.1 When Errors Occur

```
Error detected
      ↓
STOP immediately
      ↓
Log error details
      ↓
Report to user
      ↓
Fix before retrying
      ↓
NEVER proceed with broken state
```

### 4.2 Rollback Protocol

If a change breaks the system:

1. Identify last known working state
2. Revert to that state
3. Analyze root cause
4. Fix and re-test
5. Only then re-attempt

---

## 5. Uncertainty Protocol

### 5.1 When Unclear

If any of these are true:
- Requirement is ambiguous
- Multiple valid approaches exist
- Missing configuration or context
- Design decision needed

**Action:** STOP and ask user. Never guess.

### 5.2 Question Format

When asking for clarification:
- State the specific uncertainty
- Provide options if applicable
- Wait for response before proceeding

---

## 6. Code Quality Standards

### 6.1 Every File Must Have

- [ ] Type hints on all functions
- [ ] Pydantic schemas for data structures
- [ ] Docstrings for public functions
- [ ] Associated test file

### 6.2 Forbidden Patterns

- ❌ `Any` type in core logic
- ❌ Bare `except:` clauses
- ❌ Hardcoded secrets or keys
- ❌ Untested code in production paths
- ❌ Silent error swallowing

---

## 7. Testing Requirements

### 7.1 Before Proceeding

Every component must have:

| Test Type | Requirement |
|-----------|-------------|
| Unit tests | All pass |
| Schema validation | Verified |
| Integration tests | Where applicable |

### 7.2 Test Evidence

When showing test results:
- Command executed
- Full output
- Pass/fail summary

---

## 8. Documentation Standards

### 8.1 Inline Documentation

- Complex logic explained in comments
- Decision rationale documented
- Edge cases noted

### 8.2 Artifact Updates

After each phase:
- Update `task.md` with completion status
- Create/update walkthrough if significant

---

## 9. User Communication Protocol

### 9.1 Regular Updates

At minimum, update user when:
- Starting a new component
- Completing a component
- Encountering issues

### 9.2 Approval Requests

Phrase clearly:
> "Phase X complete. [Summary]. Tests passing. Ready for your approval to proceed."

Wait for explicit approval.

---

## 10. Verification Checklists

### 10.1 Pre-Phase Checklist

Before starting any phase:

- [ ] Previous phase approved
- [ ] Dependencies available
- [ ] Requirements clear
- [ ] Test strategy defined

### 10.2 Post-Phase Checklist

Before requesting approval:

- [ ] All components implemented
- [ ] All tests passing
- [ ] Documentation updated
- [ ] No known issues

---

## 11. Emergency Protocols

### 11.1 If Stuck

1. Document current state
2. Explain what's blocking
3. Present options to user
4. Wait for guidance

### 11.2 If Major Issue Discovered

1. STOP all work
2. Document the issue
3. Assess impact
4. Report to user immediately
5. Do not attempt to hide or minimize

---

## 12. Protocol Modifications

This protocol may only be modified:
- With explicit user request
- After documenting the change
- With rationale recorded

Ad-hoc deviations are **forbidden**.

---

## Acknowledgment

By proceeding with execution, these rules are acknowledged as binding.

**Protocol Version:** 1.0  
**Effective Date:** 2026-01-31
