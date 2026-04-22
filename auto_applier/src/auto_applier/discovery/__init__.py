from __future__ import annotations

from .base import DiscoveryAdapter, JobListing
from .greenhouse import GreenhouseAdapter

__all__ = ["DiscoveryAdapter", "JobListing", "GreenhouseAdapter", "load_adapters"]


def load_adapters(sources: list[str] | None = None) -> list[DiscoveryAdapter]:
    sources = sources or ["greenhouse"]
    out: list[DiscoveryAdapter] = []
    for name in sources:
        if name == "greenhouse":
            out.append(GreenhouseAdapter())
        elif name == "lever":
            from .lever import LeverAdapter

            out.append(LeverAdapter())
        elif name == "ashby":
            from .ashby import AshbyAdapter

            out.append(AshbyAdapter())
        elif name == "rss":
            from .rss import RSSAdapter

            out.append(RSSAdapter())
    return out
