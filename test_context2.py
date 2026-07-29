import asyncio
import os
from app.checkpointer import get_checkpointer_context
from app.graph import get_agent

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/financial_agent"

async def main():
    async with get_checkpointer_context() as checkpointer:
        agent = get_agent("No portfolio", checkpointer, provider="groq", model="llama-3.3-70b-versatile")
        config = {"configurable": {"thread_id": "test_thread_1234"}}
        
        print("--- Turn 3 ---")
        async for event in agent.astream_events({"messages": [("user", "What is my name?")]}, config, version="v2"):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if isinstance(chunk.content, list):
                    texts = [b.get("text", "") for b in chunk.content if isinstance(b, dict) and "text" in b]
                    print("".join(texts), end="", flush=True)
                else:
                    print(chunk.content, end="", flush=True)
        print("\n")

if __name__ == "__main__":
    asyncio.run(main())
