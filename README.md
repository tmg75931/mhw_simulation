# 🛡️ 몬스터헌터 와일즈(Monster Hunter Wilds) 장비 & 스탯 대시보드

[`.gemini/gemini.md`](./.gemini/gemini.md) 개발 지침에 따라 구축된 **Monster Hunter: Wilds 장비 분석 및 커스텀 세트 시뮬레이터 대시보드**입니다.
별도의 데이터베이스(DB) 없이 외부 API(`https://wilds.mhdb.io/`)를 호출하여 `@st.cache_data`로 인메모리 캐싱하는 가벼운 아키텍처를 사용합니다.

---

## 🛠️ 기술 스택

- **언어:** Python 3.12 (`.venv` 가상환경)
- **대시보드 프레임워크:** Streamlit (`wide` 레이아웃)
- **데이터 처리:** Pandas (`DataFrame` 전처리 및 집계)
- **데이터 시각화:** Plotly (`Scatter Plot`, `Radar Chart`, `Horizontal Bar Chart`)
- **API 통신:** Requests (`@st.cache_data` 메모리 캐싱 적용)

---

## 🚀 실행 방법

프로젝트 루트 경로에서 아래 명령어로 Streamlit 대시보드를 실행합니다:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

실행 후 브라우저에서 **`http://localhost:8501`** 로 접속하면 대시보드를 이용할 수 있습니다.

---

## ✨ 주요 기능 명세

### 1. 🔍 Feature 1: 방어구 스탯 및 가성비 탐색기 (Gear Stats Explorer)
- **스킬명 / 방어구명 검색** 및 **부위별(머리/가슴/팔/허리/다리) · 랭크별(하위/상위) 드롭다운 필터링**
- **Plotly 산점도 차트 (Scatter Plot)**:
  - X축: 물리 방어력 (기본 방어력 / 최대 강화 방어력 선택 가능)
  - Y축: 5대 속성 내성 (불, 물, 번개, 얼음, 용 내성 선택 가능)
  - 툴팁: 방어구 이름, 부위, 레어도, 보유 스킬, 슬롯 정보 표시
- **데이터 테이블 (`st.dataframe`)**: 산점도 우측에 필터링된 방어구 상세 스탯 리스트를 나란히 출력

### 2. 🛠️ Feature 2: 와일즈 커스텀 장비 시뮬레이터 (Custom Set Builder)
- **5부위 드롭다운 선택 (머리, 가슴, 팔, 허리, 다리)** 및 **풀세트 프리셋 빠른 불러오기**
- **종합 스탯 메트릭**: 총합 기본/최대 물리 방어력, 장식주 슬롯 합계(【3】/【2】/【1】), 5대 속성 내성 합계 출력
- **속성 내성 시각화 (Plotly Radar Chart)**: 불, 물, 번개, 얼음, 용 5대 속성의 합산 내성을 방사형 다각형 차트로 시각화
- **발동 스킬 시각화 (Plotly Horizontal Bar Chart)**: 조합으로 발동된 모든 스킬의 유효 레벨과 초과 레벨을 가로형 누적 막대그래프로 시각화하고, 레벨별 실제 발동 효과를 표로 제공

---

## 📂 디렉토리 구조

- [`app.py`](./app.py) : Streamlit 메인 대시보드 애플리케이션 (Phase 2 ~ Phase 4)
- [`src/data_pipeline.py`](./src/data_pipeline.py) : MH Wilds API 호출, `@st.cache_data` 캐싱 및 Pandas DataFrame 전처리 모듈 (Phase 1)
- [`requirements.txt`](./requirements.txt) : Python 패키지 의존성 목록
- [`.gemini/gemini.md`](./.gemini/gemini.md) : 프로젝트 개발 지침서
