# crawler-yt-channels

YouTube 채널의 신규 영상을 감시하는 크롤러. `BaseCrawler` 구현 — HTML 파싱이 아니라 YouTube Data API v3(`search.list`)를 직접 호출한다. JS 렌더링이 필요 없으므로 `watch-playwright`를 거치지 않는다. 컨테이너 하나로 여러 채널을 처리한다(채널 추가는 `crawlers.params.channel_id` INSERT만으로 가능).

## API

### POST /crawl

```json
{"channel_id": "UCxxxxxxxx"}
```

`channel_id` 필수 — 없으면 400. 채널의 최신 영상 5개(`maxResults=5`, `order=date`)를 조회한다.

응답: `Item[]` — `data`에 `channel_title`, `published_at`, `thumbnail` 포함

### GET /health

`{"status": "ok"}`

## 쇼츠 제외 필터

YouTube Data API 응답에는 쇼츠 여부를 나타내는 공식 필드가 없다. 대신 각 영상 ID로 `https://www.youtube.com/shorts/{id}`에 HEAD 요청을 보내 판별한다 — 쇼츠면 200, 롱폼이면 `/watch`로 3xx 리다이렉트가 온다. 판별 자체가 실패하면(네트워크 오류 등) 롱폼으로 간주해 누락보다 오탐(쇼츠를 롱폼으로 잘못 포함)을 택한다.

## id (중복 감지 키)

```python
items.append(Item(id=vid, ...))
```

YouTube가 영상마다 부여하는 `videoId`를 그대로 `id`로 쓴다 — 플랫폼이 보장하는 안정적인 고유 식별자라 별도 가공이 필요 없다.

## batch_group과의 관계

이 크롤러 자체는 `batch_group`을 모른다 — 배치 실행 여부는 `crawlers` 테이블의 `batch_group` 컬럼과 `watch-runner`가 결정한다. 즉시 알림이 필요한 채널(`batch_group=null`)과 하루 2회 요약 묶음 발송이 필요한 구독 채널(`batch_group='youtube-daily'`)이 같은 컨테이너를 params만 다르게 해서 공유한다.

## 환경변수

| 변수 | 설명 |
|---|---|
| `YOUTUBE_API_KEY` | YouTube Data API v3 키 |

## 포트

| 포트 | 용도 |
|---|---|
| 8080 | aiohttp — 컴포즈 내부에서만 노출 |
