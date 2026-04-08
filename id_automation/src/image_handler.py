"""
이미지 처리 핸들러
Phase 2: 신분증 마스킹
Phase 3: 종합 스캔에서 개별 신분증 분리 저장
추가: 모바일 신분증 추출/삽입, 순번 매칭, 정밀 크롭
"""

import cv2
import numpy as np
from pathlib import Path
from datetime import datetime


def _imread(path: str) -> np.ndarray:
    """한글 경로 지원 이미지 읽기 (Windows 호환)"""
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    return img


def _imwrite(path: str, img: np.ndarray,
             params=None) -> bool:
    """한글 경로 지원 이미지 저장 (Windows 호환)"""
    if params is None:
        params = [cv2.IMWRITE_JPEG_QUALITY, 95]
    ext = Path(path).suffix.lower()
    result, encoded = cv2.imencode(ext, img, params)
    if result:
        encoded.tofile(path)
    return result


class ImageHandler:
    # 한국 신분증 표준 비율 (가로:세로)
    ID_ASPECT_RATIO = 1.58  # 85.6mm x 53.98mm

    # 신분증 종류별 마스킹 영역 (상대 좌표: x%, y%, w%, h%)
    # 방침: 이름+사진만 남기고 나머지(번호/주소/발급)는 전부 마스킹
    # 주민등록증: 타이틀 y0~13%, 이름 y13~24%, 번호 y24~32%, 주소+발급 y32~100%
    # 운전면허증: 종별 y0~5%, 면허번호 y5~18%, 이름 y18~26%, 나머지 y26~100%
    MASK_REGIONS = {
        '주민등록증': {
            'name': '주민등록증',
            'regions': [
                # 이름(~24%) 아래 전부 마스킹
                {'label': '번호+주소+발급', 'x': 0.02, 'y': 0.30, 'w': 0.63, 'h': 0.68},
            ]
        },
        '운전면허증': {
            'name': '운전면허증',
            'regions': [
                # 면허번호 마스킹 (이름 위)
                {'label': '면허번호', 'x': 0.11, 'y': 0.04, 'w': 0.72, 'h': 0.15},
                # 이름(~26%) 아래 전부 마스킹
                {'label': '번호+주소+발급', 'x': 0.11, 'y': 0.26, 'w': 0.72, 'h': 0.72},
            ]
        },
        '외국인등록증': {
            'name': '외국인등록증/거소신고증',
            'regions': [
                # 이름 아래 전부
                {'label': '번호+주소+발급', 'x': 0.02, 'y': 0.28, 'w': 0.58, 'h': 0.70},
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
            img = _imread(scan_path)
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
                    _imwrite(filepath, card_img)
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
        """
        그리드 셀 내에서 카드 영역만 정밀 크롭.
        카드가 약간 흐트러져 있어도 정확히 잘라냄.
        """
        h, w = cell.shape[:2]
        gray = cv2.cvtColor(cell, cv2.COLOR_BGR2GRAY)

        # 1단계: 강한 블러로 카드 내부 디테일 제거
        heavy_blur = cv2.GaussianBlur(gray, (31, 31), 10)

        # 2단계: 다중 threshold로 카드 영역 감지
        # 배경(흰색)과 카드(상대적으로 어두움) 분리
        _, mask_high = cv2.threshold(heavy_blur, 210, 255, cv2.THRESH_BINARY_INV)
        _, mask_low = cv2.threshold(heavy_blur, 180, 255, cv2.THRESH_BINARY_INV)

        # 두 마스크를 합침 (더 넓은 영역 감지)
        mask = cv2.bitwise_or(mask_high, mask_low)

        # 3단계: 모폴로지 - 카드 내부 빈 공간 채우기
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 40))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)

        # 작은 노이즈 제거
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open)

        # 4단계: 가장 큰 연결 영역 = 카드
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            # 면적이 가장 큰 컨투어 선택
            largest = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(largest)

            # 셀 면적의 20% 이상이어야 유효한 카드
            if area > (w * h) * 0.20:
                # 회전된 카드 처리: minAreaRect로 기울기 감지
                rect = cv2.minAreaRect(largest)
                angle = rect[2]
                rect_w, rect_h = rect[1]

                # 기울기가 작으면 (5도 이내) 단순 바운딩 박스 사용
                if abs(angle) < 5 or abs(angle - 90) < 5 or abs(angle + 90) < 5:
                    x, y, bw, bh = cv2.boundingRect(largest)
                    margin = 3
                    x = max(0, x - margin)
                    y = max(0, y - margin)
                    bw = min(w - x, bw + 2 * margin)
                    bh = min(h - y, bh + 2 * margin)

                    if bw > w * 0.4 and bh > h * 0.4:
                        return cell[y:y+bh, x:x+bw]
                else:
                    # 기울어진 카드: 원근 보정
                    corrected = self._correct_perspective(cell, largest)
                    if corrected is not None:
                        return corrected

        # 폴백: 기본 threshold 방식
        blurred = cv2.GaussianBlur(gray, (21, 21), 5)
        _, simple_mask = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
        simple_mask = cv2.morphologyEx(simple_mask, cv2.MORPH_CLOSE, kernel)

        coords = cv2.findNonZero(simple_mask)
        if coords is not None:
            x, y, bw, bh = cv2.boundingRect(coords)
            margin = 3
            x = max(0, x - margin)
            y = max(0, y - margin)
            bw = min(w - x, bw + 2 * margin)
            bh = min(h - y, bh + 2 * margin)
            if bw > w * 0.4 and bh > h * 0.4:
                return cell[y:y+bh, x:x+bw]

        return cell

    def _correct_perspective(self, img: np.ndarray,
                             contour: np.ndarray) -> np.ndarray:
        """기울어진 카드를 원근 보정하여 반듯하게 만듦"""
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        if len(approx) == 4:
            pts = approx.reshape(4, 2).astype(np.float32)
        else:
            # 4꼭짓점이 아니면 minAreaRect의 꼭짓점 사용
            rect = cv2.minAreaRect(contour)
            pts = cv2.boxPoints(rect).astype(np.float32)

        # 꼭짓점 정렬: 좌상, 우상, 우하, 좌하
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).flatten()
        ordered = np.array([
            pts[np.argmin(s)],   # 좌상
            pts[np.argmin(d)],   # 우상
            pts[np.argmax(s)],   # 우하
            pts[np.argmax(d)],   # 좌하
        ], dtype=np.float32)

        # 출력 크기 계산
        w1 = np.linalg.norm(ordered[1] - ordered[0])
        w2 = np.linalg.norm(ordered[2] - ordered[3])
        h1 = np.linalg.norm(ordered[3] - ordered[0])
        h2 = np.linalg.norm(ordered[2] - ordered[1])

        out_w = int(max(w1, w2))
        out_h = int(max(h1, h2))

        if out_w < 50 or out_h < 50:
            return None

        # 가로가 세로보다 짧으면 90도 회전된 것
        if out_w < out_h:
            out_w, out_h = out_h, out_w
            ordered = np.roll(ordered, -1, axis=0)

        dst = np.array([
            [0, 0], [out_w, 0],
            [out_w, out_h], [0, out_h]
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(ordered, dst)
        return cv2.warpPerspective(img, M, (out_w, out_h))

    # ==================== Phase 2: 마스킹 ====================

    def mask_id_card(self, image_path: str, output_path: str,
                     card_type: str = 'auto',
                     mask_color: tuple = (255, 255, 255)) -> dict:
        """개별 신분증 이미지를 마스킹"""
        try:
            img = _imread(image_path)
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
            _imwrite(output_path, img)

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

        # 3) 기본: 주민등록증
        return '주민등록증'

    # ==================== 모바일 신분증 추출/삽입 ====================

    def extract_card_from_photo(self, photo_path: str,
                                output_path: str = None) -> dict:
        """
        사진(핸드폰 촬영)에서 신분증 카드 영역을 추출.
        배경을 제거하고 카드만 반듯하게 크롭.

        Args:
            photo_path: 촬영한 사진 경로
            output_path: 저장 경로 (None이면 저장 안 함)

        Returns:
            dict: {'success': bool, 'image': np.ndarray, 'message': str}
        """
        try:
            img = _imread(photo_path)
            if img is None:
                return {'success': False, 'image': None,
                        'message': f'이미지를 열 수 없습니다: {photo_path}'}

            card = self._detect_card_in_photo(img)
            if card is None:
                return {'success': False, 'image': None,
                        'message': '사진에서 신분증을 찾을 수 없습니다.'}

            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                _imwrite(output_path, card)

            return {
                'success': True,
                'image': card,
                'size': (card.shape[1], card.shape[0]),
                'message': f'신분증 추출 완료 ({card.shape[1]}x{card.shape[0]})'
            }

        except Exception as e:
            return {'success': False, 'image': None,
                    'message': f'추출 중 오류: {str(e)}'}

    def _detect_card_in_photo(self, img: np.ndarray) -> np.ndarray:
        """사진에서 가장 큰 사각형(카드)을 찾아 원근 보정"""
        h, w = img.shape[:2]

        # 축소하여 처리 (성능)
        max_dim = 1500
        scale = min(max_dim / w, max_dim / h, 1.0)
        if scale < 1.0:
            small = cv2.resize(img, None, fx=scale, fy=scale)
        else:
            small = img.copy()

        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)

        # 여러 방법으로 카드 에지 검출 시도
        card_contour = None

        # 방법 1: Canny 에지
        for canny_low, canny_high in [(30, 100), (20, 80), (50, 150)]:
            edges = cv2.Canny(blurred, canny_low, canny_high)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            edges = cv2.dilate(edges, kernel, iterations=2)

            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)

            # 면적 기준 정렬
            contours = sorted(contours, key=cv2.contourArea, reverse=True)

            for cnt in contours[:10]:
                area = cv2.contourArea(cnt)
                if area < (small.shape[0] * small.shape[1]) * 0.05:
                    continue

                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)

                if len(approx) == 4:
                    card_contour = approx
                    break

            if card_contour is not None:
                break

        # 방법 2: 적응형 threshold
        if card_contour is None:
            thresh = cv2.adaptiveThreshold(blurred, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 3)
            thresh = cv2.bitwise_not(thresh)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
            contours = sorted(contours, key=cv2.contourArea, reverse=True)

            for cnt in contours[:10]:
                area = cv2.contourArea(cnt)
                if area < (small.shape[0] * small.shape[1]) * 0.05:
                    continue
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
                if len(approx) == 4:
                    card_contour = approx
                    break

        if card_contour is None:
            # 폴백: 가장 큰 컨투어의 minAreaRect
            if contours:
                largest = max(contours, key=cv2.contourArea)
                if cv2.contourArea(largest) > (small.shape[0] * small.shape[1]) * 0.05:
                    rect = cv2.minAreaRect(largest)
                    card_contour = cv2.boxPoints(rect).astype(np.int32)

        if card_contour is None:
            return None

        # 원본 스케일로 좌표 변환
        pts = card_contour.reshape(-1, 2).astype(np.float32) / scale

        # 꼭짓점 정렬
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1).flatten()
        ordered = np.array([
            pts[np.argmin(s)],
            pts[np.argmin(d)],
            pts[np.argmax(s)],
            pts[np.argmax(d)],
        ], dtype=np.float32)

        # 출력 크기
        w1 = np.linalg.norm(ordered[1] - ordered[0])
        w2 = np.linalg.norm(ordered[2] - ordered[3])
        h1 = np.linalg.norm(ordered[3] - ordered[0])
        h2 = np.linalg.norm(ordered[2] - ordered[1])
        out_w = int(max(w1, w2))
        out_h = int(max(h1, h2))

        if out_w < 100 or out_h < 100:
            return None

        # 세로가 더 길면 90도 회전
        if out_w < out_h:
            out_w, out_h = out_h, out_w
            ordered = np.roll(ordered, -1, axis=0)

        dst = np.array([
            [0, 0], [out_w, 0],
            [out_w, out_h], [0, out_h]
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(ordered, dst)
        return cv2.warpPerspective(img, M, (out_w, out_h))

    def insert_card_into_scan(self, scan_path: str, card_img: np.ndarray,
                               position: int, cols: int = 2,
                               total_cards: int = 0,
                               output_path: str = None) -> dict:
        """
        추출한 카드를 종합 스캔 이미지의 지정 위치에 삽입.

        Args:
            scan_path: 기존 종합 스캔 이미지 경로
            card_img: 삽입할 카드 이미지 (numpy array)
            position: 삽입 위치 (1-based, 좌→우, 위→아래 순서)
            cols: 열 수
            total_cards: 총 카드 수
            output_path: 저장 경로 (None이면 원본 덮어쓰기)

        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            scan = _imread(scan_path)
            if scan is None:
                return {'success': False,
                        'message': f'스캔 이미지를 열 수 없습니다: {scan_path}'}

            h, w = scan.shape[:2]
            content_box = self._find_content_area(scan)
            cx, cy, cw, ch = content_box

            if total_cards <= 0:
                total_cards = self._estimate_card_count(scan, content_box, cols)

            rows = -(-total_cards // cols)
            cell_w = cw / cols
            cell_h = ch / rows

            # position (1-based) → row, col
            pos_idx = position - 1
            row = pos_idx // cols
            col = pos_idx % cols

            x1 = int(cx + col * cell_w)
            y1 = int(cy + row * cell_h)
            target_w = int(cell_w)
            target_h = int(cell_h)

            # 카드를 셀 크기에 맞게 리사이즈 (여백 포함)
            card_h, card_w = card_img.shape[:2]
            scale = min((target_w - 20) / card_w, (target_h - 20) / card_h)
            new_w = int(card_w * scale)
            new_h = int(card_h * scale)
            resized = cv2.resize(card_img, (new_w, new_h),
                                interpolation=cv2.INTER_AREA)

            # 셀 중앙에 배치
            pad_x = (target_w - new_w) // 2
            pad_y = (target_h - new_h) // 2

            # 기존 셀 영역을 흰색으로 초기화 후 카드 삽입
            scan[y1:y1+target_h, x1:x1+target_w] = 255
            insert_y = y1 + pad_y
            insert_x = x1 + pad_x
            scan[insert_y:insert_y+new_h, insert_x:insert_x+new_w] = resized

            save_path = output_path or scan_path
            _imwrite(save_path, scan)

            return {
                'success': True,
                'saved_path': save_path,
                'message': f'{position}번 위치에 카드 삽입 완료'
            }

        except Exception as e:
            return {'success': False, 'message': f'삽입 중 오류: {str(e)}'}

    def create_scan_with_mobile(self, scan_path: str, photo_paths: list,
                                 positions: list, cols: int = 2,
                                 total_cards: int = 0,
                                 output_path: str = None) -> dict:
        """
        여러 모바일 사진을 종합 스캔에 일괄 삽입.

        Args:
            scan_path: 기존 스캔 이미지 경로
            photo_paths: 모바일 사진 경로 리스트
            positions: 각 사진의 삽입 위치 리스트 (1-based)
            cols, total_cards: 그리드 설정
            output_path: 저장 경로
        """
        try:
            results = []
            current_scan = scan_path
            save = output_path or scan_path

            for photo_path, pos in zip(photo_paths, positions):
                # 1. 사진에서 카드 추출
                extract = self.extract_card_from_photo(photo_path)
                if not extract['success']:
                    results.append({'file': Path(photo_path).name,
                                   'position': pos, **extract})
                    continue

                # 2. 스캔에 삽입
                insert = self.insert_card_into_scan(
                    current_scan, extract['image'], pos,
                    cols, total_cards, save)

                current_scan = save  # 이후 삽입은 업데이트된 파일에
                results.append({'file': Path(photo_path).name,
                               'position': pos, **insert})

            success = sum(1 for r in results if r.get('success'))
            return {
                'success': success > 0,
                'total': len(photo_paths),
                'success_count': success,
                'results': results,
                'message': f'{len(photo_paths)}건 중 {success}건 삽입 완료'
            }

        except Exception as e:
            return {'success': False, 'total': 0, 'success_count': 0,
                    'results': [], 'message': f'처리 중 오류: {str(e)}'}

    # ==================== 순번 매칭 저장 ====================

    def split_with_name_order(self, scan_path: str, output_dir: str,
                               name_list: list, prefix: str = "주민",
                               cols: int = 2, total_cards: int = 0) -> dict:
        """
        종합 스캔을 분리할 때, 엑셀 종합양식의 순번(이름 순서)에 맞춰 저장.
        스캔 순서(좌→우, 위→아래)가 엑셀 순서와 동일하다고 가정.

        Args:
            scan_path: 스캔 이미지 경로
            output_dir: 출력 디렉토리
            name_list: [{'no': 1, 'name': '임지혁'}, ...] 엑셀 순서
            prefix: 파일명 접두사
            cols: 열 수
            total_cards: 총 카드 수 (0이면 name_list 길이 사용)
        """
        try:
            if total_cards <= 0:
                total_cards = len(name_list)

            # 분리 실행
            split_result = self.split_scan_image(
                scan_path, output_dir, prefix, 1, cols, total_cards)

            if not split_result['success']:
                return split_result

            # 파일명을 엑셀 순번에 맞게 변경
            out_path = Path(output_dir)
            renamed_files = []
            mapping = []

            for i, filepath in enumerate(split_result['files']):
                if i < len(name_list):
                    entry = name_list[i]
                    no = entry.get('no', i + 1)
                    name = entry.get('name', '')
                    new_filename = f"{prefix}-{no}.jpg"
                else:
                    no = i + 1
                    name = ''
                    new_filename = f"{prefix}-{no}.jpg"

                old_path = Path(filepath)
                new_path = out_path / new_filename

                # 파일명이 같으면 건너뜀
                if old_path != new_path:
                    # 임시 이름으로 먼저 변경 (충돌 방지)
                    tmp_path = out_path / f"_tmp_{no}_{old_path.name}"
                    old_path.rename(tmp_path)
                    renamed_files.append((tmp_path, new_path))
                else:
                    renamed_files.append((old_path, new_path))

                mapping.append({
                    'no': no,
                    'name': name,
                    'file': new_filename,
                    'scan_position': i + 1
                })

            # 임시 파일을 최종 이름으로 변경
            final_files = []
            for tmp, final in renamed_files:
                if tmp != final:
                    if final.exists():
                        final.unlink()
                    tmp.rename(final)
                final_files.append(str(final))

            return {
                'success': True,
                'count': len(final_files),
                'files': final_files,
                'mapping': mapping,
                'message': f'{len(final_files)}개 신분증을 순번에 맞춰 저장했습니다.'
            }

        except Exception as e:
            return {'success': False, 'count': 0, 'files': [],
                    'mapping': [], 'message': f'순번 저장 중 오류: {str(e)}'}
