"""Local Ollama adapters. They return the same contract as the OpenAI adapters."""
import json
import httpx
from app.core.config import settings


def endpoint(path: str) -> str:
    return settings.ollama_base_url.rstrip('/') + path


def local_post(path: str, payload: dict, timeout_seconds: int) -> dict:
    try:
        response=httpx.post(endpoint(path),json=payload,timeout=timeout_seconds)
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError as exc:
        raise ConnectionError('Ollama is unavailable on localhost:11434. Start Ollama and check OLLAMA_BASE_URL.') from exc
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise ValueError('The configured Ollama model is not installed. Check `ollama list` and the model name in backend/.env.') from exc
        raise


class OllamaLLM:
    def next(self, messages: list[dict], tools: list[dict], timeout_seconds: int = 90):
        if not settings.llm_model:
            raise ValueError('Set LLM_MODEL to an installed Ollama chat model')
        names={}
        converted=[]
        for message in messages:
            role=message['role']
            if role=='assistant':
                calls=[]
                for call in message.get('tool_calls') or []:
                    fn=call['function'];names[call['id']]=fn['name']
                    args=fn['arguments']
                    calls.append({'type':'function','function':{'name':fn['name'],
                        'arguments':json.loads(args) if isinstance(args,str) else args}})
                converted.append({'role':'assistant','content':message.get('content') or '',
                    **({'tool_calls':calls} if calls else {})})
            elif role=='tool':
                converted.append({'role':'tool','tool_name':names.get(message.get('tool_call_id'),''),
                    'content':message.get('content') or ''})
            else:
                converted.append({'role':role,'content':message.get('content') or ''})
        data=local_post('/api/chat',{'model':settings.llm_model,'messages':converted,
            'tools':tools,'format':'json','stream':False,'think':False,
            'options':{'temperature':0,'num_predict':1200}},timeout_seconds)
        reply=data.get('message') or {}
        calls=[]
        for index,call in enumerate(reply.get('tool_calls') or []):
            fn=call['function'];args=fn.get('arguments') or {}
            calls.append({'id':f'ollama-{index}','type':'function','function':{
                'name':fn['name'],'arguments':json.dumps(args) if not isinstance(args,str) else args}})
        result={'role':'assistant','content':reply.get('content') or None,'tool_calls':calls}
        prompt=data.get('prompt_eval_count');completion=data.get('eval_count')
        result['_usage_prompt_tokens']=prompt
        result['_usage_completion_tokens']=completion
        result['_usage_total_tokens']=prompt+completion if prompt is not None and completion is not None else None
        return result


class OllamaEmbeddings:
    def embed(self,texts: list[str],timeout_seconds: int = 60) -> list[list[float]]:
        if not settings.embedding_model:
            raise ValueError('Set EMBEDDING_MODEL to an installed Ollama embedding model')
        data=local_post('/api/embed',{'model':settings.embedding_model,'input':texts,
            'truncate':False},timeout_seconds)
        vectors=data.get('embeddings')
        if not isinstance(vectors,list) or len(vectors)!=len(texts) or any(not vector for vector in vectors):
            raise ValueError('Ollama returned an invalid embedding response')
        return vectors
