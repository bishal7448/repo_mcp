from app.core.config import settings
import os

print(f"Settings GOOGLE_API_KEY: {settings.GOOGLE_API_KEY}")

if settings.GOOGLE_API_KEY == "default_google_api_key":
    print("WARNING: Still using default key! .env loading failed.")
else:
    print("SUCCESS: Google API Key loaded from .env")
