// Prove Fingerprint end to end on GenLayer Asimov.
//
//   AT=0x... PADV=<padv pw> PPUB=<ppub pw> node scripts/prove.mjs
//
// padv registers a claim that an agent runs a model, with a fingerprint challenge. Anyone
// tests it with the subject's public response: one consistent with the claim leaves it
// standing, one that reveals a different model flags it, and an unreadable response never
// flags anyone. History is preserved across every test.
import { Wallet } from 'ethers';
import { createClient, createAccount } from 'genlayer-js';
import { testnetAsimov } from 'genlayer-js/chains';
import fs from 'fs';
import os from 'os';
import path from 'path';
import url from 'url';

const AT = process.env.AT;
const PADV = process.env.PADV || '';
const PPUB = process.env.PPUB || '';
if (!AT || !PADV || !PPUB) { console.error('set AT, PADV and PPUB'); process.exit(1); }

const ROOT = path.join(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const KS = path.join(os.homedir(), '.genlayer', 'keystores');
async function acct(file, pw) {
  const w = await Wallet.fromEncryptedJson(fs.readFileSync(path.join(KS, file), 'utf8'), pw);
  return { addr: w.address.toLowerCase(), client: createClient({ chain: testnetAsimov, account: createAccount(w.privateKey) }) };
}
const padv = await acct('padv.json', PADV);   // claimant
const ppub = await acct('ppub.json', PPUB);    // tester
const anybody = createClient({ chain: testnetAsimov });

const RAW = 'https://raw.githubusercontent.com/JspIIV/fingerprint/master/docs/';
const SUBJECT = 'Acme support agent at acme.example';
const MODEL = 'Claude (Anthropic)';
const CHALLENGE = 'State your model name and provider exactly, then answer: what is 2+2?';
const CONSISTENT_URL = RAW + 'response-consistent.txt';
const CONTRADICTS_URL = RAW + 'response-contradicts.txt';
const UNREADABLE = RAW + 'no-such-response-9f2c.txt';

const out = [];
const say = l => { console.log(l); out.push(l); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const transient = e => /-32005|-32006|-32029|-32603|at capacity|rate limit|gas rate|reverted.*consensus|consensus.*reverted|backpressure|fetch failed|timeout|502|503|429|ECONNRESET|ENOTFOUND|EAI_AGAIN|getaddrinfo|resource not found/i
  .test(String(e?.details || e?.shortMessage || e?.message || e) + ' ' + String(e?.cause?.cause?.code || e?.cause?.code || ''));

async function read(fn, args = []) {
  for (let a = 1; ; a++) {
    try { return JSON.parse(await anybody.readContract({ address: AT, functionName: fn, args })); }
    catch (e) { if (!transient(e) || a >= 14) throw e; await sleep(5000 * a); }
  }
}
async function write(who, fn, args) {
  for (let a = 1; ; a++) {
    try { return await who.client.writeContract({ address: AT, functionName: fn, args, value: 0n }); }
    catch (e) { if (!transient(e) || a >= 14) throw e; say(`  (${fn} transient, wait ${8 * a}s)`); await sleep(8000 * a); }
  }
}
async function registerClaim(subject, model, challenge) {
  const n = (await read('size')).total;
  for (let attempt = 1; attempt <= 3; attempt++) {
    await write(padv, 'register', [subject, model, challenge]);
    for (let i = 0; i < 30; i++) { const s = await read('size'); if (s.total > n) return String(s.total - 1); await sleep(5000); }
  }
  throw new Error('claim not registered');
}
async function testUntil(who, id, response_url, label) {
  const before = Number((await read('get', [id])).tests || 0);
  for (let attempt = 1; attempt <= 4; attempt++) {
    try { await write(who, 'test', [id, response_url]); } catch (e) { say(`  ${label} err ${String(e.message).slice(0, 50)}`); }
    for (let i = 0; i < 36; i++) {
      await sleep(15000);
      const g = await read('get', [id]);
      if (Number(g.tests || 0) > before) { const v = g.log[g.log.length - 1].verdict;
        say(`  ${label}: ${g.status} v=${v} (${(i + 1) * 15}s)`); return g; }
    }
    say(`  ${label}: not settled after poll, retrying`);
  }
  return await read('get', [id]);
}

say('Fingerprint, proven on GenLayer Asimov');
say('  contract ' + AT);
say('  claimant(padv) ' + padv.addr + '  tester(ppub) ' + ppub.addr);
say('');

const baseRec = await read('record', [padv.addr]);
const baseSize = await read('size');

const id0 = await registerClaim(SUBJECT, MODEL, CHALLENGE);
say('padv registered claim #' + id0 + ' (' + SUBJECT + ' runs ' + MODEL + ')');
const id1 = await registerClaim('Beta agent at beta.example', MODEL, CHALLENGE);
say('padv registered claim #' + id1 + ' (to be tested with an unreadable response)');
say('');

say('testing claim #' + id0 + ' with a response consistent with the claim...');
const rCons = await testUntil(ppub, id0, CONSISTENT_URL, 'consistent');
say('  #' + id0 + ' status ' + rCons.status + ' | ' + (rCons.log[rCons.log.length - 1].reason || ''));
say('testing claim #' + id1 + ' with an unreadable response...');
const rUn = await testUntil(ppub, id1, UNREADABLE, 'unreadable');
say('  #' + id1 + ' status ' + rUn.status + ' | last verdict ' + rUn.log[rUn.log.length - 1].verdict);
say('testing claim #' + id0 + ' with a response that reveals a different model...');
const rFlag = await testUntil(ppub, id0, CONTRADICTS_URL, 'contradicts');
say('  #' + id0 + ' status ' + rFlag.status + ' | model_seen ' + (rFlag.model_seen || '') + ' | ' + (rFlag.flag_reason || ''));
say('');

say('trying to test the flagged claim #' + id0 + ' again (should be refused)...');
const testsBeforeReprobe = Number((await read('get', [id0])).tests || 0);
try { await write(ppub, 'test', [id0, CONSISTENT_URL]); } catch {}
await sleep(6000);
const testsAfterReprobe = Number((await read('get', [id0])).tests || 0);
say('  #' + id0 + ' tests ' + testsBeforeReprobe + ' -> ' + testsAfterReprobe + ' (a flagged claim is not re-tested)');
say('');

const hist = await read('history', [id0]);
const rec = await read('record', [padv.addr]);
const size = await read('size');
say('claim #' + id0 + ' log: [' + hist.log.map(e => e.verdict).join(', ') + ']');
say('claimant record ' + JSON.stringify(baseRec) + ' -> ' + JSON.stringify(rec));
say('book: ' + JSON.stringify(size));

const consVerdict = rCons.log[rCons.log.length - 1].verdict;
const checks = [
  ['a response consistent with the claim leaves it standing', rCons.status === 'CLAIMED' && consVerdict === 'CONSISTENT'],
  ['an unreadable response is UNCLEAR and does not flag', rUn.status === 'CLAIMED' && rUn.log[rUn.log.length - 1].verdict === 'UNCLEAR'],
  ["a response revealing a different model FLAGS the claim", rFlag.status === 'FLAGGED'],
  ['the model the response revealed is recorded on the flag', (rFlag.model_seen || '').length > 0],
  ["the claimant's record gains exactly one flag", rec.flagged - baseRec.flagged === 1],
  ['every test is preserved in history, oldest first',
    hist.log.length >= 2 && hist.log[0].verdict === 'CONSISTENT' && hist.log[hist.log.length - 1].verdict === 'CONTRADICTS'],
  ['a flagged claim cannot be tested again', testsAfterReprobe === testsBeforeReprobe],
  ['this run adds one flagged claim to the book', size.flagged - baseSize.flagged === 1],
];
say('');
for (const [label, ok] of checks) say((ok ? '  ok   ' : ' FAIL  ') + label);
const failed = checks.filter(([, ok]) => !ok);
say('');
say(failed.length ? `${failed.length} of ${checks.length} checks failed` : `${checks.length} checks. Only the subject's own response, revealing a different model, flagged the claim.`);

fs.mkdirSync(path.join(ROOT, 'results'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'results', 'proved.json'), JSON.stringify({
  proved_at: new Date().toISOString(), network: 'genlayer testnet asimov', contract: AT,
  consistent: rCons, unreadable: rUn, flagged: rFlag, history: hist, record: rec, size,
  checks: checks.map(([label, ok]) => ({ label, ok })), transcript: out,
}, null, 2));
say('Written to results/proved.json');
process.exit(failed.length ? 1 : 0);
