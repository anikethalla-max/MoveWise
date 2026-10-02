export type Money = string | null;
export interface Profile { id: string; destination_city: string; workplace_area: string | null; moving_date: string | null; monthly_limit: Money; upfront_limit: Money; household_size: number; housing_preferences: string | null; commute_preferences: string | null }
export type ProfileInput = Omit<Profile, 'id'>;
export interface Housing { id: string; name: string; locality: string; rent: Money; maintenance: Money; deposit: Money; furnishing: string | null; notes: string | null; commute_minutes: number | null; listing_link: string | null; source: 'user-entered' | 'synthetic demo' }
export type HousingInput = Omit<Housing, 'id' | 'source'>;
export interface Budget { rent: Money; maintenance: Money; utilities: Money; food: Money; transport: Money; miscellaneous: Money; deposit: Money; moving_costs: Money; setup_costs: Money; monthly_total: Money; upfront_nonrefundable: Money; upfront_refundable: Money; upfront_total: Money }
export type BudgetInput = Omit<Budget, 'monthly_total' | 'upfront_nonrefundable' | 'upfront_refundable' | 'upfront_total'>;
export interface DocumentRecord { id:string; name:string; size_bytes:number; visibility:'private'|'shared-demo'; status:'pending'|'processing'|'ready'|'failed'; error:string|null; created_at:string }
export interface Citation { chunk_id:string; document_id:string; document_name:string; visibility:string; page:number|null; section:string|null; excerpt:string; score:number|null }
export interface DocumentAnswer { answer:string; citations:Citation[]; missing_information:string[]; conflicts:string[]; outcome_status:'answered'|'partial'|'unsupported'; activity:{tool:string;summary:string}[] }
export interface AgentActivity { tool:string; summary:string }
export interface HomeComparison { id:string; name:string; locality:string; source:string; commute_minutes:number|null; costs:{breakdown:Record<string,Money>;monthly_total:Money;upfront_total:Money;refundable_deposit:Money;monthly_limit:Money;upfront_limit:Money;monthly_affordable:boolean|null;upfront_affordable:boolean|null};score:number;score_possible:number;strengths:string[];tradeoffs:string[];missing_information:string[] }
export interface HousingAdvice { explanation:string; targeted_question:string|null; recommendations:HomeComparison[]; comparison:HomeComparison[]; activity:AgentActivity[]; scoring:Record<string,number> }
export interface PlanTask { id:string; title:string; stage:'before-moving'|'moving-day'|'after-moving';due_date:string|null;priority:'high'|'medium'|'low';category:string;source_kind:'general'|'document';citation_chunk_ids:string[];completed:boolean }
export interface PlanVersion { id:string;version:number;summary:string;tasks:PlanTask[];budget_concerns:string[];assumptions:string[];missing_information:string[];citations:Citation[];created_at:string }
export interface PlanProposal { id:string;base_version:number;status:'pending'|'confirmed'|'cancelled';candidate:Omit<PlanVersion,'id'|'version'|'created_at'>;changes:{additions:PlanTask[];removals:PlanTask[];edits:{before:PlanTask;after:PlanTask}[]};applied_version:number|null;created_at:string }
export interface PlanningAdvice { explanation:string;targeted_question:string|null;proposal:PlanProposal|null;activity:AgentActivity[] }
export interface RunEvent { id:number;root_run_id:string;agent_run_id:string;event_type:string;agent:string;tool_name:string|null;status:string;summary:string;details:Record<string,unknown>;created_at:string }
export interface AgentRunRecord { id:string;conversation_id:string;parent_run_id:string|null;agent:string;status:string;request:string;result:CoordinatorResult|null;error:string|null;cancel_requested:boolean;created_at:string;updated_at:string }
export interface SpecialistResult { agent:'housing'|'document'|'planning';run_id:string;status:string;result?:HousingAdvice|DocumentAnswer|PlanningAdvice;error?:string }
export interface CoordinatorResult { answer:string;citations:Citation[];missing_information:string[];conflicts:string[];specialist_results:SpecialistResult[];activity:AgentActivity[];status:string }
export interface ConversationRecord { id:string;title:string;created_at:string }
export interface ConversationDetail extends ConversationRecord { messages:{id:string;role:'user'|'assistant';content:string;payload:CoordinatorResult|null;run_id:string|null;created_at:string}[];runs:AgentRunRecord[] }
