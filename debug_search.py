from src.ingestion.search import search_web
import json

print("Searching for 'US grade 7 science curriculum'...")
results = search_web("grade 7 science", max_results=5)
print(json.dumps(results, indent=2))
