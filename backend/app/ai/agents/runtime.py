"""Bounded LangGraph agent loop with workspace-bound LangChain tools."""
import inspect
import json
import time
from collections.abc import Callable
from typing import TypedDict
from langchain_core.tools import StructuredTool
from langgraph.graph import StateGraph, START, END


class AgentLimitError(RuntimeError):
    pass


class AgentCancelled(RuntimeError):
    pass


class SharedLimits:
    """One budget shared by Coordinator and all delegated specialist runs."""
    def __init__(self,max_tool_steps=18,max_seconds=120,max_tokens=40000,cancel_check=None,event=None):
        self.max_tool_steps=max_tool_steps;self.max_tokens=max_tokens
        self.deadline=time.monotonic()+max_seconds
        self.tool_steps=0;self.token_estimate=0
        self.provider_prompt_tokens=0;self.provider_completion_tokens=0
        self.cancel_check=cancel_check or (lambda:False)
        self.event=event or (lambda **kwargs:None)

    def check(self):
        if self.cancel_check():raise AgentCancelled('Run cancelled')
        if time.monotonic()>self.deadline:raise AgentLimitError('Run time limit reached')
        if self.token_estimate>self.max_tokens:raise AgentLimitError('Run token limit reached')

    def add_tokens(self,value):
        self.token_estimate+=value
        self.check()

    def tool(self):
        self.tool_steps+=1
        if self.tool_steps>self.max_tool_steps:raise AgentLimitError('Run tool-step limit reached')
        self.check()

    def remaining_seconds(self):
        self.check()
        return max(1,min(90,int(self.deadline-time.monotonic())))


def estimate_tokens(value):
    return max(1,(len(json.dumps(value,default=str))+3)//4)


class AgentState(TypedDict):
    messages:list[dict]
    activity:list[dict]
    model_calls:int
    pending_calls:list[dict]
    answer:str|None


def run_agent(llm, system: str, user: str, tools: list[dict], handlers: dict[str, Callable],
              max_steps: int = 6, limits:SharedLimits|None=None, agent_run_id:str|None=None,
              agent_name:str|None=None):
    """The model chooses tools; LangGraph routes model and tool nodes until an answer."""
    specs={item['function']['name']:item['function'] for item in tools}
    bound={name:StructuredTool.from_function(func=handler,name=name,
        description=specs[name].get('description') or name,
        args_schema=specs[name]['parameters'],infer_schema=False)
        for name,handler in handlers.items() if name in specs}

    def model_node(state:AgentState):
        if state['model_calls']>=max_steps:
            raise AgentLimitError('Agent reached its model-step limit')
        messages=state['messages']
        if limits:
            limits.check();limits.add_tokens(estimate_tokens(messages)+estimate_tokens(tools))
        kwargs={}
        if limits and 'timeout_seconds' in inspect.signature(llm.next).parameters:
            kwargs['timeout_seconds']=limits.remaining_seconds()
        try:
            message=llm.next(messages,tools,**kwargs)
        except Exception as exc:
            # A transient model error can retry once; tools never replay on this path.
            retryable=exc.__class__.__name__ in {'TimeoutException','ConnectError'} or getattr(getattr(exc,'response',None),'status_code',0) in {429,500,502,503,504}
            if not retryable or not limits:raise
            limits.check()
            message=llm.next(messages,tools,**kwargs)
        if limits:
            limits.provider_prompt_tokens+=message.get('_usage_prompt_tokens') or 0
            limits.provider_completion_tokens+=message.get('_usage_completion_tokens') or 0
            limits.add_tokens(message.get('_usage_total_tokens') or estimate_tokens(message))
        calls=message.get('tool_calls') or []
        if not calls:
            if not message.get('content'):raise ValueError('Agent returned no answer')
            return {'model_calls':state['model_calls']+1,'pending_calls':[],
                'answer':message['content']}
        return {'messages':[*messages,{'role':'assistant','content':message.get('content'),
            'tool_calls':calls}],'model_calls':state['model_calls']+1,
            'pending_calls':calls,'answer':None}

    def tool_node(state:AgentState):
        messages=list(state['messages']);activity=list(state['activity'])
        for call in state['pending_calls']:
            if limits:limits.tool()
            name=call['function']['name']
            if name not in bound:raise ValueError('Agent requested an unavailable tool')
            raw=call['function']['arguments']
            args=json.loads(raw) if isinstance(raw,str) else raw
            if limits:limits.event(agent_run_id=agent_run_id,agent=agent_name,event_type='tool',tool_name=name,status='running',summary=f'Running {name.replace("_"," ")}',details={'step':limits.tool_steps})
            try:
                result=bound[name].invoke(args)
            except Exception:
                if limits:limits.event(agent_run_id=agent_run_id,agent=agent_name,event_type='tool',tool_name=name,status='failed',summary=f'Failed {name.replace("_"," ")}',details={'step':limits.tool_steps})
                raise
            activity.append({'tool':name,'summary':f'Used {name.replace("_"," ")}'})
            if limits:
                limits.add_tokens(estimate_tokens(result))
                limits.event(agent_run_id=agent_run_id,agent=agent_name,event_type='tool',tool_name=name,status='completed',summary=f'Completed {name.replace("_"," ")}',details={'step':limits.tool_steps})
            messages.append({'role':'tool','tool_call_id':call['id'],'content':json.dumps(result,default=str)})
        return {'messages':messages,'activity':activity,'pending_calls':[]}

    graph=StateGraph(AgentState)
    graph.add_node('model',model_node)
    graph.add_node('tools',tool_node)
    graph.add_edge(START,'model')
    graph.add_conditional_edges('model',lambda state:'tools' if state['pending_calls'] else END,
        ['tools',END])
    graph.add_edge('tools','model')
    result=graph.compile().invoke({'messages':[{'role':'system','content':system},
        {'role':'user','content':user}],'activity':[],'model_calls':0,
        'pending_calls':[],'answer':None},config={'recursion_limit':max_steps*2+2})
    return result['answer'],result['activity']
