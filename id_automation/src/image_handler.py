"""
이미지 처리 핸들러
Phase 2: 신분증 마스킹
Phase 3: 종합 스캔에서 개별 신분증 분리 저장
"""

import cv2
import numpy as np
from pathlib import Path


class ImageHandler:
    # 한국 신분증 표준 비율 (가로:세로)
    ID_ASPECT_RATIO = 1.58  # 85.6mm x 53.98mm

    # 신분증 종류별 마스킹 영역 (상대 좌표: x%, y%, w%, h%)
    MASK_REGIONS = {
        '주민등록증_구형': {
            'name': '주민등록증(구형)',
            'regions': [
                {'label': '주민번호 뒷자리', 'x': 0.23, 'y': 0.27, 'w': 0.18, 'h': 0.06},
                {'label': '주소+발급', 'x': 0.03, 'y': 0.33, 'w': 0.62, 'h': 0.64},
            ]
        },
        '주민등록증_신형': {
            'name': '주민등록증(신형)',
            'regions': [
                {'label': '주민번호 뒷자리', 'x': 0.23, 'y': 0.27, 'w': 0.18, 'h': 0.06},
                {'label': '주소+발급', 'x': 0.03, 'y': 0.33, 'w': 0.62, 'h': 0.64},
            ]
        },
        '운전면허증': {
            'name': '운전면허증',
            'regions': [
                {'label': '면허번호', 'x': 0.13, 'y': 0.07, 'w': 0.67, 'h': 0.14},
                {'label': '주민번호+주소+발급', 'x': 0.13, 'y': 0.23, 'w': 0.67, 'h': 0.74},
            ]
        },
        '외국인등록증': {
            'name': '외국인등록증/거소신고증',
            'regions': [
                {'label': '등록번호 뒷자리', 'x': 0.35, 'y': 0.12, 'w': 0.25, 'h': 0.10},
                {'label': '주소+발급', 'x': 0.03, 'y': 0.45, 'w': 0.58, 'h': 0.50},
            ]
        },
    }

    def __init__(self):
        pass

    # ==================== Phase 3: 분리 저장 ====================

    def split_scan_image(self, scan_path: str, output_dir: str,
                         prefix: str = "주민", start_num: int = 1,
                         cols: int = 2, total_cards: int = 0) -> dict:
        """
        종합 스캔 이미지에서 개별 신분증을 분리하여 저장.
        그리드 기반 분리 후 각 셀에서 카드 영역을 자동 크롭.

        Args:
            scan_path: 스캔 이미지 경로
            output_dir: 출력 디렉토리
            prefix: 파일명 접두사
            start_num: 시작 번호
            cols: 열 수 (기본: 2)
            total_cards: 총 카드 수 (0이면 자동 감지)
        """
        try:
            img = cv2.imread(scan_path)
            if img is None:
                return {'success': False, 'count': 0, 'files': [],
                        'message': f'이미지를 열 수 없습니다: {scan_path}'}

            h, w = img.shape[:2]

            # 카드 영역만 추출 (상하좌우 여백 제거)
            content_box = self._find_content_area(img)
            cx, cy, cw, ch = content_box

            # 자동 감지: 카드 수 추정
            if total_cards <= 0:
                total_cards = self._estimate_card_count(img, content_box, cols)

            rows = -(-total_cards // cols)  # ceil division
            last_row_cards = total_cards - (rows - 1) * cols

            # 그리드 분할
            cell_w = cw / cols
            cell_h = ch / rows

            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)

            saved_files = []
            card_idx = 0

            for row in range(rows):
                cards_in_row = last_row_cards if row == rows - 1 else cols
                for col in range(cards_in_row):
                    # 셀 영역 계산
                    x1 = int(cx + col * cell_w)
                    y1 = int(cy + row * cell_h)
                    x2 = int(cx + (col + 1) * cell_w)
                    y2 = int(cy + (row + 1) * cell_h)

                    # 경계 보정
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(w, x2)
                    y2 = min(h, y2)

                    cell = img[y1:y2, x1:x2]

                    # 셀 내에서 카드 영역 자동 크롭
                    card_img = self._auto_crop_card(cell)

                    num = start_num + card_idx
                    filename = f"{prefix}-{num}.jpg"
                    filepath = str(out_path / filename)
                    cv2.imwrite(filepath, card_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    saved_files.append(filepath)
                    card_idx += 1

            return {
                'success': True,
                'count': len(saved_files),
                'files': saved_files,
                'message': f'{len(saved_files)}개의 신분증을 분리 저장했습니다.'
            }

        except Exception as e:
            return {'success': False, 'count': 0, 'files': [],
                    'message': f'분리 저장 중 오류: {str(e)}'}

    def _find_content_area(self, img: np.ndarray) -> tuple:
        """이미지에서 콘텐츠가 있는 영역의 바운딩 박스를 찾기"""
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 배경(밝은 부분)과 콘텐츠(어두운 부분) 분리
        # 강한 블러로 디테일 제거
        blurred = cv2.GaussianBlur(gray, (51, 51), 20)
        _, mask = cv2.threshold(blurred, 210, 255, cv2.THRESH_BINARY_INV)

        # 모폴로지로 작은 노이즈 제거
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 50))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        # 콘텐츠 영역 바운딩 박스
        coords = cv2.findNonZero(mask)
        if coords is not None:
            x, y, bw, bh = cv2.boundingRect(coords)
            # 약간의 마진 추가
            margin = 20
            x = max(0, x - margin)
            y = max(0, y - margin)
            bw = min(w - x, bw + 2 * margin)
            bh = min(h - y, bh + 2 * margin)
            return (x, y, bw, bh)

        return (0, 0, w, h)

    def _estimate_card_count(self, img: np.ndarray, content_box: tuple,
                             cols: int) -> int:
        """콘텐츠 영역의 비율로 카드 수 추정"""
        _, _, cw, ch = content_box

        # 카드 1장의 예상 크기 (2열 기준)
        expected_card_w = cw / cols
        expected_card_h = expected_card_w / self.ID_ASPECT_RATIO

        # 예상 행 수
        estimated_rows = round(ch / expected_card_h)
        estimated_rows = max(1, estimated_rows)

        # 마지막 행이 가득 찬지 확인
        # 콘텐츠 높이 vs 예상 높이로 판단
        full_height = estimated_rows * expected_card_h
        remaining = ch - (estimated_rows - 1) * expected_card_h

        if remaining < expected_card_h * 0.7:
            # 마지막 행이 불완전 -> 이전 행까지만
            total = (estimated_rows - 1) * cols
        else:
            total = estimated_rows * cols

        # 최소 1장
        return max(1, total)

    def _auto_crop_card(self, cell: np.ndarray) -> np.ndarray:
        """그리드 셀 내에서 카드 영역만 크롭"""
        h, w = cell.shape[:2]
        gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)

        # 블러 + 이진화로 카드 영역 감지
        blurred = cv2.GaussianBlur(gray, (21, 21), 5)
        _, mask = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY_INV)

        # 모폴로지
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        coords = cv2.findNonZero(mask)
        if coords is not None:
            x, y, bw, bh = cv2.boundingRect(coords)
            # 적절한 마진
            margin = 5
            x = max(0, x - margin)
            y = max(0, y - margin)
            bw = min(w - x, bw + 2 * margin)
            bh = min(h - y, bh + 2 * margin)

            # 너무 작은 크롭 방지 (원본의 50% 이상)
            if bw > w * 0.5 and bh > h * 0.5:
                return cell[y:y+bh, x:x+bw]

        return cell

    # ==================== Phase 2: 마스킹 ====================

    def mask_id_card(self, image_path: str, output_path: str,
                     card_type: str = 'auto',
                     mask_color: tuple = (255, 255, 255)) -> dict:
        """개별 신분증 이미지를 마스킹"""
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {'success': False, 'card_type': '', 'masked_regions': [],
                        'message': f'이미지를 열 수 없습니다: {image_path}'}

            h, w = img.shape[:2]

            if card_type == 'auto':
                card_type = self._detect_card_type(img)

            if card_type not in self.MASK_REGIONS:
                return {'success': False, 'card_type': card_type, 'masked_regions': [],
                        'message': f'지원하지 않는 신분증 종류: {card_type}'}

            regions = self.MASK_REGIONS[card_type]['regions']
            masked_regions = []

            for region in regions:
                rx = int(region['x'] * w)
                ry = int(region['y'] * h)
                rw = int(region['w'] * w)
                rh = int(region['h'] * h)
                cv2.rectangle(img, (rx, ry), (rx + rw, ry + rh), mask_color, -1)
                masked_regions.append(region['label'])

            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(output_path, img, [cv2.IMWRITE_JPEG_QUALITY, 95])

            type_name = self.MASK_REGIONS[card_type]['name']
            return {
                'success': True,
                'card_type': type_name,
                'masked_regions': masked_regions,
                'message': f'{type_name} 마스킹 완료: {", ".join(masked_regions)}'
            }

        except Exception as e:
            return {'success': False, 'card_type': '', 'masked_regions': [],
                    'message': f'마스킹 중 오류: {str(e)}'}

    def mask_batch(self, image_paths: list, output_dir: str,
                   card_type: str = 'auto',
                   mask_color: tuple = (255, 255, 255)) -> dict:
        """여러 신분증을 일괄 마스킹"""
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        results = []
        success_count = 0

        for img_path in image_paths:
            filename = Path(img_path).name
            output_path = str(out_path / filename)
            result = self.mask_id_card(img_path, output_path, card_type, mask_color)
            results.append({'file': filename, **result})
            if result['success']:
                success_count += 1

        return {
            'success': success_count > 0,
            'total': len(image_paths),
            'success_count': success_count,
            'fail_count': len(image_paths) - success_count,
            'results': results,
            'message': f'총 {len(image_paths)}건 중 {success_count}건 마스킹 완료'
        }

    def mask_combined_scan(self, scan_path: str, output_dir: str,
                           prefix: str = "주민", start_num: int = 1,
                           cols: int = 2, total_cards: int = 0,
                           card_type: str = 'auto',
                           mask_color: tuple = (255, 255, 255)) -> dict:
        """종합 스캔 → 분리 → 마스킹 → 저장 (한번에 처리)"""
        try:
            split_result = self.split_scan_image(
                scan_path, output_dir, prefix, start_num, cols, total_cards)
            if not split_result['success']:
                return split_result

            mask_result = self.mask_batch(
                split_result['files'], output_dir, card_type, mask_color)

            return {
                'success': True,
                'split_count': split_result['count'],
                'mask_count': mask_result['success_count'],
                'files': split_result['files'],
                'mask_results': mask_result['results'],
                'message': (f"{split_result['count']}개 분리, "
                           f"{mask_result['success_count']}개 마스킹 완료")
            }
        except Exception as e:
            return {'success': False, 'split_count': 0, 'mask_count': 0,
                    'files': [], 'mask_results': [],
                    'message': f'처리 중 오류: {str(e)}'}

    def _detect_card_type(self, img: np.ndarray) -> str:
        """신분증 종류를 이미지 특성으로 판별 (다중 특성 분석)"""
        h, w = img.shape[:2]
        aspect = w / h if h > 0 else 0

        # 외국인등록증: 앞뒤 양면이 합쳐진 경우 가로가 매우 긴 이미지
        if aspect > 2.5:
            return '외국인등록증'

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 1) 파란색 비율 (전체) - 운전면허증은 파란 배경이 많음
        blue_mask = cv2.inRange(hsv, (85, 15, 80), (140, 255, 255))
        blue_ratio = np.sum(blue_mask > 0) / blue_mask.size

        # 확실한 운전면허증 (2종보통 등 - 파란색 배경이 뚜렷)
        if blue_ratio > 0.40:
            return '운전면허증'

        # 2) 녹색 비율 + 파란색 비율 + 우상단 채도 (1종보통 판별)
        green_mask = cv2.inRange(hsv, (35, 15, 80), (85, 255, 255))
        green_ratio = np.sum(green_mask > 0) / green_mask.size

        tr_region = hsv[:int(h * 0.3), int(w * 0.7):, :]
        tr_sat = np.mean(tr_region[:, :, 1])

        # 1종보통 면허증: 파란+녹색 비율이 높으면서 우상단 채도가 낮음
        if blue_ratio > 0.18 and green_ratio > 0.08 and tr_sat < 30:
            return '운전면허증'

        # 3) 주민등록증 구형/신형 구분
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        top_left = gray[:int(h * 0.25), :int(w * 0.5)]
        _, binary = cv2.threshold(top_left, 100, 255, cv2.THRESH_BINARY_INV)
        text_ratio = np.sum(binary > 0) / binary.size

        if text_ratio > 0.15:
            return '주민등록증_구형'

        return '주민등록증_신형'
