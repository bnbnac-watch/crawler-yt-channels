import asyncio
import logging
import os
from dataclasses import asdict

import httpx
from watch_contract import BaseCrawler, Item, CrawlerException

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_SHORTS_URL = "https://www.youtube.com/shorts/{vid}"
_MAX_RESULTS = 5


async def _is_short(client: httpx.AsyncClient, video_id: str) -> bool:
    # 공식 API에 isShort 필드가 없어 shorts URL 동작으로 판별:
    # 쇼츠는 200, 롱폼은 /watch로 3xx 리다이렉트. 판별 실패 시 롱폼으로 간주
    try:
        res = await client.head(
            _SHORTS_URL.format(vid=video_id), follow_redirects=False
        )
        return res.status_code == 200
    except Exception as e:
        logger.warning("쇼츠 판별 실패 (%s): %s", video_id, e)
        return False


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

                shorts_flags = await asyncio.gather(
                    *[_is_short(client, item.id) for item in items]
                )
            longforms = [item for item, short in zip(items, shorts_flags) if not short]
            logger.info(
                "파싱 완료: channel=%s, 롱폼 %d개 (쇼츠 %d개 제외)",
                channel_id, len(longforms), len(items) - len(longforms),
            )
            return longforms
        except Exception as e:
            logger.error("crawl 예외: channel=%s, %s", channel_id, e)
            raise CrawlerException(str(e)) from e
