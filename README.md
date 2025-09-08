# Paper Analyzer (Report Project)

폴더 안의 PDF 논문들을 자동으로 찾아 텍스트/이미지 추출 → LLM 요약 → 전체 종합 보고서와 유사성/클러스터 결과를 생성하는 CLI 도구입니다. Rich 기반 진행 표시로 전체/문서별 상태를 실시간으로 확인할 수 있습니다.

## 주요 기능
- 폴더의 `*.pdf` 자동 탐색 및 처리
- PyMuPDF로 본문/이미지 추출, 메타데이터 저장
- LM Studio API로 논문 요약(청크 기반 요약 + 통합)
- 전체 종합 요약 + 유사도 상위 페어 + 클러스터 결과
- Rich 진행바: 전체 진행 및 문서별(청크 단위) 상태 표시
- 호출 결과 캐시(JSONL)로 재실행 가속

## 사전 준비
- Python 3.10+
- LM Studio 설치 및 서버 실행
  - 기본 URL: `http://localhost:1234/v1`
  - 환경변수(선택): `LMSTUDIO_BASE_URL`, `LMSTUDIO_API_KEY` (기본값 `lm-studio`)

## 설치
- Make 사용 권장:
  - `make setup`
- 또는 직접 설치:
  - `pip install -r requirements.txt`

## 실행 예제
- 도움말 보기:
  - `make dev`
  - 또는 `python3 -m src.paper_analyzer.cli --help`

- 기본 실행(예시 데이터 폴더 사용):
  - `python3 -m src.paper_analyzer.cli --input-dir sample_data`

- 대화형 실행(옵션 수정):
  - `python3 -m src.paper_analyzer.cli --input-dir sample_data --interactive`
  - 실행 전 입력 폴더, 아티팩트/리포트 폴더, 모델/URL, temperature, 청크/토큰/클러스터 수를 프롬프트로 수정 가능

- 주요 옵션:
  - `--artifacts-dir`: 아티팩트 출력 폴더(기본 `artifacts`)
  - `--report-dir`: 보고서 출력 폴더(기본 `report`)
  - `--model`: LM Studio 모델명(기본 `openai/gpt-oss-20b`)
  - `--lmstudio-url`: LM Studio API Base URL (기본 `http://localhost:1234/v1`)
  - `--temperature`: 샘플링 온도(기본 `0.2`)
  - `--max-chars`: 청크 최대 문자수(기본 `4000`)
  - `--max-tokens`: LLM 출력 토큰 상한(기본 `512`)
  - `--clusters`: 클러스터 수(기본 `3`)

## 진행 표시(Progress)
- 전체 진행바: "총 N개 PDF 처리" 기준으로 1개 문서 완료 시 1씩 증가
- 문서별 진행바:
  - "요약 준비: <제목>" → 청크 개수 확정 후 "요약 중: <제목>"
  - 청크 요약 완료 시마다 1씩 증가
  - "결과 통합 중: <제목>" → "완료: <제목>"

## 출력물
- 보고서: `report/summary.md`
- 본문 텍스트: `artifacts/clean_text/<paper_id>.txt`
- 추출 이미지: `artifacts/figures/<paper_id>/*.png`
- 메타데이터: `artifacts/metadata/<paper_id>.json`
- LLM 캐시: `artifacts/cache/*.jsonl`

## 프로젝트 구조(요약)
```
report_project/
  src/paper_analyzer/
  sample_data/           # 예시 입력
  artifacts/             # 실행 시 생성
  report/                # summary.md 출력 위치
  requirements.txt
  Makefile
```

## 트러블슈팅
- `ModuleNotFoundError: rich`: `make setup` 또는 `pip install -r requirements.txt` 실행
- LM Studio 연결 실패: 서버 실행 및 `--lmstudio-url`/`LMSTUDIO_BASE_URL` 확인
- Python 버전 오류: Python 3.10+ 사용 권장
