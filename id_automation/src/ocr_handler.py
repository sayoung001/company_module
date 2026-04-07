"""
OCR 처리 핸들러
Phase 4: 신분증 OCR → 엑셀 데이터 검증
Naver Clova OCR API 또는 Tesseract 사용
"""

import base64
import json
import re
import time
from pathlib import Path

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import pytesseract
    from PIL import Image
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


class OCRHandler:
    def __init__(self, api_url: str = "", api_key: str = "",
                 secret_key: str = "", use_clova: bool = True):
        """
        Args:
            api_url: Naver Clova OCR API URL
            api_key: API Key ID
            secret_key: API Secret Key
            use_clova: True=Clova API, False=Tesseract
        """
        self.api_url = api_url
        self.api_key = api_key
        self.secret_key = secret_key
        self.use_clova = use_clova

    def is_available(self) -> dict:
        """OCR 엔진 사용 가능 여부 확인"""
        if self.use_clova:
            available = HAS_REQUESTS and bool(self.api_url) and bool(self.secret_key)
            return {
                'available': available,
                'engine': 'Naver Clova OCR',
                'message': '사용 가능' if available else 'API 키가 설정되지 않았습니다.'
            }
        else:
            return {
                'available': HAS_TESSERACT,
                'engine': 'Tesseract OCR',
                'message': '사용 가능' if HAS_TESSERACT else 'pytesseract가 설치되지 않았습니다.'
            }

    # ==================== OCR 실행 ====================

    def extract_text(self, image_path: str) -> dict:
        """이미지에서 텍스트 추출"""
        if self.use_clova:
            return self._clova_ocr(image_path)
        else:
            return self._tesseract_ocr(image_path)

    def _clova_ocr(self, image_path: str) -> dict:
        """Naver Clova OCR API 호출"""
        if not HAS_REQUESTS:
            return {'success': False, 'text': '', 'fields': [],
                    'message': 'requests 모듈이 설치되지 않았습니다.'}

        try:
            with open(image_path, 'rb') as f:
                img_data = f.read()

            ext = Path(image_path).suffix.lower().replace('.', '')
            if ext == 'jpg':
                ext = 'jpeg'

            request_json = {
                'images': [
                    {
                        'format': ext,
                        'name': Path(image_path).stem,
                        'data': base64.b64encode(img_data).decode('utf-8')
                    }
                ],
                'requestId': str(int(time.time() * 1000)),
                'version': 'V2',
                'timestamp': int(time.time() * 1000)
            }

            headers = {
                'X-OCR-SECRET': self.secret_key,
                'Content-Type': 'application/json'
            }

            response = requests.post(
                self.api_url,
                headers=headers,
                data=json.dumps(request_json),
                timeout=30
            )

            if response.status_code != 200:
                return {'success': False, 'text': '', 'fields': [],
                        'message': f'API 오류: {response.status_code}'}

            result = response.json()
            fields = []
            texts = []

            for image_result in result.get('images', []):
                for field in image_result.get('fields', []):
                    text = field.get('inferText', '')
                    texts.append(text)
                    fields.append({
                        'text': text,
                        'confidence': field.get('inferConfidence', 0),
                        'bounding': field.get('boundingPoly', {})
                    })

            full_text = ' '.join(texts)

            return {
                'success': True,
                'text': full_text,
                'fields': fields,
                'message': f'{len(fields)}개 텍스트 필드 인식'
            }

        except Exception as e:
            return {'success': False, 'text': '', 'fields': [],
                    'message': f'Clova OCR 오류: {str(e)}'}

    def _tesseract_ocr(self, image_path: str) -> dict:
        """Tesseract OCR 실행"""
        if not HAS_TESSERACT:
            return {'success': False, 'text': '', 'fields': [],
                    'message': 'pytesseract가 설치되지 않았습니다.'}

        try:
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang='kor+eng')

            return {
                'success': True,
                'text': text,
                'fields': [],
                'message': 'Tesseract OCR 완료'
            }
        except Exception as e:
            return {'success': False, 'text': '', 'fields': [],
                    'message': f'Tesseract 오류: {str(e)}'}

    # ==================== 정보 파싱 ====================

    def parse_id_info(self, ocr_text: str) -> dict:
        """OCR 텍스트에서 이름, 생년월일 추출"""
        info = {'name': '', 'birth': '', 'raw_text': ocr_text}

        # 생년월일 추출 (6자리: YYMMDD 또는 8자리: YYYYMMDD)
        birth_patterns = [
            r'(\d{6})\s*[-–]\s*\d{7}',    # 주민번호 형식: 980723-1234567
            r'(\d{6})\s*[-–]\s*[\d*]{1,7}', # 부분 마스킹
            r'(\d{8})',                       # 8자리 연속
        ]

        for pattern in birth_patterns:
            match = re.search(pattern, ocr_text)
            if match:
                birth = match.group(1)
                if len(birth) == 6:
                    # 6자리 → 8자리 변환
                    year = int(birth[:2])
                    if year > 50:
                        birth = '19' + birth
                    else:
                        birth = '20' + birth
                info['birth'] = birth
                break

        # 이름 추출 (한글 2~4자)
        name_patterns = [
            r'([가-힣]{2,4})\s*\(',         # 이름(한자) 형식
            r'성\s*명\s+([가-힣]{2,4})',     # 성명 뒤
            r'^([가-힣]{2,4})\s',            # 줄 시작
        ]

        for pattern in name_patterns:
            match = re.search(pattern, ocr_text, re.MULTILINE)
            if match:
                info['name'] = match.group(1)
                break

        # 위에서 못 찾으면 한글 이름 패턴으로 재시도
        if not info['name']:
            korean_names = re.findall(r'[가-힣]{2,4}', ocr_text)
            # 일반적인 단어 제외
            exclude = {'주민등록증', '운전면허증', '대한민국', '전라북도', '경기도',
                       '서울특별시', '부산광역시', '경상남도', '경상북도',
                       '충청남도', '충청북도', '전라남도', '전라북도', '강원도',
                       '제주특별', '자치도', '경찰청장', '시장', '구청장',
                       '외국인', '등록증', '거소신고증', '면허번호', '국내거소'}
            for name in korean_names:
                if name not in exclude and len(name) <= 4:
                    info['name'] = name
                    break

        return info

    # ==================== 검증 ====================

    def verify_against_excel(self, ocr_info: dict, excel_data: list) -> dict:
        """
        OCR 결과와 엑셀 데이터를 비교 검증

        Args:
            ocr_info: {'name': str, 'birth': str} (parse_id_info 결과)
            excel_data: [{'name': str, 'birth': str, ...}, ...] (엑셀 데이터)

        Returns:
            dict: {'matched': bool, 'match_index': int, 'details': str}
        """
        ocr_name = ocr_info.get('name', '').strip()
        ocr_birth = ocr_info.get('birth', '').strip()

        for i, row in enumerate(excel_data):
            excel_name = str(row.get('name', '')).strip()
            excel_birth = str(row.get('birth', '')).strip()

            name_match = ocr_name == excel_name
            birth_match = ocr_birth == excel_birth

            if name_match and birth_match:
                return {
                    'matched': True,
                    'match_index': i,
                    'excel_no': row.get('no', i + 1),
                    'details': f'✅ 일치: {excel_name} ({excel_birth})',
                    'name_match': True,
                    'birth_match': True
                }

        # 부분 일치 검색
        partial_matches = []
        for i, row in enumerate(excel_data):
            excel_name = str(row.get('name', '')).strip()
            excel_birth = str(row.get('birth', '')).strip()

            name_match = ocr_name == excel_name if ocr_name else False
            birth_match = ocr_birth == excel_birth if ocr_birth else False

            if name_match or birth_match:
                partial_matches.append({
                    'matched': False,
                    'match_index': i,
                    'excel_no': row.get('no', i + 1),
                    'name_match': name_match,
                    'birth_match': birth_match,
                    'details': (
                        f'⚠️ 부분 일치 (No.{row.get("no", i+1)}): '
                        f'이름 {"✅" if name_match else "❌"} '
                        f'({ocr_name} vs {excel_name}), '
                        f'생년월일 {"✅" if birth_match else "❌"} '
                        f'({ocr_birth} vs {excel_birth})'
                    )
                })

        if partial_matches:
            return partial_matches[0]

        return {
            'matched': False,
            'match_index': -1,
            'excel_no': None,
            'details': f'❌ 불일치: OCR 이름={ocr_name}, 생년월일={ocr_birth}',
            'name_match': False,
            'birth_match': False
        }

    def verify_batch(self, image_paths: list, excel_data: list) -> dict:
        """여러 신분증 일괄 검증"""
        results = []
        match_count = 0
        partial_count = 0
        fail_count = 0

        for img_path in image_paths:
            filename = Path(img_path).name

            # OCR 실행
            ocr_result = self.extract_text(img_path)
            if not ocr_result['success']:
                results.append({
                    'file': filename,
                    'ocr_success': False,
                    'message': ocr_result['message']
                })
                fail_count += 1
                continue

            # 정보 파싱
            info = self.parse_id_info(ocr_result['text'])

            # 엑셀 대조
            verify = self.verify_against_excel(info, excel_data)

            if verify['matched']:
                match_count += 1
            elif verify['match_index'] >= 0:
                partial_count += 1
            else:
                fail_count += 1

            results.append({
                'file': filename,
                'ocr_success': True,
                'ocr_name': info['name'],
                'ocr_birth': info['birth'],
                **verify
            })

        return {
            'total': len(image_paths),
            'matched': match_count,
            'partial': partial_count,
            'failed': fail_count,
            'results': results,
            'message': (f'총 {len(image_paths)}건: '
                       f'✅일치 {match_count}, ⚠️부분일치 {partial_count}, '
                       f'❌불일치 {fail_count}')
        }
