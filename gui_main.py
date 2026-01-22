import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
import threading
import datetime # Added for timestamp
import os
from cafeauto import NaverCafePoster  # Restored Import

# Version check
VERSION = "1.0.1"
if os.path.exists("version.txt"):
    try:
        with open("version.txt", "r", encoding="utf-8") as f:
            VERSION = f.read().strip()
    except: pass


# Google Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ct7wA-ICHZREYGNdYRSjlXBW4rUfEuI1U_BDMOLJ8h8/edit?gid=0#gid=0"

class CafeAutomationGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"카페 후기 자동화 (v{VERSION})")
        self.root.geometry("900x600") # Expanded size
        
        # Initialize Bot with Log Callback
        self.bot = NaverCafePoster(log_callback=self.log_message)
        self.check_vars = []
        self.pending_rows = []

        # Styles
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", background="#ccc")
        style.configure("TLabel", font=("Helvetica", 10))
        style.configure("Header.TLabel", font=("Helvetica", 14, "bold"))

        # Main Layout: Left (List) vs Right (Log)
        main_pane = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # --- LEFT FRAME (Use existing logic) ---
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=1)

        # Header (Left)
        header_frame = ttk.Frame(left_frame, padding="0 0 0 10")
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="네이버 카페 자동화", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(header_frame, text="데이터 새로고침", command=self.load_data).pack(side=tk.RIGHT)

        # List Area (Left)
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Control Area (Left)
        control_frame = ttk.Frame(left_frame, padding="0 10 0 0")
        control_frame.pack(fill=tk.X)
        self.run_btn = ttk.Button(control_frame, text="선택 항목 실행", command=self.run_selected)
        self.run_btn.pack(fill=tk.X)

        # --- RIGHT FRAME (Log) ---
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)
        
        log_label = ttk.Label(right_frame, text="진행 상황 로그", font=("Helvetica", 11, "bold"))
        log_label.pack(anchor="w", pady=(0, 5))

        self.log_area = tk.Text(right_frame, state='disabled', width=40, font=("Consolas", 9))
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar for log
        log_scroll = ttk.Scrollbar(right_frame, command=self.log_area.yview)
        log_scroll.pack(side="right", fill="y") # Note: This simple pack might overlap, but Text usually handles it inside frame if packed first
        # Better pack order for scrollbar:
        # Repacking for correct scrollbar placement
        self.log_area.pack_forget()
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_area['yscrollcommand'] = log_scroll.set
        
        # Footer
        footer_frame = ttk.Frame(root, padding="10")
        footer_frame.pack(fill=tk.X)
        
        link = tk.Label(footer_frame, text="카페 후기 자동화 시트", fg="blue", cursor="hand2", font=("Helvetica", 9, "underline"))
        link.pack()
        link.bind("<Button-1>", lambda e: webbrowser.open(SHEET_URL))

        # Initial Load
        self.load_data()

    def log_message(self, msg):
        """Appends a message to the log area."""
        def _log():
            self.log_area.config(state='normal')
            self.log_area.insert(tk.END, msg + "\n")
            self.log_area.see(tk.END)
            self.log_area.config(state='disabled')
        self.root.after(0, _log)

    def load_data(self):
        """Fetches data from Google Sheet and populates the list."""
        self.log_message("[시스템] 데이터 불러오는 중...")
        # Clear existing
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.check_vars.clear()
        self.pending_rows.clear()
        
        # Loading status
        lbl = ttk.Label(self.scrollable_frame, text="데이터 불러오는 중...")
        lbl.pack()
        self.root.update()

        try:
            rows = self.bot.get_pending_rows()
            lbl.destroy()
            
            if not rows:
                ttk.Label(self.scrollable_frame, text="대기 중인 작업이 없습니다.").pack()
                self.log_message("[시스템] 대기 중인 작업 없음.")
                return

            self.pending_rows = rows
            self.log_message(f"[시스템] 작업 {len(rows)}개 로드됨.")
            
            for row in rows:
                var = tk.BooleanVar()
                self.check_vars.append(var)
                
                # Format: [Name] Cafe - Board (Title)
                text = f"[{row['name']}] {row['cafe']} - {row['board']} : {row['title']}"
                chk = ttk.Checkbutton(self.scrollable_frame, text=text, variable=var)
                chk.pack(anchor='w', padx=5, pady=2)
                
        except Exception as e:
            lbl.destroy()
            self.log_message(f"[오류] 데이터 로드 실패: {e}")
            messagebox.showerror("오류", f"데이터 로드 실패: {e}")

    def run_selected(self):
        """Runs the automation for selected rows."""
        selected_indices = []
        for i, var in enumerate(self.check_vars):
            if var.get():
                selected_indices.append(self.pending_rows[i]['index'])
        
        if not selected_indices:
            messagebox.showwarning("경고", "작업을 최소 하나 이상 선택해주세요.")
            return
        
        # Disable button
        self.run_btn.config(state="disabled")
        self.log_message(f"[명령] 선택된 작업 {len(selected_indices)}개 실행 시작...")
        
        # Run in thread to not freeze GUI
        threading.Thread(target=self.run_automation_thread, args=(selected_indices,)).start()

    def run_automation_thread(self, indices):
        try:
            self.bot.run(target_rows=indices)
            self.log_message("[완료] 모든 자동화 작업 종료.")
            messagebox.showinfo("완료", "자동화 작업이 완료되었습니다.")
            # Reload data after run to show updated status (removed from list if URL filled)
            self.root.after(0, self.load_data)
        except Exception as e:
            self.log_message(f"[치명적 오류] 작업 중단: {e}")
            messagebox.showerror("오류", f"자동화 실패: {e}")
        finally:
            self.root.after(0, lambda: self.run_btn.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = CafeAutomationGUI(root)
    root.mainloop()
