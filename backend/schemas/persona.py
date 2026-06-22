"""
Schemas for Darpan — the Instagram persona-context feature.

Darpan (दर्पण, "mirror") builds a context dossier about an Instagram account from
details the Alexia extension scrapes off the live profile page (Instagram has no
open API) plus the images we already saved from that account. The dossier is both
an analytical profile and a generative "how to create as them" guide.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AccountDetails(BaseModel):
    """Account facts scraped from the Instagram profile DOM (best-effort)."""
    display_name: Optional[str] = None
    bio: Optional[str] = None
    followers: Optional[str] = None        # kept as strings ("1.2M") — IG abbreviates
    following: Optional[str] = None
    posts_count: Optional[str] = None
    avatar_url: Optional[str] = None
    external_link: Optional[str] = None
    verified: Optional[bool] = None
    category: Optional[str] = None
    raw_og_description: Optional[str] = None


class PersonaIngestRequest(BaseModel):
    """Payload the extension POSTs after scraping a profile/post page."""
    handle: str
    source_url: Optional[str] = None
    account: AccountDetails = Field(default_factory=AccountDetails)
    captured_captions: List[str] = Field(default_factory=list)
    captured_image_urls: List[str] = Field(default_factory=list)
