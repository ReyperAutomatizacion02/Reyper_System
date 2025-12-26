import os
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from dotenv import load_dotenv

load_dotenv()

url: str = os.getenv("SUPABASE_URL")
key: str = os.getenv("SUPABASE_KEY")

# Initialize client with implicit flow to avoid PKCE code_verifier issues on server-side redirects
supabase: Client = create_client(
    url, 
    key,
    options=ClientOptions(auth={"auto_islands": False, "flow_type": "implicit"})
) if url and key else None
