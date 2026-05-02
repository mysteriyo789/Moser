# Erdős–Moser Problem Search: GitHub Actions Edition
# Seeks: 1^k + 2^k + ... + m^k = (m+1)^k  for k > 1
# Prize: $500 (Erdős)
# Auto-persists via git commits. Runs 6 hours daily.

import math
import json
import time
import signal
import sys

try:
    sys.set_int_max_str_digits(0)
except AttributeError:
    pass

# ================= CONFIGURATION =================
STATE_PATH    = "erdos_moser_state.json"
RESULTS_PATH  = "erdos_moser_results.jsonl"

START_M = 2
MAX_M   = 10_000_000
MAX_K   = 100
MAX_RUNTIME_HOURS = 5.8
TIME_CHECK_INTERVAL = 10_000
SAVE_INTERVAL_SEC = 180
# =================================================

# 🟦 1. LOAD STATE
state = {
    "m": START_M, "k": 2,
    "checked": 0, "found": 0,
    "start_time": time.time()
}

with open(STATE_PATH, "r") as f:
    loaded = json.load(f)
    state.update(loaded)
    state["checked"] = loaded.get("checked", 0)
    state["found"] = loaded.get("found", 0)
    state["counterexamples"] = loaded.get("counterexamples", [])
    state["start_time"] = time.time()

state.setdefault("counterexamples", [])
state["current_run_id"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(state["start_time"]))

# 🟦 2. MODULAR SIEVE
MODULI = (16, 9, 25, 27, 7, 5, 13, 17, 19, 11, 31)
MODULI_COUNT = len(MODULI)

def target_set(modulus, max_k):
    targets = set()
    for r in range(modulus):
        for k in range(2, max_k + 1):
            targets.add(pow(r + 1, k, modulus))
    return targets

target_sets = [target_set(m, MAX_K) for m in MODULI]

# 🟦 3. SAVE HELPERS
def save_state():
    with open(STATE_PATH, "w") as f:
        json.dump(state, f)

def save_discovery_jsonl(m, k, lhs, rhs, run_id):
    discovery = {
        "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
        "run_id": run_id,
        "equation": f"1^{k} + ... + {m}^{k} = {m+1}^{k}",
        "values": {"m": m, "k": k, "LHS_sum": str(lhs), "RHS_power": str(rhs)},
    }
    with open(RESULTS_PATH, "a") as f:
        f.write(json.dumps(discovery) + "\n")

# 🟦 4. SHUTDOWN
MAX_RUNTIME_SEC = MAX_RUNTIME_HOURS * 3600
runtime_expired = False

def handle_timeout():
    global runtime_expired
    runtime_expired = True

def handle_sigterm(signum, frame):
    save_state()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
save_state()

# 🟦 5. INCREMENTAL SUMMER
class IncrementalSummer:
    def __init__(self, m_start, max_k):
        self.m = m_start - 1
        self.max_k = max_k
        self.sums = [0] * (max_k + 1)
        self.mod_sums = [[0] * MODULI_COUNT for _ in range(max_k + 1)]

        if self.m >= 1:
            for i in range(1, self.m + 1):
                for k in range(2, max_k + 1):
                    self.sums[k] += pow(i, k)
                    for mi in range(MODULI_COUNT):
                        self.mod_sums[k][mi] = (self.mod_sums[k][mi] + pow(i, k, MODULI[mi])) % MODULI[mi]

    def step(self):
        self.m += 1
        m = self.m
        for k in range(2, self.max_k + 1):
            self.sums[k] += pow(m, k)
            for mi in range(MODULI_COUNT):
                self.mod_sums[k][mi] = (self.mod_sums[k][mi] + pow(m, k, MODULI[mi])) % MODULI[mi]

    def check(self, k):
        for mi in range(MODULI_COUNT):
            target = pow(self.m + 1, k, MODULI[mi])
            if self.mod_sums[k][mi] != target:
                return False
        return self.sums[k] == pow(self.m + 1, k)

# 🟦 6. INITIALIZE
curr_m, curr_k = state["m"], state["k"]
summer = IncrementalSummer(curr_m, MAX_K)
last_save_time = time.time()
checks_since_check = 0

# 🟦 7. MAIN LOOP
try:
    for m in range(curr_m, MAX_M + 1):
        if m > curr_m:
            summer.step()
        elif m == curr_m and m > START_M:
            summer.step()

        k_start = curr_k if m == curr_m else 2

        for k in range(k_start, MAX_K + 1):
            if summer.check(k) and k > 1:
                state["found"] += 1
                run_id = state["current_run_id"]
                lhs = summer.sums[k]
                rhs = pow(m + 1, k)
                state["counterexamples"].append({
                    "m": m, "k": k, "LHS_sum": str(lhs), "RHS_power": str(rhs),
                    "run_id": run_id, "timestamp": time.time()
                })
                save_discovery_jsonl(m, k, lhs, rhs, run_id)
                save_state()

            state.update({"m": m, "k": k, "checked": state["checked"] + 1})
            checks_since_check += 1

            if checks_since_check >= TIME_CHECK_INTERVAL:
                elapsed = time.time() - state["start_time"]
                if elapsed > MAX_RUNTIME_SEC:
                    handle_timeout()
                if time.time() - last_save_time > SAVE_INTERVAL_SEC or runtime_expired:
                    save_state()
                    last_save_time = time.time()
                if runtime_expired:
                    raise KeyboardInterrupt
                checks_since_check = 0

        if m == curr_m:
            curr_k = 2

except KeyboardInterrupt:
    pass
finally:
    save_state()
    elapsed = time.time() - state["start_time"]
    cps = state["checked"] / elapsed if elapsed > 0 else 0
    print(f"\n🏁 SESSION COMPLETE")
    print(f"🔹 LAST CHECKED: m={state['m']}, k={state['k']}")
    print(f"📊 Total (m,k) pairs checked: {state['checked']:,} | Avg: {cps:,.0f} checks/sec")
    print(f"⏱️  Runtime: {elapsed/3600:.2f} hours")
    print(f"🛡️  COUNTEREXAMPLES FOUND: {state.get('found', 0)}")
    print("💾 State auto-committed to repo. Next run resumes exactly here.")
