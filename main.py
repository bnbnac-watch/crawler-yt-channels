import logging
from dataclasses import asdict

from aiohttp import web

from crawler import YtChannelsCrawler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_crawler = YtChannelsCrawler()


async def health(request):
    return web.json_response({"status": "ok"})


async def crawl(request):
    try:
        body = await request.json()
        channel_id = body.get("channel_id")
        if not channel_id:
            raise web.HTTPBadRequest(reason="channel_id required")
        items = await _crawler.crawl(channel_id)
        logger.info("crawl 완료: channel=%s, %d개", channel_id, len(items))
        return web.json_response([asdict(item) for item in items])
    except web.HTTPException:
        raise
    except Exception as e:
        logger.error("crawl 실패: %s", e)
        raise web.HTTPInternalServerError(reason=str(e))


app = web.Application()
app.router.add_get("/health", health)
app.router.add_post("/crawl", crawl)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
