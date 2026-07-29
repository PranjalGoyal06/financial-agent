from unittest.mock import patch, MagicMock
import pytest
from app.search.client import search, _call_tavily

@pytest.mark.asyncio
async def test_search_passes_topic_and_days():
    with patch("app.search.client._call_tavily") as mock_call, \
         patch("app.search.client._read_cache", return_value=None), \
         patch("app.search.client._write_cache") as _, \
         patch("app.search.client.settings") as mock_settings:
        
        mock_settings.tavily_api_key = "test_key"
        mock_call.return_value = {
            "results": [
                {
                    "title": "Test News",
                    "url": "https://example.com/test",
                    "content": "Content",
                    "published_date": "2026-07-27T10:00:00",
                    "score": 0.9,
                }
            ]
        }
        
        items = await search("test query", max_results=3, topic="news", days=7)
        
        assert len(items) == 1
        assert items[0].title == "Test News"
        mock_call.assert_called_once_with("test query", 3, "news", 7)


def test_call_tavily_invokes_client():
    with patch("app.search.client.TavilyClient") as mock_client_cls, \
         patch("app.search.client.settings") as mock_settings:
        
        mock_settings.tavily_api_key = "test_key"
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        
        _call_tavily("test query", 5, topic="news", days=7)
        
        mock_client_cls.assert_called_once_with(api_key="test_key")
        mock_instance.search.assert_called_once_with(
            "test query",
            max_results=5,
            search_depth="basic",
            topic="news",
            days=7
        )
