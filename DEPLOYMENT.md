## Deployment Playbook

This repo already contains everything needed to deploy new markets on Sepolia while hosting the Flask UI on PythonAnywhere. Follow this checklist when moving from local dev to "live".

---

### 1. Smart-contract builds (local or CI)

1. Install dependencies once.
   ```bash
   npm install
   ```
2. Compile and run the Solidity tests.
   ```bash
   npx hardhat compile
   npx hardhat test
   ```
3. Deploy to Sepolia (locally *or* inside CI) using env vars:
   ```bash
   export INFURA_PROJECT_ID=...
   export SEPOLIA_PRIVATE_KEY=...
   npx hardhat run scripts/deploy.js --network sepolia
   ```
   The script should emit the new contract address and write it into `deployed/sepolia-latest.json`. Commit this file so the Flask service can read the latest metadata.
4. (Optional) Verify the contract automatically:
   ```bash
   npx hardhat verify --network sepolia <address> "Constructor" "Args"
   ```

> **CI tip:** Use GitHub Actions with a manual `workflow_dispatch` so deploys become a single button press. Store keys (`INFURA_PROJECT_ID`, `SEPOLIA_PRIVATE_KEY`, `ETHERSCAN_API_KEY`) as repo secrets.

---

### 2. Application configuration

Update `.env` both locally and on PythonAnywhere:

```
SECRET_KEY=...
OPENAI_API_KEY=...
TAVILY_API_KEY=...
INFURA_PROJECT_ID=...
SEPOLIA_RPC_URL=https://sepolia.infura.io/v3/<INFURA_PROJECT_ID>
CONTRACT_ADDRESS=<fallback address>
PRIVATE_KEY=<account for on-chain admin actions>
CONTRACT_METADATA_PATH=/home/<user>/polymarketapp/deployed/sepolia-latest.json
```

- `CONTRACT_METADATA_PATH` is optional but keeps the backend automatically synced with the latest deploy artifact.
- Rotate any keys that were used in development.

---

### 3. PythonAnywhere (free plan) deployment

1. **Clone repo & virtualenv**
   ```bash
   git clone https://github.com/<you>/polymarketapp.git
   cd polymarketapp
   python3.10 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pip install web3 eth-account
   ```
2. **Database** – upload `polymarket.db` to the same directory. Free accounts run a single worker, so SQLite is safe.
3. **Secrets** – create `~/polymarketapp/.env` with the values listed above. Load it inside `wsgi.py` or via the PythonAnywhere "Environment variables" section.
4. **Web app config**
   - Web framework: manual (use the generated WSGI file).
   - Virtualenv: `/home/<user>/polymarketapp/.venv`.
   - Source: `/home/<user>/polymarketapp`.
   - Reload after every `git pull`.
5. **Networking constraints**
   - Free accounts only reach domains on the PythonAnywhere allowlist. `.infura.io` is already listed ([link](https://www.pythonanywhere.com/whitelist/)), so calls to Sepolia via Infura work out of the box.
   - If you need another RPC host, request it: [Requesting Allowlist additions](https://help.pythonanywhere.com/pages/RequestingAllowlistAdditions/).

---

### 4. Operational workflow

| Task | Action |
|------|--------|
| New market on chain | Run `/api/admin/markets/blockchain` (UI toggle) – already wired to `BlockchainService`. |
| Update contract | Deploy via Hardhat → commit new `deployed/sepolia-latest.json` → `git pull` on PythonAnywhere → reload web app. |
| Resolve on chain | (Placeholder) Implement `BlockchainService.resolve_market_on_chain` once the Solidity contract exposes the method. |
| Queue/DB health | Use `/health` endpoint + PythonAnywhere access/error logs. |

---

### 5. Future automation ideas

1. **GitHub Action:** After Hardhat deploy, open an automated PR with the updated metadata file so every reviewer sees the new address.
2. **PythonAnywhere API:** Script `pa_autoconfigure.py` to pull latest code & reload via their REST API.
3. **On-chain resolution:** Extend `blockchain_service.py` to call a `resolveMarket` function once available, storing the Sepolia tx hash alongside the local payout records.

With the pieces above in place, deploying a new version is literally:

1. Run/trigger the Hardhat workflow.
2. `git pull` on PythonAnywhere.
3. Reload the web app.

Everything else (keys, metadata, networking) stays encoded in config instead of tribal knowledge.
