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

## Deployment Guide (Option 1A: Subdomain Strategy)

Follow these steps to deploy your curriculum generator to `curriculum.yourwebsite.com`:

### 1. Upload to GitHub
1. Create a new repository named `edutrack-generator`.
2. Upload all files from this folder (ensure `requirements.txt` is included).

### 2. Deploy to Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io/).
2. Click **New app**.
3. Select your GitHub repo: `edutrack-generator`.
4. Set **Main file path** to `src/Home.py` (or `Home.py` if in root).
5. Click **Deploy!**.

### 3. Configure Secrets
1. In your app dashboard, go to **Settings > Secrets**.
2. **Choose ONE provider** and add the corresponding keys:

   **OPTION A: OpenRouter (Recommended for access to DeepSeek, Llama, etc.)**
   ```toml
   AI_PROVIDER = "openrouter"
   OPENROUTER_API_KEY = "sk-or-..."
   ```

   **OPTION B: Google Gemini (Direct)**
   ```toml
   AI_PROVIDER = "gemini"
   GOOGLE_API_KEY = "AIzaSy..."
   ```
   
   **(Optional) Password Protection:**
   To restrict access, add an access code:
   ```toml
   ACCESS_CODE = "secret123"
   ```
   
   *(Note: If `AI_PROVIDER` is missing, it defaults to Google Gemini)*

### 4. Connect Custom Domain
1. In **Settings > Custom Domain**, enter `curriculum.yourwebsite.com`.
2. Login to your DNS provider (GoDaddy, Namecheap, etc.).
3. Add a **CNAME** record:
   - **Host**: `curriculum`
   - **Target**: `edutrack-generator.streamlit.app` (your app URL)
4. Save. It may take up to 48 hours to propagate.

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run src/Home.py
```
