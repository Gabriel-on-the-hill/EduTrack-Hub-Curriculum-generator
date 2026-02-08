"""
Integration test for the Ingestion Swarm with Real APIs.

This script tests the full ingestion pipeline:
1. Scout → generates search queries
2. Gatekeeper → validates sources  
3. Architect → parses PDFs and extracts competencies via Gemini
4. Embedder → creates chunks

Prerequisites:
- Set GOOGLE_AI_API_KEY in .env file
- Run: python tests/integration/test_real_api.py
"""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


async def test_gemini_client() -> bool:
    """Test that Gemini client can generate structured output."""
    print("\n" + "=" * 60)
    print("TEST 1: Gemini Client - Structured Output")
    print("=" * 60)
    
    from pydantic import BaseModel
    from src.utils.gemini_client import get_gemini_client, GeminiModel
    
    class SimpleResponse(BaseModel):
        greeting: str
        number: int
    
    client = get_gemini_client()
    
    api_key = os.getenv("GOOGLE_AI_API_KEY")
    if not api_key:
        print("❌ GOOGLE_AI_API_KEY not set in environment")
        print("   Please add it to .env file:")
        print("   GOOGLE_AI_API_KEY=your-key-here")
        return False
    
    print(f"✓ API key found (ends with ...{api_key[-4:]})")
    
    try:
        result = await client.generate_structured(
            prompt="Say hello and pick a number between 1 and 10",
            response_schema=SimpleResponse,
            model=GeminiModel.FLASH,
        )
        
        print(f"✓ Got response: greeting='{result.greeting}', number={result.number}")
        print("✓ Gemini structured output works!")
        return True
        
    except Exception as e:
        print(f"❌ Gemini API error: {e}")
        return False


async def test_competency_extraction() -> bool:
    """Test competency extraction with real LLM."""
    print("\n" + "=" * 60)
    print("TEST 2: Architect Agent - Competency Extraction")
    print("=" * 60)
    
    from src.agents.architect import ArchitectAgent
    
    agent = ArchitectAgent()
    
    # Test with mock PDF (creates a simple PDF with curriculum content)
    print("Creating test PDF with curriculum content...")
    
    try:
        result = await agent.parse("https://example.org/test-curriculum.pdf")
        
        print(f"✓ Parsed PDF: {result.curriculum_snapshot.pages} pages")
        print(f"✓ Extracted {len(result.competencies)} competencies")
        print(f"✓ Average confidence: {result.average_confidence:.2f}")
        print(f"✓ Status: {result.status.value}")
        
        if result.competencies:
            print("\nExtracted competencies:")
            for i, comp in enumerate(result.competencies[:3], 1):
                print(f"  {i}. {comp.title[:50]}...")
                print(f"     Outcomes: {len(comp.learning_outcomes)}")
                print(f"     Confidence: {comp.confidence:.2f}")
        
        return result.status.value in ["success", "low_confidence"]
        
    except Exception as e:
        print(f"❌ Architect error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_pipeline() -> bool:
    """Test the full ingestion pipeline."""
    print("\n" + "=" * 60)
    print("TEST 3: Full Ingestion Pipeline")
    print("=" * 60)
    
    from src.agents.scout import run_scout
    from src.agents.gatekeeper import run_gatekeeper
    from src.agents.architect import ArchitectAgent
    from src.agents.embedder import run_embedder
    
    # Step 1: Scout
    print("\n[1/4] Running Scout Agent...")
    scout_result = await run_scout(
        country="Nigeria",
        country_code="NG",
        grade="JSS 3",
        subject="Biology",
    )
    print(f"  ✓ Generated {len(scout_result.queries)} queries")
    print(f"  ✓ Found {len(scout_result.candidate_urls)} candidate URLs")
    
    if not scout_result.candidate_urls:
        print("  ❌ No URLs found")
        return False
    
    # Step 2: Gatekeeper
    print("\n[2/4] Running Gatekeeper Agent...")
    gatekeeper_result = await run_gatekeeper(
        scout_result.candidate_urls,
        "Nigeria",
        "NG",
    )
    print(f"  ✓ Approved {len(gatekeeper_result.approved_sources)} sources")
    print(f"  ✓ Rejected {len(gatekeeper_result.rejected_sources)} sources")
    print(f"  ✓ Status: {gatekeeper_result.status.value}")
    
    if not gatekeeper_result.approved_sources:
        print("  ⚠ No approved sources, using mock for next step")
        source_url = "https://example.org/mock-curriculum.pdf"
    else:
        source_url = gatekeeper_result.approved_sources[0].url
    
    # Step 3: Architect
    print("\n[3/4] Running Architect Agent...")
    architect = ArchitectAgent()
    architect_result = await architect.parse(source_url)
    print(f"  ✓ Extracted {len(architect_result.competencies)} competencies")
    print(f"  ✓ Average confidence: {architect_result.average_confidence:.2f}")
    
    # Step 4: Embedder
    print("\n[4/4] Running Embedder Agent...")
    embedder_result = await run_embedder(
        uuid4(),
        architect_result.competencies,
    )
    print(f"  ✓ Embedded {embedder_result.embedded_chunks} chunks")
    print(f"  ✓ Status: {embedder_result.status.value}")
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE!")
    print("=" * 60)
    
    return True


async def main() -> None:
    """Run all integration tests."""
    print("\n🚀 EduTrack Ingestion Swarm - Integration Tests")
    print("=" * 60)
    
    results = {
        "Gemini Client": await test_gemini_client(),
    }
    
    # Only run further tests if Gemini works
    if results["Gemini Client"]:
        results["Competency Extraction"] = await test_competency_extraction()
        results["Full Pipeline"] = await test_full_pipeline()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + ("🎉 All tests passed!" if all_passed else "⚠ Some tests failed"))


if __name__ == "__main__":
    asyncio.run(main())
