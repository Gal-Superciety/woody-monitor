# Woody Clash Arena - Execution Blueprint (v1)

This blueprint converts the proposed game economy into implementation artifacts.

## Included artifacts

1. `contracts/interfaces/arena_treasury_interface.rs`
   - Treasury fee collection/split interface.
2. `contracts/interfaces/reward_vault_interface.rs`
   - Epoch rewards + merkle claim interface.
3. `db/schema.sql`
   - PostgreSQL schema for gameplay, anti-cheat, economy, and claims.
4. `scripts/generate_merkle.py`
   - Deterministic weekly merkle root/proof generator.

## Suggested weekly ops runbook

1. Finalize week in backend (`weekly_points`).
2. Export `[wallet, amount]` claims JSON.
3. Generate root + proofs:

```bash
python3 scripts/generate_merkle.py claims_week_2026w16.json --out merkle_week_2026w16.json
```

4. Submit `merkle_root` to `reward-vault-sc` with `set_merkle_root`.
5. Open claim window (7 days).
6. At deadline, run `sweep_unclaimed` policy.

## Notes

- Merkle hashing in script is SHA-256 over `"wallet:amount"` payload.
- Contract implementation must match exactly the same hashing and pair ordering rules.
- Use multisig ownership and timelock for fee and pool updates.

## Quick start

Pentru instrucțiuni concrete pas cu pas, vezi `docs/integrare-pas-cu-pas.md`.
