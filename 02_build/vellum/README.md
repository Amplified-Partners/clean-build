# Vellum — Governance & Audit Ledger

<!-- Authored by Devon-9892, 2026-05-09 (session devin-9892b8c738c64d0fa1c66d9f771bba5f) -->

**U13: Export pipeline + Ed25519 signing** ([AMP-217](https://linear.app/amplifiedpartners/issue/AMP-217))

Cryptographic attestation of ledger entries and verifiable data export for the Amplified Partners governance system.

## Modules

| Module | Purpose |
|--------|---------|
| `models/` | Pydantic v2 data models: `LedgerEntry`, `SignedEntry`, `ExportBundle`, `KeyInfo` |
| `signing/` | Ed25519 key generation, entry signing, and verification (PyNaCl/libsodium) |
| `export/` | Canonical JSON serialization, manifest generation, export pipeline |
| `tests/` | Full test suite: keys, signing, serialization, pipeline, tamper detection |

## Quick Start

```bash
pip install -r requirements.txt
```

## Run Tests

```bash
cd 02_build/vellum
python -m pytest tests/ -v
```

## Architecture

```
LedgerEntry
    │
    ▼
sign_entry(entry, signing_key) ──► SignedEntry
    │
    ▼
export_entries([entries], key) ──► ExportBundle
    │                                  ├── manifest (signed)
    │                                  ├── entries[] (each signed)
    │                                  └── signing keys (public)
    ▼
canonical JSON bundle (self-contained, verifiable)
```

## Key Design Decisions

- **PyNaCl** (libsodium binding) for Ed25519 — battle-tested, audited implementation
- **Canonical JSON** (sorted keys, compact separators, UTF-8) for deterministic signing
- **Hex encoding** for signatures and keys — human-readable, grep-friendly
- **Schema versioning** (v1.0) for forward compatibility
- **Self-contained bundles** — each export includes everything needed for verification

## Dependencies

- `PyNaCl>=1.5.0` — Ed25519 signing via libsodium
- `pydantic>=2.5` — Data models with validation
