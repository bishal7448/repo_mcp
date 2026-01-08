from pathlib import Path
from dotenv import load_dotenv
import os

# Replicate the logic from app/core/config.py
BASE_DIR = Path("c:/Users/sahab/Desktop/repo_mcp")
env_path = BASE_DIR / ".env"

print(f"Loading .env from: {env_path}")
print(f"File exists: {env_path.exists()}")

print("Checking for existing GOOGLE_API_KEY in environment...")
if "GOOGLE_API_KEY" in os.environ:
    val = os.environ['GOOGLE_API_KEY']
    print(f"EXISTING KEY FOUND: {val[:5]}...{val[-5:]} (Len: {len(val)})")
else:
    print("No existing GOOGLE_API_KEY found.")

# Test load_dotenv without override (default behavior)
print("\nLoading .env (override=False)...")
load_dotenv(dotenv_path=env_path) 
key = os.getenv("GOOGLE_API_KEY")

print("\n--- Loaded Key Analysis ---")
if key:
    print(f"Key found: Yes")
    print(f"Value: |{key}|")
    print(f"Repr: {repr(key)}")
    print(f"Has leading quote: {key.startswith(chr(39))}")
    print(f"Has trailing quote: {key.endswith(chr(39))}")
else:
    print("KEY NOT FOUND in environment after loading .env")
