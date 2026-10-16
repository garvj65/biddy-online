export type Category = 'deadline'|'eligibility'|'certification'|'submission'|'scope'|'commercial'|'risk';
export type Fact = {id:string;category:Category;label:string;value:string;severity:'normal'|'watch'|'blocker';citation:{document_id:string;page:number;start:number;end:number;quote:string}};
export type Page = {number:number;text:string;kind?:'page'|'section'};
export type Analysis = {version:string;title:string;facts:Fact[];missing_information:string[];recommendation:string;provider:string;model:string;metrics:{processing_ms:number;chunks:number;verified_facts:number;rejected_facts:number;cache_hit:boolean;cost_usd:number|null;usage:unknown[]}};
export type Review = {id:string;decision:'bid'|'no_bid'|'hold';notes:string;created_at:string;brief_version:string;reviewed_fact_ids:string[]};
export type Solicitation = {id:string;title:string;filename:string;status:string;pages:Page[];analysis:Analysis|null;reviews:Review[];source_url?:string|null;created_at?:string;error?:string|null;sample?:boolean;agency?:string;facts_count?:number};
export type Connection = {url:string;token:string};
