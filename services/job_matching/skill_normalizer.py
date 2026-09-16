import re


SKILL_ALIASES: dict[str, str] = {
    # Programming languages
    "python": "python",
    "python 3": "python",
    "python3": "python",
    "py": "python",

    "js": "javascript",
    "javascript": "javascript",

    "ts": "typescript",
    "typescript": "typescript",

    "sql": "sql",

    # Databases
    "postgres": "postgresql",
    "postgres db": "postgresql",
    "postgres database": "postgresql",
    "postgresql": "postgresql",

    "mongo": "mongodb",
    "mongo db": "mongodb",
    "mongodb": "mongodb",

    # APIs / frameworks
    "restful api": "rest api",
    "restful apis": "rest api",
    "rest api": "rest api",
    "rest apis": "rest api",

    "fastapi": "fastapi",

    "react": "react",
    "react.js": "react",
    "reactjs": "react",

    # Containerization
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",

    "docker": "docker",

    # Cloud
    "amazon web services": "aws",
    "aws": "aws",

    "microsoft azure": "azure",
    "azure": "azure",

    "google cloud platform": "gcp",
    "google cloud": "gcp",
    "gcp": "gcp",

    # ML / AI
    "machine learning": "machine learning",
    "ml": "machine learning",

    "artificial intelligence": "artificial intelligence",
    "ai": "artificial intelligence",

    "generative ai": "generative ai",
    "genai": "generative ai",

    "large language model": "llm",
    "large language models": "llm",
    "llms": "llm",
    "llm": "llm",

    "pytorch": "pytorch",
    "tensorflow": "tensorflow",
}


def normalize_skill(skill: str) -> str:
    """
    Convert a skill into its canonical representation.

    Unknown skills are normalized conservatively rather than
    being mapped to a potentially incorrect known skill.
    """
    if not isinstance(skill, str):
        raise TypeError("skill must be a string")

    normalized = skill.strip().lower()

    normalized = re.sub(r"\s+", " ", normalized)

    if not normalized:
        return ""

    return SKILL_ALIASES.get(normalized, normalized)


def normalize_skills(skills: list[str]) -> list[str]:
    """
    Normalize a collection of skills and remove duplicates.
    """
    normalized: list[str] = []
    seen: set[str] = set()

    for skill in skills:
        canonical = normalize_skill(skill)

        if canonical and canonical not in seen:
            normalized.append(canonical)
            seen.add(canonical)

    return normalized