"""
신분증 자동화 프로그램 v2.0
Phase 1: 엑셀 자동 복사
Phase 2: 신분증 마스킹
Phase 3: 개별 분리 저장
Phase 4: OCR 검증
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import re
import glob
import shutil
import threading
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageTk

from excel_handler import ExcelHandler
from image_handler import ImageHandler
from ocr_handler import OCRHandler

# 테마 설정
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class IDAutomationApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # 윈도우 설정
        self.title("신분증 자동화 프로그램 v2.0")
        self.geometry("900x700")
        self.minsize(800, 600)

        # 파일 경로 저장
        self.source_file = None   # 종합양식
        self.target_file = None   # 출석부양식
        self.scan_files = []      # 스캔 이미지들
        self.id_files = []        # 개별 신분증 이미지들
        self.verify_images = []
        self.verify_excel = None
        self.split_excel_path = None
        self.mobile_photos = []

        # 핸들러
        self.excel_handler = ExcelHandler()
        self.image_handler = ImageHandler()
        self.ocr_handler = OCRHandler()

        # UI 구성
        self.create_widgets()

    def create_widgets(self):
        # 메인 프레임
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # 제목
        title_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        title_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            title_frame,
            text="신분증 자동화 프로그램",
            font=ctk.CTkFont(size=22, weight="bold")
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            title_frame,
            text="v2.0",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        ).pack(side="left")

        # 탭 뷰
        self.tabview = ctk.CTkTabview(self.main_frame)
        self.tabview.pack(fill="both", expand=True)

        self.tab_excel = self.tabview.add("1. 엑셀 복사")
        self.tab_masking = self.tabview.add("2. 마스킹")
        self.tab_split = self.tabview.add("3. 분리저장")
        self.tab_verify = self.tabview.add("4. 검증")

        self.setup_excel_tab()
        self.setup_masking_tab()
        self.setup_split_tab()
        self.setup_verify_tab()

        # 상태바
        self.status_var = ctk.StringVar(value="준비됨")
        status_bar = ctk.CTkLabel(
            self.main_frame,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        status_bar.pack(fill="x", side="bottom", pady=(5, 0), padx=5)

    # ==================== 1. 엑셀 복사 탭 ====================
    def setup_excel_tab(self):
        frame = ctk.CTkFrame(self.tab_excel, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            frame,
            text="종합양식의 데이터를 출석부양식으로 자동 복사합니다.",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(0, 15))

        # 종합양식 파일 선택
        src_frame = ctk.CTkFrame(frame)
        src_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(src_frame, text="종합양식:", width=90, anchor="e").pack(side="left", padx=5)
        self.source_entry = ctk.CTkEntry(src_frame, width=450, state="readonly")
        self.source_entry.pack(side="left", padx=5)
        ctk.CTkButton(src_frame, text="찾아보기", width=90,
                       command=self.select_source_file).pack(side="left", padx=5)

        # 출석부양식 파일 선택
        tgt_frame = ctk.CTkFrame(frame)
        tgt_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(tgt_frame, text="출석부양식:", width=90, anchor="e").pack(side="left", padx=5)
        self.target_entry = ctk.CTkEntry(tgt_frame, width=450, state="readonly")
        self.target_entry.pack(side="left", padx=5)
        ctk.CTkButton(tgt_frame, text="찾아보기", width=90,
                       command=self.select_target_file).pack(side="left", padx=5)

        # 미리보기
        ctk.CTkLabel(frame, text="데이터 미리보기:", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", pady=(15, 3))
        self.preview_text = ctk.CTkTextbox(frame, height=250)
        self.preview_text.pack(fill="both", expand=True)

        # 버튼
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(btn_frame, text="미리보기", width=140,
                       command=self.preview_data).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="복사 실행", width=140,
                       fg_color="#2e7d32", hover_color="#1b5e20",
                       command=self.copy_excel_data).pack(side="left", padx=5)

    def select_source_file(self):
        path = filedialog.askopenfilename(
            title="종합양식 파일 선택",
            filetypes=[("Excel", "*.xlsx *.xls")])
        if path:
            self.source_file = path
            self._set_entry(self.source_entry, os.path.basename(path))
            self.status_var.set(f"종합양식: {os.path.basename(path)}")

    def select_target_file(self):
        path = filedialog.askopenfilename(
            title="출석부양식 파일 선택",
            filetypes=[("Excel", "*.xlsx *.xls")])
        if path:
            self.target_file = path
            self._set_entry(self.target_entry, os.path.basename(path))
            self.status_var.set(f"출석부양식: {os.path.basename(path)}")

    def preview_data(self):
        if not self.source_file:
            messagebox.showwarning("경고", "종합양식 파일을 먼저 선택하세요.")
            return
        try:
            data = self.excel_handler.read_source_data(self.source_file)
            self.preview_text.delete("1.0", "end")
            self.preview_text.insert("1.0", f"총 {len(data)}명의 데이터\n")
            self.preview_text.insert("end", "=" * 65 + "\n")
            self.preview_text.insert("end",
                f"{'No.':<5} {'성명':<10} {'생년월일':<12} {'전화번호':<15} {'취약구분':<10}\n")
            self.preview_text.insert("end", "-" * 65 + "\n")
            for row in data:
                self.preview_text.insert("end",
                    f"{str(row.get('no','')):<5} "
                    f"{str(row.get('name','')):<10} "
                    f"{str(row.get('birth','')):<12} "
                    f"{str(row.get('phone','')):<15} "
                    f"{str(row.get('vulnerable','')):<10}\n")
            self.status_var.set(f"미리보기 완료: {len(data)}명")
        except Exception as e:
            messagebox.showerror("오류", f"파일 읽기 오류: {str(e)}")

    def copy_excel_data(self):
        if not self.source_file:
            messagebox.showwarning("경고", "종합양식 파일을 먼저 선택하세요.")
            return
        if not self.target_file:
            messagebox.showwarning("경고", "출석부양식 파일을 먼저 선택하세요.")
            return
        try:
            result = self.excel_handler.copy_to_attendance(
                self.source_file, self.target_file)
            if result['success']:
                messagebox.showinfo("완료",
                    f"복사 완료!\n\n"
                    f"복사된 인원: {result['count']}명\n"
                    f"저장 위치: {result['saved_path']}")
                self.status_var.set(f"복사 완료: {result['count']}명")
            else:
                messagebox.showerror("오류", result['message'])
        except Exception as e:
            messagebox.showerror("오류", f"복사 중 오류: {str(e)}")

    # ==================== 2. 마스킹 탭 ====================
    def setup_masking_tab(self):
        frame = ctk.CTkFrame(self.tab_masking, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            frame,
            text="신분증 이미지의 주민번호 뒷자리, 주소, 발급정보를 마스킹합니다.",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(0, 10))

        # 파일 선택
        file_frame = ctk.CTkFrame(frame)
        file_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(file_frame, text="신분증 이미지:", width=100, anchor="e").pack(side="left", padx=5)
        self.mask_entry = ctk.CTkEntry(file_frame, width=400, state="readonly")
        self.mask_entry.pack(side="left", padx=5)
        ctk.CTkButton(file_frame, text="파일 선택", width=90,
                       command=self.select_mask_files).pack(side="left", padx=5)

        # 옵션
        opt_frame = ctk.CTkFrame(frame)
        opt_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(opt_frame, text="신분증 종류:", width=100, anchor="e").pack(side="left", padx=5)
        self.card_type_var = ctk.StringVar(value="auto (자동감지)")
        card_type_menu = ctk.CTkOptionMenu(
            opt_frame, variable=self.card_type_var, width=200,
            values=["auto (자동감지)", "주민등록증_구형", "주민등록증_신형",
                    "운전면허증", "외국인등록증"])
        card_type_menu.pack(side="left", padx=5)

        ctk.CTkLabel(opt_frame, text="출력 폴더:", width=80, anchor="e").pack(side="left", padx=5)
        self.mask_out_entry = ctk.CTkEntry(opt_frame, width=200)
        self.mask_out_entry.pack(side="left", padx=5)
        self.mask_out_entry.insert(0, "output/마스킹")
        ctk.CTkButton(opt_frame, text="변경", width=60,
                       command=self.select_mask_output_dir).pack(side="left", padx=5)

        # 결과 로그
        ctk.CTkLabel(frame, text="처리 결과:", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", pady=(10, 3))
        self.mask_log = ctk.CTkTextbox(frame, height=250)
        self.mask_log.pack(fill="both", expand=True)

        # 버튼
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(btn_frame, text="마스킹 실행", width=140,
                       fg_color="#2e7d32", hover_color="#1b5e20",
                       command=self.run_masking).pack(side="left", padx=5)

    def select_mask_files(self):
        paths = filedialog.askopenfilenames(
            title="마스킹할 신분증 이미지 선택",
            filetypes=[("Image", "*.jpg *.jpeg *.png *.bmp")])
        if paths:
            self.id_files = list(paths)
            if len(paths) == 1:
                self._set_entry(self.mask_entry, os.path.basename(paths[0]))
            else:
                self._set_entry(self.mask_entry, f"{len(paths)}개 파일 선택됨")
            self.status_var.set(f"마스킹 대상: {len(paths)}개 파일")

    def select_mask_output_dir(self):
        path = filedialog.askdirectory(title="마스킹 출력 폴더 선택")
        if path:
            self.mask_out_entry.delete(0, "end")
            self.mask_out_entry.insert(0, path)

    def run_masking(self):
        if not self.id_files:
            messagebox.showwarning("경고", "마스킹할 이미지를 선택하세요.")
            return

        card_type = self.card_type_var.get()
        if card_type.startswith("auto"):
            card_type = "auto"

        output_dir = self.mask_out_entry.get()
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(os.path.dirname(self.id_files[0]), output_dir)

        self.mask_log.delete("1.0", "end")
        self.mask_log.insert("1.0", f"마스킹 시작... ({len(self.id_files)}개 파일)\n\n")
        self.status_var.set("마스킹 처리 중...")

        def do_mask():
            result = self.image_handler.mask_batch(
                self.id_files, output_dir, card_type)
            self.after(0, lambda: self._show_mask_result(result))

        threading.Thread(target=do_mask, daemon=True).start()

    def _show_mask_result(self, result):
        self.mask_log.delete("1.0", "end")
        self.mask_log.insert("1.0", f"{result['message']}\n")
        self.mask_log.insert("end", "=" * 60 + "\n\n")

        for r in result.get('results', []):
            status = "OK" if r['success'] else "FAIL"
            self.mask_log.insert("end",
                f"[{status}] {r['file']}\n"
                f"    종류: {r.get('card_type', '?')}\n"
                f"    마스킹: {', '.join(r.get('masked_regions', []))}\n\n")

        self.status_var.set(result['message'])
        messagebox.showinfo("완료", result['message'])

    # ==================== 3. 분리저장 탭 ====================
    def setup_split_tab(self):
        frame = ctk.CTkFrame(self.tab_split, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            frame,
            text="종합 스캔 이미지에서 개별 신분증을 분리하여 저장합니다.",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(0, 10))

        # 스캔 파일 선택
        scan_frame = ctk.CTkFrame(frame)
        scan_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(scan_frame, text="스캔 이미지:", width=100, anchor="e").pack(side="left", padx=5)
        self.scan_entry = ctk.CTkEntry(scan_frame, width=400, state="readonly")
        self.scan_entry.pack(side="left", padx=5)
        ctk.CTkButton(scan_frame, text="파일 선택", width=90,
                       command=self.select_scan_file).pack(side="left", padx=5)

        # 옵션
        opt_frame = ctk.CTkFrame(frame)
        opt_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(opt_frame, text="파일명 접두사:", width=100, anchor="e").pack(side="left", padx=5)
        self.prefix_entry = ctk.CTkEntry(opt_frame, width=80)
        self.prefix_entry.pack(side="left", padx=5)
        self.prefix_entry.insert(0, "주민")

        ctk.CTkLabel(opt_frame, text="시작 번호:", width=70, anchor="e").pack(side="left", padx=5)
        self.start_num_entry = ctk.CTkEntry(opt_frame, width=40)
        self.start_num_entry.pack(side="left", padx=5)
        self.start_num_entry.insert(0, "1")

        ctk.CTkLabel(opt_frame, text="열 수:", width=50, anchor="e").pack(side="left", padx=5)
        self.cols_entry = ctk.CTkEntry(opt_frame, width=40)
        self.cols_entry.pack(side="left", padx=5)
        self.cols_entry.insert(0, "2")

        ctk.CTkLabel(opt_frame, text="총 인원:", width=60, anchor="e").pack(side="left", padx=5)
        self.total_entry = ctk.CTkEntry(opt_frame, width=40)
        self.total_entry.pack(side="left", padx=5)
        self.total_entry.insert(0, "9")

        # 출력 폴더
        out_frame = ctk.CTkFrame(frame)
        out_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(out_frame, text="출력 폴더:", width=100, anchor="e").pack(side="left", padx=5)
        self.split_out_entry = ctk.CTkEntry(out_frame, width=400)
        self.split_out_entry.pack(side="left", padx=5)
        self.split_out_entry.insert(0, "output/분리")
        ctk.CTkButton(out_frame, text="변경", width=60,
                       command=self.select_split_output_dir).pack(side="left", padx=5)

        # 옵션 체크박스
        chk_frame = ctk.CTkFrame(frame, fg_color="transparent")
        chk_frame.pack(fill="x", pady=5)

        self.split_mask_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(chk_frame, text="분리 후 마스킹",
                         variable=self.split_mask_var).pack(side="left", padx=10)

        self.name_order_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(chk_frame, text="종합양식 순번으로 저장",
                         variable=self.name_order_var).pack(side="left", padx=10)

        # 종합양식 파일 (순번 매칭용)
        excel_frame = ctk.CTkFrame(frame)
        excel_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(excel_frame, text="종합양식:", width=100, anchor="e").pack(side="left", padx=5)
        self.split_excel_entry = ctk.CTkEntry(excel_frame, width=350, state="readonly")
        self.split_excel_entry.pack(side="left", padx=5)
        ctk.CTkButton(excel_frame, text="파일 선택", width=90,
                       command=self.select_split_excel).pack(side="left", padx=5)

        # 모바일 신분증 추가
        mobile_frame = ctk.CTkFrame(frame)
        mobile_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(mobile_frame, text="모바일 사진:", width=100, anchor="e").pack(side="left", padx=5)
        self.mobile_entry = ctk.CTkEntry(mobile_frame, width=250, state="readonly")
        self.mobile_entry.pack(side="left", padx=5)
        ctk.CTkButton(mobile_frame, text="사진 선택", width=80,
                       command=self.select_mobile_photos).pack(side="left", padx=5)
        ctk.CTkLabel(mobile_frame, text="위치:", width=35).pack(side="left", padx=2)
        self.mobile_pos_entry = ctk.CTkEntry(mobile_frame, width=80,
                                              placeholder_text="예: 3,7")
        self.mobile_pos_entry.pack(side="left", padx=2)

        # 결과 로그
        ctk.CTkLabel(frame, text="처리 결과:", anchor="w",
                     font=ctk.CTkFont(size=12)).pack(fill="x", pady=(8, 3))
        self.split_log = ctk.CTkTextbox(frame, height=150)
        self.split_log.pack(fill="both", expand=True)

        # 버튼
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(btn_frame, text="분리 실행", width=140,
                       fg_color="#2e7d32", hover_color="#1b5e20",
                       command=self.run_split).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="모바일 삽입", width=140,
                       command=self.run_mobile_insert).pack(side="left", padx=5)

    def select_scan_file(self):
        paths = filedialog.askopenfilenames(
            title="종합 스캔 이미지 선택",
            filetypes=[("Image", "*.jpg *.jpeg *.png *.bmp")])
        if paths:
            self.scan_files = list(paths)
            if len(paths) == 1:
                self._set_entry(self.scan_entry, os.path.basename(paths[0]))
            else:
                self._set_entry(self.scan_entry, f"{len(paths)}개 파일 선택됨")
            self.status_var.set(f"스캔 이미지: {len(paths)}개 선택")

    def select_split_output_dir(self):
        path = filedialog.askdirectory(title="분리 출력 폴더 선택")
        if path:
            self.split_out_entry.delete(0, "end")
            self.split_out_entry.insert(0, path)

    def select_split_excel(self):
        path = filedialog.askopenfilename(
            title="종합양식 파일 선택 (순번 매칭용)",
            filetypes=[("Excel", "*.xlsx *.xls")])
        if path:
            self.split_excel_path = path
            self._set_entry(self.split_excel_entry, os.path.basename(path))

    def select_mobile_photos(self):
        paths = filedialog.askopenfilenames(
            title="모바일 신분증 사진 선택",
            filetypes=[("Image", "*.jpg *.jpeg *.png *.bmp")])
        if paths:
            self.mobile_photos = list(paths)
            self._set_entry(self.mobile_entry,
                          f"{len(paths)}개 사진" if len(paths) > 1
                          else os.path.basename(paths[0]))

    def run_mobile_insert(self):
        """모바일 사진을 종합 스캔에 삽입"""
        if not hasattr(self, 'mobile_photos') or not self.mobile_photos:
            messagebox.showwarning("경고", "모바일 사진을 선택하세요.")
            return
        if not self.scan_files:
            messagebox.showwarning("경고", "스캔 이미지를 먼저 선택하세요.")
            return

        pos_text = self.mobile_pos_entry.get().strip()
        if not pos_text:
            messagebox.showwarning("경고",
                "삽입 위치를 입력하세요. (예: 3,7)")
            return

        try:
            positions = [int(p.strip()) for p in pos_text.split(',')]
        except ValueError:
            messagebox.showwarning("경고", "위치는 숫자를 쉼표로 구분하세요. (예: 3,7)")
            return

        if len(positions) != len(self.mobile_photos):
            messagebox.showwarning("경고",
                f"사진 {len(self.mobile_photos)}개에 맞게 위치를 "
                f"{len(self.mobile_photos)}개 입력하세요.")
            return

        try:
            cols = int(self.cols_entry.get())
        except ValueError:
            cols = 2
        try:
            total_cards = int(self.total_entry.get())
        except ValueError:
            total_cards = 0

        scan_path = self.scan_files[0]
        output_dir = self.split_out_entry.get()
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(os.path.dirname(scan_path), output_dir)

        # 출력 파일 경로
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        out_scan = os.path.join(output_dir,
            os.path.basename(scan_path).replace('.', '_모바일삽입.'))

        self.split_log.delete("1.0", "end")
        self.split_log.insert("1.0", "모바일 삽입 시작...\n\n")
        self.status_var.set("모바일 삽입 중...")

        def do_insert():
            # 원본 복사
            shutil.copy2(scan_path, out_scan)

            result = self.image_handler.create_scan_with_mobile(
                out_scan, self.mobile_photos, positions,
                cols, total_cards, out_scan)
            self.after(0, lambda: self._show_mobile_result(result))

        threading.Thread(target=do_insert, daemon=True).start()

    def _show_mobile_result(self, result):
        self.split_log.delete("1.0", "end")
        self.split_log.insert("1.0", f"{result['message']}\n\n")
        for r in result.get('results', []):
            status = "OK" if r.get('success') else "FAIL"
            self.split_log.insert("end",
                f"[{status}] {r.get('file', '?')} -> 위치 {r.get('position', '?')}\n"
                f"    {r.get('message', '')}\n")
        self.status_var.set(result['message'])
        messagebox.showinfo("완료", result['message'])

    def run_split(self):
        if not self.scan_files:
            messagebox.showwarning("경고", "스캔 이미지를 선택하세요.")
            return

        prefix = self.prefix_entry.get() or "주민"
        try:
            start_num = int(self.start_num_entry.get())
        except ValueError:
            start_num = 1
        try:
            cols = int(self.cols_entry.get())
        except ValueError:
            cols = 2
        try:
            total_cards = int(self.total_entry.get())
        except ValueError:
            total_cards = 0

        output_dir = self.split_out_entry.get()
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(os.path.dirname(self.scan_files[0]), output_dir)

        do_mask = self.split_mask_var.get()

        self.split_log.delete("1.0", "end")
        self.split_log.insert("1.0", "분리 처리 시작...\n\n")
        self.status_var.set("분리 처리 중...")

        # 순번 매칭 여부
        use_name_order = self.name_order_var.get()
        name_list = None
        if use_name_order and hasattr(self, 'split_excel_path') and self.split_excel_path:
            try:
                data = self.excel_handler.read_source_data(self.split_excel_path)
                name_list = [{'no': r.get('no', i+1), 'name': r.get('name', '')}
                             for i, r in enumerate(data)]
            except Exception:
                name_list = None

        def do_split():
            all_results = []
            current_num = start_num

            for scan_path in self.scan_files:
                filename = os.path.basename(scan_path)
                self.after(0, lambda f=filename:
                    self.split_log.insert("end", f"처리 중: {f}\n"))

                if name_list and not do_mask:
                    # 순번 매칭 분리
                    result = self.image_handler.split_with_name_order(
                        scan_path, output_dir, name_list, prefix,
                        cols, total_cards)
                elif do_mask:
                    result = self.image_handler.mask_combined_scan(
                        scan_path, output_dir, prefix, current_num,
                        cols, total_cards)
                else:
                    result = self.image_handler.split_scan_image(
                        scan_path, output_dir, prefix, current_num,
                        cols, total_cards)

                all_results.append({'file': filename, **result})
                if result['success']:
                    count = result.get('split_count', result.get('count', 0))
                    current_num += count

            self.after(0, lambda: self._show_split_result(all_results))

        threading.Thread(target=do_split, daemon=True).start()

    def _show_split_result(self, results):
        self.split_log.delete("1.0", "end")

        total_count = 0
        for r in results:
            count = r.get('split_count', r.get('count', 0))
            total_count += count
            self.split_log.insert("end",
                f"[{'OK' if r['success'] else 'FAIL'}] {r['file']}\n"
                f"    {r['message']}\n")

            # 순번 매칭 정보 표시
            for m in r.get('mapping', []):
                self.split_log.insert("end",
                    f"    No.{m['no']} {m['name']} -> {m['file']}\n")

            # 매핑 없으면 파일 목록 표시
            if not r.get('mapping'):
                for f in r.get('files', []):
                    self.split_log.insert("end",
                        f"    -> {os.path.basename(f)}\n")
            self.split_log.insert("end", "\n")

        msg = f"총 {total_count}개 신분증 분리 완료"
        self.status_var.set(msg)
        messagebox.showinfo("완료", msg)

    # ==================== 4. 검증 탭 ====================
    def setup_verify_tab(self):
        frame = ctk.CTkFrame(self.tab_verify, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(
            frame,
            text="순번별 신분증이 종합양식 개인정보와 일치하는지 검증합니다.",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(0, 10))

        # 파일 선택
        file_frame = ctk.CTkFrame(frame)
        file_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(file_frame, text="신분증 폴더:", width=100, anchor="e").pack(side="left", padx=5)
        self.verify_img_entry = ctk.CTkEntry(file_frame, width=350, state="readonly")
        self.verify_img_entry.pack(side="left", padx=5)
        ctk.CTkButton(file_frame, text="폴더 선택", width=90,
                       command=self.select_verify_folder).pack(side="left", padx=5)
        ctk.CTkButton(file_frame, text="파일 선택", width=90,
                       command=self.select_verify_images).pack(side="left", padx=5)

        excel_frame = ctk.CTkFrame(frame)
        excel_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(excel_frame, text="종합양식:", width=100, anchor="e").pack(side="left", padx=5)
        self.verify_excel_entry = ctk.CTkEntry(excel_frame, width=350, state="readonly")
        self.verify_excel_entry.pack(side="left", padx=5)
        ctk.CTkButton(excel_frame, text="파일 선택", width=90,
                       command=self.select_verify_excel).pack(side="left", padx=5)

        # OCR API 설정 (선택사항)
        api_toggle = ctk.CTkFrame(frame)
        api_toggle.pack(fill="x", pady=5)
        self.use_ocr_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(api_toggle, text="OCR 자동 검증 사용 (Clova API 필요)",
                         variable=self.use_ocr_var,
                         command=self._toggle_api_fields).pack(side="left", padx=5)

        self.api_detail_frame = ctk.CTkFrame(frame)
        # API 필드 (기본 숨김)
        api_row1 = ctk.CTkFrame(self.api_detail_frame)
        api_row1.pack(fill="x", pady=2)
        ctk.CTkLabel(api_row1, text="OCR URL:", width=100, anchor="e").pack(side="left", padx=5)
        self.api_url_entry = ctk.CTkEntry(api_row1, width=500)
        self.api_url_entry.pack(side="left", padx=5)

        api_row2 = ctk.CTkFrame(self.api_detail_frame)
        api_row2.pack(fill="x", pady=2)
        ctk.CTkLabel(api_row2, text="Secret Key:", width=100, anchor="e").pack(side="left", padx=5)
        self.api_secret_entry = ctk.CTkEntry(api_row2, width=350, show="*")
        self.api_secret_entry.pack(side="left", padx=5)

        # 신분증 미리보기 + 엑셀 정보 대조 영역
        preview_frame = ctk.CTkFrame(frame)
        preview_frame.pack(fill="both", expand=True, pady=(8, 0))

        # 좌측: 이미지 미리보기
        self.preview_left = ctk.CTkFrame(preview_frame, width=300)
        self.preview_left.pack(side="left", fill="both", expand=True, padx=(0, 5))

        ctk.CTkLabel(self.preview_left, text="신분증 이미지",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(pady=3)
        self.img_preview_label = ctk.CTkLabel(self.preview_left, text="",
                                               width=280, height=180)
        self.img_preview_label.pack(pady=5)

        # 이미지 탐색 버튼
        nav_frame = ctk.CTkFrame(self.preview_left, fg_color="transparent")
        nav_frame.pack(pady=3)
        ctk.CTkButton(nav_frame, text="<< 이전", width=80,
                       command=self.prev_verify_card).pack(side="left", padx=5)
        self.card_index_label = ctk.CTkLabel(nav_frame, text="0 / 0", width=80)
        self.card_index_label.pack(side="left", padx=5)
        ctk.CTkButton(nav_frame, text="다음 >>", width=80,
                       command=self.next_verify_card).pack(side="left", padx=5)

        # 우측: 엑셀 데이터 + 검증 결과
        self.preview_right = ctk.CTkFrame(preview_frame, width=400)
        self.preview_right.pack(side="right", fill="both", expand=True, padx=(5, 0))

        ctk.CTkLabel(self.preview_right, text="종합양식 정보 대조",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(pady=3)
        self.verify_log = ctk.CTkTextbox(self.preview_right, height=180)
        self.verify_log.pack(fill="both", expand=True, pady=5)

        # 버튼
        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(btn_frame, text="순번 대조 검증", width=150,
                       fg_color="#2e7d32", hover_color="#1b5e20",
                       command=self.run_order_verify).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="OCR 자동 검증", width=150,
                       command=self.run_verify).pack(side="left", padx=5)

        # 검증 상태 변수
        self.verify_cards = []
        self.verify_excel_data = []
        self.verify_current_idx = 0

    def _toggle_api_fields(self):
        if self.use_ocr_var.get():
            self.api_detail_frame.pack(fill="x", pady=3)
        else:
            self.api_detail_frame.pack_forget()

    def select_verify_folder(self):
        path = filedialog.askdirectory(title="신분증 이미지 폴더 선택")
        if path:
            files = sorted(glob.glob(os.path.join(path, "*.jpg")) +
                          glob.glob(os.path.join(path, "*.jpeg")) +
                          glob.glob(os.path.join(path, "*.png")))
            if files:
                self.verify_images = files
                self._set_entry(self.verify_img_entry,
                              f"{path} ({len(files)}개)")
                self.status_var.set(f"검증 대상: {len(files)}개 파일")
            else:
                messagebox.showwarning("경고", "폴더에 이미지 파일이 없습니다.")

    def select_verify_images(self):
        paths = filedialog.askopenfilenames(
            title="검증할 신분증 이미지 선택",
            filetypes=[("Image", "*.jpg *.jpeg *.png *.bmp")])
        if paths:
            self.verify_images = sorted(list(paths))
            self._set_entry(self.verify_img_entry,
                          f"{len(paths)}개 파일" if len(paths) > 1
                          else os.path.basename(paths[0]))

    def select_verify_excel(self):
        path = filedialog.askopenfilename(
            title="종합양식 파일 선택",
            filetypes=[("Excel", "*.xlsx *.xls")])
        if path:
            self.verify_excel = path
            self._set_entry(self.verify_excel_entry, os.path.basename(path))

    # ---------- 순번 대조 검증 (API 불필요) ----------
    def run_order_verify(self):
        """파일명 순번과 엑셀 순번을 매칭하여 나란히 보여줌"""
        if not self.verify_images:
            messagebox.showwarning("경고", "신분증 이미지를 선택하세요.")
            return
        if not self.verify_excel:
            messagebox.showwarning("경고", "종합양식 파일을 선택하세요.")
            return

        try:
            self.verify_excel_data = self.excel_handler.read_source_data(
                self.verify_excel)
        except Exception as e:
            messagebox.showerror("오류", f"엑셀 읽기 실패: {e}")
            return

        # 파일명에서 번호 추출하여 엑셀 순번과 매칭
        self.verify_cards = []
        for img_path in self.verify_images:
            filename = os.path.basename(img_path)
            # 파일명에서 숫자 추출 (주민-1.jpg → 1)
            nums = re.findall(r'(\d+)', filename)
            file_no = int(nums[-1]) if nums else 0

            # 엑셀에서 매칭되는 행 찾기
            excel_row = None
            for row in self.verify_excel_data:
                if row.get('no') == file_no:
                    excel_row = row
                    break

            self.verify_cards.append({
                'path': img_path,
                'filename': filename,
                'file_no': file_no,
                'excel_row': excel_row,
            })

        self.verify_current_idx = 0
        self._show_verify_card(0)

        # 요약 로그
        self.verify_log.delete("1.0", "end")
        self.verify_log.insert("1.0", "=== 순번 대조 검증 ===\n\n")
        matched = sum(1 for c in self.verify_cards if c['excel_row'])
        self.verify_log.insert("end",
            f"이미지: {len(self.verify_cards)}개\n"
            f"엑셀 데이터: {len(self.verify_excel_data)}명\n"
            f"매칭: {matched}건\n\n")

        for card in self.verify_cards:
            row = card['excel_row']
            if row:
                self.verify_log.insert("end",
                    f"[No.{card['file_no']}] {card['filename']}\n"
                    f"  엑셀: {row['name']} / {row['birth']} / "
                    f"{row.get('phone', '')}\n"
                    f"  << 이미지와 비교하여 확인하세요 >>\n\n")
            else:
                self.verify_log.insert("end",
                    f"[No.{card['file_no']}] {card['filename']}\n"
                    f"  !! 엑셀에 매칭되는 순번 없음\n\n")

        self.status_var.set(
            f"순번 대조: {len(self.verify_cards)}개 이미지, "
            f"{matched}건 매칭 - 이미지를 확인하세요")

    def _show_verify_card(self, idx):
        """이미지 미리보기 + 엑셀 데이터 표시"""
        if not self.verify_cards or idx < 0 or idx >= len(self.verify_cards):
            return

        self.verify_current_idx = idx
        card = self.verify_cards[idx]

        # 인덱스 표시
        self.card_index_label.configure(
            text=f"{idx + 1} / {len(self.verify_cards)}")

        # 이미지 로드 및 표시
        try:
            pil_img = Image.open(card['path'])
            # 미리보기 크기로 축소
            max_w, max_h = 280, 175
            pil_img.thumbnail((max_w, max_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(pil_img)
            self.img_preview_label.configure(image=photo, text="")
            self.img_preview_label._photo = photo  # 참조 유지
        except Exception:
            self.img_preview_label.configure(image=None,
                text=f"이미지 로드 실패:\n{card['filename']}")

        # 엑셀 정보 강조 표시
        self.verify_log.delete("1.0", "end")
        row = card['excel_row']
        self.verify_log.insert("1.0",
            f"파일: {card['filename']} (No.{card['file_no']})\n")
        self.verify_log.insert("end", "-" * 40 + "\n\n")

        if row:
            self.verify_log.insert("end", "종합양식 정보:\n")
            self.verify_log.insert("end", f"  순번: No.{row.get('no', '?')}\n")
            self.verify_log.insert("end", f"  성명: {row.get('name', '?')}\n")
            self.verify_log.insert("end", f"  생년월일: {row.get('birth', '?')}\n")
            self.verify_log.insert("end", f"  전화번호: {row.get('phone', '?')}\n")
            self.verify_log.insert("end",
                f"  취약구분: {row.get('vulnerable', '일반')}\n")
            self.verify_log.insert("end",
                f"  결제: {row.get('payment', '')}\n\n")
            self.verify_log.insert("end",
                ">> 신분증 이미지의 이름/생년월일이\n"
                ">> 위 정보와 일치하는지 확인하세요.\n")
        else:
            self.verify_log.insert("end",
                "!! 엑셀에 매칭되는 순번이 없습니다.\n"
                "!! 파일명의 번호를 확인하세요.\n")

    def prev_verify_card(self):
        if self.verify_current_idx > 0:
            self._show_verify_card(self.verify_current_idx - 1)

    def next_verify_card(self):
        if self.verify_current_idx < len(self.verify_cards) - 1:
            self._show_verify_card(self.verify_current_idx + 1)

    # ---------- OCR 자동 검증 (API 필요) ----------
    def run_verify(self):
        if not self.verify_images:
            messagebox.showwarning("경고", "검증할 이미지를 선택하세요.")
            return
        if not self.verify_excel:
            messagebox.showwarning("경고", "종합양식 파일을 선택하세요.")
            return

        api_url = self.api_url_entry.get().strip()
        secret_key = self.api_secret_entry.get().strip()

        if not api_url or not secret_key:
            messagebox.showwarning("경고",
                "OCR 자동 검증에는 Clova API 키가 필요합니다.\n\n"
                "API 없이 검증하려면 '순번 대조 검증' 버튼을 사용하세요.")
            return

        self.ocr_handler = OCRHandler(
            api_url=api_url, secret_key=secret_key, use_clova=True)

        self.verify_log.delete("1.0", "end")
        self.verify_log.insert("1.0", "OCR 검증 시작...\n\n")
        self.status_var.set("OCR 검증 중...")

        def do_verify():
            try:
                excel_data = self.excel_handler.read_source_data(self.verify_excel)
                result = self.ocr_handler.verify_batch(
                    self.verify_images, excel_data)
                self.after(0, lambda: self._show_ocr_verify_result(result))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("오류", str(e)))
                self.after(0, lambda: self.status_var.set("검증 오류"))

        threading.Thread(target=do_verify, daemon=True).start()

    def _show_ocr_verify_result(self, result):
        self.verify_log.delete("1.0", "end")
        self.verify_log.insert("1.0", f"=== OCR 자동 검증 결과 ===\n")
        self.verify_log.insert("end", f"{result['message']}\n")
        self.verify_log.insert("end", "=" * 45 + "\n\n")

        for r in result.get('results', []):
            self.verify_log.insert("end", f"[{r['file']}]\n")
            if r.get('ocr_success'):
                self.verify_log.insert("end",
                    f"  OCR: 이름={r.get('ocr_name', '?')}, "
                    f"생년월일={r.get('ocr_birth', '?')}\n")
                self.verify_log.insert("end", f"  {r.get('details', '')}\n\n")
            else:
                self.verify_log.insert("end",
                    f"  OCR 실패: {r.get('message', '')}\n\n")

        self.status_var.set(result['message'])
        messagebox.showinfo("검증 완료", result['message'])

    # ==================== 유틸리티 ====================
    def _set_entry(self, entry, text):
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, text)
        entry.configure(state="readonly")


if __name__ == "__main__":
    app = IDAutomationApp()
    app.mainloop()
