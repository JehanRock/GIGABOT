# Debugging & Issues Log

## ⚡ "Lightning" Debug Sub-agent Protocol

This protocol defines how the **Debug Sub-agent** operates to monitor, diagnose, and fix issues within GigaBOT.

### 🎯 Mission
To autonomously detect failures, analyze root causes using contextual memory, and implement fixes or escalate to the user.

### 🔄 Workflow

1.  **Detection:**
    -   Monitor `06_DEBUG_LOG.md` (this file) for new entries.
    -   Listen for `ERROR` level events on the Event Bus.
    -   Watch for failed Swarm tasks.

2.  **Analysis (The "Lightning" Scan):**
    -   **Read Context:** Retrieve the last 50 lines of logs/traceback.
    -   **Memory Check:** Query Vector Memory for similar past issues.
    -   **Code Trace:** Identify the failing function in `02_CORE_FUNCTIONS.md`.

3.  **Action:**
    -   **Safe Fix:** If the fix is low-risk (e.g., config change, retry), attempt it.
    -   **Report:** If high-risk (code change), draft a solution and wait for approval.

4.  **Indexing:**
    -   Record the incident in the **Known Issues** table below.
    -   Update the solution status once resolved.

---

## 🐞 Known Issues Index

| ID | Status | Severity | Component | Description | Solution/Fix |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **ISSUE-001** | 🟢 Fixed | Low | CLI | Example issue description. | Updated `commands.py` argument parsing. |
| | | | | | |

## 📝 Debugging Notes

-   **Logs Location:** Check `terminals/` for raw output.
-   **UI Debugging:** Use the `DebugPanel` in the dashboard to inspect state.
