import asyncio
from unittest.mock import MagicMock
from app.main import stream_chat_events
from app.schemas import ChatRequest

async def _astream(inputs, version="v2"):
    yield {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="Hi")}}

stub = MagicMock()
stub.astream_events = _astream

async def run():
    req = ChatRequest(message="Hello")
    session = MagicMock()
    
    # We also need a mock request for is_disconnected
    mock_raw = MagicMock()
    mock_raw.is_disconnected = MagicMock(return_value=asyncio.Future())
    mock_raw.is_disconnected.return_value.set_result(False)
    
    from unittest.mock import patch
    with patch("app.main.get_agent", return_value=stub), patch("app.main.get_checkpointer_context") as chk_ctx:
        chk_ctx.return_value.__aenter__.return_value = MagicMock()
        chk_ctx.return_value.__aexit__.return_value = None
        async for chunk in stream_chat_events(req, session, mock_raw):
            print(repr(chunk))

asyncio.run(run())
