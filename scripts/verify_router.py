
import sys
import os
import requests
import time

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.model_router import ModelRouter, TaskType

def verify_model(model_id):
    """
    Verify a model is available on OpenRouter by making a minimal request.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in environment")
        return False

    print(f"Testing connectivity for: {model_id}...", end=" ", flush=True)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://github.com/Gabriel-on-the-hill/EduTrack-Curriculum-generator",
        "X-Title": "EduTrack Verification",
        "Content-Type": "application/json"
    }
    
    # Minimal prompt to save tokens/time
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 5
    }
    
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ OK ({response.elapsed.total_seconds():.2f}s)")
            return True
        else:
            print(f"❌ Failed (Status {response.status_code})")
            print(f"   Response: {response.text[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=== Model Router Verification (Dry Run) ===")
    router = ModelRouter()
    
    # Test top model for each category
    task_types = [TaskType.REASONING, TaskType.CREATIVE, TaskType.FORMATTING]
    
    results = {}
    
    for task in task_types:
        print(f"\n--- Verifying {task.value.upper()} Models ---")
        models = router.get_candidate_models(task)
        
        # Test primarily the first model, but if it fails, try the fallback
        # This confirms we have at least ONE working model per category
        at_least_one_working = False
        
        for model in models[:2]: # Test top 2 to ensure fallback is also valid
             if verify_model(model):
                 at_least_one_working = True
             time.sleep(1) # Be nice to API 
        
        results[task] = at_least_one_working

    print("\n=== Summary ===")
    all_pass = True
    for task, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{task.value.capitalize()}: {status}")
        if not success:
            all_pass = False
            
    if all_pass:
        print("\nRocket systems go! All task types have valid models.")
        exit(0)
    else:
        print("\nSome model categories failed verification.")
        exit(1)

if __name__ == "__main__":
    from dotenv import load_dotenv
    # 1. Try loading .env from project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, '.env'))
    
    # 2. If valid key not in env, try Streamlit secrets.toml
    if not os.environ.get("OPENROUTER_API_KEY"):
        try:
            import tomllib
            secrets_path = os.path.join(project_root, ".streamlit", "secrets.toml")
            if os.path.exists(secrets_path):
                with open(secrets_path, "rb") as f:
                    secrets = tomllib.load(f)
                    if "OPENROUTER_API_KEY" in secrets:
                        os.environ["OPENROUTER_API_KEY"] = secrets["OPENROUTER_API_KEY"]
                        print("Loaded key from .streamlit/secrets.toml")
        except ImportError:
            # Python < 3.11, try toml
            try:
                import toml
                secrets_path = os.path.join(project_root, ".streamlit", "secrets.toml")
                if os.path.exists(secrets_path):
                    secrets = toml.load(secrets_path)
                    if "OPENROUTER_API_KEY" in secrets:
                        os.environ["OPENROUTER_API_KEY"] = secrets["OPENROUTER_API_KEY"]
                        print("Loaded key from .streamlit/secrets.toml")
            except ImportError:
                pass

    # 3. Last resort: Ask user
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("⚠️  OPENROUTER_API_KEY not found in .env or .streamlit/secrets.toml")
        print("Please enter it manually for this verification run (it won't be saved):")
        manual_key = input("OPENROUTER_API_KEY: ").strip()
        if manual_key:
            os.environ["OPENROUTER_API_KEY"] = manual_key

    main()
