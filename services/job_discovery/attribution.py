"""Source attribution registry (AJI-028).

Many zero-cost job sources license their data on the condition that it
is credited: name the source and link back to the posting on the source's
site. This registry is the one generic place that obligation is declared,
keyed by the `source` value an adapter stamps on every `DiscoveredJob`
(and that is stored on `Job.source`). The API reads it per job to return
`source_attribution`; the Jobs UI renders it. Nothing downstream branches
on a provider name.

Adding an approved source means adding one entry here next to its
adapter. A source with no entry is shown by its raw `source` label with no
attribution link - which is correct for the synthetic test fixture and
for user-submitted jobs, both deliberately absent.

`requires_link_back=True` means every place the job is shown must carry a
visible link to the posting on the source (`Job.source_url`), or to
`homepage_url` when the posting has no URL, naming the source.
"""

from __future__ import annotations

from dataclasses import dataclass

from services.job_discovery.normalizer import normalize_url


@dataclass(frozen=True)
class SourceAttribution:
    source: str
    display_name: str
    homepage_url: str | None = None
    requires_link_back: bool = False

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.display_name.strip():
            raise ValueError("source and display_name are required.")

        if self.homepage_url is not None and (
            normalize_url(self.homepage_url) != self.homepage_url
        ):
            raise ValueError("homepage_url must be an absolute http(s) URL.")

        if self.requires_link_back and self.homepage_url is None:
            # A posting may arrive without its own URL; the source's
            # homepage is the fallback link, so it must exist.
            raise ValueError(
                "A source that requires a link back needs a homepage_url."
            )


def _registry(*entries: SourceAttribution) -> dict[str, SourceAttribution]:
    registry: dict[str, SourceAttribution] = {}
    for entry in entries:
        if entry.source in registry:
            raise ValueError(f"Duplicate attribution for '{entry.source}'.")
        registry[entry.source] = entry
    return registry


SOURCE_ATTRIBUTIONS: dict[str, SourceAttribution] = _registry(
    # Greenhouse board data belongs to the employer whose board it is; the
    # public board API has no attribution requirement. Registered for its
    # display name only, which is what the UI already showed.
    SourceAttribution(source="greenhouse", display_name="Greenhouse"),
)


def get_source_attribution(
    source: str | None,
    *,
    registry: dict[str, SourceAttribution] | None = None,
) -> SourceAttribution | None:
    if not source:
        return None

    return (SOURCE_ATTRIBUTIONS if registry is None else registry).get(source)


def attribution_link(
    attribution: SourceAttribution,
    *,
    source_url: str | None,
) -> str | None:
    """Where the attribution should link: the posting on the source when
    known, else the source's homepage."""
    return normalize_url(source_url) or attribution.homepage_url
