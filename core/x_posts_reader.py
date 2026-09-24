"""Read original posts from the official WOODY X account and relay them to Telegram."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests

logger = logging.getLogger("WOODY_X_POSTS")
X_API_BASE = "https://api.x.com/2"


class XOfficialPostsReader:
    def __init__(
        self,
        *,
        bearer_token: str,
        username: str,
        state_file: str,
        timeout_seconds: int = 10,
        max_results: int = 10,
    ) -> None:
        self.bearer_token = bearer_token.strip()
        self.username = username.strip().lstrip("@")
        self.state_file = Path(state_file)
        self.timeout_seconds = max(1, int(timeout_seconds))
        self.max_results = max(5, min(100, int(max_results)))
        self._user_id: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return bool(self.bearer_token and self.username)

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.bearer_token}", "User-Agent": "WOODY-Monitor/2"}

    def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        response = requests.get(url, headers=self._headers(), params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected X API response")
        return payload

    def _resolve_user_id(self) -> str:
        if self._user_id:
            return self._user_id
        payload = self._get_json(f"{X_API_BASE}/users/by/username/{self.username}")
        user_id = str((payload.get("data") or {}).get("id") or "").strip()
        if not user_id:
            raise ValueError(f"X user @{self.username} was not found")
        self._user_id = user_id
        return user_id

    def fetch_recent(self) -> List[Dict[str, Any]]:
        user_id = self._resolve_user_id()
        params = {
            "max_results": self.max_results,
            "exclude": "retweets,replies",
            "tweet.fields": "created_at,referenced_tweets,entities,attachments",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url",
        }
        payload = self._get_json(f"{X_API_BASE}/users/{user_id}/tweets", params=params)
        media_by_key = {
            str(item.get("media_key")): item
            for item in (payload.get("includes") or {}).get("media", [])
            if item.get("media_key")
        }
        posts: List[Dict[str, Any]] = []
        for tweet in payload.get("data") or []:
            if not self._is_original(tweet):
                continue
            item = dict(tweet)
            item["_media"] = [
                media_by_key[key]
                for key in ((tweet.get("attachments") or {}).get("media_keys") or [])
                if key in media_by_key
            ]
            posts.append(item)
        return posts

    @staticmethod
    def _is_original(tweet: Dict[str, Any]) -> bool:
        # Replies/retweets are excluded server-side. This second check also rejects
        # quote tweets and protects us if X changes the endpoint filtering behavior.
        if tweet.get("referenced_tweets"):
            return False
        # User requirement: do not relay posts that mention other X accounts.
        if (tweet.get("entities") or {}).get("mentions"):
            return False
        return bool(str(tweet.get("id") or "").strip())

    def _load_seen(self) -> set[str]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
            values = payload.get("seen_ids", []) if isinstance(payload, dict) else []
            return {str(value) for value in values if value}
        except FileNotFoundError:
            return set()
        except Exception as exc:
            logger.warning("X state read failed: %s", exc)
            return set()

    def _save_seen(self, seen: Iterable[str]) -> None:
        values = list(dict.fromkeys(str(value) for value in seen if value))[-500:]
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        tmp.write_text(json.dumps({"seen_ids": values}, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_file)

    def new_posts(self) -> List[Dict[str, Any]]:
        posts = self.fetch_recent()
        seen = self._load_seen()
        current_ids = [str(post.get("id")) for post in posts if post.get("id")]

        # First successful run establishes a baseline and never floods Telegram
        # with historical posts.
        if not seen:
            self._save_seen(current_ids)
            logger.info("X baseline initialized with %s posts", len(current_ids))
            return []

        fresh = [post for post in posts if str(post.get("id")) not in seen]
        self._save_seen(list(seen) + current_ids)
        return list(reversed(fresh))


def post_url(username: str, post_id: str) -> str:
    return f"https://x.com/{username.lstrip('@')}/status/{post_id}"


def post_media(post: Dict[str, Any]) -> Optional[Dict[str, str]]:
    for media in post.get("_media") or []:
        media_type = str(media.get("type") or "")
        url = str(media.get("url") or media.get("preview_image_url") or "").strip()
        if url:
            return {"type": media_type, "url": url}
    return None
