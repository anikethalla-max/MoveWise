import type { Budget, BudgetInput, Housing, HousingInput, Profile, ProfileInput, Money, DocumentRecord, DocumentAnswer, HousingAdvice, PlanVersion, PlanProposal, PlanningAdvice, ConversationRecord, ConversationDetail, AgentRunRecord, RunEvent } from '@/types';

const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
export const apiBase = base;
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}${path}`, { credentials: 'include', headers: { 'Content-Type': 'application/json' }, ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message || body?.detail || `Request failed (${response.status})`);
  }
  return response.status === 204 ? undefined as T : response.json();
}
const put = (body: unknown): RequestInit => ({ method: 'PUT', body: JSON.stringify(body) });
async function upload(file: File): Promise<DocumentRecord> {
  const form = new FormData(); form.append('file', file);
  const response = await fetch(`${base}/documents`, {method:'POST',credentials:'include',body:form});
  if (!response.ok) { const body = await response.json().catch(()=>null); throw new Error(body?.error?.message || body?.detail || `Upload failed (${response.status})`); }
  return response.json();
}
export const api = {
  session: () => request<{ready: boolean}>('/session', { method: 'POST' }),
  profile: () => request<Profile | null>('/profile'),
  saveProfile: (body: ProfileInput) => request<Profile>('/profile', put(body)),
  housing: () => request<Housing[]>('/housing'),
  addHousing: (body: HousingInput) => request<Housing>('/housing', { method: 'POST', body: JSON.stringify(body) }),
  saveHousing: (id: string, body: HousingInput) => request<Housing>(`/housing/${id}`, put(body)),
  deleteHousing: (id: string) => request<void>(`/housing/${id}`, { method: 'DELETE' }),
  budget: () => request<Budget>('/budget'),
  saveBudget: (body: BudgetInput) => request<Budget>('/budget', put(body)),
  documents: () => request<DocumentRecord[]>('/documents'),
  uploadDocument: upload,
  retryDocument: (id:string) => request<DocumentRecord>(`/documents/${id}/retry`,{method:'POST'}),
  deleteDocument: (id:string) => request<void>(`/documents/${id}`,{method:'DELETE'}),
  askDocuments: (question:string,document_ids:string[]|null) => request<DocumentAnswer>('/documents/questions/ask',{method:'POST',body:JSON.stringify({question,document_ids})}),
  askHousingAgent: (question:string) => request<HousingAdvice>('/agents/housing',{method:'POST',body:JSON.stringify({question})}),
  selectedHome: () => request<{home_id:string;name:string}|null>('/selection/home'),
  selectHome: (home_id:string) => request<{home_id:string;name:string}>('/selection/home',put({home_id})),
  clearSelectedHome: () => request<void>('/selection/home',{method:'DELETE'}),
  currentPlan: () => request<PlanVersion|null>('/plans/current'),
  planHistory: () => request<PlanVersion[]>('/plans/history'),
  planProposals: () => request<PlanProposal[]>('/plans/proposals'),
  askPlanningAgent: (question:string) => request<PlanningAdvice>('/agents/planning',{method:'POST',body:JSON.stringify({question})}),
  confirmProposal: (id:string) => request<PlanVersion>(`/plans/proposals/${id}/confirm`,{method:'POST'}),
  cancelProposal: (id:string) => request<PlanProposal>(`/plans/proposals/${id}/cancel`,{method:'POST'}),
  completeTask: (id:string,completed:boolean) => request<{task_id:string;completed:boolean}>(`/plans/tasks/${id}/completion`,put({completed})),
  conversations: () => request<ConversationRecord[]>('/assistant/conversations'),
  conversation: (id:string) => request<ConversationDetail>(`/assistant/conversations/${id}`),
  sendAssistant: (content:string,request_key:string,conversation_id:string|null) => request<{run_id:string;conversation_id:string;created:boolean}>('/assistant/messages',{method:'POST',body:JSON.stringify({content,request_key,conversation_id})}),
  assistantRun: (id:string) => request<{run:AgentRunRecord;specialist_runs:AgentRunRecord[];events:RunEvent[]}>(`/assistant/runs/${id}`),
  cancelAssistantRun: (id:string) => request<AgentRunRecord>(`/assistant/runs/${id}/cancel`,{method:'POST'}),
};
export const money = (value: Money) => value === null ? 'Unknown' : new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR'}).format(Number(value));
export const date = (value: string | null) => value ? new Date(`${value}T00:00:00`).toLocaleDateString('en-IN', {day:'numeric',month:'long',year:'numeric'}) : 'Not set';
