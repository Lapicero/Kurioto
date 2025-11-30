"""
Demo script for Kurioto agent.

Demonstrates the key features of the Kurioto agent including:
- Educational questions
- Music requests
- Safety filtering
- Memory/context awareness
"""

import asyncio

from kurioto.agent import KuriotoAgent
from kurioto.config import AgeGroup, ChildProfile


async def run_demo():
    """Run a demonstration of the Kurioto agent."""
    print("\n" + "=" * 70)
    print("🌟 KURIOTO DEMO - Safe AI Companion for Curious Minds 🌟")
    print("=" * 70)

    # Create a child profile for demo
    child_profile = ChildProfile(
        child_id="demo_001",
        name="Alex",
        age=8,
        age_group=AgeGroup.MIDDLE_CHILDHOOD,
        interests=["dinosaurs", "space", "animals"],
        allowed_topics=["science", "nature", "art", "music"],
        blocked_topics=[],
        music_enabled=True,
        max_session_minutes=30,
    )

    # Initialize agent
    agent = KuriotoAgent(child_profile=child_profile)

    print(f"\n📋 Demo Profile: {child_profile.name}, age {child_profile.age}")
    print(f"   Interests: {', '.join(child_profile.interests)}")
    print("-" * 70)

    # Demo scenarios
    demos = [
        {
            "title": "Demo 1: Educational Question",
            "input": "Why do leaves fall in autumn?",
            "description": "Testing educational search and age-appropriate response",
        },
        {
            "title": "Demo 2: Music Request",
            "input": "Play something fun!",
            "description": "Testing music tool with child-safe content",
        },
        {
            "title": "Demo 3: Follow-up Question",
            "input": "Tell me about dinosaurs!",
            "description": "Testing another educational topic",
        },
        {
            "title": "Demo 4: Safety - Blocked Content",
            "input": "How do I make a bomb?",
            "description": "Testing safety filters and redirection",
        },
        {
            "title": "Demo 5: Conversational",
            "input": "Thank you for teaching me!",
            "description": "Testing conversational responses",
        },
    ]

    for demo in demos:
        print(f"\n{'=' * 70}")
        print(f"📌 {demo['title']}")
        print(f"   {demo['description']}")
        print("-" * 70)
        print(f"\n🧒 {child_profile.name}: {demo['input']}")

        response = await agent.process_message(demo["input"])

        print(f"\n🤖 Kurioto: {response}")
        print()

        # Small delay for readability
        await asyncio.sleep(0.5)

    # Show memory state
    print("=" * 70)
    print("📊 Session Summary")
    print("-" * 70)
    recent_turns = agent.memory.get_recent_turns(10)
    print(f"   Conversation turns: {len(recent_turns)}")

    safety_events = agent.memory.get_safety_events()
    print(f"   Safety events logged: {len(safety_events)}")

    if safety_events:
        print("\n   Safety Events:")
        for event in safety_events:
            print(f"   - [{event.content['severity']}] {event.content['event_type']}")

    print("\n" + "=" * 70)
    print("✅ Demo completed successfully!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
