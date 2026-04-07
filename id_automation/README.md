# 🪪 신분증 자동화 프로그램

신분증 관리 업무를 자동화하는 GUI 프로그램입니다.

## 📋 기능

| Phase | 기능 | 상태 |
|-------|------|------|
| 1 | 엑셀 자동 복사 (종합양식 → 출석부) | ✅ 완료 |
| 2 | 신분증 마스킹 | 🚧 개발 예정 |
| 3 | 개별 신분증 분리 저장 | 🚧 개발 예정 |
| 4 | OCR 검증 (Naver Clova API) | 🚧 개발 예정 |

## 🚀 설치 방법

### 1. Python 설치
- Python 3.10 이상 필요
- https://www.python.org/downloads/

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 실행
```bash
cd src
python main.py
```

## 📦 exe 파일 만들기

```bash
pip install pyinstaller
cd src
pyinstaller --onefile --windowed --name "신분증자동화" main.py
```

생성된 exe 파일: `dist/신분증자동화.exe`

## 📁 폴더 구조

```
id_automation/
├── src/
│   ├── main.py           # GUI 메인 프로그램
│   └── excel_handler.py  # 엑셀 처리 모듈
├── data/                  # 데이터 파일
├── output/                # 출력 파일
├── requirements.txt       # 의존성 목록
└── README.md
```

## 🔧 사용 방법

### Phase 1: 엑셀 복사

1. 프로그램 실행
2. "1️⃣ 엑셀 복사" 탭 선택
3. "종합양식" 파일 선택 (찾아보기 버튼)
4. "출석부양식" 파일 선택 (찾아보기 버튼)
5. "미리보기" 버튼으로 데이터 확인
6. "복사 실행" 버튼 클릭
7. 새 파일이 타임스탬프와 함께 저장됨

## ⚠️ 주의사항

- 원본 파일은 수정되지 않습니다 (새 파일로 저장)
- 엑셀 파일에 '출석부양식' 시트가 있어야 합니다
- 한글 경로에서도 정상 작동합니다

## 📞 문의

개발 관련 문의는 담당자에게 연락 바랍니다.
