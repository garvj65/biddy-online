import type {Solicitation, Fact, Page, Category} from './types';
import { sourceReference } from './core.mjs';

const documentText = [
`ILLUSTRATIVE SOLICITATION — NOT A LIVE PROCUREMENT
Digital services & Drupal support
Solicitation: BIDDY-SAMPLE-014
Agency: Civic Services Office (fictional)

01  OPPORTUNITY OVERVIEW
The contractor shall provide Drupal 10 website maintenance, accessibility remediation, security patching and managed cloud support for the Civic Services Office.
The period of performance is twelve months from award, with two optional twelve-month extensions.

02  IMPORTANT DATES
Proposals are due October 30, 2026 at 5:00 PM Eastern Time.
Questions must be submitted by October 21, 2026 at 12:00 PM Eastern Time.
Dates in this illustrative document are examples only. They do not describe a real procurement.`,
`ILLUSTRATIVE SOLICITATION — NOT A LIVE PROCUREMENT
Digital services & Drupal support

03  ELIGIBILITY & REGISTRATION
This procurement is a total small business set-aside under NAICS 541511, with a size standard of $34 million.
Offerors must maintain an active SAM registration at the time of award.
The offeror shall identify one Drupal technical lead and one accessibility specialist, with resumes and evidence of two comparable projects.

04  DELIVERY REQUIREMENTS
The technical lead must attend on-site meetings in Arlington, Virginia twice each month; remote-only delivery is not acceptable.
The contractor shall provide critical incident acknowledgement within one hour, including weekends and federal holidays.
The agency will evaluate a transition plan covering the first thirty days of service.`,
`ILLUSTRATIVE SOLICITATION — NOT A LIVE PROCUREMENT
Digital services & Drupal support

05  SUBMISSION & EVALUATION
Submit separate technical and price volumes through the designated procurement portal; the technical volume must not exceed twenty pages, excluding resumes.
Award will follow a best-value evaluation of technical approach, past performance and price; the agency has not published relative factor weights in this document.
The contract will use firm-fixed-price monthly payments; offerors must include all travel costs in their pricing.

06  AMENDMENTS & CHECKS
Offerors are responsible for checking for amendments and acknowledging each amendment in their proposal.
No contract ceiling, incumbent information or complete evaluation rubric is supplied in this illustrative document.`
];

export function demoDocuments():Solicitation[] {
  const id='sample-drupal';
  const pages:Page[]=documentText.map((text,i)=>({number:i+1,text,kind:'section'}));
  const sourceFacts:[Category,string,string,number,Fact['severity']][]=[
    ['deadline','Proposal deadline','Proposals are due October 30, 2026 at 5:00 PM Eastern Time.',1,'normal'],
    ['deadline','Questions deadline','Questions must be submitted by October 21, 2026 at 12:00 PM Eastern Time.',1,'normal'],
    ['eligibility','Small business set-aside','This procurement is a total small business set-aside under NAICS 541511, with a size standard of $34 million.',2,'normal'],
    ['certification','Active SAM registration','Offerors must maintain an active SAM registration at the time of award.',2,'normal'],
    ['eligibility','Key personnel & past performance','The offeror shall identify one Drupal technical lead and one accessibility specialist, with resumes and evidence of two comparable projects.',2,'watch'],
    ['risk','Twice-monthly on-site meetings','The technical lead must attend on-site meetings in Arlington, Virginia twice each month; remote-only delivery is not acceptable.',2,'watch'],
    ['scope','One-hour incident response','The contractor shall provide critical incident acknowledgement within one hour, including weekends and federal holidays.',2,'watch'],
    ['submission','Two volumes, twenty-page limit','Submit separate technical and price volumes through the designated procurement portal; the technical volume must not exceed twenty pages, excluding resumes.',3,'normal'],
    ['commercial','Travel included in fixed price','The contract will use firm-fixed-price monthly payments; offerors must include all travel costs in their pricing.',3,'watch'],
    ['risk','Check and acknowledge amendments','Offerors are responsible for checking for amendments and acknowledging each amendment in their proposal.',3,'watch'],
  ];
  const facts:Fact[]=sourceFacts.map(([category,label,quote,page,severity],i)=>({id:`sample-fact-${i}`,category,label,value:quote,severity,citation:sourceReference(id,pages,page,quote)}));
  return [{id,title:'Digital services & Drupal support',agency:'Civic Services Office',filename:'digital-services-sample.txt',status:'ready',pages,sample:true,reviews:[],created_at:new Date().toISOString(),analysis:{version:'sample-v1',title:'Digital services & Drupal support',facts,missing_information:['Confirm your small business status and active SAM registration.','Verify the availability of the named technical lead and accessibility specialist.','Confirm ability to staff Arlington meetings and weekend incident coverage.','Retrieve the full evaluation rubric and any amendments before deciding.'],recommendation:'review_required',provider:'curated-sample',model:'manually-authored',metrics:{processing_ms:0,chunks:3,verified_facts:facts.length,rejected_facts:0,cache_hit:false,cost_usd:0,usage:[]}}}];
}
