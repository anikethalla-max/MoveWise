'use client';
import {useEffect,useState} from 'react';
import {apiBase} from '@/lib/api';

export default function AuthGate({children}:{children:React.ReactNode}){
 const [state,setState]=useState<'loading'|'ready'|'signin'|'error'>('loading');
 const [message,setMessage]=useState('');
 const [mock,setMock]=useState(process.env.NEXT_PUBLIC_EVALUATION_MOCK_MODE==='true');
 const mode=process.env.NEXT_PUBLIC_AUTH_MODE||'development';
 useEffect(()=>{void fetch(`${new URL(apiBase).origin}/auth/status`,{credentials:'include'})
    .then(async response=>{if(!response.ok)throw new Error('Backend authentication status unavailable');const result=await response.json();setMock(Boolean(result.mock_evaluation));setState(result.authenticated?'ready':'signin')})
    .catch(e=>{setMessage((e as Error).message);setState(mode==='oidc'?'error':'ready')})},[mode]);
 if(state==='ready')return <>{mock&&<div role="status" className="bg-amber-100 text-amber-950 text-center px-3 py-2 font-bold">Deterministic evaluation simulation · responses are not a real AI run</div>}{children}{mode==='oidc'&&<a className="fixed bottom-3 right-3 bg-white border rounded-lg px-3 py-2 shadow" href={`${new URL(apiBase).origin}/auth/logout`}>Sign out</a>}</>;
 if(state==='loading')return <main className="max-w-xl mx-auto p-8" role="status">Checking sign-in…</main>;
 if(state==='error')return <main className="max-w-xl mx-auto p-8" role="alert"><h1 className="text-2xl font-bold">Sign-in unavailable</h1><p>{message}</p><button className="btn mt-3" onClick={()=>window.location.reload()}>Retry</button></main>;
 return <main className="max-w-xl mx-auto p-8"><h1 className="text-2xl font-bold">Sign in to MoveWise</h1><p className="muted mt-2">Your relocation workspace is private to your account.</p><a className="btn inline-block mt-4" href={`${new URL(apiBase).origin}/auth/login`}>Sign in</a></main>;
}
