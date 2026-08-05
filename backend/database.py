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

# --- Darshan audience side (Track F): taste signals + consent ---
# taste_signals_collection: an audience tap is a LIGHTWEIGHT EVENT, never a Region.
# It references an existing region_id/embedding_id and aggregates into Anuraṇana, so
# consumer friction stays ≈0 and the creator's curated region array stays clean.
# Deliberately separate from `personas` (F7): audience taste is not creator voice.
# taste_consent_collection: the explicit opt-in that gates every signal write (F4),
# keyed by the same opaque subject id, so "clear my taste" is a real delete.
taste_signals_collection = database.get_collection("taste_signals")
taste_consent_collection = database.get_collection("taste_consent")

# --- Manuscript-Oriented Writing Studio (WS-0A · the sacred manuscript) ---
# The writing studio is a second application on the same orchestration kernel. Its
# canon lives in three plain collections, deliberately separate from the vision
# `posts` world:
#   manuscript_collection:    one doc per work — metadata + the chapter hierarchy
#                             (ordered chapters, each an ordered list of scene ids).
#                             Structure is a single atomic source of truth here.
#   scene_collection:         one doc per scene — the body as `text_blocks` (the same
#                             {id,type,content,color,origin} shape the editor uses),
#                             plus title + word_count.
#   scene_version_collection: immutable snapshots of a scene's blocks. Never edited by
#                             normal flows; a restore copies a snapshot FORWARD into
#                             the live scene rather than rewriting history.
manuscript_collection = database.get_collection("manuscripts")
scene_collection = database.get_collection("scenes")
scene_version_collection = database.get_collection("scene_versions")

# --- Semant Writer (W1 · the executable document) ---
# The Writer wraps the orchestration kernel for the manuscript half. It adds no canon of
# its own: Accept writes THROUGH `manuscript_service` into the scenes above, so the sacred
# manuscript keeps exactly one owner. What is new here is the ontology, the quarantine and
# the usage record:
#   writer_operator_collection: the LEDGER half of the two memories — one doc per operator
#                               the author has authored (`#create`), the actuator registry
#                               made author-editable and persisted. Versioned in place, so
#                               a passage can cite the operator as it stood when it fired.
#   writer_passage_collection:  the SESSION half — one doc per RENDERED passage, born
#                               `committed: False`. Accept flips it and copies the prose
#                               into a scene; Dismiss drops it. Nothing here is canon, and
#                               a passage that is never accepted never touches a scene.
#   writer_usage_collection:    instrumentation ONLY (W1 is instrument-now, build-later):
#                               operator invocations, co-occurrence, accept/reject. Tier 2
#                               (assemblages) and Tier 3 are data-gated and cannot be built
#                               without this corpus. Write-behind — a failed write must
#                               never change what the render or accept path does.
writer_operator_collection = database.get_collection("writer_operators")
writer_passage_collection = database.get_collection("writer_passages")
writer_usage_collection = database.get_collection("writer_usage")

# --- Semant Writer W5 · the portable ontology ---
# writer_library_collection: the author's cross-manuscript operator/assemblage library,
# ABOVE project scope and keyed by author. It is purely additive — no existing operator
# moves into it and nothing auto-migrates; the author populates it by PROMOTING operators
# they want to reuse.
#
# Entries hold FULL IMMUTABLE VERSION HISTORY and old versions are never discarded, because
# committed passages across every book pin an exact version and must always resolve. That
# is the one property the whole of W5 rests on: portability is safe exactly as long as
# every passage can still name what made it.
#
# Import is a LINKED COPY, not a live reference — a project copy carries `library_ref`
# lineage and versions independently thereafter, so editing an operator while writing Book B
# can never silently redefine the language under Book A's committed prose.
writer_library_collection = database.get_collection("writer_library")

# --- Vision runtime provenance (CIRCULATION-SPINE-001 · P1) ---
# vision_run_collection: one poll-friendly document per vision operation attempt, with
# its stage events embedded (mirrors the agent_runs run+step-ledger pattern). This is a
# WRITE-BEHIND observability record only — it never holds authoritative geometry and a
# failed write must never change the instrumented route's behavior. Currently records
# the inline Dissect/detect-regions route; other vision endpoints stay uninstrumented
# until they adopt the same pattern.
vision_run_collection = database.get_collection("vision_runs")

# --- Corpus runs (CIRCUIT-002 · SURFACE-002) ---
# run_collection: one document per corpus run — the RunView the API serves, plus A3's serialized
# ResumeState. Unlike `vision_runs` this is NOT write-behind observability: an `awaiting_answer`
# run is RESUMED FROM this document, so a failed write means the curator's answer would have
# nowhere to land, and the route must say so rather than report a run that cannot be continued. It
# holds no authoritative geometry either — every suggestion in it is quarantined and uncommitted.
run_collection = database.get_collection("runs")

# --- The Atlas (ATLAS · C1) ---
# atlas_collection: one document per Atlas canvas. It stores ARRANGEMENT ONLY — which corpus the
# canvas is over, where each image node sits, and (later) the edge list and draft state. It holds
# no percept data whatsoever: nodes carry a `post_id` and the overlays are hydrated from the
# ledger at read time. That is the whole discipline of this collection, and the reason a stale
# Atlas document can never disagree with the ledger about what was seen — it makes no claim about
# what was seen. Spatial position is a writer's thinking aid and asserts no relation; only a
# drawn edge (a real `compare_views` percept, C3) asserts one.
atlas_collection = database.get_collection("atlases")

# --- Movement axes (WAVE2 · Lane G) ---
# movement_axis_collection: the discovered dimensions movements run along (nestedness, enclosure,
# recession). Its own collection rather than an array on one Atlas, because an axis found while
# reading one corpus is referenced by movements on another, and an embedded one would have to be
# COPIED to be reused — the drift this architecture keeps closing. An axis holds a name, a relation
# kind and the ids of what grounds it. It stores NO epistemic status: that is derived at read time
# from the movements that instantiate it, exactly as a movement edge derives its own from its mark.
movement_axis_collection = database.get_collection("movement_axes")

# --- Agent observations (WAVE3 · the first situated agent) ---
# agent_observation_collection: what a situated agent reported from where it stood. Its own
# collection rather than an array on the Atlas, because `atlas_collection` above holds NO percept
# data by design and `assert_no_percept_data` enforces that on every save path — an agent's report
# IS percept data, so putting it on the canvas would mean weakening that guard from this lane to
# admit the very thing it exists to keep out. It points at the canvas by `atlas_id` and `node_id`
# instead, the way a movement axis does. It stores NO epistemic status: the row cites the organ's
# `mark_id`, and what kind of knowing it is comes off that mark at read time — so an agent's report
# reads `proposed` until a curator commits the mark. That is the private-measured / ledger-proposed
# decision made structural rather than promised.
agent_observation_collection = database.get_collection("agent_observations")

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