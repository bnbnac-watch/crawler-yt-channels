import asyncio
import logging
import os
from urllib.parse import urlsplit

import httpx
from watch_contract import BaseCrawler, Item, CrawlerException

logger = logging.getLogger(__name__)

_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
_SHORTS_URL = "https://www.youtube.com/shorts/{vid}"
_MAX_RESULTS = 5


def _uploads_playlist_id(channel_id: str) -> str:
    # 채널의 업로드 재생목록 ID는 채널 ID의 "UC" 접두사를 "UU"로 바꾼 값과 같다(YouTube 규약).
    # playlistItems.list는 search.list보다 100배 싸고(1 unit vs 100 unit) 인덱스 지연도 없다.
    return "UU" + channel_id[2:] if channel_id.startswith("UC") else channel_id


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
            "playlistId": _uploads_playlist_id(channel_id),
            "maxResults": _MAX_RESULTS,
            "key": _API_KEY,
        }
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.get(_PLAYLIST_ITEMS_URL, params=params)
                res.raise_for_status()
                data = res.json()

                items = []
                for entry in data.get("items", []):
                    snippet = entry["snippet"]
                    vid = snippet["resourceId"]["videoId"]
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
        except httpx.HTTPStatusError as e:
            host = urlsplit(str(e.request.url)).netloc
            msg = f"{host} 응답 {e.response.status_code}"
            logger.error("crawl 예외: channel=%s, %s (key 포함 전체 URL은 debug 로그 생략)", channel_id, msg)
            raise CrawlerException(msg) from e
        except Exception as e:
            logger.error("crawl 예외: channel=%s, %s", channel_id, e)
            raise CrawlerException(str(e)) from e
