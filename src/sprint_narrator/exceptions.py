class SprintNarratorError(Exception):
    """Base exception for sprint-narrator."""


class ConfigError(SprintNarratorError):
    """Configuration is missing or invalid."""


class SourceAuthError(SprintNarratorError):
    """Authentication failed for a data source."""


class SourceFetchError(SprintNarratorError):
    """Failed to fetch data from a source."""


class NarratorError(SprintNarratorError):
    """Failed to generate narrative via LLM."""
