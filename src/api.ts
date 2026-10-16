import type {Connection, Solicitation} from './types';
export async function request(connection:Connection,path:string,init:RequestInit={}) {
  const headers = new Headers(init.headers);
  headers.set('Authorization',`Bearer ${connection.token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type','application/json');
  const response=await fetch(connection.url.replace(/\/$/,'')+path,{...init,headers});
  if(!response.ok) {
    const data=await response.json().catch(()=>({detail:'The API could not complete that request.'}));
    throw new Error(typeof data.detail==='string'?data.detail:'Check the form fields and try again.');
  }
  return response;
}
export async function loadDocuments(connection:Connection):Promise<Solicitation[]> {
  const summaries=await (await request(connection,'/api/solicitations')).json();
  return Promise.all(summaries.map(async (s:{id:string})=>(await request(connection,`/api/solicitations/${s.id}`)).json()));
}
