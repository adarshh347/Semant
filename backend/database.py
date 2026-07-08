import motor.motor_asyncio
# pymongo(synchronous) and motor(asynchronous) both are python libraries that are used to interact with mongodb database
# the node framework equivalent is mongoose
from backend.config import settings

# --- MongoDB Connection Setup with SSL/TLS configuration ---
# For MongoDB Atlas on Windows, we need explicit TLS configuration
# This fixes the "TLSV1_ALERT_INTERNAL_ERROR" SSL handshake issue
try:
    # MongoDB Atlas connection
    # MongoDB Atlas requires TLS/SSL for all connections
    # The connection string (MONGO_DETAILS) should already include TLS parameters
    # For mongodb+srv:// URLs, TLS is automatically enabled
    import os
    
    # Check if we're in a production environment (Render sets PORT env var)
    is_render = os.getenv("PORT") is not None
    
    # Base connection parameters
    connection_params = {
        "serverSelectionTimeoutMS": 30000,
        "socketTimeoutMS": 30000,
        "connectTimeoutMS": 30000,
        "retryWrites": True,
        "retryReads": True,
        "maxPoolSize": 50,
        "minPoolSize": 10
    }
    
    # MongoDB Atlas connection strings (mongodb+srv://) handle TLS automatically
    # Only add explicit TLS settings for local development if needed
    # For Render/Linux, let the connection string handle TLS (it should work by default)
    if not is_render:
        # On local development (Windows): May need relaxed SSL settings
        # Only add if connection string doesn't already specify TLS
        if "mongodb+srv://" not in settings.MONGO_DETAILS:
            connection_params["tls"] = True
            connection_params["tlsAllowInvalidCertificates"] = True
    
    # Create client - let connection string handle TLS for mongodb+srv:// URLs
    client = motor.motor_asyncio.AsyncIOMotorClient(
        settings.MONGO_DETAILS,
        **connection_params
    )
except Exception as e:
    print(f"Error creating MongoDB client: {e}")
    raise

# theory imp: clusters and database are different
database = client.visualDictionaryDB
post_collection = database.get_collection("posts")
epic_collection = database.get_collection("epics")
phrase_learning_collection = database.get_collection("phrase_learning")

# --- Research Article Agent + Sankalpa (will-detection) ---
# research_article_collection: articles composed by the background agent
# agent_run_collection: background job queue/state for agent runs
# sankalpa_collection: the evolving "will profile" inferred from reader feedback
research_article_collection = database.get_collection("research_articles")
agent_run_collection = database.get_collection("agent_runs")
sankalpa_collection = database.get_collection("sankalpa")

# --- Instagram persona context (Darpan) ---
# persona_collection: per-account context dossiers built from extension-scraped
# Instagram details + the images we already have from that account.
persona_collection = database.get_collection("personas")

# --- Anatomy Catalog (Issue #9): scaled category insights ---
# anatomy_catalog_collection: cached aggregated anatomy category profiles +
# LLM-synthesised insights on cross-image annotation patterns.
anatomy_catalog_collection = database.get_collection("anatomy_catalog")

# --- Darshan taste graph (Track A): region embedding sidecar ---
# region_embeddings_collection: FashionCLIP taste-vectors stored OUT of the Region
# doc, keyed by embedding_id. Region carries only the embedding_id pointer; the
# vector lives here so post payloads stay light and the store is swappable
# (Atlas Vector Search / external DB) later. Write path filled in Track B.
region_embeddings_collection = database.get_collection("region_embeddings")

# --- Connection Test Function ---
async def ping_server():
    """Checks if the MongoDB server is responsive."""
    try:
        await client.admin.command('ping')
        print("✅ Successfully connected to MongoDB!")
        return True
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB. Error: {e}")
        return False
        # Optionally, you could raise an exception here to stop the app
        # raise RuntimeError(f"Could not connect to MongoDB: {e}")