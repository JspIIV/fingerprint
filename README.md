# Fingerprint

**An on-chain model disclosure, flagged when the discloser's own answer contradicts it.** An identity primitive for GenLayer, with a live register.

Agents are about to act for us and charge for it, and the first thing anyone will claim is which model is behind the agent. A claim about a third party, tested against a page a stranger points at, proves nothing: anyone can host a page that says anything, so a flag built that way says only that somebody made a page. Fingerprint removes the stranger and the page. The subject of a claim is the caller's own address, by construction, not a name anyone can assign. The subject answers the fingerprint challenge in their own transaction, and that answer is stored on chain as their own bytes. A round of GenLayer validators reads the subject's own committed answer against the model they claimed, and flags the disclosure if the answer reveals a different model.

## How it works

1. **`register(model, challenge)`** — you disclose that you run `model`, with a fingerprint `challenge` (a prompt whose answer reveals the model). The subject is `gl.message.sender_address`, you, by construction.
2. **`answer(claim_id, response)`** — **only the subject** answers, and only once. The answer is committed on chain as the subject's own bytes.
3. **`verify(claim_id)`** — open to anybody. A GenLayer round reads the subject's on-chain answer against the claimed model and returns `CONTRADICTS` / `CONSISTENT` / `UNCLEAR`. `CONTRADICTS` (the answer reveals a different model) **flags** the claim; `CONSISTENT` clears it; `UNCLEAR` leaves it open to verify again.
4. **`record(address)`** — the subject's record: model claims disclosed, and claims flagged as self-contradicting.

Reads: `status(id)`, `claim(id)`, `size()`, `page(start, count)`.

## Provenance, settled by construction

The gap a steward named in the first version, that any tester could point an unauthenticated page at a claim and trigger a reputational flag, so the contract never established that the subject produced the response, is closed here, not patched. The subject is the caller's own address, never a name assigned to a third party. Only the subject can answer. The judged text is the subject's own on-chain bytes, in their own transaction. **The contract fetches nothing from the web**, so there is no page to forge and no one can answer for a subject who did not. The tests cover the fabrication and impersonation cases directly.

## What it does and does not prove

This catches a self-contradiction, not a hidden lie. An operator who answers consistently while running something else is not caught here, and the disclosure says so. What it establishes is an on-chain, un-forgeable, consensus-checked record of what an agent claimed and answered, in which a claim whose own answer contradicts it is flagged, by consensus, and cannot be disowned. Only a `CONTRADICTS`, drawn from the subject's own committed answer, moves anything; a claim left standing is not a certificate, only an uncontradicted disclosure, and no one can remove a flag. Every verification is kept, append-only.

## Why it needs GenLayer

Whether an answer reveals a different model than the one claimed is a judgement over real-world text that no ordinary contract can make and no single referee should be trusted with. GenLayer validators each read the on-chain answer and reach consensus on one categorical field.

## Tests

`python tests/fingerprint_rules.py` — the rules exercised through the real `register()`, `answer()` and `verify()` on a Fingerprint built against a stub of the runtime, with only the verdict controlled. It proves provenance by construction (the subject is the sender, only the subject can answer, the answer is their own on-chain bytes, and no web page is ever fetched), only a `CONTRADICTS` flags, a `CONSISTENT` clears, `UNCLEAR` leaves a claim open, a settled claim is not re-judged, a flag cannot be removed, and history is preserved. 22 checks, covering the fabrication and impersonation cases.

## Live

- **Contract (GenLayer Asimov):** `0xde7e7A9Aae774ed0BdF62B45463e9A355E70df88`
- Explorer: https://explorer-asimov.genlayer.com/address/0xde7e7A9Aae774ed0BdF62B45463e9A355E70df88
- **App:** https://jspiiv.github.io/fingerprint/ — reads the register from chain without a wallet; registering, answering and verifying are transactions on Asimov.

## Proven on Asimov

`scripts/prove.mjs`, `results/proved.json`. A subject discloses it runs Claude, with a fingerprint challenge, and answers on chain:
- a third party cannot answer the subject's claim; the attempt leaves the claim awaiting.
- an answer consistent with the claim → verified → **CONSISTENT**, the claim is cleared.
- an answer that names a different model ("I am GPT-4, by OpenAI") → verified → **CONTRADICTS** → `FLAGGED`, and the subject's `record` gains a flag.
- a settled claim cannot be verified again.

## Where it stops, plainly

It judges what a subject's own committed answer shows about the model behind it, not the model itself: write a challenge whose answer actually reveals the model. It records a signal, not a certificate: a claim left standing only means the subject's own answer has not been shown to contradict it.

## Licence

AGPL-3.0-or-later.
