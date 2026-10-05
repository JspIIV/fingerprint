"""The fingerprint rules, exercised through the real contract methods.

fingerprint.py is loaded against a stub of the runtime, a real Fingerprint is built, and the
assertions go through register() and test(). The stub controls the response page the round
fetches and the verdict it returns. It proves only a CONTRADICTS flags a claim (and only from
the subject's own response), a CONSISTENT leaves it standing, an unreadable or not-found page
never flags anyone, a flagged claim is settled, and history is preserved.

    python tests/fingerprint_rules.py
"""

import io
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = os.path.join(HERE, "..", "contracts", "fingerprint.py")


class _Store:
    def __init__(self, kind): self.kind = kind
    def __class_getitem__(cls, item): return cls("map" if isinstance(item, tuple) else "list")
    def make(self): return {} if self.kind == "map" else []


class _Address:
    def __init__(self, hex_value): self.as_hex = str(hex_value)
    def __str__(self): return str(self.as_hex)


class _Message:
    def __init__(self):
        self.sender_address = _Address("0x" + "0" * 40)
        self.value = 0


class _Web:
    def __init__(self):
        self.page = "a response"

    def render(self, url):
        if self.page is None:
            raise RuntimeError("could not fetch")
        return self.page


class _Nondet:
    def __init__(self, web):
        self.web = web
        self.last_prompt = None
        self.answer = "{}"

    def exec_prompt(self, task):
        self.last_prompt = task
        return self.answer


class _Write:
    def __call__(self, fn): return fn
    def payable(self, fn): return fn


class _PublicNS:
    def __init__(self):
        self.write = _Write()
        self.view = lambda fn: fn


class _EqPrinciple:
    def prompt_comparative(self, run, principle=None): return run()


class _GL:
    def __init__(self):
        self.Contract = object
        self.public = _PublicNS()
        self.message = _Message()
        self.nondet = _Nondet(_Web())
        self.eq_principle = _EqPrinciple()


def load():
    gl = _GL()
    fake = types.ModuleType("genlayer")
    fake.gl = gl
    fake.DynArray = _Store
    fake.TreeMap = _Store
    fake.u32 = int
    fake.u256 = int
    fake.Address = _Address
    sys.modules["genlayer"] = fake
    module = types.ModuleType("fingerprint_under_test")
    exec(compile(io.open(CONTRACT, encoding="utf-8").read(), CONTRACT, "exec"), module.__dict__)
    return module, gl


def fresh(module):
    contract = module.Fingerprint.__new__(module.Fingerprint)
    for field, declared in module.Fingerprint.__annotations__.items():
        setattr(contract, field, declared.make())
    contract.__init__()
    return contract


RESULTS = []


def check_(label, condition):
    RESULTS.append((label, bool(condition)))
    print(("  ok  " if condition else " FAIL "), label)


ALICE = "0x1111111111111111111111111111111111111111"
BOB = "0x2222222222222222222222222222222222222222"

SUBJECT = "Acme support agent at acme.example"
MODEL = "Claude (Anthropic)"
CHALLENGE = "State your model name and provider exactly, then answer: what is 2+2?"
U = "https://example.org/response"


def answer(verdict, model_seen="", reason="r", quote="q"):
    return json.dumps({"verdict": verdict, "model_seen": model_seen, "reason": reason, "quote": quote})


def main():
    module, gl = load()

    def as_(address): gl.message.sender_address = _Address(address)

    print("the pure outcome rule")
    check_("CONTRADICTS flags the claim", module._status_after("CONTRADICTS") == ("FLAGGED", 1, 0))
    check_("CONSISTENT leaves it claimed and counts a consistency", module._status_after("CONSISTENT") == ("CLAIMED", 0, 1))
    check_("UNCLEAR changes nothing", module._status_after("UNCLEAR") == ("CLAIMED", 0, 0))

    print("\nregistering a claim")
    c = fresh(module)
    as_(ALICE)
    check_("a claim needs a fingerprint challenge", not json.loads(c.register(SUBJECT, MODEL, "hi"))["ok"])
    reg = json.loads(c.register(SUBJECT, MODEL, CHALLENGE))
    cid = reg["id"]
    check_("a claim registers as CLAIMED", reg["ok"] and reg["status"] == "CLAIMED")
    check_("the claimant's record counts the claim, no flag",
           json.loads(c.record(ALICE)) == {"exists": True, "address": ALICE, "claims": 1, "flagged": 0})
    check_("testing with a non-url is refused", not json.loads(c.test(cid, "not a url"))["ok"])

    print("\na response consistent with the claimed model leaves the claim standing")
    as_(BOB)
    gl.nondet.answer = answer("CONSISTENT", model_seen="Claude", reason="identifies as Claude by Anthropic")
    r0 = json.loads(c.test(cid, U))
    check_("a consistent response does not flag", r0["verdict"] == "CONSISTENT" and json.loads(c.status(cid))["status"] == "CLAIMED")
    check_("the challenge was put in front of the round", CHALLENGE in gl.nondet.last_prompt)
    check_("a consistency is counted", json.loads(c.status(cid))["consistent"] == 1)
    check_("no reputation moved for a consistent test", json.loads(c.record(ALICE))["flagged"] == 0)

    print("\nan unreadable or not-found response never flags")
    gl.nondet.web.page = None
    ru = json.loads(c.test(cid, U))
    check_("an unreadable response is UNCLEAR and the claim stands", ru["verdict"] == "UNCLEAR" and json.loads(c.status(cid))["status"] == "CLAIMED")
    gl.nondet.web.page = "404: Not Found"
    rn = json.loads(c.test(cid, U))
    check_("a not-found response is UNCLEAR and does not flag", rn["verdict"] == "UNCLEAR" and json.loads(c.record(ALICE))["flagged"] == 0)

    print("\na response that reveals a different model flags the claim")
    gl.nondet.web.page = "a response that names another model"
    gl.nondet.answer = answer("CONTRADICTS", model_seen="GPT-4 (OpenAI)", reason="the response says it is GPT-4 by OpenAI, not Claude")
    rf = json.loads(c.test(cid, U))
    check_("a contradicting response FLAGS the claim", rf["verdict"] == "CONTRADICTS" and json.loads(c.status(cid))["status"] == "FLAGGED")
    check_("the claimant's record gains a flag", json.loads(c.record(ALICE))["flagged"] == 1)
    check_("the model the response revealed is recorded", json.loads(c.status(cid))["model_seen"] == "GPT-4 (OpenAI)")

    print("\na flagged claim is settled")
    check_("a flagged claim cannot be tested again", not json.loads(c.test(cid, U))["ok"])

    print("\nhistory keeps every test, oldest first")
    hist = json.loads(c.history(cid))
    verdicts = [e["verdict"] for e in hist["log"]]
    check_("the full test log is preserved", verdicts == ["CONSISTENT", "UNCLEAR", "UNCLEAR", "CONTRADICTS"])

    print("\nthe book counts claims standing and flagged")
    as_(ALICE)
    c.register("Second agent", "Gemini (Google)", CHALLENGE)
    size = json.loads(c.size())
    check_("two claims, one flagged and one standing", size["total"] == 2 and size["flagged"] == 1 and size["claimed"] == 1)

    failed = [label for label, ok in RESULTS if not ok]
    print()
    if failed:
        print("%d of %d checks failed" % (len(failed), len(RESULTS)))
        return 1
    print("%d checks, all through register() and test() on a real Fingerprint, the flag un-gameable"
          % len(RESULTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
