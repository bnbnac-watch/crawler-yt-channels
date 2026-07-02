import logging
import os
from dataclasses import asdict

import httpx
from watch_contract import BaseCrawler, Item, CrawlerException

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_MAX_RESULTS = 5


class YtChannelsCrawler(BaseCrawler):
    async def crawl(self, channel_id: str) -> list[Item]:
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": _MAX_RESULTS,
            "key": _API_KEY,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.get(_SEARCH_URL, params=params)
                res.raise_for_status()
                data = res.json()

            items = []
            for entry in data.get("items", []):
                vid = entry["id"]["videoId"]
                snippet = entry["snippet"]
                url = f"https://www.youtube.com/watch?v={vid}"
                items.append(Item(
                    id=vid,
                    title=snippet["title"],
                    url=url,
                    data={
                        "channel_title": snippet.get("channelTitle", ""),
                        "published_at": snippet.get("publishedAt", ""),
                        "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                    },
                ))
            logger.info("파싱 완료: channel=%s, %d개", channel_id, len(items))
            return items
        except Exception as e:
            logger.error("crawl 예외: channel=%s, %s", channel_id, e)
            raise CrawlerException(str(e)) from e
