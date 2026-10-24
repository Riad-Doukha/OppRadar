# Rule-first criteria check: every requirement a source states is evaluated against
# the profile with cheap text rules -> MET / MISSED / UNKNOWN, always with evidence
# and never with an LLM. Called by: matching/composer.py and the notebooks.
# Absence of data gives UNKNOWN (flag it); contradicting data gives MISSED.

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import date

from rapidfuzz import fuzz

from oppradar_ai.config import get_settings
from oppradar_ai.schemas import CriteriaStatus, EligibilityCriterion, Opportunity, Profile

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Languages: canonical names, aliases (fr/anglais/...) and code mapping
# --------------------------------------------------------------------------- #
_LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "english": ("english", "anglais"),
    "french": ("french", "français", "francais"),
    "arabic": ("arabic", "arabe"),
    "spanish": ("spanish", "espagnol"),
    "german": ("german", "allemand"),
    "italian": ("italian", "italien"),
    "portuguese": ("portuguese", "portugais"),
    "chinese": ("chinese", "mandarin"),
    "japanese": ("japanese",),
    "korean": ("korean",),
    "russian": ("russian", "russe"),
    "turkish": ("turkish", "turc"),
    "dutch": ("dutch", "néerlandais", "neerlandais"),
}
_LANGUAGE_CODES = {
    "en": "english",
    "fr": "french",
    "ar": "arabic",
    "es": "spanish",
    "de": "german",
    "it": "italian",
    "pt": "portuguese",
    "zh": "chinese",
    "ja": "japanese",
    "ko": "korean",
    "ru": "russian",
    "tr": "turkish",
    "nl": "dutch",
}
_LANGUAGE_PATTERNS = {
    name: re.compile(
        "|".join(rf"\b{re.escape(word)}\b" for word in dict.fromkeys(words)), re.IGNORECASE
    )
    for name, words in _LANGUAGE_ALIASES.items()
}


def normalize_language(value: str) -> str:
    """Canonical language name of a CV/opportunity value.

    Example:
        >>> normalize_language("FR"), normalize_language("English (B2)")
        ('french', 'english')
    """
    text = " ".join((value or "").split()).casefold()
    if not text:
        return ""
    if text in _LANGUAGE_CODES:
        return _LANGUAGE_CODES[text]
    head = re.split(r"[(\[:/]", text)[0].strip()
    for canonical, pattern in _LANGUAGE_PATTERNS.items():
        if pattern.fullmatch(text) or pattern.fullmatch(head):
            return canonical
    return head


# --------------------------------------------------------------------------- #
# Degree levels
# --------------------------------------------------------------------------- #
_LEVEL_NAMES = {1: "baccalaureate", 2: "bachelor", 3: "master", 4: "doctorate"}


def _deg(pattern: str, level: int) -> tuple[re.Pattern[str], int]:
    """A degree pattern paired with the level it stands for."""
    return re.compile(pattern, re.IGNORECASE), level


_DEGREE_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    _deg(r"\bph\.?\s?d\b|\bdoctorat\w*|\bdoctorate\b", 4),
    _deg(r"\bmaster'?s?\b|\bm\.?\s?sc\.?\b|\bmsc\b|\bmba\b|\bm\.?\s?a\.?\b", 3),
    _deg(r"\bbachelor'?s?\b|\bb\.?\s?sc\.?\b|\bbsc\b|\bundergrad", 2),
    _deg(r"\bbaccalaur[eé]at\w*|\bbac\s*\+?\s*\d|\bhigh school\b|\bsecondary\b", 1),
)
_EDUCATION_WORDS = re.compile(
    r"\bstudents?\b|\bgraduates?\b|\benrolled\b|\bschool\b|\bdegree\b|\bdiploma\b|\bqualif\w*",
    re.IGNORECASE,
)

# "African residents": claim MET only for a country we are sure is in Africa,
# never MISSED — an incomplete list cannot prove the opposite.
_AFRICAN_COUNTRIES = frozenset(
    {
        "algeria", "angola", "benin", "botswana", "burkina faso", "burundi", "cabo verde",
        "cameroon", "cape verde", "central african republic", "chad", "comoros", "congo",
        "dr congo", "djibouti", "egypt", "equatorial guinea", "eritrea", "eswatini", "ethiopia",
        "gabon", "gambia", "ghana", "guinea", "guinea-bissau", "ivory coast", "côte d'ivoire",
        "kenya", "lesotho", "liberia", "libya", "madagascar", "malawi", "mali", "mauritania",
        "mauritius", "morocco", "mozambique", "namibia", "niger", "nigeria", "rwanda",
        "sao tome and principe", "senegal", "seychelles", "sierra leone", "somalia",
        "south africa", "south sudan", "sudan", "tanzania", "togo", "tunisia", "uganda",
        "zambia", "zimbabwe",
    }
)
_GEOGRAPHIC_RE = re.compile(
    r"\bresidents?\b|\bcitizens?\b|\bnationals?\b|\bnationality\b|\bcountry\b"
    r"|\buniversity\b|\bcollege\b|\bfrom a\b",
    re.IGNORECASE,
)
_PERSONAL_RE = re.compile(
    r"\brelocat\w*|\bavailable\b|\bavailability\b|\bteams?\b|\bhours?\s*/\s*week\b"
    r"|\bwork style\b|\basync\w*|\bflexib\w*",
    re.IGNORECASE,
)
_AGE_RE = re.compile(
    r"\bages?\b|\bunder \d+\b|\bover \d+\b|\b\d{1,2}\s*[-–]\s*\d{1,2}\s*years?\b", re.IGNORECASE
)
_NO_REQUIREMENT_RE = re.compile(
    r"\bopen to (?:all|everyone)\b|\bno (?:degree|skills?|experience|qualification)s?"
    r"\s+(?:needed|required|necessary)\b|\bnot required\b",
    re.IGNORECASE,
)

# Experience: only lines that state a duration ("Two years of work experience").
_NUMBER_WORDS = {
    "one": 1.0, "two": 2.0, "three": 3.0, "four": 4.0, "five": 5.0,
    "six": 6.0, "seven": 7.0, "eight": 8.0, "nine": 9.0, "ten": 10.0,
}
_YEARS_RE = re.compile(
    r"\b(?P<low>\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"(?:\s*[-–]\s*\d+)?\s*\+?\s*years?\b",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"^(?P<y>\d{4})(?:-(?P<m>\d{2}))?(?:-(?P<d>\d{2}))?$")
_ONGOING = frozenset({"", "present", "now", "current", "présent", "actuel", "ongoing", "to date"})

# Keyword matching: filler words are dropped before fuzzy comparison.
_FILLER = frozenset(
    {
        "required", "requirement", "requirements", "experience", "knowledge", "understanding",
        "familiarity", "proficiency", "fluency", "fluent", "basics", "basic", "strong", "solid",
        "good", "great", "proven", "background", "interest", "interested", "welcome", "students",
        "student", "juniors", "junior", "coursework", "ability", "able", "know", "knows",
        "preferred", "preference", "prefer", "preferably", "desirable", "must", "have", "hands",
        "on", "working", "well", "familiar", "the", "a", "an", "of", "in", "to", "for", "with",
        "by", "at", "from", "and", "or", "is", "are", "be", "we", "you", "your", "our", "their",
        "this", "that", "any", "all", "plus", "portfolio", "sample", "samples", "style", "work",
    }
)
_SKILL_MARKERS = (
    "skill", "knowledge", "fluency", "basics", "required", "proficiency", "familiarity",
    "experience", "background", "interest", "know", "coursework", "prefer", "able",
)
# Acronyms are expanded before matching: "cs" also looks for "computer science".
_ACRONYMS = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "nlp": "natural language processing",
    "cs": "computer science",
    "dl": "deep learning",
    "ds": "data science",
}


def check_criteria(profile: Profile, opportunity: Opportunity) -> list[EligibilityCriterion]:
    """Evaluate every requirement the source states (empty when it states none).

    Example:
        >>> check_criteria(profile, opportunity)[0].status in tuple(CriteriaStatus)
        True
    """
    return [evaluate_line(profile, line) for line in opportunity.eligibility if line.strip()]


def evaluate_line(profile: Profile, line: str) -> EligibilityCriterion:
    """One requirement line -> MET / MISSED / UNKNOWN, always with evidence.

    Example:
        >>> evaluate_line(profile_with_english, "English required").status.value
        'met'
    """
    text = " ".join(line.split())
    for rule in _RULES:
        hit = rule(profile, text)
        if hit is not None:
            return hit
    return _keyword_rule(profile, text)


# --------------------------------------------------------------------------- #
# Rules, in evaluation order (the first that recognizes the line answers it)
# --------------------------------------------------------------------------- #
def _rule_no_requirement(profile: Profile, line: str) -> EligibilityCriterion | None:
    """'Open to all', 'No degree required' — nothing to check, so MET."""
    del profile
    if _NO_REQUIREMENT_RE.search(line):
        return _criterion(line, CriteriaStatus.MET, "the source states no requirement")
    return None


def _rule_personal(profile: Profile, line: str) -> EligibilityCriterion | None:
    """Relocation, availability, team size, work style — a CV cannot show these."""
    del profile
    if _PERSONAL_RE.search(line):
        return _criterion(line, CriteriaStatus.UNKNOWN, "personal constraint, not checkable")
    return None


def _rule_age(profile: Profile, line: str) -> EligibilityCriterion | None:
    """Age limits are never stored, so they are flagged, not guessed."""
    del profile
    if _AGE_RE.search(line):
        note = "age is not stored in the profile (privacy)"
        return _criterion(line, CriteriaStatus.UNKNOWN, note)
    return None


def _rule_geographic(profile: Profile, line: str) -> EligibilityCriterion | None:
    """Nationality / university-country lines: verified only when we are sure."""
    if not _GEOGRAPHIC_RE.search(line):
        return None
    if not re.search(r"\bafrican\b", line, re.IGNORECASE):
        return _criterion(
            line, CriteriaStatus.UNKNOWN, "the source asks about a location we do not store"
        )
    country = normalize_word(profile.country)
    if not country:
        return _criterion(line, CriteriaStatus.UNKNOWN, "your country is unknown")
    if country in _AFRICAN_COUNTRIES:
        return _criterion(line, CriteriaStatus.MET, f"your country {profile.country} is in Africa")
    known = f"your country {profile.country} is not in our Africa list"
    return _criterion(line, CriteriaStatus.UNKNOWN, known)


def _rule_language(profile: Profile, line: str) -> EligibilityCriterion | None:
    """A stated language requirement, against the profile's language list."""
    wanted = [name for name, pattern in _LANGUAGE_PATTERNS.items() if pattern.search(line)]
    if not wanted:
        return None
    have = {normalize_language(value) for value in profile.languages if value.strip()}
    if not have:
        return _criterion(line, CriteriaStatus.UNKNOWN, "the profile lists no languages")
    if any(name not in have for name in wanted):
        return _criterion(line, CriteriaStatus.MISSED, f"you list: {', '.join(sorted(have))}")
    return _criterion(line, CriteriaStatus.MET, f"you list: {', '.join(wanted)}")


def _rule_degree(profile: Profile, line: str) -> EligibilityCriterion | None:
    """Degree level and field of study, checked against the education entries."""
    if not _education_line(line):
        return None
    if not profile.education:
        return _criterion(line, CriteriaStatus.UNKNOWN, "the profile lists no education")
    required, have = _level_of(line), _profile_level(profile)
    if required is not None and have is None:
        note = "your degree level is not readable from the profile"
        return _criterion(line, CriteriaStatus.UNKNOWN, note)
    if required is not None and have is not None and have < required:
        return _criterion(
            line,
            CriteriaStatus.MISSED,
            f"you list {_LEVEL_NAMES[have]}, the offer asks for {_LEVEL_NAMES[required]}",
        )
    blob = profile_blob(profile)
    terms = _field_terms(line)
    for term in terms:
        word = best_match(term, blob)
        if word is not None:
            return _criterion(line, CriteriaStatus.MET, f"field matches {word!r}")
    if terms:
        return _criterion(line, CriteriaStatus.MISSED, "the field of study is not in your profile")
    if required is None:
        return _criterion(line, CriteriaStatus.MET, "your profile lists education")
    if have > required:
        more = f"you list {_LEVEL_NAMES[have]} (>= {_LEVEL_NAMES[required]} required)"
        return _criterion(line, CriteriaStatus.MET, more)
    return _criterion(line, CriteriaStatus.MET, f"degree level ok ({_LEVEL_NAMES[required]})")


def _rule_experience_years(profile: Profile, line: str) -> EligibilityCriterion | None:
    """'Two years of work experience' — counted from the profile's own dates."""
    if "experience" not in line.casefold():
        return None
    match = _YEARS_RE.search(line)
    if match is None:
        return None
    token = match.group("low").casefold()
    needed = float(token) if token.isdigit() else _NUMBER_WORDS[token]
    if not profile.experience:
        return _criterion(line, CriteriaStatus.MISSED, "your profile lists no experience")
    have = experience_years(profile)
    if have is None:
        note = "the dates in your profile are not machine-readable"
        return _criterion(line, CriteriaStatus.UNKNOWN, note)
    years = f"your entries add up to ~{have:.1f} year(s)"
    status = CriteriaStatus.MISSED if have + 0.04 < needed else CriteriaStatus.MET
    return _criterion(line, status, years)


_RULES: tuple[Callable[[Profile, str], EligibilityCriterion | None], ...] = (
    _rule_no_requirement,
    _rule_personal,
    _rule_age,
    _rule_geographic,
    _rule_language,
    _rule_degree,
    _rule_experience_years,
)


# --------------------------------------------------------------------------- #
# Last resort: fuzzy keyword matching against the whole profile
# --------------------------------------------------------------------------- #
def _keyword_rule(profile: Profile, line: str) -> EligibilityCriterion:
    """Match the line's phrases in the profile (fuzzy); decide how to fail."""
    blob = profile_blob(profile)
    alternatives = _alternatives(line)
    if not alternatives:
        return _criterion(line, CriteriaStatus.UNKNOWN, "nothing checkable in this line")
    for alternative in alternatives:
        matched = _alternative_match(alternative, blob)
        if matched is not None:
            return _criterion(line, CriteriaStatus.MET, f"profile matches {matched}")
    missing = _missing_words(alternatives, blob)
    if _looks_like_a_skill(line):
        return _criterion(line, CriteriaStatus.MISSED, f"not found in your profile: {missing}")
    return _criterion(line, CriteriaStatus.UNKNOWN, "not machine-checkable from a CV")


def _missing_words(alternatives: list[str], blob: str) -> str:
    """Only the words the profile really lacks ('Python and C++' blames C++ alone)."""
    missing: list[str] = []
    for alternative in alternatives:
        if " and " in alternative:
            missing += [p for p in alternative.split(" and ") if _first_word_match(p, blob) is None]
        else:
            missing += _content_words(alternative)
    return ", ".join(missing) or ", ".join(_content_words(alternatives[0]))


def _alternatives(line: str) -> list[str]:
    """Split a requirement into options: 'FastAPI or Django' -> ['fastapi', 'django']."""
    parts = re.split(r"\s*(?:,|;|\bor\b|&|/)\s*", line.casefold())
    return [part for part in parts if _content_words(part)]


def _content_words(text: str) -> list[str]:
    """The words left after filler is removed (the ones that carry meaning)."""
    return [w for w in re.findall(r"[a-z0-9+#.]+", text) if w not in _FILLER and len(w) > 1]


def _alternative_match(alternative: str, blob: str) -> str | None:
    """Evidence for one option: 'x and y' needs every part, any word otherwise."""
    if " and " in alternative:
        matched = [_first_word_match(part, blob) for part in alternative.split(" and ")]
        return ", ".join(word for word in matched if word) if all(matched) else None
    for word in _content_words(alternative):
        if best_match(word, blob) is not None:
            return word
    return None


def _first_word_match(text: str, blob: str) -> str | None:
    """First content word of `text` the profile contains (fuzzy), else None."""
    for word in _content_words(text):
        if best_match(word, blob) is not None:
            return word
    return None


def best_match(term: str, blob: str) -> str | None:
    """Which word of `term` the text contains (rapidfuzz, threshold from Settings).

    Example:
        >>> best_match("python", "skills: python, sql")
        'python'
        >>> best_match("kubernetes", "skills: python, sql") is None
        True
    """
    if not blob or not term.strip():
        return None
    threshold = get_settings().criteria_fuzzy_threshold
    tokens = blob.split()
    for word in term.casefold().split():
        for candidate in _candidates(word):
            if len(candidate) < 4:
                if candidate in tokens:
                    return word
            elif fuzz.partial_ratio(candidate, blob) >= threshold:
                return word
    return None


def _candidates(word: str) -> tuple[str, ...]:
    """The word plus its acronym expansion ('cs' also looks for 'science')."""
    expansion = _ACRONYMS.get(word)
    if expansion is None:
        return (word,)
    return (word, expansion, *expansion.split())


def profile_blob(profile: Profile) -> str:
    """Lowercased bag of everything the profile says about itself.

    Example:
        >>> "python" in profile_blob(Profile(skills=["Python"]))
        True
    """
    parts: list[str] = [
        profile.headline,
        profile.summary,
        profile.country,
        " ".join(profile.skills),
        " ".join(profile.interests),
        " ".join(profile.languages),
    ]
    for item in profile.education:
        parts += [item.institution, item.degree, item.field]
    for item in profile.experience:
        parts += [item.title, item.organization, item.description]
    for item in profile.projects:
        parts += [item.name, item.description, *item.technologies]
    return normalize_word(" ".join(part for part in parts if part))


def experience_years(profile: Profile, today: date | None = None) -> float | None:
    """Years of experience addable from ISO-ish dates; None when nothing parses.

    Example:
        >>> experience_years(profile_with_one_year_stint)   # doctest: +ELLIPSIS
        1.0
    """
    today = today or date.today()
    total, counted = 0.0, 0
    for item in profile.experience:
        start = _iso_date(item.start_date)
        end_text = (item.end_date or "").strip().casefold()
        end = today if end_text in _ONGOING else _iso_date(item.end_date)
        if start is None or end is None or end < start:
            continue
        total += (end - start).days / 365.25
        counted += 1
    return round(total, 2) if counted else None


def _iso_date(value: str | None) -> date | None:
    """'2025', '2025-06', '2025-06-01' -> date; anything else -> None (never guessed)."""
    match = _ISO_DATE_RE.match((value or "").strip())
    if match is None:
        return None
    try:
        return date(int(match.group("y")), int(match.group("m") or 1), int(match.group("d") or 1))
    except ValueError:
        return None


def _education_line(line: str) -> bool:
    """True for lines about a degree, a level or being enrolled somewhere."""
    return bool(_EDUCATION_WORDS.search(line) or _level_of(line) is not None)


def _level_of(text: str) -> int | None:
    """Highest degree level named in `text` (baccalaureate=1 ... doctorate=4)."""
    levels = [level for pattern, level in _DEGREE_PATTERNS if pattern.search(text)]
    return max(levels) if levels else None


def _profile_level(profile: Profile) -> int | None:
    """Highest degree level the profile's own education entries state."""
    levels = [_level_of(f"{item.degree} {item.field}") for item in profile.education]
    return max((level for level in levels if level), default=None)


def _field_terms(line: str) -> list[str]:
    """Disciplines a requirement names: 'in ML or CS' / 'Maths or CS students'."""
    captured: list[str] = []
    inside = re.search(r"\bin\s+(?!progress\b)([^,.;]+)", line, re.IGNORECASE)
    if inside:
        captured.append(inside.group(1))
    students = re.match(r"^(.*?)\s+students?\b", line, re.IGNORECASE)
    if students:
        captured.append(students.group(1))
    terms: list[str] = []
    for chunk in captured:
        for piece in re.split(r"\s*(?:,|\bor\b|\band\b|&)\s*", chunk):
            term = normalize_word(piece)
            if _is_field_term(term):
                terms.append(term)
    return list(dict.fromkeys(terms))


def _is_field_term(term: str) -> bool:
    """A real discipline, not a level word ('master') nor a generic ('a field').

    Short terms stay valid on purpose: 'ML' and 'CS' are disciplines too.
    """
    return bool(term) and "field" not in term and term not in _FILLER and _level_of(term) is None


def _looks_like_a_skill(line: str) -> bool:
    """MISSED (not just UNKNOWN) only when the line clearly asks for a skill."""
    low = line.casefold()
    if any(marker in low for marker in _SKILL_MARKERS):
        return True
    return len(line.split()) <= 3


def _criterion(line: str, status: CriteriaStatus, evidence: str) -> EligibilityCriterion:
    """One criterion row (text as written, status, why)."""
    return EligibilityCriterion(text=line.strip(), status=status, evidence=evidence)


def normalize_word(value: str) -> str:
    """Lowercased, whitespace-collapsed text (the project's comparison form).

    Example:
        >>> normalize_word("  Data   Science ")
        'data science'
    """
    return " ".join((value or "").split()).casefold()
