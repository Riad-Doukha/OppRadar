# Chat phase, fully offline and deterministic (fake provider, network mocked): every
# answer branch is a valid ChatAnswer, unanswerable questions say "not in the source",
# a privacy spy proves no profile text reaches the model, a 429 degrades to rules-only,
# history is trimmed, answers are cached, links/pasted text are extracted, turns round-trip
# through JsonStore and the widget never raises.

from __future__ import annotations

import re
from datetime import date
from types import SimpleNamespace

import pytest

from oppradar_ai import api, chat
from oppradar_ai.chat import REFUSAL_PHRASE, answer, assess_eligibility, build_prompt
from oppradar_ai.chat_ui import (
    answer_html,
    bubble_html,
    citations_html,
    eligibility_html,
    header_html,
)
from oppradar_ai.config import get_settings
from oppradar_ai.ingestion.fetch import PageDoc
from oppradar_ai.llm import LLMError, QuotaExhausted, get_llm, get_stats, reset_stats
from oppradar_ai.schemas import (
    Certificate,
    ChatAnswer,
    ChatTurn,
    Citation,
    CriteriaStatus,
    EducationItem,
    EligibilityAssessment,
    EligibilityCriterion,
    ExperienceItem,
    Opportunity,
    OpportunityType,
    Profile,
    Project,
)

QUESTION = "What is the deadline?"
URL = "https://jobs.acme-careers.net/ml-intern"
ANNOUNCEMENT = (
    "Atlas Digital Foundation is opening applications for the Atlas Merit Scholarship.\n"
    "The programme funds one year of postgraduate study in data science for students "
    "from Africa and covers tuition, a monthly stipend and a laptop.\n"
    "Deadline: 2099-05-01\n"
    "Eligibility: open to students; applicants must write English; under 30 years old.\n"
    "Apply on the foundation's website with a motivation letter and two references."
)
LISTICLE = "Top 10 scholarships of 2099 you must not miss! " + "Read on for the list. " * 25


@pytest.fixture(autouse=True)
def _clean_stats():
    reset_stats()
    yield
    reset_stats()


@pytest.fixture(autouse=True)
def _never_a_real_provider(monkeypatch):
    """Tests may only ever build the fake provider: a stray gemini lookup fails the test."""
    attempted: list[str] = []
    real = chat.get_llm

    def guard(provider=None):
        if provider not in (None, "fake"):
            attempted.append(provider)
            raise LLMError("a test must never build a real provider")
        return real(provider)

    monkeypatch.setattr(chat, "get_llm", guard)
    yield
    assert not attempted, f"a test tried to build a real provider: {attempted}"


def _settings(**updates):
    """The test settings (fake provider, temp data dir) with a few overrides."""
    return get_settings().model_copy(update=updates)


def _live(**updates):
    """Settings whose gate is open: a real provider name plus RUN_LIVE_LLM=1."""
    return _settings(llm_provider="gemini", run_live_llm=True, **updates)


def _opp(**updates) -> Opportunity:
    fields = {
        "id": "opp-chat",
        "title": "Machine Learning Intern",
        "organizer": "Ooredoo Algerie",
        "type": OpportunityType.INTERNSHIP,
        "mode": "hybrid",
        "location": "Algiers",
        "country": "Algeria",
        "deadline": date(2099, 3, 15),
        "funding": "15,000 DZD/month",
        "eligibility": ["English required", "French required", "Willing to relocate"],
        "benefits": ["Mentorship"],
        "summary": "Predictive models for telecom churn.",
        "url": "https://jobs.acme-careers.net/ml-intern",
        "source": "test",
    }
    return Opportunity(**{**fields, **updates})


def _profile(**updates) -> Profile:
    fields = {"user_id": "u-chat", "full_name": "Test User", "languages": ["english"]}
    return Profile(**{**fields, **updates})


PRIVATE = {
    "name": "Zakaria Bensalem-Ouyahia",
    "email": "z.bensalem.private@mail-example.test",
    "headline": "Quantum basket-weaving apprentice",
    "summary": "PRIVATE-SUMMARY-7731 lives near Tamanrasset and loves quilting",
    "institution": "Universite Privee de Tamanrasset",
    "employer": "Zorblax Industries",
    "project": "SecretProject-9912",
    "skill": "cobol-wizardry",
    "interest": "hyperlocal-beekeeping",
    "certificate": "Obscure Cert 4410",
}


def _private_profile() -> Profile:
    return Profile(
        user_id="u-private-5521",
        full_name=PRIVATE["name"],
        email=PRIVATE["email"],
        headline=PRIVATE["headline"],
        summary=PRIVATE["summary"],
        languages=["english"],
        skills=[PRIVATE["skill"]],
        interests=[PRIVATE["interest"]],
        education=[EducationItem(institution=PRIVATE["institution"], degree="MSc")],
        experience=[ExperienceItem(organization=PRIVATE["employer"], title="Engineer")],
        certificates=[Certificate(title=PRIVATE["certificate"])],
        projects=[Project(name=PRIVATE["project"])],
    )


class _Spy:
    """Wraps the fake provider and records every structured() call."""

    def __init__(self) -> None:
        self.real = get_llm("fake")
        self.calls: list[SimpleNamespace] = []

    def structured(self, prompt, schema, system=None):
        self.calls.append(SimpleNamespace(prompt=prompt, schema=schema, system=system))
        return self.real.structured(prompt, schema, system=system)


class _Stub:
    """A provider that answers with a fixed value or raises a fixed error."""

    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result, self.error, self.calls = result, error, 0

    def structured(self, prompt, schema, system=None):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def _use(monkeypatch, llm):
    monkeypatch.setattr(chat, "get_llm", lambda provider=None: llm)
    return llm


def _spy(monkeypatch) -> _Spy:
    return _use(monkeypatch, _Spy())


def _assert_valid(reply: ChatAnswer) -> None:
    """The reply is a ChatAnswer that survives a JSON round trip, with a sane shape."""
    assert isinstance(reply, ChatAnswer)
    assert ChatAnswer.model_validate(reply.model_dump(mode="json")) == reply
    assert reply.answer.strip()
    assert re.fullmatch(r"[a-z]{2,3}(-[a-z]{2,4})?", reply.language)
    assert all(isinstance(c, Citation) for c in reply.citations)
    if not reply.in_source:
        assert REFUSAL_PHRASE in reply.answer.casefold()


# --------------------------------------------------------------------------- #
# Grounded answers and refusals
# --------------------------------------------------------------------------- #
def test_grounded_answer_cites_the_record_and_attaches_local_eligibility():
    opp = _opp()
    reply = answer(_profile(), opp, [], QUESTION, settings=_settings())

    _assert_valid(reply)
    assert reply.in_source is True
    assert "2099-03-15" in reply.answer
    assert reply.language == "en"
    assert [c.url for c in reply.citations] == [opp.url]
    assert reply.citations[0].title == opp.title
    assert reply.citations[0].quote in build_prompt(_profile(), opp, [], QUESTION)
    assert reply.eligibility is not None and reply.eligibility.eligible is False
    assert reply.extracted_opportunity is None


@pytest.mark.parametrize(
    ("question", "updates"),
    [
        ("What is the application fee?", {}),  # a topic the record never states
        ("How much funding is offered?", {"funding": None}),
        ("What is the deadline?", {"deadline": None}),
        ("What are the benefits?", {"benefits": []}),
    ],
)
def test_unanswerable_questions_say_not_in_the_source(question, updates):
    opp = _opp(**updates)
    reply = answer(_profile(), opp, [], question, settings=_settings())

    _assert_valid(reply)
    assert REFUSAL_PHRASE in reply.answer.casefold()
    assert reply.in_source is False
    assert reply.citations == [Citation(url=opp.url, title=opp.title)]  # the page to verify on


def test_no_opportunity_at_all_is_a_refusal_not_an_invention():
    reply = answer(_profile(), None, [], QUESTION, settings=_settings())

    _assert_valid(reply)
    assert reply.in_source is False and reply.eligibility is None


def test_empty_message_asks_for_a_question_without_calling_the_model(monkeypatch):
    spy = _spy(monkeypatch)
    reply = answer(_profile(), _opp(), [], "   \n ", settings=_settings())

    _assert_valid(reply)
    assert reply.in_source is True and spy.calls == []


def test_the_model_is_never_trusted_for_the_contract(monkeypatch):
    forged = ChatAnswer(
        answer="Sorry, that is not in the source.",
        language="French",  # not a language code
        in_source=True,  # contradicts its own refusal
        citations=[
            Citation(url="https://evil.test/phish", title="x", quote="invented words nowhere"),
            Citation(url="", title="", quote="Mentorship"),  # really in the record
        ],
        eligibility=EligibilityAssessment(eligible=True, met=["everything"]),
        extracted_opportunity=_opp(title="Forged Opportunity"),
    )
    _use(monkeypatch, _Stub(forged))
    opp = _opp()

    reply = answer(_profile(), opp, [], "Is it safe?", settings=_settings())

    _assert_valid(reply)
    assert reply.in_source is False  # the refusal phrase wins over the flag
    assert reply.language == "en"  # junk code -> the offline hint
    assert [c.quote for c in reply.citations] == ["Mentorship"]  # invented quote dropped
    assert {c.url for c in reply.citations} == {opp.url}  # never an invented URL
    assert reply.eligibility is not None and reply.eligibility.eligible is False  # local
    assert reply.extracted_opportunity is None


def test_a_refusal_without_the_phrase_gets_it_added(monkeypatch):
    _use(monkeypatch, _Stub(ChatAnswer(answer="I cannot tell.", in_source=False)))

    reply = answer(_profile(), _opp(), [], "Is it safe?", settings=_settings())

    _assert_valid(reply)
    assert reply.answer.startswith("I cannot tell.") and REFUSAL_PHRASE in reply.answer


def test_an_empty_model_answer_is_a_refusal(monkeypatch):
    _use(monkeypatch, _Stub(ChatAnswer(answer="  ", in_source=True)))

    reply = answer(_profile(), _opp(), [], QUESTION, settings=_settings())

    _assert_valid(reply)
    assert reply.in_source is False


def test_the_prompt_marks_missing_fields_and_expired_deadlines():
    prompt = build_prompt(
        _profile(), _opp(funding=None, deadline=None, benefits=[]), [], QUESTION
    )
    assert "Deadline: none stated" in prompt
    assert "Funding: none stated" in prompt
    assert "Benefits: none stated" in prompt

    expired = build_prompt(_profile(), _opp(deadline=date(2020, 1, 1)), [], QUESTION)
    assert "Status: the deadline has already passed" in expired


# --------------------------------------------------------------------------- #
# Eligibility is local
# --------------------------------------------------------------------------- #
def _criteria(*statuses: CriteriaStatus) -> list[EligibilityCriterion]:
    return [EligibilityCriterion(text=f"req {i}", status=s) for i, s in enumerate(statuses)]


def test_assess_eligibility_verdicts():
    opp = _opp(deadline=date(2099, 3, 15))
    met, missed, unknown = CriteriaStatus.MET, CriteriaStatus.MISSED, CriteriaStatus.UNKNOWN

    assert assess_eligibility(_criteria(met, met), opp).eligible is True
    assert assess_eligibility(_criteria(met, missed, unknown), opp).eligible is False
    assert assess_eligibility(_criteria(met, unknown), opp).eligible is None
    empty = assess_eligibility([], opp)
    assert empty.eligible is None and "official page" in empty.next_steps[0]
    verdict = assess_eligibility(_criteria(met, missed, unknown), opp)
    assert verdict.met == ["req 0"] and verdict.gaps == ["req 1"]
    assert any("req 2" in step for step in verdict.next_steps)
    assert "Apply before 2099-03-15." in verdict.next_steps


def test_eligibility_comes_from_the_rules_not_the_model():
    opp = _opp(eligibility=["English required", "Willing to relocate"])
    reply = answer(_profile(), opp, [], "Am I eligible?", settings=_settings())

    _assert_valid(reply)
    assert reply.eligibility is not None
    assert reply.eligibility.met == ["English required"]
    assert reply.eligibility.eligible is None  # relocation cannot be checked from a CV
    assert reply.eligibility.next_steps[0] == "Confirm with the organizer: Willing to relocate"


# --------------------------------------------------------------------------- #
# Privacy
# --------------------------------------------------------------------------- #
def test_no_profile_text_reaches_the_model(monkeypatch):
    spy = _spy(monkeypatch)
    profile, opp = _private_profile(), _opp()

    answer(profile, opp, [], "Am I eligible?", settings=_settings())

    assert len(spy.calls) == 1  # one structured call per question
    sent = (spy.calls[0].prompt + "\n" + (spy.calls[0].system or "")).casefold()
    for field, value in PRIVATE.items():
        assert value.casefold() not in sent, f"profile field {field!r} leaked to the model"
    assert profile.user_id.casefold() not in sent
    assert "you list" not in sent  # the criteria *evidence* quotes the profile: never sent
    assert "- MET: English required".casefold() in sent  # requirement-level outcomes only
    assert "- NOT MET: French required".casefold() in sent
    assert "- UNKNOWN: Willing to relocate".casefold() in sent


def test_build_prompt_is_exactly_what_the_model_receives(monkeypatch):
    spy = _spy(monkeypatch)
    profile, opp = _private_profile(), _opp()

    answer(profile, opp, [], QUESTION, settings=_settings())

    assert spy.calls[0].prompt == build_prompt(profile, opp, [], QUESTION, settings=_settings())
    assert spy.calls[0].schema is ChatAnswer
    assert "answer_question" not in spy.calls[0].prompt  # instructions live in the .md system


def test_the_system_prompt_comes_from_the_markdown_file(monkeypatch):
    spy = _spy(monkeypatch)
    answer(_profile(), _opp(), [], QUESTION, settings=_settings())

    expected = (get_settings().prompts_dir / "answer_question.md").read_text(encoding="utf-8")
    assert spy.calls[0].system == expected
    assert REFUSAL_PHRASE in expected  # the refusal contract is written in the prompt file


# --------------------------------------------------------------------------- #
# The cost gate and failures
# --------------------------------------------------------------------------- #
def test_model_allowed_truth_table():
    assert chat.model_allowed(_settings(llm_provider="fake", run_live_llm=False)) is True
    assert chat.model_allowed(_settings(llm_provider="gemini", run_live_llm=False)) is False
    assert chat.model_allowed(_settings(llm_provider="gemini", run_live_llm=True)) is True


def test_closed_gate_never_calls_a_real_provider(monkeypatch):
    def _forbidden(provider=None):
        raise AssertionError("the gate is closed: no model may be built")

    monkeypatch.setattr(chat, "get_llm", _forbidden)
    settings = _settings(llm_provider="gemini", run_live_llm=False)

    reply = answer(_profile(), _opp(), [], QUESTION, settings=settings)

    _assert_valid(reply)
    assert "switched off" in reply.answer and "2099-03-15" in reply.answer
    assert reply.in_source is True and reply.eligibility is not None


@pytest.mark.parametrize(
    ("error", "wording"),
    [
        (QuotaExhausted("429 RESOURCE_EXHAUSTED " + "x" * 400), "quota"),
        (LLMError("model returned invalid JSON"), "could not be reached"),
        (RuntimeError("socket closed"), "could not be reached"),
    ],
)
def test_a_failing_model_gives_a_rules_only_answer_without_retrying(monkeypatch, error, wording):
    stub = _use(monkeypatch, _Stub(error=error))
    opp = _opp()

    reply = answer(_profile(), opp, [], QUESTION, settings=_live())

    _assert_valid(reply)
    assert stub.calls == 1  # no retry
    assert wording in reply.answer
    assert "Deadline: 2099-03-15" in reply.answer  # deadline straight from the record
    assert "Requirements you meet: English required." in reply.answer
    assert "do not meet yet: French required." in reply.answer
    assert "Willing to relocate" in reply.answer  # listed as "to check yourself"
    assert reply.in_source is True and reply.language == "en"
    assert reply.eligibility is not None and reply.eligibility.eligible is False
    assert reply.citations == [Citation(url=opp.url, title=opp.title)]


def test_rules_only_answer_without_a_deadline_does_not_pretend_to_refuse(monkeypatch):
    _use(monkeypatch, _Stub(error=QuotaExhausted("429")))

    reply = answer(_profile(), _opp(deadline=None, funding=None), [], QUESTION, settings=_live())

    _assert_valid(reply)
    assert "No deadline is stated in the record." in reply.answer
    assert reply.in_source is True  # the facts it does state are in the source


# --------------------------------------------------------------------------- #
# History, cache, purity
# --------------------------------------------------------------------------- #
def _turns(count: int) -> list[ChatTurn]:
    return [
        ChatTurn(role="user" if i % 2 == 0 else "assistant", content=f"history marker {i:02d}")
        for i in range(count)
    ]


def test_history_is_trimmed_to_the_configured_recent_turns(monkeypatch):
    spy = _spy(monkeypatch)

    answer(_profile(), _opp(), _turns(30), QUESTION, settings=_settings(chat_history_turns=4))

    prompt = spy.calls[0].prompt
    assert [i for i in range(30) if f"history marker {i:02d}" in prompt] == [26, 27, 28, 29]
    assert prompt.index("history marker 26") < prompt.index("history marker 29")  # oldest first


def test_a_zero_limit_sends_no_history(monkeypatch):
    spy = _spy(monkeypatch)

    answer(_profile(), _opp(), _turns(5), QUESTION, settings=_settings(chat_history_turns=0))

    assert "Recent conversation" not in spy.calls[0].prompt


def test_the_default_limit_is_ten_turns(monkeypatch):
    spy = _spy(monkeypatch)

    answer(_profile(), _opp(), _turns(30), QUESTION, settings=_settings(chat_history_turns=10))

    sent = [i for i in range(30) if f"history marker {i:02d}" in spy.calls[0].prompt]
    assert sent == list(range(20, 30))


def test_the_current_question_is_not_sent_twice(monkeypatch):
    spy = _spy(monkeypatch)
    history = [*_turns(2), ChatTurn(role="user", content=QUESTION)]  # a UI stored it already

    answer(_profile(), _opp(), history, QUESTION, settings=_settings())

    assert spy.calls[0].prompt.count(QUESTION) == 1


def test_an_oversized_prompt_drops_the_oldest_turns_and_keeps_the_question(monkeypatch):
    spy = _spy(monkeypatch)
    turns = [
        ChatTurn(role="user", content=f"history marker {i:02d} " + "word " * 5000)
        for i in range(10)
    ]
    requirements = [f"English required, option {i} " + "x" * 120 for i in range(8)]
    opp = _opp(summary="long " * 5000, eligibility=requirements)
    budget = get_settings().llm_max_input_chars

    answer(_profile(), opp, turns, QUESTION, settings=_settings())

    prompt = spy.calls[0].prompt
    assert len(prompt) <= budget  # the LLM layer would cut the tail: nothing is left to cut
    assert f"Question: {QUESTION}" in prompt and "Requirement check" in prompt
    assert "history marker 09" in prompt  # the newest turn is the last to go
    assert "history marker 00" not in prompt  # the oldest went first


def test_the_same_question_is_answered_from_the_cache_the_second_time():
    question = "What is the deadline? (cache test)"
    opp, settings = _opp(), _settings()

    first = answer(_profile(), opp, [], question, settings=settings)
    assert (get_stats().calls, get_stats().cached) == (1, 0)
    second = answer(_profile(), opp, [], question, settings=settings)

    assert (get_stats().calls, get_stats().cached) == (1, 1)  # no second provider call
    assert first == second
    system = (settings.prompts_dir / "answer_question.md").read_text(encoding="utf-8")
    prompt = build_prompt(_profile(), opp, [], question, settings=settings)
    assert get_llm("fake").is_cached(prompt, ChatAnswer, system=system)


def test_answer_never_writes_chat_history(monkeypatch):
    from oppradar_ai.store import JsonStore

    def _forbidden(*args, **kwargs):
        raise AssertionError("answer() must be pure: the caller persists turns")

    monkeypatch.setattr(JsonStore, "append_chat", _forbidden)

    _assert_valid(answer(_profile(), _opp(), _turns(2), QUESTION, settings=_settings()))


def test_api_answer_proxies_the_chat_module():
    opp, profile = _opp(), _profile()

    via_api = api.answer(profile, opp, [], QUESTION, settings=_settings())

    assert via_api == answer(profile, opp, [], QUESTION, settings=_settings())


# --------------------------------------------------------------------------- #
# Pasted announcements and links -> extracted_opportunity
# --------------------------------------------------------------------------- #
def test_a_pasted_announcement_is_extracted_and_answered_from():
    message = f"{QUESTION}\n\n{ANNOUNCEMENT}"
    assert len(message) >= chat.PASTE_MIN_CHARS

    reply = answer(_profile(), None, [], message, settings=_settings())

    _assert_valid(reply)
    extracted = reply.extracted_opportunity
    assert extracted is not None and extracted.title == "Atlas Merit Scholarship 2027"
    assert extracted.deadline == date(2099, 5, 1)  # the explicit "Deadline:" line wins
    assert reply.in_source is True and "2099-05-01" in reply.answer
    assert reply.eligibility is not None  # computed against the extracted record
    assert reply.citations[0].title == extracted.title


def test_a_pasted_text_that_is_not_an_opportunity_falls_back_to_the_selected_one():
    opp = _opp()

    reply = answer(_profile(), opp, [], f"{QUESTION}\n{LISTICLE}", settings=_settings())

    _assert_valid(reply)
    assert reply.extracted_opportunity is None
    assert "2099-03-15" in reply.answer  # answered from the opportunity the user selected
    assert "Note: Pasted text not used: it does not look like a single opportunity" in reply.answer


def test_pasted_text_is_not_analysed_when_the_gate_is_closed(monkeypatch):
    def _forbidden(*args, **kwargs):
        raise AssertionError("no model call while the gate is closed")

    monkeypatch.setattr(chat, "extract_opportunity", _forbidden)
    monkeypatch.setattr(chat, "get_llm", _forbidden)
    settings = _settings(llm_provider="gemini", run_live_llm=False)

    reply = answer(_profile(), _opp(), [], f"{QUESTION}\n{ANNOUNCEMENT}", settings=settings)

    _assert_valid(reply)
    assert reply.extracted_opportunity is None
    assert "Pasted text not used: model calls are off." in reply.answer


class _FakeFetcher:
    """Stands in for PageFetcher: no network, records what was requested."""

    requested: list[str] = []
    page = PageDoc(url=URL, ok=True, html="<html><body>page</body></html>")

    def __init__(self, settings=None) -> None:
        pass

    def get(self, url: str, check_robots: bool = True) -> PageDoc:
        type(self).requested.append(url)
        return type(self).page.model_copy(update={"url": url})


@pytest.fixture
def mocked_network(monkeypatch):
    """PageFetcher and the HTML cleaner replaced: the URL path runs without a socket."""
    _FakeFetcher.requested = []
    _FakeFetcher.page = PageDoc(url=URL, ok=True, html="<html><body>page</body></html>")
    monkeypatch.setattr(api, "PageFetcher", _FakeFetcher)
    monkeypatch.setattr(api, "clean_html", lambda html, url="": SimpleNamespace(text=ANNOUNCEMENT))
    return _FakeFetcher


def test_a_url_is_fetched_extracted_and_answered_from(monkeypatch, mocked_network):
    spy = _spy(monkeypatch)  # chat's own model; extraction keeps the global fake provider

    reply = answer(_profile(), None, [], f"{QUESTION} See {URL}.", settings=_live())

    _assert_valid(reply)
    assert mocked_network.requested == [URL]  # trailing "." stripped, fetched exactly once
    extracted = reply.extracted_opportunity
    assert extracted is not None and extracted.url == URL
    assert reply.in_source is True and "2099-05-01" in reply.answer
    assert len(spy.calls) == 1  # still one answer call per question


def test_a_url_is_not_fetched_offline(monkeypatch, mocked_network):
    reply = answer(_profile(), _opp(), [], f"{QUESTION} {URL}", settings=_settings())

    _assert_valid(reply)
    assert mocked_network.requested == []  # the fake provider never fetches
    assert reply.extracted_opportunity is None
    assert "Link not used: live page reading is off" in reply.answer
    assert "2099-03-15" in reply.answer  # answered from the selected opportunity


def test_a_failed_download_is_reported_not_raised(monkeypatch, mocked_network):
    _spy(monkeypatch)
    mocked_network.page = PageDoc(url=URL, ok=False, error="HTTP 404")

    reply = answer(_profile(), _opp(), [], f"{QUESTION} {URL}", settings=_live())

    _assert_valid(reply)
    assert "Link not used: the page could not be downloaded." in reply.answer
    assert reply.extracted_opportunity is None


def test_a_failed_link_without_any_opportunity_is_a_refusal(mocked_network):
    mocked_network.page = PageDoc(url=URL, ok=False, error="HTTP 404")

    reply = answer(_profile(), None, [], f"{QUESTION} {URL}", settings=_live())

    _assert_valid(reply)
    assert reply.in_source is False and "Link not used" in reply.answer


# --------------------------------------------------------------------------- #
# JsonStore round trip (the caller persists, answer() only reads history)
# --------------------------------------------------------------------------- #
def test_turns_round_trip_through_the_store_into_the_next_prompt(monkeypatch, tmp_store):
    spy = _spy(monkeypatch)
    profile, opp, settings = _profile(), _opp(), _settings()

    before = tmp_store.chat_history(profile.user_id)
    first = answer(profile, opp, before, QUESTION, settings=settings)
    tmp_store.append_chat(profile.user_id, ChatTurn(role="user", content=QUESTION))
    tmp_store.append_chat(profile.user_id, ChatTurn(role="assistant", content=first.answer))
    stored = tmp_store.chat_history(profile.user_id)

    assert [t.role for t in stored] == ["user", "assistant"]
    assert stored[1].content == first.answer
    answer(profile, opp, stored, "And the funding?", settings=settings)
    assert f"assistant: {first.answer}" in spy.calls[1].prompt  # the stored turn came back
    assert spy.calls[1].prompt.count(QUESTION) == 1


# --------------------------------------------------------------------------- #
# Language
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("What is the deadline?", "en"),
        ("Quelle est la date limite ?", "fr"),
        ("Où se déroule le stage ?", "fr"),
        ("ما هو الموعد النهائي؟", "ar"),
        ("Am I eligible for the AI Research Intern?", "en"),
    ],
)
def test_the_reply_language_follows_the_question(question, code):
    assert chat.detect_language(question) == code

    reply = answer(_profile(), _opp(), [], question, settings=_settings())

    _assert_valid(reply)
    assert reply.language == code
    assert reply.answer.startswith(f"[fake:{code}]")
    if code != "en":  # a grounded answer in the user's language, still cited
        assert reply.in_source is True and reply.citations


def test_a_refusal_keeps_the_exact_english_phrase_in_any_language():
    reply = answer(_profile(), _opp(), [], "ما هي رسوم التسجيل؟", settings=_settings())

    _assert_valid(reply)
    assert reply.language == "ar" and reply.in_source is False
    assert REFUSAL_PHRASE in reply.answer


# --------------------------------------------------------------------------- #
# chat_ui: pure renderers and the widget
# --------------------------------------------------------------------------- #
def test_renderers_escape_untrusted_text_and_links():
    assert "<script>" not in bubble_html("user", "<script>alert(1)</script>")
    assert "<br>" in bubble_html("assistant", "line 1\nline 2")
    html = citations_html([Citation(url="javascript:alert(1)", title="Bad", quote='"x"')])
    assert "href=" not in html and "Bad" in html
    good = citations_html([Citation(url="https://a.org/x", title="A", quote="Mentorship")])
    assert 'href="https://a.org/x"' in good and "Mentorship" in good
    assert citations_html([]) == "" and eligibility_html(None) == ""


def test_the_answer_card_shows_refusals_sources_and_eligibility():
    refusal = answer_html(ChatAnswer(answer=f"That is {REFUSAL_PHRASE}.", in_source=False))
    assert "⚠ not in the source" in refusal

    assessment = EligibilityAssessment(
        eligible=False, met=["English required"], gaps=["French required"], next_steps=["Apply"]
    )
    box = eligibility_html(assessment)
    assert "Not eligible yet" in box and "✓ English required" in box and "✗ French required" in box
    assert "Looks eligible" in eligibility_html(EligibilityAssessment(eligible=True))
    assert "Not enough information" in eligibility_html(EligibilityAssessment())

    extracted = answer_html(ChatAnswer(answer="ok", extracted_opportunity=_opp(title="Atlas <1>")))
    assert "Read from your message" in extracted and "Atlas &lt;1&gt;" in extracted
    assert "No opportunity" in header_html(None) and "Machine Learning" in header_html(_opp())


def _panel(tmp_store, **kwargs):
    pytest.importorskip("ipywidgets")
    from oppradar_ai.chat_ui import ChatPanel

    return ChatPanel(_profile(), kwargs.pop("opportunity", _opp()), tmp_store,
                     settings=_settings(), **kwargs)


def test_panel_send_stores_exactly_the_two_turns_and_renders_them(tmp_store):
    panel = _panel(tmp_store)

    reply = panel.send(QUESTION)

    assert reply is not None and "2099-03-15" in reply.answer
    stored = tmp_store.chat_history("u-chat")
    assert [(t.role, t.content) for t in stored] == [
        ("user", QUESTION),
        ("assistant", reply.answer),
    ]
    assert QUESTION in panel.log.value and "2099-03-15" in panel.log.value
    assert panel.status.value == ""
    assert panel.send("   ") is None and len(tmp_store.chat_history("u-chat")) == 2


def test_a_reopened_panel_shows_the_stored_conversation(tmp_store):
    _panel(tmp_store).send(QUESTION)

    reopened = _panel(tmp_store)

    assert QUESTION in reopened.log.value
    reopened.clear()
    assert reopened.log.value == "" and len(tmp_store.chat_history("u-chat")) == 2


def test_the_send_button_never_raises_into_the_kernel(tmp_store):
    def _dead(*args, **kwargs):
        raise RuntimeError("answer function exploded")

    panel = _panel(tmp_store, answer_fn=_dead)
    panel.box.value = QUESTION

    panel._on_send(None)  # must not raise

    assert "Something went wrong (RuntimeError)" in panel.status.value
    assert tmp_store.chat_history("u-chat") == []  # a failed turn is not stored
    assert panel.box.value == QUESTION  # the user's text is kept for another try
    panel._on_clear(None)


def test_the_panel_switches_to_the_opportunity_found_in_a_message(tmp_store):
    panel = _panel(tmp_store, opportunity=None)

    panel.send(f"{QUESTION}\n\n{ANNOUNCEMENT}")

    assert panel.opportunity is not None
    assert panel.opportunity.title == "Atlas Merit Scholarship 2027"
    assert "Atlas Merit Scholarship 2027" in panel.header.value
