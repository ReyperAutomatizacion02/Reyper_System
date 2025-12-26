import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

# Initialize client only if keys are present (safe for build time)
supabase: Client = create_client(url, key) if url and key else None
