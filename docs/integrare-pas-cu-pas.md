# Integrare pas cu pas: Woody Clash Arena (backend + on-chain)

Acest ghid este orientat pe execuție practică, de la zero până la primul claim săptămânal.

## 0) Ce ai nevoie înainte

- Python 3.10+
- PostgreSQL 14+
- Repo clonat local
- Wallet-uri MultiversX pentru:
  - `owner_multisig`
  - `treasury_wallet`
  - `burn_wallet`
  - `reward_vault_sc` (contract)

> Recomandat: începe pe testnet/devnet, nu direct pe mainnet.

---

## 1) Pregătește baza de date

1. Creează baza de date:
   ```bash
   createdb woody_arena
   ```
2. Aplică schema:
   ```bash
   psql woody_arena -f db/schema.sql
   ```
3. Verifică tabelele:
   ```bash
   psql woody_arena -c "\dt"
   ```
4. Verifică view-ul de audit:
   ```bash
   psql woody_arena -c "select * from v_weekly_payout_audit;"
   ```

Rezultat așteptat: tabele + view create fără erori.

---

## 2) Configurează contractele (interfețe -> implementare)

Fișierele de referință pentru endpointuri:
- `contracts/interfaces/arena_treasury_interface.rs`
- `contracts/interfaces/reward_vault_interface.rs`

Pași:
1. Implementează contractul de treasury (`deposit_fees`, `set_fee_config`, `pause_deposits`).
2. Implementează contractul de reward vault (`create_epoch_pool`, `set_merkle_root`, `claim`).
3. Setează ownership pe multisig.
4. Adaugă timelock (ex. 24h) pentru schimbări de configurație fee.
5. Deploy pe testnet/devnet.

Checklist minim după deploy:
- `set_fee_config` funcționează.
- `deposit_fees` produce split corect (vault/treasury/burn).
- `create_epoch_pool` + `set_merkle_root` funcționează.
- `claim` poate fi executat o singură dată per user/epoch.

---

## 3) Leagă backend-ul de economie

1. La fiecare acțiune plătită (ranked entry/retry/premium quest):
   - trimite tx către `arena-treasury-sc`
   - loghează eveniment în `economy_events`
2. La fiecare run:
   - inserează în `runs`
   - aplică validare anti-cheat (`validation_status`)
3. La fiecare match:
   - scrie în `match_results`
4. O dată/zi:
   - calculează `daily_leaderboard`
5. O dată/săptămână:
   - calculează `weekly_points`
   - aplică cap-ul de puncte

---

## 4) Generează rewards săptămânale (Merkle)

1. Exportă claims din DB în format JSON listă:
   ```json
   [
     {"wallet": "erd1...", "amount": "1200"},
     {"wallet": "erd1...", "amount": "845"}
   ]
   ```

2. Rulează generatorul:
   ```bash
   python3 scripts/generate_merkle.py claims_week_2026w16.json --out merkle_week_2026w16.json
   ```

3. Verifică output-ul:
   - `merkle_root`
   - `leaf_count`
   - `proofs[wallet]`

4. Scrie fiecare leaf în tabela `claims` (pentru audit intern).

---

## 5) Publică epoch-ul on-chain

1. `create_epoch_pool(epoch_id, total_amount, claim_deadline)`
2. `set_merkle_root(epoch_id, root_hash)`
3. Anunță comunitatea că epoch-ul este deschis pentru claim.
4. Backend-ul oferă endpoint care întoarce proof-ul per wallet.

---

## 6) Flux claim user (frontend/backend)

1. User conectează wallet.
2. Frontend cere proof de la backend (`GET /claims/proof?week_id=...`).
3. Frontend trimite tx de claim către `reward-vault-sc` cu:
   - `epoch_id`
   - `amount`
   - `proof[]`
4. După confirmare:
   - marchezi `claimed_onchain=true`
   - salvezi `tx_hash` + `claimed_at` în `claims`

---

## 7) Închiderea săptămânii

1. După deadline:
   - rulezi `sweep_unclaimed(epoch_id)`
2. Aplici politica:
   - ex. 50% rollover rewards
   - 50% treasury
3. Publici raport:
   - total claim-uit
   - total neclaim-uit
   - adrese active

---

## 8) Comenzi de verificare rapide (smoke tests)

```bash
python3 -m py_compile scripts/generate_merkle.py
python3 scripts/generate_merkle.py /tmp/claims_sample.json --out /tmp/merkle_sample.json
psql woody_arena -c "select count(*) from users;"
psql woody_arena -c "select * from v_weekly_payout_audit;"
```

---

## 9) Cele mai frecvente greșeli

1. Hashing diferit între backend și contract (`wallet:amount` trebuie identic).
2. Sortare frunze nedeterministă (același input trebuie să dea același root).
3. Lipsă cap weekly points (inflație).
4. Claim dublu permis (trebuie blocat în contract).
5. Fără pause mechanism la incidente.

---

## 10) Ordinea exactă pentru primul launch

1. DB schema aplicată.
2. Contracts deploy pe testnet.
3. Fee split configurat + test tx.
4. Gameplay live cu AP off-chain (fără payout direct).
5. Primul weekly export claims.
6. Merkle root setat on-chain.
7. Claim window deschis 7 zile.
8. Sweep + raport public.
9. Abia după 2-3 săptămâni stabile -> mainnet.
