import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sourceReference,canReview,localScan,briefMarkdown} from '../src/core.mjs';

test('source references reject invented quotes and resolve exact offsets',()=>{
 const pages=[{number:1,text:'Header\nProposals are due Friday at 5 PM ET.\nEnd.'}];
 const c=sourceReference('a',pages,1,'Proposals are due Friday at 5 PM ET.');
 assert.equal(pages[0].text.slice(c.start,c.end),c.quote);
 assert.throws(()=>sourceReference('a',pages,1,'Monday'),/does not exist/);
 assert.throws(()=>sourceReference('a',pages,2,'Header'),/does not exist/);
});
test('review gate requires every finding, acknowledged gaps, and useful rationale',()=>{
 const facts=[{id:'a'},{id:'b'}];
 assert.equal(canReview(facts,['a'],true,'This is a reason.'),false);
 assert.equal(canReview(facts,['a','b'],false,'This is a reason.'),false);
 assert.equal(canReview([],[],true,'This is a reason.'),false);
 assert.equal(canReview(facts,['a','b'],true,'          '),false);
 assert.equal(canReview(facts,['a','b'],true,'Staffing is available.'),true);
});
test('local scan preserves timezone and source text, distinguishing question and response dates',()=>{
 const pages=[{number:1,kind:'section',text:'EXAMPLE SOLICITATION\nProposals are due October 30, 2026 at 5:00 PM Eastern Time.\nQuestions must be submitted by October 20, 2026 at noon ET.\nThis is a total small business set-aside.\nSubmit via the portal.'}];
 const a=localScan('a',pages);
 assert.equal(a.facts.filter(f=>f.category==='deadline').length,2);
 assert.ok(a.facts.some(f=>f.value.includes('Eastern Time')));
 for(const f of a.facts) assert.equal(pages[0].text.slice(f.citation.start,f.citation.end),f.citation.quote);
});
test('exports cannot present an unreviewed brief as approved',()=>{
 const pages=[{number:1,text:'Proposals are due October 30, 2026 at 5:00 PM Eastern Time.'}];
 const a=localScan('a',pages);const doc={title:'Example',filename:'example.txt',pages,analysis:a,reviews:[]};
 const draft=briefMarkdown(doc);assert.match(draft,/DRAFT — NOT REVIEWED/);assert.match(draft,/Eastern Time/);assert.match(draft,/characters/);
 const approved=briefMarkdown({...doc,reviews:[{brief_version:a.version,decision:'hold',notes:'Need staffing confirmation.',created_at:'2026-10-15'}]});
 assert.match(approved,/Status: HOLD/);assert.match(approved,/Need staffing confirmation/);
});

test('absence of a deadline and missing timezone remain explicit gaps',()=>{
 const noDate=localScan('a',[{number:1,text:'No response schedule or closing date is specified in this excerpt.\nQuestions must be submitted by October 20, 2026 at noon ET.'}]);
 assert.equal(noDate.facts.filter(f=>f.category==='deadline').length,1);
 assert.ok(noDate.missing_information.some(m=>m.includes('Response deadline')));
 const noZone=localScan('a',[{number:1,text:'Proposals are due November 12, 2026 at 5:00 PM.'}]);
 assert.ok(noZone.missing_information.some(m=>m.includes('timezone')));
});
