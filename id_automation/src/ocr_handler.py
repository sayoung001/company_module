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

            # http → https 자동 변환 (Clova API는 HTTPS 필수)
            api_url = self.api_url
            if api_url.startswith('http://'):
                api_url = api_url.replace('http://', 'https://', 1)

            response = requests.post(
                api_url,
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

    def get_mask_regions(self, image_path: str) -> dict:
        """
        OCR로 텍스트 위치를 감지하여 마스킹할 영역 좌표를 반환.
        주민번호 뒷자리, 주소, 발급일/기관, 면허번호 등을 정밀 감지.

        Returns:
            dict: {
                'success': bool,
                'regions': [{'label': str, 'points': [(x,y),...]}],
                'name': str,  # 감지된 이름
                'card_type': str
            }
        """
        ocr_result = self.extract_text(image_path)
        if not ocr_result['success']:
            return {'success': False, 'regions': [],
                    'message': ocr_result['message']}

        fields = ocr_result['fields']
        if not fields:
            return {'success': False, 'regions': [],
                    'message': '텍스트를 인식하지 못했습니다.'}

        mask_regions = []
        detected_name = ''
        card_type = '주민등록증'

        # 모든 필드를 순회하며 민감 정보 식별
        skip_indices = set()  # 이름 필드 인덱스 (마스킹 제외)

        # 1단계: 카드 종류 판별 + 이름 찾기
        for i, field in enumerate(fields):
            text = field['text'].strip()
            if '면허' in text or 'License' in text or 'Driver' in text:
                card_type = '운전면허증'
            if '외국' in text or '거소' in text or 'RESIDENT' in text:
                card_type = '외국인등록증'

        # 이름 찾기: "이름(한자)" 패턴 또는 이름 단독
        for i, field in enumerate(fields):
            text = field['text'].strip()
            name_match = re.match(r'^([가-힣]{2,4})\s*[\(（]', text)
            if name_match:
                detected_name = name_match.group(1)
                skip_indices.add(i)
                break

        if not detected_name:
            for i, field in enumerate(fields):
                text = field['text'].strip()
                if re.match(r'^[가-힣]{2,4}$', text):
                    # 일반적인 단어 제외
                    exclude = {'주민등록증', '운전면허증', '전라북도', '경기도',
                               '충청남도', '경상북도', '경상남도', '강원도',
                               '서울특별시', '부산광역시', '대구광역시',
                               '종보통', '종소형', '종대형'}
                    if text not in exclude:
                        detected_name = text
                        skip_indices.add(i)
                        break

        # 2단계: 마스킹 대상 식별
        for i, field in enumerate(fields):
            if i in skip_indices:
                continue

            text = field['text'].strip()
            bbox = self._get_bbox(field)
            if not bbox:
                continue

            should_mask = False
            label = ''

            # 주민번호 (XXXXXX-XXXXXXX)
            if re.search(r'\d{6}\s*[-–]\s*\d{7}', text):
                # 전체 번호 마스킹 (뒷자리뿐 아니라 연결된 필드)
                should_mask = True
                label = '주민번호'

            # 숫자 6자리-숫자 7자리가 분리되어 있을 수 있음
            elif re.match(r'^\d{7}$', text):
                # 주민번호 뒷자리 단독
                should_mask = True
                label = '주민번호 뒷자리'

            # 면허번호 (XX-XX-XXXXXX-XX)
            elif re.search(r'\d{2}-\d{2}-\d{6}-\d{2}', text):
                should_mask = True
                label = '면허번호'

            # 주소 키워드
            elif re.search(r'(도\s|시\s|군\s|구\s|동\s|읍\s|면\s|리\s|로\s|길\s|호\s|'
                           r'아파트|빌라|오피스텔|층|동$|번지|번$)', text):
                should_mask = True
                label = '주소'

            # 발급 관련
            elif re.search(r'(발급|경찰|시장|구청|청장|도지사|군수)', text):
                should_mask = True
                label = '발급기관'

            # 날짜 패턴 (발급일 등) - 이름 아래쪽에 있는 날짜
            elif re.search(r'\d{4}\.\s*\d{1,2}\.\s*\d{1,2}', text):
                should_mask = True
                label = '날짜'

            # 적성검사, 기간 등
            elif re.search(r'(적성검사|기\s*간|갱신기간)', text):
                should_mask = True
                label = '발급정보'

            # 코드류 (6FVFET, N8UUR6 등)
            elif re.match(r'^[A-Z0-9]{5,}$', text):
                should_mask = True
                label = '코드'

            # 전화번호
            elif re.search(r'0\d{2}[-\s]?\d{3,4}[-\s]?\d{4}', text):
                should_mask = True
                label = '전화번호'

            if should_mask:
                mask_regions.append({
                    'label': label,
                    'text': text,
                    'bbox': bbox
                })

        # "주민등록증", "1종보통" 등 타이틀은 마스킹하지 않음
        return {
            'success': True,
            'regions': mask_regions,
            'name': detected_name,
            'card_type': card_type,
            'total_fields': len(fields),
            'masked_fields': len(mask_regions),
            'message': (f'{card_type} / 이름: {detected_name} / '
                       f'{len(mask_regions)}개 영역 마스킹')
        }

    def _get_bbox(self, field: dict) -> list:
        """OCR 필드에서 바운딩 박스 좌표 추출 [(x,y), ...]"""
        bp = field.get('bounding', {})
        if not bp:
            return None
        vertices = bp.get('vertices', [])
        if not vertices or len(vertices) < 4:
            return None
        return [(int(v.get('x', 0)), int(v.get('y', 0))) for v in vertices]

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
