import json
from unittest.mock import patch
from app.core.config import settings
from app.ai.providers.ollama import OllamaLLM, OllamaEmbeddings
from app.ai.agents.runtime import run_agent


class Reply:
    def __init__(self,data):self.data=data
    def raise_for_status(self):pass
    def json(self):return self.data


def test_ollama_tool_round_trip_and_usage():
    previous=settings.llm_model;settings.llm_model='local-tool-model'
    calls=[]
    def post(url,json,timeout):
        calls.append((url,json,timeout))
        if len(calls)==1:
            return Reply({'message':{'role':'assistant','content':'','tool_calls':[
                {'function':{'name':'lookup','arguments':{'key':'budget'}}}]},
                'prompt_eval_count':40,'eval_count':12})
        assert json['messages'][-2]['tool_calls'][0]['function']['arguments']=={'key':'budget'}
        assert json['messages'][-1]['tool_name']=='lookup'
        return Reply({'message':{'role':'assistant','content':'{"answer":"Known budget"}'},
            'prompt_eval_count':60,'eval_count':10})
    try:
        with patch('app.ai.providers.ollama.httpx.post',side_effect=post):
            result,activity=run_agent(OllamaLLM(),'Return JSON','Find budget',
                [{'type':'function','function':{'name':'lookup','parameters':{'type':'object','properties':{'key':{'type':'string'}}}}}],
                {'lookup':lambda key:{'value':'known'}})
        assert json.loads(result)['answer']=='Known budget'
        assert activity[0]['tool']=='lookup'
        assert calls[0][1]['stream'] is False
    finally:settings.llm_model=previous


def test_ollama_embeddings_accept_native_dimensions():
    previous=settings.embedding_model;settings.embedding_model='local-embedding-model'
    try:
        with patch('app.ai.providers.ollama.httpx.post',return_value=Reply({'embeddings':[[.1,.2,.3],[.3,.2,.1]]})) as post:
            vectors=OllamaEmbeddings().embed(['first','second'])
        assert len(vectors)==2 and len(vectors[0])==3
        assert post.call_args.kwargs['json']['model']=='local-embedding-model'
    finally:settings.embedding_model=previous
