"""
PDF 처리 핸들러
통합 PDF를 이수카드발급대장 + 출석부로 분리
"""

from PyPDF2 import PdfReader, PdfWriter
from pathlib import Path
from datetime import datetime
import re


class PDFHandler:
    def __init__(self):
        pass

    def analyze_pdf(self, pdf_path: str) -> dict:
        """PDF 파일의 페이지 수와 구조 분석"""
        try:
            reader = PdfReader(pdf_path)
            total = len(reader.pages)

            return {
                'success': True,
                'total_pages': total,
                'message': f'{total}페이지 PDF'
            }
        except Exception as e:
            return {'success': False, 'total_pages': 0,
                    'message': f'PDF 읽기 오류: {e}'}

    def split_combined_pdf(self, pdf_path: str, output_dir: str,
                           date_str: str = "", person_count: int = 0,
                           session: str = "오후",
                           card_pages: int = 0,
                           attend_pages: int = 0) -> dict:
        """
        통합 PDF를 이수카드발급대장 + 출석부로 분리.

        Args:
            pdf_path: 통합 PDF 경로
            output_dir: 출력 디렉토리
            date_str: 날짜 문자열 (예: "20260402"). 빈 값이면 파일명에서 추출
            person_count: 인원 수 (0이면 파일명에서 추출 시도)
            session: 시간대 (오전/오후)
            card_pages: 이수카드 페이지 수 (0이면 자동: 총페이지/2)
            attend_pages: 출석부 페이지 수 (0이면 자동: 나머지)

        Returns:
            dict: {'success': bool, 'files': list, 'message': str}
        """
        try:
            reader = PdfReader(pdf_path)
            total = len(reader.pages)

            if total < 2:
                return {'success': False, 'files': [],
                        'message': f'PDF가 {total}페이지로 분리할 수 없습니다.'}

            # 날짜 추출 (파일명에서)
            if not date_str:
                date_str = self._extract_date(pdf_path)

            # 페이지 분배
            if card_pages <= 0 and attend_pages <= 0:
                card_pages = total // 2
                attend_pages = total - card_pages
            elif card_pages <= 0:
                card_pages = total - attend_pages
            elif attend_pages <= 0:
                attend_pages = total - card_pages

            if card_pages + attend_pages > total:
                return {'success': False, 'files': [],
                        'message': f'페이지 수 초과: 이수카드({card_pages}) + '
                                   f'출석부({attend_pages}) > 총({total})'}

            # 출력 디렉토리 생성
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)

            count_str = f"-{person_count}명" if person_count > 0 else ""

            # 이수카드발급대장 PDF
            card_writer = PdfWriter()
            for i in range(card_pages):
                card_writer.add_page(reader.pages[i])

            card_filename = f"{date_str}-이수카드발급대장-{session}{count_str}.pdf"
            card_path = str(out_path / card_filename)
            with open(card_path, 'wb') as f:
                card_writer.write(f)

            # 출석부 PDF
            attend_writer = PdfWriter()
            for i in range(card_pages, card_pages + attend_pages):
                attend_writer.add_page(reader.pages[i])

            attend_filename = f"{date_str}-출석부-{session}{count_str}.pdf"
            attend_path = str(out_path / attend_filename)
            with open(attend_path, 'wb') as f:
                attend_writer.write(f)

            files = [card_path, attend_path]

            return {
                'success': True,
                'files': files,
                'card_file': card_filename,
                'attend_file': attend_filename,
                'card_pages': card_pages,
                'attend_pages': attend_pages,
                'message': (f'분리 완료: {card_filename} ({card_pages}p) + '
                           f'{attend_filename} ({attend_pages}p)')
            }

        except Exception as e:
            return {'success': False, 'files': [],
                    'message': f'PDF 분리 오류: {e}'}

    def _extract_date(self, pdf_path: str) -> str:
        """파일명에서 날짜(YYYYMMDD) 추출"""
        filename = Path(pdf_path).stem
        match = re.search(r'(\d{8})', filename)
        if match:
            return match.group(1)

        match = re.search(r'(\d{6})', filename)
        if match:
            return match.group(1)

        return datetime.now().strftime('%Y%m%d')
