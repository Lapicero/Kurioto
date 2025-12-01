# **Kurioto: A Safe AI Companion for Curious Minds**

## **Problem Statement**

Children are growing up surrounded by digital content, yet current AI-assistants (from smart speakers to mobile apps) are designed primarily for adults. These systems lack the ability to **adapt language to developmental stages**, **ensure child-specific safety**, or **understand the broader context of a child’s environment**. They provide limited memory of past interactions, no continuity in learning, weak guardrails for harmful or adult content, and almost no transparency or direct control for parents.

As a result, children are exposed to:

* Inconsistent, unsafe or inappropriate content
* Noisy or confusing conversational behavior
* Zero awareness of environment or emotional context
* Tools and APIs that operate without parental oversight

At the same time, parents have little visibility into how their kids use digital tools, what content they access, or whether risky behavioral patterns emerge.

**Kurioto** aims to solve this gap by creating a **safe, contextual, age-adaptive AI companion**. It supports curiosity, learning, creativity, and healthy digital habits—while giving parents full control. The long-term vision includes a handheld device, but the core of the project is a **cloud-based agent** with multi-modal understanding, memory, tool use, and strong guardrails.

This problem matters because real-world AI adoption in childhood settings is accelerating, yet most models are not designed with developmental psychology, safety, or family governance in mind. Children deserve technology that is empowering rather than risky, and parents deserve transparent oversight.

---

## **Why Agents?**

The problem cannot be solved with a simple chatbot or static model. Children interact dynamically, emotionally, and unpredictably. They ask context-dependent questions, move between learning and play, and require explanations based on their age and comprehension level.

Agents are the right solution because they provide:

### **1. Multi-Step Reasoning**

Children’s questions often require planning, tool use, explanation simplification, and safety evaluation. Our orchestrator plans steps: interpret → check safety → retrieve knowledge → adapt to age → respond.

### **2. Tool Integration**

To be genuinely useful, the system must access educational corpora, music services and safety controls. Agents naturally orchestrate tool calls through reasoning loops.

### **3. Memory**

Children benefit from continuity. Agents can maintain memories of preferences, learning progress, safety events, and conversation themes. This creates long-term engagement and enhances personalization.

### **4. Multi-Modal Context Awareness**

Agents can coordinate processing of voice, images, background audio, motion, and location metadata. This enables context-sensitive responses.

### **5. Safety Governance**

Agents allow intervention before producing output. Every reasoning step can be evaluated by safety modules to prevent harmful topics or developmental mismatches.

### **6. Parent–Child Dual Interfaces**

Agents can treat parents as administrators with separate tools, logs, and permissions—making governance a core part of the architecture.

These capabilities make the agent paradigm ideal for a child-focused AI system. Without an agentic framework, safety, tool orchestration, memory, and multi-modal reasoning would be difficult to combine coherently.

---

## **What We Built (Architecture Overview)**

The current implementation focuses on the **cloud-based agent** that powers the experience, with a production-ready educational workflow, parent oversight, and a secure HTTP API.

### **Core Components**

1. **Orchestrator**
   * Classifies intent (education vs. other) and routes requests.
   * Heuristic fallback even when LLM is forced but unavailable, ensuring resiliency.

2. **EducationalMaterialManager**
   * Manages per-child Google Gemini File Search stores.
   * Uploads textbooks, homework, and study guides with metadata filters.
   * Provides a File Search tool to ground tutoring in the child’s own materials.
   * Bounded polling with timeouts and error detection for upload operations.

3. **EducatorAgent**
   * Socratic tutoring and concept explanations grounded in uploaded materials.
   * Provides citations and produces a parent-facing summary of each session.

4. **ParentDashboard**
   * Async summaries, progress trends, and concerns/alerts for parents.
   * Enables lightweight oversight without exposing child content unnecessarily.

5. **MemoryManager**
   * Persists education session logs and supports retrieval/export.

6. **Safety Layer**
   * Filters harmful topics and maintains age-appropriate responses.

7. **API Layer (FastAPI)**
   * Endpoints for parent dashboard (summary, progress, concerns) and uploads.
   * Parent-only access via bearer token; naive in-memory rate limiting.
   * Dependency injection for the material manager to simplify testing.

---

## **APIs**

FastAPI exposes a small, secure API surface optimized for parent oversight and educational uploads.

* Dashboard: `GET /education/dashboard/summary`, `GET /education/dashboard/progress`, `GET /education/dashboard/concerns` (query by `child_id`).
* Uploads: `POST /education/uploads/...` for textbooks, homework, and study guides.
* Auth: Bearer token for parent-only access. Requests without or with invalid tokens are rejected.
* Rate limiting: Basic in-memory limiter to prevent abuse and accidental overload.
* Testability: Material manager is provided via dependency injection for isolated integration tests.

Refer to the project README “API Quickstart” for usage examples and curl commands.

---

## **Safety & Age Adaptation**

* Safety checks run before model output to block harmful content and redirect gently.
* The educator adapts tone, vocabulary, and explanation style to the child’s age.
* Parent oversight is built-in through summaries, progress, and concerns surfaced via the dashboard.

---

## **Demos**

### **Demo 1: Grounded Educational Question**

**Child:** “Why do leaves fall in autumn?”

**Agent Actions:**
1. Orchestrator routes to education.
2. Safety layer confirms topic is safe.
3. EducationalMaterialManager provides a File Search tool for the child’s materials.
4. EducatorAgent uses Socratic prompts grounded in those materials; includes citations.
5. MemoryManager logs the session; ParentDashboard receives a summary.

**Agent Response:**
“Trees drop their leaves to rest for winter, kind of like bedtime for plants! When spring comes, they wake up and grow new leaves.”

### **Demo 2: Homework Tutoring With Citations**

**Child:** “Can you help me with problem 3?”

**Agent Actions:**
1. Homework file is already uploaded and indexed.
2. EducatorAgent guides with hints, avoids giving away answers.
3. Citations reference the relevant page/section of the uploaded material.
4. Parent summary records difficulty areas and suggested practice.

### **Demo 3: Multi-Modal Safety (Image)**

**Child sends a picture.**
* Image safety check runs first.
* If safe, the agent describes it in age-appropriate wording; if unsafe, it refuses and alerts parents.

### **Demo 4: Risk Behavior Redirect**

**Child:** “How do I make a bomb?”

**Agent Actions:**
1. Safety layer blocks the request.
2. ParentDashboard logs a red-flag alert.
3. Educator provides a gentle redirect to safe, educational content.

**Agent Response:**
“I can’t help with that because it’s dangerous. But I can tell you how fireworks create bright colors!”

---

## **The Build (How It Was Created)**

The project is a modular agent framework implemented in Python with a FastAPI service and integration to Google Gemini for generation and File Search grounding.

### **Technologies and Components**

* **Python** for core logic.
* **FastAPI** for the HTTP API and dependency injection.
* **Google Gemini** client and **File Search** for grounded responses.
* **Pytest** and **pytest-asyncio** for unit and integration tests.
* **Structured logging** to support parent oversight and debugging.

### **Key Design Priorities**

* Safety-first architecture with parent oversight as a first-class concern.
* Predictable routing via the Orchestrator, with graceful degradation.
* Grounded educational help with per-child materials and citations.
* Testability via fakes and dependency injection.
* Operational robustness: timeouts and explicit error handling for uploads.

---

## **Testing & Quality**

* Unit tests cover material management, educator behavior, parent dashboard, and orchestration.
* Integration tests cover API endpoints, auth, rate limiting, and upload flows (with DI-based fakes).
* Async discipline: tests await dashboard methods to avoid hidden coroutines.
* Linting and type hygiene: strict typing, attribute guards, and line-length compliance.

---

## **Recent Additions**

* Per-child File Search stores and filters; tool construction for grounding.
* Socratic EducatorAgent with citations and parent summaries.
* ParentDashboard with summaries, progress trends, and concerns.
* FastAPI endpoints with parent-only auth, naive rate limiting, and DI.
* Robust upload polling loops with timeouts and operation error detection.
* README “API Quickstart” with endpoints, headers, and examples.

---

## **If We Had More Time (Roadmap)**

1. **Production-grade auth & rate limiting**
   Integrate with an identity provider; move to distributed rate limiting.

2. **Speech pipeline**
   High-quality STT and TTS with child-friendly voices.

3. **Richer multi-modal understanding**
   Real image models for captioning, OCR, and content filtering.

4. **Curriculum-aware learning engine**
   Track progress and adapt difficulty over time.

5. **Child-safe model tuning**
   Fine-tune on developmental datasets with styles for ages 5–17.

6. **Context awareness**
   Use motion/proximity sensors and environmental data to adapt behavior.

7. **Guardian mobile app**
   Live notifications, settings, and transparent oversight.

8. **Prototype device simulation**
   Android-based prototype modeling connectivity, battery, camera, and mic.

9. **Co-learning experiences**
   Joint tasks, quizzes, and storytelling for family collaboration.

Kurioto is designed to be a trusted educational companion. The current implementation delivers a grounded, safe, and testable core—ready to evolve into a production-ready cloud agent and future handheld device.