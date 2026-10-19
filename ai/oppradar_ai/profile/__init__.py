"""CV → structured Profile.

    from oppradar_ai.profile import parse_cv
    profile = parse_cv("data/private/my_cv.pdf")
"""

from oppradar_ai.profile.cv_parser import CVParseError, parse_cv

__all__ = ["parse_cv", "CVParseError"]
