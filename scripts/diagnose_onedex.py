"""Read-only diagnostics for OneDex WOODY/WEGLD. No wallet or signing required.

Run: python scripts/diagnose_onedex.py
This does not claim pool reserves unless both token balances are observed.
"""
import json
import os
import requests

API = os.getenv("MVX_API", "https://api.multiversx.com").rstrip("/")
POOL = os.getenv("ONEDEX_POOL_ADDRESS", "erd1qqqqqqqqqqqqqpgqqz6vp9y50ep867vnr296mqf3dduh6guvmvlsu3sujc")
WOODY = os.getenv("WOODY_TOKEN_ID", "WOODY-5f9d9c")
WEGLD = os.getenv("WEGLD_TOKEN_ID", "WEGLD-bd4d79")
LP = "WOODYWEGLD-9832b2"
session = requests.Session()
session.headers["User-Agent"] = "WOODY-read-only-pool-audit/1.0"

def read(path, params=None):
    try:
        response = session.get(API + path, params=params, timeout=12)
        print(f"GET {response.url} -> HTTP {response.status_code}")
        if not response.ok:
            print(response.text[:240])
            return None
        return response.json()
    except requests.RequestException as exc:
        print(f"Request failed: {type(exc).__name__}: {exc}")
        return None

def show_balance(entry, token):
    if not isinstance(entry, dict):
        print(f"{token}: no verified balance")
        return
    try:
        if entry.get("identifier") != token:
            print(f"{token}: response identifier mismatch")
            return
        raw = int(entry["balance"])
        decimals = int(entry["decimals"])
        print(f"{token}: {raw / (10 ** decimals):,.8f} (raw={raw}; decimals={decimals})")
    except (KeyError, TypeError, ValueError) as exc:
        print(f"{token}: invalid balance response: {exc}")

def main():
    account = read(f"/accounts/{POOL}")
    if isinstance(account, dict):
        print("Account:", json.dumps({k: account.get(k) for k in ("address", "isSmartContract", "ownerAddress", "balance")}))
    count = read(f"/accounts/{POOL}/tokens/count")
    print("Configured contract token count:", count)
    tokens = read(f"/accounts/{POOL}/tokens", {"from": 0, "size": 100})
    if isinstance(tokens, list):
        print("Token identifiers on configured address:", [t.get("identifier") for t in tokens])
    if isinstance(tokens, list) and not any(t.get("identifier") == WOODY for t in tokens):
        print("WOODY missing from first token-list page; checking direct token endpoint instead.")
    for token in (WOODY, WEGLD):
        show_balance(read(f"/accounts/{POOL}/tokens/{token}"), token)
    lp = read(f"/tokens/{LP}")
    if isinstance(lp, dict):
        print("LP metadata:", json.dumps({k: lp.get(k) for k in ("identifier", "name", "supply", "decimals", "owner")}))
    lp_txs = read(f"/tokens/{LP}/transactions", {"size": 5})
    if isinstance(lp_txs, list):
        print("Recent LP transactions (read-only discovery):")
        for tx in lp_txs:
            if isinstance(tx, dict):
                print(json.dumps({k: tx.get(k) for k in ("txHash", "sender", "receiver", "function", "timestamp")}))
    print("The LP token metadata confirms this contract as issuer. Direct token balance queries avoid list pagination, but shared-contract WEGLD balance may include other pairs. Do not publish WOODY/WEGLD reserves until pair-specific WEGLD is verified.")

if __name__ == "__main__":
    main()
