"""
Spotify metadata client for the combined JioSaavn + Spotify bot.
Uses spotipy Client Credentials (no user login required).
Optional env: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Link patterns
TRACK_RE = re.compile(
    r"(?:https?://)?open\.spotify\.com/track/([a-zA-Z0-9]+)(?:\?.*)?"
)
ALBUM_RE = re.compile(
    r"(?:https?://)?open\.spotify\.com/album/([a-zA-Z0-9]+)(?:\?.*)?"
)
PLAYLIST_RE = re.compile(
    r"(?:https?://)?open\.spotify\.com/playlist/([a-zA-Z0-9]+)(?:\?.*)?"
)
SHORT_RE = re.compile(r"(?:https?://)?spotify\.link/([a-zA-Z0-9]+)")

PAGE_SIZE = 10


def get_link_type(text: str) -> Optional[str]:
    if TRACK_RE.search(text):
        return "track"
    if ALBUM_RE.search(text):
        return "album"
    if PLAYLIST_RE.search(text):
        return "playlist"
    if SHORT_RE.search(text):
        return "shortened"
    return None


def extract_id(text: str, link_type: str) -> Optional[str]:
    patterns = {
        "track": TRACK_RE,
        "album": ALBUM_RE,
        "playlist": PLAYLIST_RE,
        "shortened": SHORT_RE,
    }
    m = patterns.get(link_type)
    if not m:
        return None
    match = m.search(text)
    return match.group(1) if match else None


def resolve_short_link(url: str) -> str:
    import requests

    try:
        r = requests.head(url, allow_redirects=True, timeout=15)
        return r.url
    except Exception as e:
        logger.warning("Failed to resolve short Spotify link: %s", e)
        return url


def _make_spotipy():
    """Build a spotipy client. Returns None if credentials / package missing."""
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        from spotipy.cache_handler import MemoryCacheHandler
    except ImportError:
        logger.error("spotipy not installed. pip install spotipy")
        return None

    client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        logger.error(
            "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET not set. "
            "Get them at https://developer.spotify.com/dashboard"
        )
        return None

    mgr = SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret,
        cache_handler=MemoryCacheHandler(),
    )
    return spotipy.Spotify(client_credentials_manager=mgr, requests_timeout=20)


def _artist_names(item: dict) -> str:
    artists = item.get("artists") or []
    names = [a.get("name") for a in artists if isinstance(a, dict) and a.get("name")]
    return ", ".join(names)


def _track_entry(t: dict) -> Optional[Dict[str, Any]]:
    if not t or not t.get("id"):
        return None
    return {
        "id": t["id"],
        "name": t.get("name") or "Unknown",
        "artist": _artist_names(t),
        "album": (t.get("album") or {}).get("name") or "",
        "duration_ms": t.get("duration_ms") or 0,
        "url": (t.get("external_urls") or {}).get("spotify")
        or f"https://open.spotify.com/track/{t['id']}",
        "image": _best_image(t.get("album") or {}),
    }


def _best_image(obj: dict) -> str:
    images = obj.get("images") or []
    if not images:
        return ""
    # Prefer larger images
    sorted_imgs = sorted(images, key=lambda i: i.get("width") or 0, reverse=True)
    return sorted_imgs[0].get("url") or ""


class SpotifyAPI:
    """Thin async-friendly wrapper (spotipy is sync; call via executor if needed)."""

    def __init__(self):
        self._sp = None

    @property
    def sp(self):
        if self._sp is None:
            self._sp = _make_spotipy()
        return self._sp

    def get_track(self, track_id: str) -> Optional[Dict[str, Any]]:
        if not self.sp:
            return None
        try:
            t = self.sp.track(track_id)
            return _track_entry(t)
        except Exception as e:
            logger.error("get_track(%s) failed: %s", track_id, e)
            return None

    def get_album(self, album_id: str) -> Optional[Dict[str, Any]]:
        if not self.sp:
            return None
        try:
            album = self.sp.album(album_id)
            tracks: List[Dict[str, Any]] = []
            results = self.sp.album_tracks(album_id, limit=50)
            items = results.get("items") or []
            while True:
                for t in items:
                    # album_tracks items lack album/image; attach parent
                    t = dict(t)
                    t["album"] = {
                        "name": album.get("name"),
                        "images": album.get("images"),
                    }
                    entry = _track_entry(t)
                    if entry:
                        tracks.append(entry)
                if results.get("next"):
                    results = self.sp.next(results)
                    items = results.get("items") or []
                else:
                    break
            return {
                "type": "album",
                "id": album_id,
                "title": album.get("name") or "Album",
                "artist": _artist_names(album),
                "url": (album.get("external_urls") or {}).get("spotify")
                or f"https://open.spotify.com/album/{album_id}",
                "image": _best_image(album),
                "total": len(tracks),
                "tracks": tracks,
            }
        except Exception as e:
            logger.error("get_album(%s) failed: %s", album_id, e)
            return None

    def get_playlist(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        if not self.sp:
            return None
        try:
            pl = self.sp.playlist(playlist_id, fields="name,external_urls,images,owner")
            tracks: List[Dict[str, Any]] = []
            results = self.sp.playlist_tracks(playlist_id, limit=100)
            items = results.get("items") or []
            while True:
                for row in items:
                    t = (row or {}).get("track")
                    entry = _track_entry(t) if t else None
                    if entry:
                        tracks.append(entry)
                if results.get("next"):
                    results = self.sp.next(results)
                    items = results.get("items") or []
                else:
                    break
            return {
                "type": "playlist",
                "id": playlist_id,
                "title": pl.get("name") or "Playlist",
                "artist": (pl.get("owner") or {}).get("display_name") or "",
                "url": (pl.get("external_urls") or {}).get("spotify")
                or f"https://open.spotify.com/playlist/{playlist_id}",
                "image": _best_image(pl),
                "total": len(tracks),
                "tracks": tracks,
            }
        except Exception as e:
            logger.error("get_playlist(%s) failed: %s", playlist_id, e)
            return None

    def search_tracks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.sp:
            return []
        try:
            results = self.sp.search(q=query, type="track", limit=min(limit, 20))
            items = (results.get("tracks") or {}).get("items") or []
            out = []
            for t in items:
                entry = _track_entry(t)
                if entry:
                    out.append(entry)
            return out
        except Exception as e:
            logger.error("search_tracks(%r) failed: %s", query, e)
            return []
