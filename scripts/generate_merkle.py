#!/usr/bin/env python3
"""Generate a SHA-256 merkle root and proofs for weekly WOODY claims.

Input JSON format (list):
[
  {"wallet": "erd1...", "amount": "1200"},
  {"wallet": "erd1...", "amount": "845"}
]

Output JSON includes:
- merkle_root (hex)
- leaves (wallet, amount, leaf)
- proofs mapping wallet -> leaf/proof[]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def leaf_hash(wallet: str, amount: str) -> bytes:
    payload = f"{wallet}:{amount}".encode("utf-8")
    return sha256(payload)


def build_tree(leaves: list[bytes]) -> list[list[bytes]]:
    if not leaves:
        raise ValueError("At least one leaf is required")

    levels: list[list[bytes]] = [leaves]
    current = leaves
    while len(current) > 1:
        nxt: list[bytes] = []
        for i in range(0, len(current), 2):
            left = current[i]
            right = current[i + 1] if i + 1 < len(current) else current[i]
            nxt.append(sha256(left + right))
        levels.append(nxt)
        current = nxt
    return levels


def get_proof(levels: list[list[bytes]], index: int) -> list[str]:
    proof: list[str] = []
    idx = index
    for level in levels[:-1]:
        sibling = idx ^ 1
        if sibling < len(level):
            proof.append(level[sibling].hex())
        else:
            proof.append(level[idx].hex())
        idx //= 2
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate merkle root/proofs for claims")
    parser.add_argument("input", type=Path, help="Input JSON file")
    parser.add_argument("--out", type=Path, default=Path("merkle_output.json"), help="Output JSON file")
    args = parser.parse_args()

    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Input must be a list of claim objects")

    normalized: list[tuple[str, str, bytes]] = []
    for row in raw:
        wallet = str(row["wallet"]).strip()
        amount = str(row["amount"]).strip()
        if not wallet or not amount.isdigit():
            raise ValueError(f"Invalid row: {row}")
        normalized.append((wallet, amount, leaf_hash(wallet, amount)))

    # Deterministic ordering by leaf hash.
    normalized.sort(key=lambda x: x[2].hex())
    leaves = [entry[2] for entry in normalized]
    levels = build_tree(leaves)

    result = {
        "merkle_root": levels[-1][0].hex(),
        "leaf_count": len(leaves),
        "leaves": [
            {"wallet": wallet, "amount": amount, "leaf": leaf.hex()}
            for wallet, amount, leaf in normalized
        ],
        "proofs": {
            wallet: {
                "amount": amount,
                "leaf": leaf.hex(),
                "proof": get_proof(levels, i),
            }
            for i, (wallet, amount, leaf) in enumerate(normalized)
        },
    }

    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Merkle root: {result['merkle_root']}")
    print(f"Wrote: {args.out}")


if __name__ == "__main__":
    main()
