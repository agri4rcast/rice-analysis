# 🌾 산지쌀값 분석 웹앱

통계청 KOSIS 데이터를 활용한 산지쌀값·공공비축 수매가 자동 분석 웹앱

---

## 폴더 구조

```
rice-analysis/
├── backend/
│   ├── main.py           ← 분석 서버 (FastAPI)
│   ├── requirements.txt  ← 패키지 목록
│   └── start.sh          ← 서버 시작 명령
└── frontend/
    └── index.html        ← 웹 화면
```

---

## 배포 방법

### 1단계: Render (백엔드 서버)
1. render.com 접속
2. New → Web Service
3. GitHub 저장소 연결
4. Root Directory: `backend`
5. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. 배포 완료 후 URL 확인 (예: https://rice-analysis.onrender.com)

### 2단계: index.html 수정
frontend/index.html 안의 API_URL을 Render URL로 교체:
```
const API_URL = "https://YOUR-APP.onrender.com/analyze";
```

### 3단계: GitHub Pages (프론트엔드)
1. Settings → Pages
2. Source: main 브랜치 / frontend 폴더
3. 접속 주소: https://아이디.github.io/rice-analysis
