// =============================================================================
// Withdrawal finality demo — wallet-connected frontend
//
// Talks directly to the Hardhat node (or Sepolia, if you redeploy there) via
// ethers.js and an injected wallet (MetaMask). No backend involved: this page
// reads contracts.json (written by l1/scripts/deploy.js) for addresses, then
// calls the WithdrawalEscrow + verifier contracts straight from the browser.
// =============================================================================

const HARDHAT_CHAIN_ID_HEX = "0x7a69"; // 31337

const ESCROW_ABI = [
  "function deposit(uint256 commitmentId) external payable",
  "function claim(uint256 commitmentId) external",
  "function deposits(uint256) view returns (address user, uint256 amount, bool claimed)",
];

const ZK_VERIFIER_ABI = ["function isFinalized(uint256 id) view returns (bool)"];

const OPT_VERIFIER_ABI = [
  "function isFinalized(uint256 id) view returns (bool)",
  "function getFinalityStatus(uint256 id) view returns (string)",
  "function blocksUntilFinality(uint256 id) view returns (uint256)",
];

let provider, signer;
let contracts = null; // loaded from contracts.json
let zkEscrow, zkVerifier, optEscrow, optVerifier;
let pollHandle = null;

const $ = (id) => document.getElementById(id);

function setStatus(el, text, kind) {
  el.textContent = text;
  el.className = "status-line" + (kind ? " " + kind : "");
}

function shortAddress(addr) {
  return addr.slice(0, 6) + "..." + addr.slice(-4);
}

async function loadContracts() {
  const res = await fetch("contracts.json", { cache: "no-store" });
  if (!res.ok) {
    throw new Error(
      "contracts.json not found — run `docker compose up --build` first so deploy.js can write it.",
    );
  }
  return res.json();
}

async function ensureHardhatNetwork() {
  const network = await provider.getNetwork();
  const currentChainIdHex = "0x" + network.chainId.toString(16);
  const warning = $("network-warning");
  if (currentChainIdHex.toLowerCase() !== HARDHAT_CHAIN_ID_HEX) {
    warning.classList.remove("hidden");
    return false;
  }
  warning.classList.add("hidden");
  return true;
}

async function switchToHardhatNetwork() {
  try {
    await window.ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: HARDHAT_CHAIN_ID_HEX }],
    });
  } catch (err) {
    // 4902 = chain not added to the wallet yet
    if (err.code === 4902) {
      await window.ethereum.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: HARDHAT_CHAIN_ID_HEX,
            chainName: "Hardhat local",
            nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
            rpcUrls: ["http://127.0.0.1:8545"],
          },
        ],
      });
    } else {
      throw err;
    }
  }
}

async function connectWallet() {
  if (!window.ethereum) {
    alert("No injected wallet found. Install MetaMask and reload this page.");
    return;
  }

  provider = new ethers.BrowserProvider(window.ethereum);
  await provider.send("eth_requestAccounts", []);
  signer = await provider.getSigner();

  const address = await signer.getAddress();
  $("wallet-address").textContent = shortAddress(address);
  $("connect-btn").textContent = "Connected";
  $("connect-btn").disabled = true;

  const onRightNetwork = await ensureHardhatNetwork();

  contracts = await loadContracts();

  zkEscrow = new ethers.Contract(contracts.escrowZk, ESCROW_ABI, signer);
  zkVerifier = new ethers.Contract(contracts.zk, ZK_VERIFIER_ABI, provider);
  optEscrow = new ethers.Contract(contracts.escrowOptimistic, ESCROW_ABI, signer);
  optVerifier = new ethers.Contract(contracts.optimistic, OPT_VERIFIER_ABI, provider);

  if (onRightNetwork) {
    $("zk-deposit-btn").disabled = false;
    $("opt-deposit-btn").disabled = false;
  }

  startPolling();
}

async function depositTo(escrow, amountInputId, statusId) {
  const amountEl = $(amountInputId);
  const statusEl = $(statusId);
  const amount = amountEl.value.trim();

  if (!amount || Number(amount) <= 0) {
    setStatus(statusEl, "Enter a deposit amount greater than zero.", "error");
    return;
  }

  try {
    setStatus(statusEl, "Confirm the deposit in your wallet...", "");
    const tx = await escrow.deposit(contracts.demoCommitmentId, {
      value: ethers.parseEther(amount),
    });
    setStatus(statusEl, "Waiting for L1 confirmation...", "");
    await tx.wait();
    setStatus(statusEl, "Deposited. Watching finality status below.", "success");
  } catch (err) {
    setStatus(statusEl, extractRevertReason(err), "error");
  }
}

async function claimFrom(escrow, statusId) {
  const statusEl = $(statusId);
  try {
    setStatus(statusEl, "Confirm the claim in your wallet...", "");
    const tx = await escrow.claim(contracts.demoCommitmentId);
    await tx.wait();
    setStatus(statusEl, "Claimed — funds returned to your wallet.", "success");
  } catch (err) {
    setStatus(statusEl, extractRevertReason(err), "error");
  }
}

function extractRevertReason(err) {
  return err.reason || err.shortMessage || err.message || "Transaction failed.";
}

function setBadge(el, text, kind) {
  el.textContent = text;
  el.className = "finality-badge " + kind;
}

async function pollZk() {
  const finalized = await zkVerifier.isFinalized(contracts.demoCommitmentId);
  if (finalized) {
    setBadge($("zk-finality-status"), "Finalized — claim available", "ready");
    $("zk-claim-btn").disabled = false;
  } else {
    setBadge($("zk-finality-status"), "Pending 5-block L1 confirmation", "waiting");
    $("zk-claim-btn").disabled = true;
  }
}

async function pollOptimistic() {
  const status = await optVerifier.getFinalityStatus(contracts.demoCommitmentId);
  const blocksLeft = await optVerifier.blocksUntilFinality(contracts.demoCommitmentId);

  if (status === "CHALLENGED") {
    setBadge($("opt-finality-status"), "Challenged — withdrawal blocked", "blocked");
    $("opt-claim-btn").disabled = true;
  } else if (status === "HARD_FINAL") {
    setBadge($("opt-finality-status"), "Challenge window closed — claim available", "ready");
    $("opt-claim-btn").disabled = false;
  } else {
    setBadge(
      $("opt-finality-status"),
      `Challenge window open — ${blocksLeft} block(s) remaining`,
      "waiting",
    );
    $("opt-claim-btn").disabled = true;
  }
}

function startPolling() {
  if (pollHandle) clearInterval(pollHandle);
  const tick = () => {
    pollZk().catch(() => {});
    pollOptimistic().catch(() => {});
  };
  tick();
  pollHandle = setInterval(tick, 3000);
}

$("connect-btn").addEventListener("click", () => {
  connectWallet().catch((err) => alert(extractRevertReason(err)));
});

$("switch-network-btn").addEventListener("click", () => {
  switchToHardhatNetwork().catch((err) => alert(extractRevertReason(err)));
});

$("zk-deposit-btn").addEventListener("click", () => depositTo(zkEscrow, "zk-amount", "zk-deposit-status"));
$("zk-claim-btn").addEventListener("click", () => claimFrom(zkEscrow, "zk-claim-status"));
$("opt-deposit-btn").addEventListener("click", () => depositTo(optEscrow, "opt-amount", "opt-deposit-status"));
$("opt-claim-btn").addEventListener("click", () => claimFrom(optEscrow, "opt-claim-status"));

if (window.ethereum) {
  window.ethereum.on("chainChanged", () => window.location.reload());
  window.ethereum.on("accountsChanged", () => window.location.reload());
}
