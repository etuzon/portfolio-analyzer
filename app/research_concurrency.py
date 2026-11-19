"""Shared concurrency configuration for public research coordinators and workers."""

DEFAULT_RESEARCH_CONCURRENCY = 5


def research_concurrency(settings):
    value = settings.get("research_concurrency", DEFAULT_RESEARCH_CONCURRENCY)
    if type(value) is not int or value < 1:
        raise ValueError("price_agent.research_concurrency must be a positive integer.")
    return value
