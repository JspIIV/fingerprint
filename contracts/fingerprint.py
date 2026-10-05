# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Fingerprint: a public register that flags an agent whose own output contradicts the model it claims to run.

Agents are about to act for us and charge for it, and the first thing anyone will lie about
is which model is behind the agent. You cannot prove a positive from a page the operator
controls: a transcript can be made to say anything. What you can do is catch a contradiction.
Fingerprint registers a claim, "this agent runs that model", together with a fingerprint
challenge, a prompt whose answer reveals the model. Anyone may then submit the subject's
public response to that challenge, and a round of GenLayer validators reads it and decides
whether the response contradicts the claimed model. If the agent's own answer names a
different model, the claim is flagged.

A claim that has not been contradicted is not a certificate; it is simply unchallenged.
Originality here is the absence of a proven contradiction, and that absence can never be
manufactured, only left standing.

## What it settles, per test

    CONTRADICTS  the response reveals a different model than claimed -> the claim is FLAGGED
    CONSISTENT   the response was read and is consistent with the claimed model -> the claim stands
    UNCLEAR      the response could not be read, or does not reveal the model -> nothing changes

Only CONTRADICTS flags a claim, and only from the subject's own public response. An unreadable
or unrelated page never flags anyone.

## What it refuses

The claim and its fingerprint challenge are fixed when registered and cannot be edited. The
claimant is bound to the caller of register, the tester to the caller of test. A response that
does not reveal the model is UNCLEAR, never a flag. Every test is kept, append-only, on the
claim. Once a claim is flagged it is settled.

## Where it stops, plainly

It judges what a public response shows about the model behind it, not the model itself: name a
challenge whose answer actually reveals the model, and a response page a third party can open.
It records a signal, not a certificate: a claim left standing only means nobody has shown its
own output to contradict it.
"""

from genlayer import *
import json

CONTRADICTS = "CONTRADICTS"
CONSISTENT = "CONSISTENT"
UNCLEAR = "UNCLEAR"
VERDICTS = (CONTRADICTS, CONSISTENT, UNCLEAR)

CLAIMED = "CLAIMED"
FLAGGED = "FLAGGED"

MAX_SUBJECT = 200
MAX_MODEL = 120
MAX_CHALLENGE = 400
MAX_URL = 300
MAX_PAGE = 6000
MAX_REASON = 300
MAX_QUOTE = 300
MAX_LOG = 60

FETCH_FAILED = "__FETCH_FAILED__"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _clip(text: str, limit: int) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit] + " [...]"


def _whole(value) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return -1


def _addr(value) -> str:
    text = str(value).strip().lower()
    if not text.startswith("0x") or len(text) != 42:
        return ""
    for character in text[2:]:
        if character not in "0123456789abcdef":
            return ""
    return text


def _url_ok(url: str) -> bool:
    text = str(url).strip()
    if len(text) < 8 or len(text) > MAX_URL or " " in text:
        return False
    return text.startswith("https://") or text.startswith("http://")


def _status_after(verdict: str):
    """Only CONTRADICTS flags a claim. Returns (status, flagged_delta, consistent_delta)."""
    if verdict == CONTRADICTS:
        return FLAGGED, 1, 0
    if verdict == CONSISTENT:
        return CLAIMED, 0, 1
    return CLAIMED, 0, 0


def _field(raw: str, name: str, allowed, fallback: str) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            said = str(obj.get(name, "")).strip().upper()
            return said if said in allowed else fallback
    except Exception:
        pass
    return fallback


def _text_field(raw: str, name: str, limit: int) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            return _clip(str(obj.get(name, "")), limit)
    except Exception:
        pass
    return ""


def _fetch(url: str) -> str:
    try:
        got = gl.nondet.web.render(url)
        page = got if isinstance(got, str) else getattr(got, "body", "")
        if isinstance(page, (bytes, bytearray)):
            page = page.decode("utf-8", "replace")
        page = _clip(str(page), MAX_PAGE)
        if not page:
            return FETCH_FAILED
        if page.strip().lower().startswith(("404: not found", "404 not found", "not found")):
            return FETCH_FAILED
        return page
    except Exception:
        return FETCH_FAILED


def _task(subject: str, model: str, challenge: str, response: str) -> str:
    return f"""Someone claims the agent or service below runs a specific model, and set a fingerprint
challenge to test it. The response page is the subject's own answer to that challenge. Read
the response and decide whether it contradicts the claimed model.

THE CLAIM:
{subject} runs the model: {model}

THE FINGERPRINT CHALLENGE (the prompt the subject was asked):
{challenge}

THE SUBJECT'S RESPONSE:
{response}

Decide one of:
  {CONTRADICTS} the response reveals or implies a DIFFERENT model than the one claimed: it names
    another model or provider, states a different version, or shows behaviour inconsistent with
    the claimed model
  {CONSISTENT} the response was read and is consistent with running the claimed model: it
    identifies as that model, or matches its known behaviour
  {UNCLEAR} the response could not be read, or does not reveal which model produced it

Judge only what the response actually shows. A response that names a different model or provider
is {CONTRADICTS}. A response that does not reveal the model is {UNCLEAR}, not {CONTRADICTS}. An
error page, a "404" or "not found" notice, an empty page, or a page unrelated to the challenge
is {UNCLEAR}, never {CONTRADICTS}.

Reply with bare JSON and nothing else:
{{"verdict": "{CONTRADICTS}" or "{CONSISTENT}" or "{UNCLEAR}",
  "model_seen": "the model the response indicates, or empty",
  "quote": "the passage that decided it, or empty",
  "reason": "one sentence naming what decided it"}}"""


class Fingerprint(gl.Contract):
    """Model claims, each flagged only when the subject's own public response reveals a different model."""

    # str(id) -> the claim as JSON, including its append-only test log.
    items: TreeMap[str, str]
    ids: DynArray[str]
    # address -> {"claims": n, "flagged": n} as JSON.
    records: TreeMap[str, str]

    def __init__(self) -> None:
        pass

    def _bump(self, who: str, claims_delta: int, flagged_delta: int) -> None:
        raw = self.records.get(who, None)
        rec = json.loads(raw) if raw is not None else {"claims": 0, "flagged": 0}
        rec["claims"] = int(rec.get("claims", 0)) + claims_delta
        rec["flagged"] = int(rec.get("flagged", 0)) + flagged_delta
        self.records[who] = json.dumps(rec)

    @gl.public.write
    def register(self, subject: str, model: str, challenge: str) -> str:
        """Claim that a subject runs a model, with a fingerprint challenge to test it. Bound to the caller."""
        claimant = gl.message.sender_address.as_hex.lower()
        subj = _clip(subject, MAX_SUBJECT)
        mdl = _clip(model, MAX_MODEL)
        chg = _clip(challenge, MAX_CHALLENGE)
        if not subj:
            return json.dumps({"ok": False, "error": "name the agent or service"})
        if not mdl:
            return json.dumps({"ok": False, "error": "name the model it is claimed to run"})
        if len(chg) < 6:
            return json.dumps({"ok": False, "error": "give a fingerprint challenge, a prompt whose answer reveals the model"})

        cid = str(len(self.ids))
        record = {
            "id": cid,
            "claimant": claimant,
            "registered_at": _now_iso(),
            "subject": subj,
            "model": mdl,
            "challenge": chg,
            "status": CLAIMED,
            "tests": 0,
            "consistent": 0,
            "flag_reason": "",
            "flag_quote": "",
            "model_seen": "",
            "log": [],
        }
        self.items[cid] = json.dumps(record)
        self.ids.append(cid)
        self._bump(claimant, 1, 0)
        return json.dumps({"ok": True, "id": cid, "status": CLAIMED})

    @gl.public.write
    def test(self, claim_id: str, response_url: str) -> str:
        """Test a claim: submit the subject's public response to the fingerprint challenge. Open to anybody.

        The contract fetches the response in the round and consensus rules CONTRADICTS,
        CONSISTENT or UNCLEAR. Only CONTRADICTS flags the claim, and it accrues to the claimant.
        """
        tester = gl.message.sender_address.as_hex.lower()
        cid = str(claim_id).strip()
        link = str(response_url).strip()
        stored = self.items.get(cid, None)
        if stored is None:
            return json.dumps({"ok": False, "error": "no claim with that id"})
        if not _url_ok(link):
            return json.dumps({"ok": False, "error": "give an http(s) URL for the subject's response"})
        record = json.loads(stored)
        if record["status"] == FLAGGED:
            return json.dumps({"ok": False, "error": "this claim is already flagged", "status": FLAGGED})

        # Copy into locals before the round. Nothing inside the block reads self
        # and nothing inside it raises.
        subject = record["subject"]
        model = record["model"]
        challenge = record["challenge"]

        def look() -> str:
            page = _fetch(link)
            if page == FETCH_FAILED:
                return json.dumps({"verdict": UNCLEAR, "model_seen": "", "quote": "",
                                   "reason": "the response page could not be read"})
            try:
                return str(gl.nondet.exec_prompt(_task(subject, model, challenge, page)))
            except Exception as error:
                return json.dumps({"verdict": UNCLEAR, "model_seen": "", "quote": "",
                                   "reason": _clip("the prompt failed: " + str(error), MAX_REASON)})

        raw = gl.eq_principle.prompt_comparative(
            look,
            principle=(
                f"Both answers must carry the same value in the field named verdict, one of "
                f"{CONTRADICTS}, {CONSISTENT} or {UNCLEAR}. That single field decides whether a model "
                "claim is flagged, so two readers differing on it disagree about whether the response "
                "reveals a different model, not about wording. The other fields are not compared, and "
                "the two readers will not have fetched byte-identical copies of the page."
            ),
        )

        verdict = _field(raw, "verdict", VERDICTS, "")
        if not verdict:
            return json.dumps({"ok": False, "error": "the round produced no verdict this contract recognises",
                               "round_said": _clip(str(raw), 400)})

        reason = _text_field(raw, "reason", MAX_REASON)
        quote = _text_field(raw, "quote", MAX_QUOTE)
        model_seen = _text_field(raw, "model_seen", MAX_MODEL)
        status, flagged_delta, consistent_delta = _status_after(verdict)

        record["tests"] = int(record.get("tests", 0)) + 1
        record["consistent"] = int(record.get("consistent", 0)) + consistent_delta
        entry = {"n": record["tests"], "at": _now_iso(), "by": tester, "response_url": link,
                 "verdict": verdict, "model_seen": model_seen, "quote": quote, "reason": reason}
        log = list(record.get("log", []))
        log.append(entry)
        if len(log) > MAX_LOG:
            log = log[-MAX_LOG:]
        record["log"] = log
        if status == FLAGGED:
            record["status"] = FLAGGED
            record["flag_reason"] = reason
            record["flag_quote"] = quote
            record["model_seen"] = model_seen
            self._bump(record["claimant"], 0, 1)
        # CONSISTENT and UNCLEAR leave the claim CLAIMED.
        self.items[cid] = json.dumps(record)
        return json.dumps({"ok": True, "id": cid, "verdict": verdict, "status": record["status"],
                           "model_seen": model_seen, "reason": reason})

    # ------------------------------------------------------------------ reads

    @gl.public.view
    def record(self, address: str) -> str:
        """A claimant's record: model claims registered, and claims flagged as contradicted."""
        a = _addr(address)
        if not a:
            return json.dumps({"exists": False, "claims": 0, "flagged": 0})
        raw = self.records.get(a, None)
        if raw is None:
            return json.dumps({"exists": False, "address": a, "claims": 0, "flagged": 0})
        rec = json.loads(raw)
        return json.dumps({"exists": True, "address": a,
                           "claims": int(rec.get("claims", 0)), "flagged": int(rec.get("flagged", 0))})

    @gl.public.view
    def status(self, claim_id: str) -> str:
        """A claim's current standing and the reason it was flagged."""
        cid = str(claim_id).strip()
        stored = self.items.get(cid, None)
        if stored is None:
            return json.dumps({"exists": False})
        record = json.loads(stored)
        return json.dumps({"exists": True, "id": cid, "status": record["status"],
                           "tests": record["tests"], "consistent": record["consistent"],
                           "model_seen": record.get("model_seen", ""), "reason": record.get("flag_reason", "")})

    @gl.public.view
    def history(self, claim_id: str) -> str:
        """The append-only log of every test run against a claim."""
        cid = str(claim_id).strip()
        stored = self.items.get(cid, None)
        if stored is None:
            return json.dumps({"exists": False})
        record = json.loads(stored)
        return json.dumps({"exists": True, "id": cid, "status": record["status"],
                           "tests": record["tests"], "log": record.get("log", [])})

    @gl.public.view
    def get(self, claim_id: str) -> str:
        """The whole claim, including its test history."""
        cid = str(claim_id).strip()
        stored = self.items.get(cid, None)
        if stored is None:
            return json.dumps({"exists": False})
        return stored

    @gl.public.view
    def size(self) -> str:
        """How many claims stand and how many are flagged."""
        claimed = 0
        flagged = 0
        for position in range(len(self.ids)):
            state = json.loads(self.items[self.ids[position]])["status"]
            if state == CLAIMED:
                claimed += 1
            elif state == FLAGGED:
                flagged += 1
        return json.dumps({"total": len(self.ids), "claimed": claimed, "flagged": flagged})

    @gl.public.view
    def page(self, start: str, count: str) -> str:
        """A slice of the claims, newest first, for a frontend to render."""
        total = len(self.ids)
        begin = _whole(start)
        want = _whole(count)
        if begin < 0:
            begin = 0
        if want < 1:
            want = 20
        if want > 50:
            want = 50
        out = []
        seen = 0
        position = total - 1 - begin
        while position >= 0 and seen < want:
            record = json.loads(self.items[self.ids[position]])
            record["test_count"] = len(record.get("log", []))
            record.pop("log", None)
            out.append(record)
            position -= 1
            seen += 1
        return json.dumps({"total": total, "start": begin, "count": len(out), "items": out})
