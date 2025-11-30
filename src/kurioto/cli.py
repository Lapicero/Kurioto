"""
CLI entry point for Kurioto.

Provides a simple command-line interface for testing the agent.
"""

from __future__ import annotations

import asyncio

from kurioto.agent import KuriotoAgent
from kurioto.config import DEFAULT_CHILD_PROFILE, get_settings
from kurioto.logging import get_logger

logger = get_logger(__name__)


async def interactive_session():
    """Run an interactive chat session with the agent."""
    settings = get_settings()

    print("\n" + "=" * 60)
    print("🌟 Welcome to Kurioto - Your Safe AI Companion! 🌟")
    print("=" * 60)

    if not settings.validate_api_key():
        print("\n⚠️  Note: Running in demo mode (no API key configured)")
        print("   Set GOOGLE_API_KEY in .env for full functionality\n")

    # Create agent with default child profile
    profile = DEFAULT_CHILD_PROFILE
    agent = KuriotoAgent(child_profile=profile, settings=settings)

    print(f"\nHi! I'm Kurioto, and I'm here to help {profile.name} learn and explore!")
    print(f"({profile.name} is {profile.age} years old)\n")
    print("Type 'quit' or 'exit' to end the session.")
    print("-" * 60 + "\n")

    while True:
        try:
            user_input = input(f"🧒 {profile.name}: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "bye"]:
                print("\n🌟 Goodbye! Thanks for exploring with Kurioto! 🌟\n")
                break

            # Process the message
            response = await agent.process_message(user_input)
            print(f"\n🤖 Kurioto: {response}\n")

        except KeyboardInterrupt:
            print("\n\n🌟 Goodbye! Thanks for exploring with Kurioto! 🌟\n")
            break
        except Exception as e:
            logger.error("session_error", error=str(e))
            print(f"\n😅 Oops! Something went wrong. Let's try again!\n")


def main():
    """Main entry point."""
    asyncio.run(interactive_session())


if __name__ == "__main__":
    main()
