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
