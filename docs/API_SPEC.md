# Maritime Patrol AI - 추론 API 명세서

AI 기반 해양 경비순찰 경로분석 REST API. Q-Learning으로 최적 순찰 경로를 생성하고, 순찰 필요 지역(복합영향도 기반)을 산출합니다.

---

## 기본 정보

| 항목 | 내용 |
|------|------|
| **Base URL** | `http://127.0.0.1:8000` (기본) |
| **추론 엔드포인트** | `POST /inference` |
| **Content-Type** | `application/json` |
| **응답 형식** | JSON |

---

## 엔드포인트

### 1. 헬스 체크

```
GET /
GET /health
```

**응답 예시:**
```json
{
  "status": "ok",
  "service": "maritime-patrol-inference"
}
```

---

### 2. 추론 (경로·순찰 지역 생성)

```
POST /inference
```

#### 요청 본문 (Request Body)

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `requestId` | string | O | 요청 식별자 |
| `filter` | object | O | 필터 조건 |
| `options` | object | - | 출력 옵션 (기본값 있음) |
| `strategy` | string | - | 순찰 전략: `safety`, `efficiency`, `surveillance` (기본: `safety`) |
| `map_seed` | int | - | 맵 시드 (재현성). 미지정 시 변동 시드 사용 |
| `polygon` | array | - | 순찰 영역 Polygon [lat, lng]. 2점 이상. 미지정 시 기본 영역 |
| `port` | string | - | 출발 항구. `gunsan`=군산항. `null`이면 격자 (0,0) 기준 |
| `start_position` | object | - | 순찰 시작 좌표. port 지정 시 무시 |
| `end_position` | object | - | 순찰 종료 좌표. 미지정 시 start와 동일 |

**filter 객체:**

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `startTime` | string | O | 시작 시간 (ISO 8601) |
| `endTime` | string | O | 종료 시간 (ISO 8601) |
| `shipId` | string | - | 선박 ID (기본: `ALL`) |
| `accidentType` | string | - | 사고 유형 (기본: `ALL`) |

**options 객체:**

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `includeRoute` | boolean | true | 경로 포함 여부 |
| `includeAccidentZone` | boolean | true | 순찰 지역(patrolZones) 포함 여부 |
| `includeLabels` | boolean | true | 라벨 포함 여부 |
| `includeGrid` | boolean | true | 격자 정보 포함 여부 |

---

#### 요청 예시 (최소)

```json
{
  "requestId": "REQ-20260313-001",
  "filter": {
    "startTime": "2026-03-01T00:00:00Z",
    "endTime": "2026-03-09T23:59:59Z"
  }
}
```

#### 요청 예시 (전체 옵션)

```json
{
  "requestId": "REQ-20260313-001",
  "filter": {
    "startTime": "2026-03-01T00:00:00Z",
    "endTime": "2026-03-09T23:59:59Z",
    "shipId": "ALL",
    "accidentType": "ALL"
  },
  "options": {
    "includeRoute": true,
    "includeAccidentZone": true,
    "includeLabels": true,
    "includeGrid": true
  },
  "strategy": "safety",
  "map_seed": 42,
  "polygon": [
    { "lat": 35.97530, "lng": 126.5657 },
    { "lat": 36.0528187, "lng": 126.1917131 }
  ],
  "port": "gunsan",
  "start_position": null,
  "end_position": null
}
```

#### 요청 예시 (출발지 없음 - 실패 케이스)

```json
{
  "requestId": "REQ-NO-START",
  "filter": {
    "startTime": "2026-03-01T00:00:00Z",
    "endTime": "2026-03-09T23:59:59Z"
  },
  "port": null,
  "start_position": null
}
```

---

#### 응답 본문 (Response Body)

| 필드 | 타입 | 설명 |
|------|------|------|
| `success` | boolean | 서비스 동작 여부. 출발지 미지정 시 `false` |
| `requestId` | string | 요청 ID |
| `summary` | object | 요약 정보 |
| `routes` | array | 순찰 경로 목록 |
| `patrolZones` | array | 순찰 필요 지역 목록 |
| `accidents` | array | patrolZones 복사본 (하위 호환) |
| `labels` | array | 라벨 목록 |
| `grid` | object \| null | 격자 정보. includeGrid=false 시 null |

**summary 객체:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `routeCount` | int | 경로 개수 |
| `patrolZoneCount` | int | 순찰 필요 지역 개수 |
| `accidentCount` | int | patrolZoneCount와 동일 (하위 호환) |

**routes[].path 요소 (LatLngPoint):**

| 필드 | 타입 | 설명 |
|------|------|------|
| `lat` | float | 위도 |
| `lng` | float | 경도 |

**patrolZones[] (PatrolZone):**

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 식별자 |
| `type` | string | 예: 고위험, 위험 |
| `label` | string | 예: 순찰필요 고도 |
| `center` | object | 중심 좌표 {lat, lng} |
| `radius` | float | 반경(미터). 75→최대의 50%, 100→최대 |
| `patrolNecessity` | float | 순찰 필요성 0~1. 0.75 이상만 원 표시 |
| `staticScore` | float | 정적위험 점수 0~1 |
| `dynamicScore` | float | 동적위험 점수 0~1 |
| `environmentScore` | float | 환경제약 점수 0~1 |

**grid 객체:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `bbox` | object | {latMin, latMax, lngMin, lngMax} |
| `rows` | int | 격자 행 수 |
| `cols` | int | 격자 열 수 |
| `lines` | array | 격자선 좌표 |
| `influence` | array | 셀별 복합영향도 0~1 (행우선) |
| `staticInfluence` | array | 셀별 정적위험 0~1 |
| `dynamicInfluence` | array | 셀별 동적위험 0~1 |
| `environmentInfluence` | array | 셀별 환경제약 0~1 |

---

#### 응답 예시 (성공)

```json
{
  "success": true,
  "requestId": "REQ-20260313-001",
  "summary": {
    "routeCount": 1,
    "patrolZoneCount": 7,
    "accidentCount": 7
  },
  "routes": [
    {
      "routeId": "R001",
      "name": "AI 순찰 경로",
      "path": [
        { "lat": 35.981, "lng": 126.499 },
        { "lat": 35.982, "lng": 126.501 },
        { "lat": 35.983, "lng": 126.503 }
      ]
    }
  ],
  "patrolZones": [
    {
      "id": "PZ-0-3",
      "type": "고위험",
      "label": "순찰필요 고도",
      "center": { "lat": 35.985, "lng": 126.45 },
      "radius": 55.6,
      "count": 0,
      "patrolNecessity": 0.82,
      "staticScore": 0.85,
      "dynamicScore": 0.12,
      "environmentScore": 0.34
    }
  ],
  "accidents": [
    {
      "id": "PZ-0-3",
      "type": "고위험",
      "label": "순찰필요 고도",
      "center": { "lat": 35.985, "lng": 126.45 },
      "radius": 55.6,
      "count": 0,
      "patrolNecessity": 0.82,
      "staticScore": 0.85,
      "dynamicScore": 0.12,
      "environmentScore": 0.34
    }
  ],
  "labels": [],
  "grid": {
    "bbox": {
      "latMin": 35.9753,
      "latMax": 36.0528,
      "lngMin": 126.1917,
      "lngMax": 126.5657
    },
    "rows": 20,
    "cols": 25,
    "lines": [
      {
        "start": { "lat": 36.0528, "lng": 126.1917 },
        "end": { "lat": 36.0528, "lng": 126.5657 }
      }
    ],
    "influence": [0.12, 0.85, 0.34, 0.56],
    "staticInfluence": [0.05, 0.78, 0.22, 0.45],
    "dynamicInfluence": [0.08, 0.12, 0.15, 0.18],
    "environmentInfluence": [0.12, 0.25, 0.30, 0.22]
  }
}
```

#### 응답 예시 (실패 - 출발지 미지정)

```json
{
  "success": false,
  "requestId": "REQ-NO-START",
  "summary": {
    "routeCount": 0,
    "patrolZoneCount": 0,
    "accidentCount": 0
  },
  "routes": [],
  "patrolZones": [],
  "accidents": [],
  "labels": [],
  "grid": null
}
```

---

## 순찰 전략 (strategy)

| 값 | 설명 | 특징 |
|----|------|------|
| `safety` | 안전 우선 | 순찰 필요성 높은 구역 우선 탐색 |
| `efficiency` | 효율 우선 | 최소 이동으로 효율적 순찰 |
| `surveillance` | 광역 감시 | 넓은 영역 커버리지 |

---

## cURL 예시

```bash
curl -X POST http://127.0.0.1:8000/inference \
  -H "Content-Type: application/json" \
  -d '{
    "requestId": "REQ-001",
    "filter": {
      "startTime": "2026-03-01T00:00:00Z",
      "endTime": "2026-03-09T23:59:59Z"
    },
    "port": "gunsan"
  }'
```

---

## 에러 응답

| HTTP 코드 | 상황 |
|-----------|------|
| 200 | 정상 (success: true/false로 결과 구분) |
| 422 | 요청 JSON 형식 오류 (Validation Error) |
| 500 | 서버 내부 오류 |

---

## 버전 정보

- **API 버전**: 1.0.0
- **문서 작성일**: 2026-03-13
