try:
    from app_additions import app_ingest_ui
    print("Import successful")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"Exception: {e}")
