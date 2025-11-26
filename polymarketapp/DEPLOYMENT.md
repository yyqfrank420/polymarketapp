## Deployment Playbook

This repo contains everything needed to push the Sepolia smart contract and host the Flask app on PythonAnywhere. Follow this checklist when moving from local dev to “live”.

---

### 1. Smart-contract builds (local or CI)

1. **Install deps once**
   ```bash
   npm install
   ```
2. **Compile & test**
   ```bash
   npx hardhat compile
   npx hardhat test
   ```
3. **Deploy to Sepolia** (locally *or* inside CI)
   ```bash
   export INFURA_PROJECT_ID=...
   export SEPOLIA_PRIVATE_KEY=...
   npx hardhat run scripts/deploy.js --network sepolia
   ```
   The deploy script should write metadata to `deployed/sepolia-latest.json`. Commit that file so Flask always knows the latest address/ABI.
4. **(Optional) Verify**
   ```bash
   npx hardhat verify --network sepolia <address>
   ```

> **CI tip:** GitHub Actions + `workflow_dispatch` = one-click deploy. Store `INFURA_PROJECT_ID`, `SEPOLIA_PRIVATE_KEY`, `ETHERSCAN_API_KEY` as secrets.

---

### 2. Application configuration

Update `.env` locally and on PythonAnywhere:

```
SECRET_KEY=...
OPENAI_API_KEY=...
TAVILY_API_KEY=...
INFURA_PROJECT_ID=...
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/<INFURA_PROJECT_ID>
CONTRACT_ADDRESS=<fallback>
PRIVATE_KEY=<admin signer>
CONTRACT_METADATA_PATH=/home/<user>/polymarketapp/deployed/sepolia-latest.json
```

- `CONTRACT_METADATA_PATH` keeps backend + ABI synced automatically.
- Rotate keys when you move from dev to prod.

---

### 3. PythonAnywhere deployment (free plan friendly)

1. **Clone + virtualenv**
   ```bash
   git clone https://github.com/<you>/polymarketapp.git
   cd polymarketapp
   python3.10 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install web3 eth-account
   ```
2. **Database** – upload `polymarket.db` beside the code. Single worker = safe for SQLite.
3. **Secrets** – create `/home/<user>/polymarketapp/.env` with the values above. Load inside `wsgi.py` or use the PythonAnywhere “Environment variables” UI.
4. **Web app settings**
   - Working dir: `/home/<user>/polymarketapp`
   - WSGI file: `/home/<user>/polymarketapp/wsgi.py`
   - Virtualenv: `/home/<user>/polymarketapp/.venv`
   - Reload after every `git pull`
5. **Networking constraints**
   - Free accounts only reach allowlisted hosts. `.infura.io` is already on the list (<https://www.pythonanywhere.com/whitelist/>), so Sepolia via Infura just works.
   - Need another RPC? Request it here: <https://help.pythonanywhere.com/pages/RequestingAllowlistAdditions/>.

---

### 4. Operational workflow

| Task | Action |
|------|--------|
| Deploy new market on chain | Use `/api/admin/markets/blockchain` (UI toggle). Writes tx hash + contract address back to DB. |
| Update contract | Run the Hardhat deploy → commit `deployed/sepolia-latest.json` → `git pull` on PythonAnywhere → reload web app. |
| On-chain resolution | Fill in `BlockchainService.resolve_market_on_chain` once the Solidity contract exposes `resolveMarket`. |
| Monitoring | `/health` endpoint + PythonAnywhere access/error logs + Etherscan for tx confirmation. |

---

### 5. Future automation ideas

1. GitHub Action commits the updated metadata file automatically after each deploy.
2. PythonAnywhere API script pulls latest main + reloads app on demand.
3. Add a Hardhat task that publishes ABI + metadata straight to S3/GitHub Releases.

With this flow in place, “deploy” becomes:

1. Trigger the Hardhat workflow (local or CI).
2. `git pull` + reload on PythonAnywhere.

No manual key shuffling, and the backend auto-loads the right contract metadata.
