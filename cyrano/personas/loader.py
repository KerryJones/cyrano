"""Load persona profiles from YAML config."""

from cyrano.config import load_personality


def load_persona(filename: str = "personality.yml") -> dict:
    """Load a persona profile from config."""
    return load_personality(filename)
