import httpx
from app.core.config import settings


class LLMError(RuntimeError):
    pass


class OpenAILLM:
    def next(self, messages: list[dict], tools: list[dict], timeout_seconds: int = 90):
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is required for document questions")
        response = httpx.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={"model": settings.llm_model, "messages": messages, "tools": tools,
                  "tool_choice": "auto", "response_format": {"type": "json_object"},
                  "temperature": 0, "max_completion_tokens": 1000}, timeout=timeout_seconds)
        response.raise_for_status()
        data=response.json()
        message=data["choices"][0]["message"]
        message['_usage_total_tokens']=data.get('usage',{}).get('total_tokens')
        message['_usage_prompt_tokens']=data.get('usage',{}).get('prompt_tokens')
        message['_usage_completion_tokens']=data.get('usage',{}).get('completion_tokens')
        return message


def llm_provider():
    if settings.llm_provider == "openai":
        return OpenAILLM()
    if settings.llm_provider == 'ollama':
        from app.ai.providers.ollama import OllamaLLM
        return OllamaLLM()
    if settings.llm_provider == 'mock-evaluation' and settings.evaluation_mock_mode and settings.environment!='production':
        from app.ai.providers.mock_evaluation import ScriptedEvaluationLLM
        return ScriptedEvaluationLLM()
    raise LLMError("No real LLM provider configured. Mock providers are test-only.")
