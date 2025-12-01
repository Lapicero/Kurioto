<p align="center">
  <a href="https://kurioto.com">
    <picture>
      <source srcset="./public/kurioto-banner.webp" type="image/webp">
      <img src="./public/kurioto-banner.png" alt="Kurioto Banner" width="800">
    </picture>
  </a>
</p>

# Kurioto: a Safe AI Companion for Curious Minds

A next-generation educational device combining portable hardware and trusted AI to enrich childhood learning and play.

---

**This repository implements an early version of the cloud software logic for Kurioto.**

---

## **Motivation**

Children are growing up surrounded by digital content, yet current AI-assistants (from smart speakers to mobile apps) are designed primarily for adults. These systems lack the ability to **adapt language to developmental stages**, **ensure child-specific safety**, or **understand the broader context of a child’s environment**. They provide limited memory of past interactions, no continuity in learning, weak guardrails for harmful or adult content, and almost no transparency or direct control for parents.

As a result, children are exposed to:

- Inconsistent, unsafe or inappropriate content
- Noisy or confusing conversational behavior
- Zero awareness of environment or emotional context
- Tools and APIs that operate without parental oversight

At the same time, parents have little visibility into how their kids use digital tools, what content they access, or whether risky behavioral patterns emerge.

**Kurioto** aims to solve this gap by creating a **safe, contextual, age-adaptive AI companion**. It supports curiosity, learning, creativity, and healthy digital habits—while giving parents full control.

This problem matters because real-world AI adoption in childhood settings is accelerating, yet most models are not designed with developmental psychology, safety, or family governance in mind. Children deserve technology that is empowering rather than risky, and parents deserve transparent oversight.

---

## **The Solution**

Kurioto is a modular AI agent framework designed specifically for children’s educational needs. It combines:

**1. Multi-Step Reasoning**

Children’s questions often require planning, tool use, explanation simplification, and safety evaluation. An agent planner can break tasks into steps: interpret, check safety, retrieve knowledge, adapt to age, and respond.

**2. Tool Integration**
To be genuinely useful, the system must access educational corpora, music services and safety controls. Agents naturally orchestrate tool calls through reasoning loops.

**3. Memory**

Children benefit from continuity. Agents can maintain memories of preferences, learning progress, safety events, and conversation themes. Hence creating long-term engagement, and enhancing product personalization.

**4. Multi-Modal Context Awareness**
Agents can coordinate processing of voice, images, background audio, motion, and location metadata. This enables context-sensitive responses.

**5. Safety Governance**

Agents allow intervention before producing output. Every reasoning step can be evaluated by safety modules to prevent harmful topics or developmental mismatches.

**6. Parent–Child Dual Interfaces**
Agents can treat parents as administrators with separate tools, logs, and permissions—making governance a core part of the architecture.

---

## **System Architecture**

```
User Input (voice/image/sensor)
        ↓
Input Interpreter (STT, image captioning mock, metadata builder)
        ↓
Agent Core
  ├─ Planner (multi-step reasoning)
  ├─ Memory Manager (episodic + semantic)
  ├─ Safety Evaluator (block/rewrite/warn)
  ├─ Age Adapter (adjust tone and complexity)
  └─ Tool Router
        ├─ Search Tool (child-safe educational corpus)
        ├─ Spotify Tool (mock)
        ├─ Parent Dashboard Tool
        ├─ Image/Audio Safety Tool
        └─ Environment Context Tool
        ↓
Response Generator (text → simplified → TTS-ready)
        ↓
Device Output (voice + optional screen text)
```

### **Core Components**

1. **Planner**

   - Produces step-by-step plans (e.g., “check safety → call tool → adapt answer”).

2. **Memory Manager**

   - Episodic: recent conversation
   - Semantic: child preferences, profile, safety flags

3. **Safety Evaluator**

   - Filters harmful topics
   - Applies refusal patterns
   - Ensures content fits developmental level

4. **Age Adapter**

   - Simplifies vocabulary
   - Adjusts tone, sentence length, and metaphor style

5. **Tool Layer**

   - SearchTool: queries curated educational knowledge
   - SpotifyTool mock: music suggestions and controls
   - ParentDashboardTool: usage logs, location, settings
   - SafetyTool: checks for image/audio risk
   - ImageUnderstandingTool: simple captioning mock

6. **Output Layer**

   - Generates child-friendly explanations
   - Prepares for TTS (voice output on device)

### **Key Design Priorities**

- Safety-first architecture
- Predictable tool routing
- Clear separation of parent and child roles
- Consistent reasoning trace for evaluation
- Extensibility for physical device integration

Everything is built to maximize clarity, readability, and AI agents best-practices, including multi-step reasoning, multi-modal support, memory, tool usage, and safety.

---

## 📁 **Project Structure**

```
Kurioto/
├── src/kurioto/                   # Main package
│   ├── __init__.py                # Package exports
│   ├── agent.py                   # 🤖 Main KuriotoAgent class
│   ├── cli.py                     # CLI entry point
│   ├── config.py                  # Settings & ChildProfile
│   ├── logging.py                 # Structured logging & tracing
│   ├── memory.py                  # Episodic & semantic memory
│   ├── safety/                    # Multi-layer safety system
│   │   ├── base.py                # Core datatypes & protocol
│   │   ├── multi_layer.py         # Orchestrator across classifiers
│   │   ├── evaluator.py           # Backwards-compatible facade
│   │   └── classifiers/           # Individual safety classifiers
│   │       ├── regex_classifier.py
│   │       ├── gemini_classifier.py
│   │       └── perspective_classifier.py
│   └── tools/                     # Agent tools
│       ├── base.py                # BaseTool interface
│       ├── search.py              # Educational search
│       ├── music.py               # Music playback (mock)
│       ├── parent_dashboard.py    # Parent oversight
│       └── image_safety.py        # Image analysis (mock)
├── tests/                         # Test suite
│   ├── test_safety.py
│   ├── test_agent.py
│   └── test_tools.py
├── examples/
│   └── demo.py                    # Interactive demo
├── docs/                          # Documentation & specs
├── pyproject.toml                 # Modern Python packaging (pinned versions)
├── constraints.txt                # Resolver constraint pins
├── requirements.lock              # Frozen, reproducible environment
└── .env.example                   # Environment template
```

---

## 🚀 **Quick Start**

### Prerequisites

- Python 3.10+
- (Optional) Google API Key for Gemini integration

### Installation

Reproducible (recommended) using the lock file:

```bash
git clone https://github.com/Lapicero/Kurioto.git
cd Kurioto
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.lock
cp .env.example .env  # then set GOOGLE_API_KEY=your_key_here
```

Or editable development install (uses pinned versions + constraints):

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e .[dev] -c constraints.txt
```

To update the lock file after intentional version upgrades:

```bash
pip install -e .[dev] -c constraints.txt --upgrade
pip freeze > requirements.lock
```

### Run the Demo

```bash
# Run the interactive demo
python examples/demo.py

# Or start the CLI
python -m kurioto.cli
```

### Run Tests

```bash
pytest tests/
```

If you installed via lock file and later add dev tools, run:

```bash
pip install -e .[dev] -c constraints.txt
```

---

## 📡 **API Quickstart**

Kurioto includes FastAPI endpoints for parent-facing features: dashboard summaries, learning progress, and educational material uploads.

### Configuration

Set environment variables in `.env`:

```bash
GOOGLE_API_KEY=your_gemini_api_key
PARENT_API_TOKEN=your_secure_token  # Optional; enables auth
RATE_LIMIT_REQUESTS=60              # Requests per window (default 60)
RATE_LIMIT_WINDOW_SECONDS=60        # Window in seconds (default 60)
```

### Running the API

```bash
# Install uvicorn if not present
pip install uvicorn

# Start the server
uvicorn kurioto.app:app --reload
```

The API will be available at `http://localhost:8000`.

### Endpoints

**Dashboard:**
- `GET /api/children/{child_id}/dashboard/summary?timeframe=week`
- `GET /api/children/{child_id}/dashboard/progress?subject=math&days=30`
- `GET /api/children/{child_id}/dashboard/concerns`

**Material Uploads:**
- `POST /api/children/{child_id}/materials/textbook` (form: `file`, `subject`, `grade_level`, optional `metadata_json`)
- `POST /api/children/{child_id}/materials/homework` (form: `file`, `subject`, `assignment_name`, optional `due_date`)
- `POST /api/children/{child_id}/materials/study_guide` (form: `file`, `subject`, `topic`)

### Authentication

If `PARENT_API_TOKEN` is set, include an `Authorization` header:

```bash
curl -H "Authorization: Bearer your_secure_token" \
  http://localhost:8000/api/children/child123/dashboard/summary
```

### Example Upload

```bash
curl -X POST \
  -H "Authorization: Bearer your_secure_token" \
  -F "file=@math_textbook.pdf" \
  -F "subject=math" \
  -F "grade_level=5" \
  http://localhost:8000/api/children/child123/materials/textbook
```

Returns `{"operation": "op_xyz"}` with HTTP 202 (Accepted).

---

## **Work in Progress**

1. **Implement a speech pipeline**
   Integrate high-quality STT and TTS with child-friendly voices.

2. **Enhance multi-modal understanding**
   Add real image models for captioning, OCR, and content filtering.

3. **Build a curriculum-aware learning engine**
   Track educational progress and adjust difficulty over time.

4. **Fine-tune a dedicated child-safe LLM**
   Using a curated developmental dataset, with language styles for ages 5–17.

5. **Implement real-time context awareness**
   Use motion, proximity sensors, and environmental data to adapt behavior.

6. **Create a parent–child co-learning system**
   Joint tasks, quizzes, and storytelling for family collaboration.

Kurioto is designed to become a trusted educational companion. This project is evolving into a fully operational device backed by a production-ready cloud agent with rich multi-modal intelligence and robust safety governance.
