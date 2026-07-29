from app.llm.provider import get_chat_model

def test_get_chat_model_ollama_cloud_default():
    model = get_chat_model(provider="ollama_cloud")
    assert model.model == "nemotron-3-super:cloud"


