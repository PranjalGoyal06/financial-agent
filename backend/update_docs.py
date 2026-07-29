import datetime

with open("docs/CHANGES.md", "r") as f:
    content = f.read()

new_entry = f"""### [{datetime.date.today()}] — Unified Slash Command Graphs into MasterGraph
- Implemented `MasterGraph` containing all specialized subgraphs (`paisa_agent`, `compare_graph`, `create_artifact_graph`, `recommend_graph`) routed by a single top-level state containing a `slash_command` string.
- Removed custom manual routing and condition logic from `backend/app/main.py`, drastically simplifying the `/chat` endpoint stream handler.
- Fixed mock test leaks and route prefixing bugs that were throwing 404s and 500s across `test_chat_endpoint.py`, `test_market_endpoints.py`, and `test_portfolio_endpoints.py`.
- *Why:* Ensures slash command executions are properly processed through the `langgraph` checkpointer, persisting all outputs (`AIMessage`) seamlessly to the chat session database history.

"""
if new_entry not in content:
    with open("docs/CHANGES.md", "w") as f:
        f.write(new_entry + content)
