import sys
import os

# Ensure we can import app
sys.path.append(os.getcwd())

from app.core.config import settings

print(f"Loaded GOOGLE_API_KEY from settings: {settings.GOOGLE_API_KEY}")

# Check if it matches the expected new key (starts with AIzaSyD0...)
# The specific value matches what we saw in .env
if settings.GOOGLE_API_KEY.startswith("AIzaSyD0"):
    print("SUCCESS: New key loaded correctly!")
elif settings.GOOGLE_API_KEY.startswith("AIzaSyA2"):
    print("FAILURE: Still loading old expired key.")
else:
    print("UNKNOWN: Loaded key is neither expected nor known old key.")
