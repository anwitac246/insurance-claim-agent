"""
seed_pinecone.py
================
SecureWheel Insurance AI — Policy Knowledge Base Seeder
--------------------------------------------------------
Reads all policy documents from data/policy_docs/,
chunks them with metadata, embeds them using BAAI/bge
(via HuggingFace sentence-transformers), and upserts into
the Pinecone `insurance-policies` index.

Model options (set EMBEDDING_MODEL in .env):
  ┌──────────────┬─────┬────────┬──────────────────────┐
  │ Value        │ Dim │ Size   │ Best for             │
  ├──────────────┼─────┼────────┼──────────────────────┤
  │ bge-small    │ 384 │ ~90MB  │ Fastest, dev/testing │
  │ bge-base     │ 768 │ ~440MB │ Best CPU balance ✓   │
  │ minilm       │ 384 │ ~90MB  │ General purpose      │
  └──────────────┴─────┴────────┴──────────────────────┘

Namespaces:
  - policy_rules      : Coverage, exclusions, decision rules
  - document_rules    : Document requirements & validation
  - fraud_rules       : Fraud detection flags & scoring
  - settlement_rules  : Payout computation & depreciation
  - vehicle_rules     : Vehicle classes & eligibility
  - geographic_rules  : Geographic coverage & catastrophe protocols
  - legal_rules       : TP liability, PA cover, legal proceedings

Usage:
  python seed_pinecone.py               # Seed all documents
  python seed_pinecone.py --dry-run     # Preview chunks without upserting
  python seed_pinecone.py --reset       # Delete index and re-seed fresh
  python seed_pinecone.py --doc POL_001 # Seed a specific document only

Requirements:
  pip install pinecone sentence-transformers python-dotenv
"""

import os
import re
import sys
import json
import time
import hashlib
import argparse
import logging
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

# ─────────────────────────────────────────────────────────────
# MODEL REGISTRY
# ─────────────────────────────────────────────────────────────
_MODEL_REGISTRY = {
    "bge-small": {
        "hf_id": "BAAI/bge-small-en-v1.5",
        "dim": 384,
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "doc_prefix": "",
    },
    "bge-base": {
        "hf_id": "BAAI/bge-base-en-v1.5",
        "dim": 768,
        "query_prefix": "Represent this sentence for searching relevant passages: ",
        "doc_prefix": "",
    },
    "minilm": {
        "hf_id": "sentence-transformers/all-MiniLM-L6-v2",
        "dim": 384,
        "query_prefix": "",
        "doc_prefix": "",
    },
}

MODEL_SIZE = os.getenv("EMBEDDING_MODEL", "bge-base")

if MODEL_SIZE not in _MODEL_REGISTRY:
    raise ValueError(
        f"Invalid EMBEDDING_MODEL='{MODEL_SIZE}'. "
        f"Choose from: {list(_MODEL_REGISTRY.keys())}"
    )

EMBEDDING_MODEL_ID = _MODEL_REGISTRY[MODEL_SIZE]["hf_id"]
EMBEDDING_DIM      = _MODEL_REGISTRY[MODEL_SIZE]["dim"]
QUERY_PREFIX       = _MODEL_REGISTRY[MODEL_SIZE]["query_prefix"]
DOC_PREFIX         = _MODEL_REGISTRY[MODEL_SIZE]["doc_prefix"]

# ─────────────────────────────────────────────────────────────
# PINECONE / CHUNKING CONFIG
# ─────────────────────────────────────────────────────────────
PINECONE_API_KEY  = os.getenv("PINECONE_API_KEY")
INDEX_NAME        = "insurance-policies"
CHUNK_SIZE        = 600   # words per chunk
CHUNK_OVERLAP     = 80    # words overlap between chunks
UPSERT_BATCH_SIZE = 50    # vectors per Pinecone upsert call
POLICY_DOCS_DIR   = Path(__file__).parent / "data" / "policy_docs"

# ─────────────────────────────────────────────────────────────
# NAMESPACE MAP
# ─────────────────────────────────────────────────────────────
NAMESPACE_MAP = {
    "POL_001": "policy_rules",
    "POL_002": "document_rules",
    "POL_003": "settlement_rules",
    "POL_004": "fraud_rules",
    "POL_005": "vehicle_rules",
    "POL_006": "policy_rules",
    "POL_007": "geographic_rules",
    "POL_008": "legal_rules",
}

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("seed_pinecone")


# ─────────────────────────────────────────────────────────────
# EMBEDDING MODEL (singleton — loaded once, reused for all batches)
# ─────────────────────────────────────────────────────────────
_ST_MODEL = None


def get_model():
    """
    Load the embedding model once and cache it for the entire session.
    BGE models are small and load in a few seconds after the first download.
    """
    global _ST_MODEL
    if _ST_MODEL is None:
        log.info(f"Loading embedding model : {EMBEDDING_MODEL_ID}")
        log.info(f"Output dimension        : {EMBEDDING_DIM}")
        from sentence_transformers import SentenceTransformer
        _ST_MODEL = SentenceTransformer(EMBEDDING_MODEL_ID)
        log.info("✓ Model loaded successfully")
    return _ST_MODEL


def embed_documents(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of document chunks.
    BGE document chunks don't need an instruction prefix — only queries do.
    """
    model = get_model()
    prefixed = [DOC_PREFIX + t for t in texts] if DOC_PREFIX else texts
    embeddings = model.encode(
        prefixed,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=True,
    )
    return embeddings.tolist()


def embed_query(query: str) -> list[float]:
    """
    Embed a single query string with the BGE query prefix.
    Import and call this from main.py at inference time.
    Using the same prefix here as during seeding keeps queries
    and documents in the same vector space.
    """
    model = get_model()
    prefixed = QUERY_PREFIX + query if QUERY_PREFIX else query
    embedding = model.encode(
        [prefixed],
        normalize_embeddings=True,
    )
    return embedding[0].tolist()


# ─────────────────────────────────────────────────────────────
# STEP 1: PARSE POLICY DOCUMENTS INTO SECTIONS
# ─────────────────────────────────────────────────────────────
def parse_document(filepath: Path) -> dict:
    """
    Parse a Markdown policy document into metadata + sections.
    Returns:
      {
        "policy_id": "POL-001",
        "title": "Master Coverage Policy",
        "effective_date": "April 1, 2026",
        "version": "4.2",
        "full_text": "...",
        "sections": [
            {"section_title": "Section 1: ...", "content": "..."},
            ...
        ]
      }
    """
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    metadata = {
        "policy_id": "",
        "title": "",
        "effective_date": "",
        "version": "",
        "full_text": text,
        "sections": [],
    }

    for line in lines[:10]:
        if line.startswith("# POLICY DOCUMENT:"):
            metadata["policy_id"] = line.replace("# POLICY DOCUMENT:", "").strip()
        elif line.startswith("# ") and not metadata["title"]:
            if "POLICY DOCUMENT" not in line:
                metadata["title"] = line.lstrip("# ").strip()
        elif "Effective:" in line:
            match = re.search(r"Effective:\s*([^|]+)", line)
            if match:
                metadata["effective_date"] = match.group(1).strip()
        elif "Version:" in line:
            match = re.search(r"Version:\s*([\d.]+)", line)
            if match:
                metadata["version"] = match.group(1).strip()

    current_section = None
    current_content = []

    for line in lines:
        if line.startswith("## "):
            if current_section:
                metadata["sections"].append({
                    "section_title": current_section,
                    "content": "\n".join(current_content).strip(),
                })
            current_section = line.lstrip("# ").strip()
            current_content = []
        elif current_section:
            current_content.append(line)

    if current_section and current_content:
        metadata["sections"].append({
            "section_title": current_section,
            "content": "\n".join(current_content).strip(),
        })

    log.info(
        f"  Parsed {metadata['policy_id']} | "
        f"{len(metadata['sections'])} sections | "
        f"{len(text.split())} words"
    )
    return metadata


# ─────────────────────────────────────────────────────────────
# STEP 2: CHUNK TEXT (sliding window)
# ─────────────────────────────────────────────────────────────
def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping word-based chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start += chunk_size - overlap
    return chunks


def build_chunks_from_document(doc: dict) -> list[dict]:
    """
    Build enriched chunk objects from a parsed policy document.
    Each chunk carries metadata for Pinecone filtering.
    """
    pol_id_clean = doc["policy_id"].replace("-", "_")
    namespace = NAMESPACE_MAP.get(pol_id_clean, "policy_rules")
    chunks = []

    for section in doc["sections"]:
        section_text = f"{section['section_title']}\n\n{section['content']}"
        text_chunks = chunk_text(section_text)

        for i, chunk_content in enumerate(text_chunks):
            chunk_id = hashlib.md5(
                f"{doc['policy_id']}_{section['section_title']}_{i}".encode()
            ).hexdigest()[:16]

            chunks.append({
                "chunk_id": f"{pol_id_clean}_{chunk_id}",
                "text": chunk_content,
                "namespace": namespace,
                "metadata": {
                    "policy_id": doc["policy_id"],
                    "policy_title": doc["title"],
                    "effective_date": doc["effective_date"],
                    "version": doc["version"],
                    "section_title": section["section_title"],
                    "chunk_index": i,
                    "word_count": len(chunk_content.split()),
                    "source_file": f"{pol_id_clean}.md",
                    "namespace": namespace,
                    "embedding_model": EMBEDDING_MODEL_ID,
                    "indexed_at": datetime.utcnow().isoformat(),
                },
            })

    log.info(
        f"  Chunked {doc['policy_id']} → {len(chunks)} chunks "
        f"across {len(doc['sections'])} sections"
    )
    return chunks


# ─────────────────────────────────────────────────────────────
# STEP 3: UPSERT TO PINECONE
# ─────────────────────────────────────────────────────────────
def upsert_chunks(
    chunks: list[dict],
    index,
    dry_run: bool = False,
) -> int:
    """
    Embed and upsert chunks into Pinecone, grouped by namespace.
    Returns total vectors upserted.
    """
    by_namespace: dict[str, list] = {}
    for chunk in chunks:
        by_namespace.setdefault(chunk["namespace"], []).append(chunk)

    total_upserted = 0

    for namespace, ns_chunks in by_namespace.items():
        log.info(f"\n  Namespace '{namespace}': {len(ns_chunks)} chunks")

        for batch_start in range(0, len(ns_chunks), UPSERT_BATCH_SIZE):
            batch = ns_chunks[batch_start: batch_start + UPSERT_BATCH_SIZE]
            batch_num = batch_start // UPSERT_BATCH_SIZE + 1

            if dry_run:
                log.info(
                    f"    [DRY RUN] Batch {batch_num}: would embed & upsert "
                    f"{len(batch)} vectors → namespace='{namespace}'"
                )
                for c in batch[:2]:
                    log.info(f"      Sample ID   : {c['chunk_id']}")
                    log.info(f"      Text preview: {c['text'][:120]}...")
                total_upserted += len(batch)
                continue

            log.info(f"    Embedding batch {batch_num} ({len(batch)} texts)...")
            vectors_data = embed_documents([c["text"] for c in batch])

            # Dimension sanity check — catches model/index mismatches early
            actual_dim = len(vectors_data[0])
            if actual_dim != EMBEDDING_DIM:
                raise RuntimeError(
                    f"Dimension mismatch! Expected {EMBEDDING_DIM}, got {actual_dim}. "
                    f"Did you change EMBEDDING_MODEL without running --reset?"
                )

            pinecone_vectors = [
                {
                    "id": chunk["chunk_id"],
                    "values": vector,
                    "metadata": chunk["metadata"],
                }
                for chunk, vector in zip(batch, vectors_data)
            ]

            index.upsert(vectors=pinecone_vectors, namespace=namespace)
            total_upserted += len(batch)
            log.info(f"    ✓ Upserted {len(batch)} vectors to '{namespace}'")
            time.sleep(0.3)

    return total_upserted


# ─────────────────────────────────────────────────────────────
# STEP 4: PINECONE INDEX MANAGEMENT
# ─────────────────────────────────────────────────────────────
def get_or_create_index(pc: Pinecone, reset: bool = False):
    """Create or retrieve the Pinecone index, with dimension mismatch guard."""
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if reset and INDEX_NAME in existing_indexes:
        log.warning(f"--reset flag set: Deleting index '{INDEX_NAME}'...")
        pc.delete_index(INDEX_NAME)
        existing_indexes = []
        time.sleep(5)

    if INDEX_NAME not in existing_indexes:
        log.info(
            f"Creating Pinecone index '{INDEX_NAME}' "
            f"(dim={EMBEDDING_DIM}, metric=cosine, model={EMBEDDING_MODEL_ID})..."
        )
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        log.info("  Waiting for index to be ready...")
        for _ in range(30):
            if pc.describe_index(INDEX_NAME).status.get("ready"):
                break
            time.sleep(2)
        log.info(f"  ✓ Index '{INDEX_NAME}' is ready")
    else:
        existing_dim = pc.describe_index(INDEX_NAME).dimension
        if existing_dim != EMBEDDING_DIM:
            log.error(
                f"Dimension mismatch! Existing index has dim={existing_dim} but "
                f"{EMBEDDING_MODEL_ID} outputs dim={EMBEDDING_DIM}. "
                f"Run with --reset to rebuild the index."
            )
            sys.exit(1)
        log.info(f"  ✓ Using existing index '{INDEX_NAME}' (dim={existing_dim})")

    return pc.Index(INDEX_NAME)


# ─────────────────────────────────────────────────────────────
# STEP 5: VERIFY SEEDING WITH REAL SEMANTIC QUERIES
# ─────────────────────────────────────────────────────────────
def verify_seeding(index) -> dict:
    """
    Run real semantic queries against the seeded index to confirm quality.
    BGE top scores should be 0.55+ for clearly relevant queries.
    """
    log.info("\n─── VERIFICATION ─────────────────────────────────────────")
    stats = index.describe_index_stats()
    log.info(f"Index stats:\n{json.dumps(stats.to_dict(), indent=2)}")

    test_queries = [
        ("fraud_rules",      "What is the fraud risk score threshold for auto-rejection?"),
        ("settlement_rules", "How is vehicle depreciation calculated for total loss claims?"),
        ("policy_rules",     "What are the exclusions for pre-existing damage?"),
    ]

    for namespace, query in test_queries:
        log.info(f"\n  Query [{namespace}]:\n  '{query}'")
        query_vector = embed_query(query)

        if len(query_vector) != EMBEDDING_DIM:
            log.error(
                f"Query vector dim {len(query_vector)} != index dim {EMBEDDING_DIM}"
            )
            continue

        result = index.query(
            vector=query_vector,
            top_k=3,
            namespace=namespace,
            include_metadata=True,
        )

        if not result.matches:
            log.warning(f"  ⚠ No matches returned for namespace '{namespace}'")
            continue

        for match in result.matches:
            log.info(
                f"    [{match.score:.4f}] "
                f"{match.metadata.get('policy_id')} | "
                f"{match.metadata.get('section_title')} | "
                f"chunk #{match.metadata.get('chunk_index')}"
            )

        top_score = result.matches[0].score
        if top_score < 0.4:
            log.warning(
                f"  ⚠ Top score {top_score:.4f} is lower than expected. "
                f"Ensure embed_query() is used with the same prefix at inference time."
            )
        else:
            log.info(f"  ✓ Top score {top_score:.4f} looks healthy")

    return stats.to_dict()


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Seed SecureWheel policy documents into Pinecone"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Parse and chunk without upserting to Pinecone",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Delete and recreate the Pinecone index before seeding",
    )
    parser.add_argument(
        "--doc", type=str, default=None,
        help="Seed only a specific document (e.g. --doc POL_001)",
    )
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("SecureWheel Insurance — Pinecone Policy Seeder")
    log.info("=" * 60)
    log.info(f"Mode            : {'DRY RUN' if args.dry_run else 'LIVE'}")
    log.info(f"Reset           : {args.reset}")
    log.info(f"Filter          : {args.doc or 'ALL DOCUMENTS'}")
    log.info(f"Index           : {INDEX_NAME}")
    log.info(f"Embedding model : {EMBEDDING_MODEL_ID}")
    log.info(f"Embedding dim   : {EMBEDDING_DIM}")
    log.info(f"Docs dir        : {POLICY_DOCS_DIR}")
    log.info("─" * 60)

    if not PINECONE_API_KEY:
        log.error("PINECONE_API_KEY not set in .env")
        sys.exit(1)

    # Load model once upfront — avoids any per-namespace reload penalty
    if not args.dry_run:
        get_model()

    pc = Pinecone(api_key=PINECONE_API_KEY)

    if not args.dry_run:
        index = get_or_create_index(pc, reset=args.reset)
    else:
        index = None
        log.info("[DRY RUN] Skipping Pinecone index creation")

    # Discover documents
    doc_files = sorted(POLICY_DOCS_DIR.glob("*.md"))
    if not doc_files:
        log.error(f"No .md files found in {POLICY_DOCS_DIR}")
        sys.exit(1)

    if args.doc:
        doc_files = [f for f in doc_files if args.doc.upper() in f.stem.upper()]
        if not doc_files:
            log.error(f"No document matching '{args.doc}' found")
            sys.exit(1)

    log.info(f"\nFound {len(doc_files)} document(s) to process:\n")

    all_chunks = []
    summary_rows = []

    for filepath in doc_files:
        log.info(f"{'─' * 50}")
        log.info(f"Processing: {filepath.name}")
        try:
            doc = parse_document(filepath)
            chunks = build_chunks_from_document(doc)
            all_chunks.extend(chunks)
            summary_rows.append({
                "file": filepath.name,
                "chunks": len(chunks),
                "namespace": NAMESPACE_MAP.get(
                    doc["policy_id"].replace("-", "_"), "policy_rules"
                ),
            })
        except Exception as e:
            log.error(f"  ✗ Failed to process {filepath.name}: {e}")
            continue

    # Summary table
    log.info(f"\n{'═' * 60}")
    log.info("DOCUMENT SUMMARY")
    log.info(f"{'═' * 60}")
    log.info(f"{'FILE':<45} {'CHUNKS':>6}  NAMESPACE")
    log.info("─" * 60)
    for row in summary_rows:
        log.info(f"{row['file']:<45} {row['chunks']:>6}  {row['namespace']}")
    log.info("─" * 60)
    log.info(f"{'TOTAL':<45} {sum(r['chunks'] for r in summary_rows):>6}")
    log.info(f"{'═' * 60}\n")

    if all_chunks:
        log.info(f"Starting upsert of {len(all_chunks)} total chunks...\n")
        total = upsert_chunks(all_chunks, index, dry_run=args.dry_run)
        log.info(
            f"\n✓ {'Would upsert' if args.dry_run else 'Upserted'} {total} vectors total"
        )

    if not args.dry_run and index:
        verify_seeding(index)

    log.info("\n✓ Seeding complete!")
    log.info("Next step: Run `python main.py` to test claims against the policy knowledge base.")
    log.info(
        f"\nIMPORTANT — in main.py, embed queries using embed_query() from this file:\n"
        f"  from seed_pinecone import embed_query\n"
        f"  vector = embed_query('your question here')"
    )


if __name__ == "__main__":
    main()