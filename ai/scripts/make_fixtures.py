# Generates ai/data/fixtures/: 30 synthetic opportunities and 5 synthetic
# profiles used by notebooks 04/05 and the tests. Deadlines are computed
# relative to today so the fixtures never expire. No real data.
# Run from ai/:  python scripts/make_fixtures.py

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "data" / "fixtures"
EVAL = Path(__file__).resolve().parents[1] / "data" / "eval"
STAMP = FIXTURES / "generated_on.txt"
TODAY = date.today()

# Ids of the two fixture entries that ARE scams (all others, including the two
# borderline ones, are legitimate). Written to data/eval/scam_labels.json.
KNOWN_SCAMS = {"opp-31", "opp-32"}

# title, organizer, type, mode, location, country, days_to_deadline, funding,
# eligibility, benefits, language, summary
ROWS = [
    (
        "AI Research Intern",
        "NVIDIA",
        "internship",
        "remote",
        "Remote",
        "USA",
        45,
        "$5,000/mo",
        ["Master's students in ML or CS", "PyTorch experience"],
        ["Mentorship", "Publication track"],
        "en",
        "Work with the NVIDIA research team on efficient training of large models.",
    ),
    (
        "Machine Learning Intern",
        "Ooredoo Algerie",
        "internship",
        "hybrid",
        "Algiers",
        "Algeria",
        21,
        "15,000 DZD/mo",
        ["Students only", "Python required"],
        ["Mentorship", "Possibility of conversion to CDI"],
        "fr",
        "Modeles predictifs pour la retention client. Rythme hybride, deux jours sur site.",
    ),
    (
        "Frontend Developer Intern",
        "Yassir",
        "internship",
        "hybrid",
        "Algiers",
        "Algeria",
        12,
        "20,000 DZD/mo",
        ["React knowledge", "Students welcome"],
        ["Product impact", "Sport card"],
        "en",
        "Join the Yassir product squad building the super-app used across the Maghreb.",
    ),
    (
        "Data Analyst Intern",
        "DP World",
        "internship",
        "onsite",
        "Djibouti",
        "Djibouti",
        60,
        "Unpaid",
        ["Statistics or CS background", "Willing to relocate"],
        ["Housing provided", "Certificate"],
        "en",
        "Port logistics analytics on-site in Djibouti.",
    ),
    (
        "Backend Engineer (Junior)",
        "Acme Cloud Labs",
        "job",
        "remote",
        "Remote",
        "France",
        30,
        "38k-45k EUR/yr",
        ["Python", "FastAPI or Django", "SQL"],
        ["Remote work", "12 extra vacation days"],
        "en",
        "Junior backend role on a FastAPI and Postgres stack, remote within EU timezones.",
    ),
    (
        "Software Engineer I",
        "Canonical",
        "job",
        "remote",
        "Remote",
        "United Kingdom",
        40,
        "70k-90k USD/yr",
        ["Professional English writing", "Linux fluency"],
        ["All-remote", "Annual retreat"],
        "en",
        "Ubuntu engineering team, async-first, written communication is key.",
    ),
    (
        "PhD Position - NLP for Arabic",
        "MBZUAI",
        "research",
        "onsite",
        "Abu Dhabi",
        "UAE",
        25,
        "Fully funded",
        ["MSc in CS or NLP", "Research experience", "English"],
        ["Full funding", "Stipend", "Conference budget"],
        "en",
        "Fully funded PhD on low-resource Arabic NLP, start Spring 2027.",
    ),
    (
        "Master's Scholarship in AI",
        "ENSICAEN",
        "scholarship",
        "onsite",
        "Caen",
        "France",
        18,
        "8,000 EUR/yr",
        ["Bachelor's degree", "English B2"],
        ["Tuition coverage", "Mobility grant"],
        "en",
        "Erasmus Mundus joint master's scholarship in artificial intelligence.",
    ),
    (
        "DAAD Development-Related Scholarships",
        "DAAD",
        "scholarship",
        "onsite",
        "Germany",
        "Germany",
        35,
        "992 EUR/mo",
        ["Graduate from a developing country", "Two years of work experience"],
        ["Monthly stipend", "Tuition covered"],
        "en",
        "Scholarships for graduates from developing countries pursuing "
        "postgraduate degrees in Germany.",
    ),
    (
        "Expired Data Viz Contest",
        "Old Charts Org",
        "hackathon",
        "remote",
        "Remote",
        "Global",
        -30,
        "$500 prize",
        ["Open to all"],
        ["Prize"],
        "en",
        "This listing closed a month ago - used to test expired-opportunity filtering.",
    ),
    (
        "Global Hack: Fintech",
        "Devpost",
        "hackathon",
        "remote",
        "Remote",
        "Global",
        8,
        "$5,000 prize",
        ["Teams of 1-4", "Open to all"],
        ["Prize pool", "Sponsor mentorship"],
        "en",
        "48-hour online hackathon building the future of payments with sponsor APIs.",
    ),
    (
        "Deep Learning Bootcamp",
        "ALX Africa",
        "bootcamp",
        "remote",
        "Remote",
        "Nigeria",
        28,
        "Free",
        ["African residents", "Ages 18-34"],
        ["12-week program", "Career support"],
        "en",
        "12-week intensive deep learning program for African developers, selection-based.",
    ),
    (
        "Full-Stack Bootcamp Selection",
        "1337 - 42 Network",
        "bootcamp",
        "onsite",
        "Benguerir",
        "Morocco",
        50,
        "Free",
        ["No degree required", "Able to relocate to Benguerir"],
        ["No tuition", "Peer learning"],
        "fr",
        "Curriculum full-stack par les pairs. Pas de professeur, pas de frais, "
        "selection par le game.",
    ),
    (
        "Research Assistant - Computer Vision",
        "Institut Polytechnique de Paris",
        "research",
        "hybrid",
        "Palaiseau",
        "France",
        33,
        "1,700 EUR/mo",
        ["MSc in progress", "PyTorch"],
        ["Research contract", "Lab access"],
        "fr",
        "Contrat de 6 mois en reconstruction 3D pour la robotique.",
    ),
    (
        "Volunteer AI Tutor",
        "Code.org Maghreb",
        "volunteer",
        "remote",
        "Remote",
        "Algeria",
        20,
        "Unpaid",
        ["Fluent in Python", "Available 2h/week"],
        ["Impact", "Community"],
        "en",
        "Mentor high-school students in Python twice a week, remote.",
    ),
    (
        "Summer Intern - Quantitative Research",
        "Wren Capital",
        "internship",
        "onsite",
        "London",
        "United Kingdom",
        10,
        "2,500 GBP/mo",
        ["Maths or CS students", "Strong Python"],
        ["Paid internship", "Return offer possible"],
        "en",
        "Quant research internship for maths and CS students, June to August.",
    ),
    (
        "DevOps Engineer",
        "GitLab",
        "job",
        "remote",
        "Remote",
        "Global",
        55,
        "85k-105k USD/yr",
        ["Kubernetes", "Terraform", "English"],
        ["All-remote", "Company paid home office"],
        "en",
        "Own the CI/CD platform serving hundreds of engineers.",
    ),
    (
        "Graphic Design Intern",
        "Yassir",
        "internship",
        "hybrid",
        "Oran",
        "Algeria",
        9,
        "12,000 DZD/mo",
        ["Figma portfolio", "Students welcome"],
        ["Portfolio pieces", "Mentorship"],
        "en",
        "Design marketing assets and app screens with the brand team.",
    ),
    (
        "Erasmus+ Traineeship Grant",
        "European Commission",
        "grant",
        "hybrid",
        "EU",
        "France",
        70,
        "600 EUR/mo",
        ["Enrolled in a European university"],
        ["Grant funding", "Travel allowance"],
        "en",
        "Grant funding a 2-3 month traineeship anywhere in the EU for enrolled students.",
    ),
    (
        "Junior Data Scientist",
        "InstaDeep",
        "job",
        "hybrid",
        "Tunis",
        "Tunisia",
        27,
        "4,500 TND/mo",
        ["Python", "Optimization or ML background", "English"],
        ["Relocation support", "Equity"],
        "en",
        "Optimization plus ML hybrid role, hybrid in the Tunis office.",
    ),
    (
        "Open Source Summer - Compilers",
        "MLIR Community",
        "research",
        "remote",
        "Remote",
        "Global",
        3,
        "6,000 USD stipend",
        ["C++ skills", "Open source interest"],
        ["Stipend", "Mentorship"],
        "en",
        "Paid open-source summer program on the MLIR compiler infrastructure.",
    ),
    (
        "Cloud Engineering Intern",
        "Amazon Web Services",
        "internship",
        "onsite",
        "Cape Town",
        "South Africa",
        19,
        "25,000 ZAR/mo",
        ["CS students", "Linux basics"],
        ["Graduate rotation", "Return offers"],
        "en",
        "12-month graduate rotation across AWS solution teams in Cape Town.",
    ),
    (
        "MSc Scholarship - Data Science",
        "Mohammed VI Polytechnic University",
        "scholarship",
        "onsite",
        "Ben Guerir",
        "Morocco",
        44,
        "Full funding",
        ["BSc in a quantitative field", "English"],
        ["Full funding", "Industry internship"],
        "en",
        "Fully funded master's in data science with a research track.",
    ),
    (
        "Backend Intern - Rust",
        "Astra Labs",
        "internship",
        "remote",
        "Remote",
        "Global",
        30,
        "1,200 USD/mo",
        ["Rust basics", "Async-first work style"],
        ["Remote", "Open-source work"],
        "en",
        "Rust services for a satellite ground-station network, remote, async-first.",
    ),
    (
        "AI Ethics Fellowship",
        "Mozilla Foundation",
        "fellowship",
        "remote",
        "Remote",
        "Global",
        60,
        "20,000 USD stipend",
        ["Interest in AI policy", "Publications or writing samples"],
        ["Stipend", "Network"],
        "en",
        "One-year fellowship at the intersection of AI policy and open technology.",
    ),
    (
        "React Native Developer",
        "Batolis",
        "job",
        "hybrid",
        "Algiers",
        "Algeria",
        22,
        "60,000 DZD/mo",
        ["React Native", "TypeScript", "Arabic and French"],
        ["Hybrid work", "Transport allowance"],
        "en",
        "Mobile engineer for a logistics platform, hybrid rhythm in Algiers.",
    ),
    (
        "Robotics Intern",
        "Boston Dynamics AI Institute",
        "internship",
        "onsite",
        "Boston",
        "USA",
        48,
        "6,500 USD/mo",
        ["Robotics coursework", "Python and C++"],
        ["Research internship", "Housing help"],
        "en",
        "Research internship on learning-based manipulation, on-site in Boston.",
    ),
    (
        "Web Development Training",
        "Algerie Telecom Foundation",
        "bootcamp",
        "onsite",
        "Constantine",
        "Algeria",
        6,
        "Free",
        ["Baccalaureate or equivalent"],
        ["Free training", "Certificate"],
        "fr",
        "Formation de 6 mois en developpement web sur le campus de Constantine.",
    ),
    # --- Borderline #1: legitimate event that charges a registration fee ------
    # A fee on its own is NOT a scam (summits/hackathons charge fees) — the
    # scam checker must not flag this one.
    (
        "Algiers AI Summit Hackathon",
        "Sahara Tech Events",
        "hackathon",
        "onsite",
        "Algiers",
        "Algeria",
        14,
        "5,000 DZD prize",
        ["Students and juniors welcome", "Teams of 1-4"],
        ["Meals and starter kit included", "Mentorship"],
        "en",
        "48-hour student hackathon during the Algiers AI Summit. The 1,500 DZD registration "
        "fee covers meals, t-shirt and starter kit; free for scholarship holders.",
    ),
    # --- Borderline #2: legitimate offer whose contact is a free e-mail -------
    # A gmail contact on its own is NOT a scam (small studios use free mail).
    # No fee, no urgency, no bank/ID requests — must stay unflagged.
    (
        "Junior Web Developer (Small Studio)",
        "Studio Lina Digital",
        "job",
        "hybrid",
        "Oran",
        "Algeria",
        16,
        "25,000 DZD/mo",
        ["React or Vue basics", "Portfolio required"],
        ["Paid trial task", "Flexible hours"],
        "en",
        "A five-person studio in Oran builds e-commerce sites. Write to "
        "contact.studiolinadigital@gmail.com with your portfolio. No application fee, "
        "paid trial task, signed contract from day one.",
    ),
    # --- Known scam #1: application fee + urgency (must be flagged) ----------
    (
        "URGENT Make Money From Home - No Experience",
        "Global Talent Now LLC",
        "job",
        "remote",
        "Remote",
        "Unknown",
        2,
        "5,000 USD/week",
        ["No skills needed"],
        ["Instant income"],
        "en",
        "Send your passport by WhatsApp and pay a 2,000 DZD registration fee to start immediately. "
        "LAST CHANCE! Contact hr.talentnow@gmail.com.",
    ),
    # --- Known scam #2: bank details + free-mail organizer (must be flagged) --
    (
        "Bank Transfer Scholarship 100% Guaranteed",
        "Education Fund Intl",
        "scholarship",
        "remote",
        "Remote",
        "Unknown",
        5,
        "10,000 USD",
        ["Send your RIB and ID card by email now"],
        ["100% guaranteed funding"],
        "en",
        "Easy money for students! Send your bank details (RIB) and a copy of your ID card to "
        "fund.intl.scholarships@yahoo.com within 48h to receive your grant. Guaranteed 100%!",
    ),
]


def make_opportunities() -> list[dict]:
    opportunities = []
    for i, row in enumerate(ROWS, start=1):
        (
            title,
            organizer,
            typ,
            mode,
            loc,
            country,
            days,
            funding,
            elig,
            benef,
            language,
            summary,
        ) = row
        deadline = (TODAY + timedelta(days=days)).isoformat()
        opportunities.append(
            {
                "id": f"opp-{i:02d}",
                "title": title,
                "organizer": organizer,
                "type": typ,
                "mode": mode,
                "location": loc,
                "country": country,
                "language": language,
                "deadline": deadline,
                "funding": funding,
                "eligibility": elig,
                "benefits": benef,
                "summary": summary,
                "url": f"https://example.org/opportunities/{i:02d}",
                "source": "fixture",
                "trust_level": "unknown",
                "added_via": "pipeline",
            }
        )
    return opportunities


PROFILES = [
    {
        "user_id": "u-amine",
        "full_name": "Amine Kaddour",
        "headline": "Data Science Master's student",
        "country": "Algeria",
        "skills": [
            "python",
            "sql",
            "pandas",
            "numpy",
            "pytorch",
            "scikit-learn",
            "machine learning",
            "deep learning",
            "git",
            "linux",
        ],
        "languages": ["arabic", "french", "english"],
        "interests": ["nlp", "computer vision", "ai research"],
        "education": [
            {"institution": "USTHB", "degree": "MSc", "field": "Data Science", "end_date": "2027"}
        ],
        "experience": [
            {
                "organization": "NAMOCO Analytics",
                "title": "Machine Learning Intern",
                "start_date": "2025-06",
                "end_date": "2025-09",
            }
        ],
        "preferences": {
            "types": ["internship", "research", "scholarship"],
            "modes": ["remote", "hybrid"],
            "countries": [],
            "needs_funding": True,
        },
        "summary": "Data science master's student in Algiers, ML and NLP, seeking remote ML "
        "internships and research positions.",
    },
    {
        "user_id": "u-sara",
        "full_name": "Sara Belkacem",
        "headline": "Frontend Developer",
        "country": "Algeria",
        "skills": ["react", "typescript", "next.js", "css", "figma", "react native"],
        "languages": ["french", "english"],
        "interests": ["web development", "ui design"],
        "education": [
            {
                "institution": "ENSMAD",
                "degree": "BSc",
                "field": "Web Development",
                "end_date": "2024",
            }
        ],
        "experience": [
            {
                "organization": "Startup Studio Oran",
                "title": "Frontend Developer",
                "start_date": "2024",
            }
        ],
        "preferences": {
            "types": ["job", "internship"],
            "modes": ["hybrid", "remote"],
            "countries": ["Algeria"],
            "needs_funding": False,
        },
        "summary": "Frontend developer in Oran, React and TypeScript, looking for hybrid roles "
        "in Algeria.",
    },
    {
        "user_id": "u-youcef",
        "full_name": "Youcef Merabet",
        "headline": "Backend and DevOps engineer",
        "country": "Algeria",
        "skills": ["python", "fastapi", "postgresql", "docker", "kubernetes", "terraform", "linux"],
        "languages": ["arabic", "french", "english"],
        "interests": ["cloud", "infrastructure"],
        "education": [
            {
                "institution": "ENP Oran",
                "degree": "MSc",
                "field": "Software Engineering",
                "end_date": "2023",
            }
        ],
        "experience": [
            {"organization": "Freelance", "title": "Backend Engineer", "start_date": "2023"}
        ],
        "preferences": {
            "types": ["job"],
            "modes": ["remote"],
            "countries": [],
            "needs_funding": False,
        },
        "summary": "Backend and DevOps engineer with FastAPI, Docker and Kubernetes, seeking "
        "remote roles worldwide.",
    },
    {
        "user_id": "u-lina",
        "full_name": "Lina Haddad",
        "headline": "Humanities master's student",
        "country": "Algeria",
        "skills": ["research", "writing", "english", "french"],
        "languages": ["arabic", "french", "english"],
        "interests": ["human rights", "public policy", "migration studies"],
        "education": [
            {"institution": "USTHB", "degree": "MA", "field": "Humanities", "end_date": "2026"}
        ],
        "experience": [],
        "preferences": {
            "types": ["scholarship", "grant", "fellowship"],
            "modes": ["onsite"],
            "countries": ["France"],
            "needs_funding": True,
        },
        "summary": "Humanities master's student seeking funded scholarships and fellowships "
        "in France for 2027.",
    },
    {
        "user_id": "u-karim",
        "full_name": "Karim Ziani",
        "headline": "Product designer and hackathon player",
        "country": "Morocco",
        "skills": ["figma", "ui design", "javascript", "html", "css", "prototyping"],
        "languages": ["arabic", "french", "english"],
        "interests": ["hackathons", "product design", "startups"],
        "education": [
            {"institution": "ENSA", "degree": "BSc", "field": "Design", "end_date": "2023"}
        ],
        "experience": [
            {"organization": "Freelance", "title": "Product Designer", "start_date": "2023"}
        ],
        "preferences": {
            "types": ["hackathon", "bootcamp", "internship"],
            "modes": ["remote", "hybrid"],
            "countries": [],
            "needs_funding": False,
        },
        "summary": "Product designer who joins hackathons and bootcamps, remote or hybrid, "
        "based in Morocco.",
    },
]


def make_scam_labels(opportunities: list[dict]) -> dict[str, bool]:
    """is_scam ground truth for every fixture id: only KNOWN_SCAMS are True."""
    return {opp["id"]: opp["id"] in KNOWN_SCAMS for opp in opportunities}


def warn_if_stale(stamp_path: Path | None = None, today: date | None = None) -> bool:
    """Warn when the fixtures were generated on a previous day.

    Fixture deadlines are relative to the generation day, so they drift out of
    date. Call this before a demo; re-run `python scripts/make_fixtures.py` to
    refresh. Returns True when the fixtures are stale.

    Example:
        >>> warn_if_stale()  # True + warning if generated before today
        True
    """
    stamp_path = stamp_path or STAMP
    today = today or date.today()
    stamp = stamp_path.read_text(encoding="utf-8").strip() if stamp_path.exists() else None
    if stamp != today.isoformat():
        print(
            f"WARNING: fixtures were last generated on {stamp or 'unknown'} — deadlines may "
            "be stale. Re-run: python scripts/make_fixtures.py"
        )
        return True
    return False


def main() -> None:
    warn_if_stale()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    EVAL.mkdir(parents=True, exist_ok=True)
    opportunities = make_opportunities()
    (FIXTURES / "opportunities.json").write_text(
        json.dumps(opportunities, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (FIXTURES / "profiles.json").write_text(
        json.dumps(PROFILES, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (STAMP).write_text(TODAY.isoformat() + "\n", encoding="utf-8")
    labels = make_scam_labels(opportunities)
    (EVAL / "scam_labels.json").write_text(
        json.dumps(labels, indent=2) + "\n", encoding="utf-8"
    )
    scams = sum(labels.values())
    print(
        f"wrote {len(opportunities)} opportunities ({scams} known scams) and "
        f"{len(PROFILES)} profiles (today={TODAY.isoformat()})"
    )


if __name__ == "__main__":
    main()
