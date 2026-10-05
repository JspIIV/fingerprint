# Fingerprint

**A public register that flags an agent whose own output contradicts the model it claims to run.** An identity primitive for GenLayer, with a live register.

Agents are about to act for us and charge for it, and the first thing anyone will lie about is which model is behind the agent. You cannot prove a positive from a page the operator controls: a transcript can be made to say anything. What you can do is catch a contradiction. Fingerprint registers a claim, that an agent runs a model, together with a fingerprint challenge, a prompt whose answer reveals the model. Anyone may then submit the subject's public response to that challenge, and a round of GenLayer validators reads it and decides whether the response contradicts the claimed model. If the agent's own answer names a different model, the claim is flagged.

## How it works

1. **`register(subject, model, challenge)`** — a claim that `subject` runs `model`, with a fingerprint `challenge` (a prompt whose answer reveals the model). Bound to `gl.message.sender_address`. Starts `CLAIMED`.
2. **`test(claim_id, response_url)`** — open to anybody. It names a public page carrying the subject's own response to the challenge. The contract **fetches it** and a GenLayer round returns `CONTRADICTS` / `CONSISTENT` / `UNCLEAR`. `CONTRADICTS` (the response reveals a different model) **flags** the claim and marks the claimant; `CONSISTENT` leaves it standing and counts a consistency; `UNCLEAR` changes nothing.
3. **`record(address)`** — the claimant's record: model claims made, and claims flagged as contradicted.

Reads: `status(id)`, `history(id)`, `get(id)`, `size()`, `page(start, count)`.

## Why it cannot be gamed

A positive is not provable from evidence the subject controls, so Fingerprint does not sell one. Only a `CONTRADICTS`, drawn from the subject's **own** public response revealing a different model, changes anything, and it is the negative. A claim that has not been contradicted is not a certificate; it is simply unchallenged, and that standing can never be manufactured, only left intact. `CONSISTENT` and `UNCLEAR` move no reputation, and an unrelated, unreadable, or not-found page never flags anyone. Every test is kept, append-only, on the claim.

## Why it needs GenLayer

Whether a response reveals a different model than the one claimed is a judgement over real-world text that no ordinary contract can make and no single referee should be trusted with. GenLayer validators each fetch the response and reach consensus on one categorical field; the flag is built from the subject's own output, read in the round.

## Tests

`python tests/fingerprint_rules.py` — the rules exercised through the real `register()` and `test()` on a Fingerprint built against a stub of the runtime, with the response and verdict controlled. It proves only a `CONTRADICTS` flags a claim, a `CONSISTENT` leaves it standing, an unreadable or not-found response never flags anyone, the challenge is put in front of the round, a flagged claim is settled, and history is preserved. 19 checks.

## Live

- **Contract (GenLayer Asimov):** `0xf0337f0E6C60e312Fa95867D65dBA82032ec9Dd8`
- Explorer: https://explorer-asimov.genlayer.com/address/0xf0337f0E6C60e312Fa95867D65dBA82032ec9Dd8
- **App:** https://jspiiv.github.io/fingerprint/ — reads the register from chain without a wallet; registering and testing are transactions on Asimov.

## Proven on Asimov

`scripts/prove.mjs`, `results/proved.json`. A claim that an agent runs Claude, with a fingerprint challenge, tested against the subject's own responses in `docs/`:
- a response that identifies as the claimed model (`response-consistent.txt`) → **CONSISTENT**, the claim stands.
- an unreadable response → `UNCLEAR`, the claim stands.
- a response that names a different model (`response-contradicts.txt`, "I am GPT-4, by OpenAI") → **CONTRADICTS** → `FLAGGED`, and the claimant's `record` gains a flag.
- a flagged claim cannot be tested again; `history` keeps every test.

## Where it stops, plainly

It judges what a public response shows about the model behind it, not the model itself: name a challenge whose answer actually reveals the model, and a response page a third party can open. It records a signal, not a certificate: a claim left standing only means nobody has shown its own output to contradict it.

## Licence

AGPL-3.0-or-later.
