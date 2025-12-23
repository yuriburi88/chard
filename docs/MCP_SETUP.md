# CHARD MCP 서버 설정 가이드

## 🚀 빠른 시작

### 1. 필수 패키지 설치

```bash
pip install mcp
```

### 2. Claude Desktop 설정

**Windows 설정 파일 경로:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**설정 내용:**

이 프로젝트의 `claude_desktop_config.json` 파일 내용을 복사하여 위 경로에 붙여넣으세요.

또는 직접 입력:

```json
{
  "mcpServers": {
    "chard": {
      "command": "python",
      "args": [
        "C:\\Users\\Richard\\Test\\CHARD\\chard\\run_mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "C:\\Users\\Richard\\Test\\CHARD\\chard",
        "PYTHONIOENCODING": "utf-8"
      }
    }
  }
}
```

### 3. Claude Desktop 재시작

설정 파일을 저장한 후 Claude Desktop을 완전히 종료하고 다시 시작하세요.

---

## 📋 사용 가능한 도구

### 1. `collect_rss`
RSS 피드에서 뉴스를 수집합니다.

**사용 예시:**
```
CoinDesk RSS 피드에서 최근 24시간 뉴스 수집해줘
```

### 2. `collect_telegram`
Telegram 채널에서 메시지를 수집합니다.

**사용 예시:**
```
Telegram coinnesskr 채널에서 최근 100개 메시지 가져와줘
```

### 3. `run_full_analysis`
전체 파이프라인을 실행합니다.

**사용 예시:**
```
전체 분석 실행해줘
```

### 4. `get_latest_keywords`
최신 키워드 분석 결과를 조회합니다.

**사용 예시:**
```
오늘 주요 키워드 10개 보여줘
```

### 5. `list_rss_feeds`
설정된 RSS 피드 목록을 조회합니다.

**사용 예시:**
```
설정된 RSS 피드 목록 보여줘
```

### 6. `list_telegram_channels`
설정된 Telegram 채널 목록을 조회합니다.

**사용 예시:**
```
Telegram 채널 목록 알려줘
```

---

## 📚 사용 가능한 리소스

### 1. `chard://config`
CHARD 설정 파일 (config.yml)

### 2. `chard://reports/latest`
최신 분석 리포트

### 3. `chard://data/latest`
최신 수집 데이터

### 4. `chard://analysis/latest`
최신 분석 결과

**리소스 조회 예시:**
```
최신 리포트 보여줘
설정 파일 내용 확인해줘
```

---

## 🎯 실전 사용 예시

### 시나리오 1: 일일 브리핑

```
사용자: "오늘 암호화폐 시장 브리핑해줘"

Claude:
1. [list_rss_feeds 사용] 설정된 피드 확인
2. [collect_rss 사용] 모든 RSS 수집
3. [collect_telegram 사용] Telegram 메시지 수집
4. [run_full_analysis 사용] 분석 실행
5. [chard://reports/latest 조회] 리포트 제공

결과: 종합 브리핑 제공
```

### 시나리오 2: 특정 키워드 추적

```
사용자: "최근 'ETF' 키워드가 얼마나 나왔어?"

Claude:
1. [get_latest_keywords 사용] 키워드 분석 조회
2. ETF 관련 정보 필터링
3. 트렌드 분석 제공
```

### 시나리오 3: 설정 확인 및 수정

```
사용자: "어떤 RSS 피드들이 설정되어 있어?"

Claude:
[list_rss_feeds 사용]

사용 가능한 RSS 피드:
1. BlockMedia - https://www.blockmedia.co.kr/feed
2. CoinDesk - https://www.coindesk.com/...
...
```

---

## 🔧 문제 해결

### MCP 서버가 연결되지 않을 때

1. **Python 경로 확인**
   ```bash
   which python  # Mac/Linux
   where python  # Windows
   ```

2. **mcp 패키지 설치 확인**
   ```bash
   pip show mcp
   ```

3. **Claude Desktop 로그 확인**
   - Windows: `%APPDATA%\Claude\logs\`
   - Mac: `~/Library/Logs/Claude/`

4. **수동 테스트**
   ```bash
   python run_mcp_server.py
   ```

### 도구 호출이 실패할 때

1. **config.yml 확인**
   - 파일이 존재하는지
   - 형식이 올바른지

2. **데이터 디렉토리 확인**
   - `output/` 디렉토리가 존재하는지
   - 분석 결과 파일이 있는지

3. **권한 확인**
   - 파일 읽기/쓰기 권한
   - 디렉토리 접근 권한

---

## 📝 개발자 노트

### 테스트 방법

```bash
# MCP 서버 직접 실행
python run_mcp_server.py

# 도구 목록 확인 (서버 실행 후 JSON-RPC 요청)
# 실제로는 Claude Desktop이 자동으로 처리
```

### 커스터마이징

1. **새 도구 추가**: `mcp/tools.py` 편집
2. **새 리소스 추가**: `mcp/resources.py` 편집
3. **설정 변경**: `config.yml` 편집

---

## 🎉 완료!

이제 Claude Desktop에서 자연어로 CHARD를 제어할 수 있습니다!

**테스트 명령:**
```
"CHARD가 뭘 할 수 있는지 알려줘"
"RSS 피드 목록 보여줘"
"최신 분석 결과 요약해줘"
```
