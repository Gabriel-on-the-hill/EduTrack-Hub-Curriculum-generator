# EduTrack Engine

A curriculum intelligence engine that fetches, validates, and generates educational content from official curricula.

## Quick Start

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -e ".[dev]"

# Copy environment template
copy .env.example .env
# Edit .env with your API keys

# Run tests
pytest
```

## Project Structure

```
src/
├── schemas/          # Pydantic models (Section 13 of Blueprint)
├── agents/           # Scout, Gatekeeper, Architect, Embedder
├── orchestrator/     # LangGraph state machine
├── api/              # Streamlit UI + controllers
└── utils/            # Shared utilities
tests/
├── unit/             # Unit tests
└── integration/      # Integration tests
```

## Documentation

- [Execution Blueprint](edu_track_engine_execution_blueprint.md) - What we're building
- [Execution Protocol](EXECUTION_PROTOCOL.md) - How we're building it

## Phase Status

- [x] Phase 0: Spec Frozen
- [ ] Phase 1: Schemas + Validation (In Progress)
- [ ] Phase 2: LangGraph State Machine
- [ ] Phase 3: Ingestion Swarm
- [ ] Phase 4: Synthetic Simulators  
- [ ] Phase 5: Generation Layer
- [ ] Phase 6: Kill Tests + Launch
