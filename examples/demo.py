#!/usr/bin/env python3
"""
Demo: Marionette detecting and intervening in common agent failures
Simulates various failure modes to showcase Marionette's capabilities.
"""

import asyncio
from orchestrator.marionette import Marionette
from orchestrator.config import Config


async def demo_prompt_quality_check():
    """Demo: Prompt quality enforcement."""
    print("\n" + "="*60)
    print("DEMO 1: Prompt Quality Enforcement")
    print("="*60)
    
    config = Config.from_env()
    marionette = Marionette(config)
    await marionette.start()
    
    # Bad prompt
    print("\n📝 Testing vague prompt...")
    bad_prompt = "make it better"
    result = await marionette.process_user_input(bad_prompt)
    
    if not result["approved"]:
        print("✅ REJECTED (as expected)")
        print(f"   Feedback: {result['feedback']}")
    
    # Good prompt
    print("\n📝 Testing specific prompt...")
    good_prompt = "Refactor the UserAuth class to use async/await pattern with proper error handling and add unit tests"
    result = await marionette.process_user_input(good_prompt)
    
    if result["approved"]:
        print("✅ APPROVED")
    
    await marionette.shutdown()


async def demo_sycophancy_detection():
    """Demo: Detecting overly agreeable agent."""
    print("\n" + "="*60)
    print("DEMO 2: Sycophancy Detection")
    print("="*60)
    
    config = Config.from_env()
    marionette = Marionette(config)
    await marionette.start()
    
    # Sycophantic response
    print("\n🤖 Testing sycophantic agent response...")
    sycophantic = "You're absolutely right! That's a brilliant idea! Perfect approach, I'll implement exactly that."
    
    result = await marionette.process_agent_output(sycophantic)
    
    if result["warnings"]:
        print("✅ SYCOPHANCY DETECTED")
        for warning in result["warnings"]:
            print(f"   {warning}")
    
    await marionette.shutdown()


async def demo_debug_loop_detection():
    """Demo: Detecting debug loops."""
    print("\n" + "="*60)
    print("DEMO 3: Debug Loop Detection & Auto-Kill")
    print("="*60)
    
    config = Config.from_env()
    config.auto_kill_loops = True
    marionette = Marionette(config)
    await marionette.start()
    
    # Simulate repetitive errors
    print("\n❌ Simulating agent stuck in debug loop...")
    
    error_sequence = [
        "Error: Module 'pandas' not found. Installing...",
        "Error: Module 'pandas' not found. Retrying installation...",
        "Error: Module 'pandas' not found. Trying pip install pandas...",
        "Error: Module 'pandas' not found. Attempting conda install...",
        "Error: Module 'pandas' not found. Checking PATH...",
    ]
    
    for i, error in enumerate(error_sequence, 1):
        print(f"\n  Attempt {i}: {error}")
        result = await marionette.process_agent_output(error, is_error=True)
        
        if result["kill_agent"]:
            print("\n✅ DEBUG LOOP DETECTED - AGENT KILLED")
            print("\n💡 Marionette's suggestion:")
            for suggestion in result["suggestions"]:
                print(suggestion)
            break
        
        await asyncio.sleep(0.5)  # Simulate time between attempts
    
    await marionette.shutdown()


async def demo_context_drift():
    """Demo: Context drift detection."""
    print("\n" + "="*60)
    print("DEMO 4: Context Drift Detection")
    print("="*60)
    
    config = Config.from_env()
    marionette = Marionette(config)
    await marionette.start()
    
    # Establish initial goal
    print("\n📝 User establishes goal...")
    initial_prompts = [
        "Build a REST API for user authentication",
        "Use FastAPI and PostgreSQL",
        "Include JWT token handling",
        "Add password hashing with bcrypt",
        "Write OpenAPI documentation"
    ]
    
    for prompt in initial_prompts:
        print(f"   → {prompt}")
        await marionette.process_user_input(prompt)
    
    # Wait for goal learning
    await asyncio.sleep(2)
    
    # Simulate drift
    print("\n🤖 Agent starts drifting to different work...")
    drifted_actions = [
        "Implemented frontend React components",
        "Added CSS styling with Tailwind",
        "Created dashboard with charts",
        "Building mobile responsive design",
    ]
    
    for action in drifted_actions:
        print(f"   → {action}")
        await marionette.process_agent_output(action)
    
    # Manual drift check
    print("\n🔍 Checking for context drift...")
    await asyncio.sleep(3)  # Wait for background monitor
    
    await marionette.shutdown()


async def run_all_demos():
    """Run all demonstration scenarios."""
    print("\n🎭 MARIONETTE DEMONSTRATION")
    print("Showcasing Gemini-powered agent supervision")
    
    await demo_prompt_quality_check()
    await asyncio.sleep(1)
    
    await demo_sycophancy_detection()
    await asyncio.sleep(1)
    
    await demo_debug_loop_detection()
    await asyncio.sleep(1)
    
    await demo_context_drift()
    
    print("\n" + "="*60)
    print("✅ All demos complete!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(run_all_demos())
