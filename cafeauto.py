import time
import os
import glob
import pyperclip
import gspread
import datetime # Added for timestamp
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, NoAlertPresentException

# Configuration
SHEET_URL = "https://docs.google.com/spreadsheets/d/1ct7wA-ICHZREYGNdYRSjlXBW4rUfEuI1U_BDMOLJ8h8/edit?gid=0#gid=0"
CREDENTIALS_FILE = "service_account.json"

class NaverCafePoster:
    def __init__(self, log_callback=None):
        self.driver = None
        self.sheet_client = None
        self.main_sheet = None
        self.board_sheet = None
        self.log_callback = log_callback # Function to send logs to GUI

    def log(self, message):
        """Logs message to console and GUI if callback provided."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted)
        if self.log_callback:
            self.log_callback(message) # Send raw message, GUI adds timestamp or format if needed

    def setup_driver(self):
        """Initializes the Chrome driver with options."""
        options = Options()
        # Headless Mode Settings
        # options.add_argument("--headless=new") 
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Clipboard permissions for Headless
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
            "profile.content_settings.exceptions.clipboard": {"*": {'setting': 1}} # Allow clipboard
        })
        options.add_experimental_option("detach", True)
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.maximize_window()
        self.driver.implicitly_wait(10)

    def connect_to_sheets(self):
        """Connects to Google Sheets using service account."""
        if not os.path.exists(CREDENTIALS_FILE):
            self.log(f"[오류] 인증 파일 없음: {CREDENTIALS_FILE}")
            return False

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
            self.sheet_client = gspread.authorize(creds)
            full_sheet = self.sheet_client.open_by_url(SHEET_URL)
            self.main_sheet = full_sheet.get_worksheet(0) # First sheet
            self.board_sheet = full_sheet.worksheet("게시판") # Sheet named "게시판"
            self.log("[시스템] 구글 시트 연결 성공.")
            return True
        except Exception as e:
            self.log(f"[오류] 시트 연결 실패: {e}")
            return False

    def get_cafe_url(self, cafe_name):
        """Finds the Cafe URL from the '게시판' sheet based on cafe name."""
        try:
            records = self.board_sheet.get_all_values()
            for row in records[1:]: 
                if len(row) >= 2:
                    url = row[0] 
                    name = row[1] 
                    if name.strip() == cafe_name.strip():
                        return url
            return None
        except Exception as e:
            self.log(f"[오류] 카페 URL 찾기 실패: {e}")
            return None

    def login_naver(self, user_id, user_pw):
        """Logs into Naver using clipboard method."""
        self.log(f"[로그인] {user_id} 로그인 시도 중...")
        self.driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(2)

        # Input ID
        id_input = self.driver.find_element(By.ID, "id")
        id_input.click()
        pyperclip.copy(user_id)
        id_input.send_keys(Keys.CONTROL, 'v')
        time.sleep(1)

        # Input PW
        pw_input = self.driver.find_element(By.ID, "pw")
        pw_input.click()
        pyperclip.copy(user_pw)
        pw_input.send_keys(Keys.CONTROL, 'v')
        time.sleep(1)

        # Click Login
        self.driver.find_element(By.ID, "log.login").click()
        time.sleep(2)
        
        self.log(f"[로그인] 로그인 버튼 클릭 완료.")
        return True

    def find_image_file(self, folder_path, pattern_prefix):
        """Finds a file starting with the given prefix in the folder."""
        if not os.path.isdir(folder_path):
            print(f"[WARN] Directory not found: {folder_path}")
            return None
        
        search_pattern = os.path.join(folder_path, f"{pattern_prefix}*")
        files = glob.glob(search_pattern)
        
        if files:
            return files[0] 
        return None

    def process_row(self, row_index):
        """Processes a single row from the main sheet."""
        # Note: gspread uses 1-based indexing for rows/cols
        # C=3, D=4, F=6, G=7, H=8, I=9, J=10
        
        try:
            # Fetch data for the specific row
            # It's better to fetch the whole row to avoid multiple API calls
            row_values = self.main_sheet.row_values(row_index)
            
            # Should have enough columns. Pad if necessary.
            if len(row_values) < 10:
                print(f"Row {row_index} does not have enough data.")
                # You might handle this more gracefully
                pass

            # Correct Mapping (0-indexed) based on NEW 11-column structure:
            # B(1)=Name, C(2)=ID, D(3)=PW, E(4)=BeforeFolder, F(5)=AfterFolder, G(6)=Cafe, H(7)=Board, I(8)=Title, J(9)=Body, K(10)=File, L(11)=URL
            
            user_id = row_values[2] if len(row_values) > 2 else "" # C column
            user_pw = row_values[3] if len(row_values) > 3 else "" # D column
            
            before_folder = row_values[4] if len(row_values) > 4 else "" # E column
            after_folder = row_values[5] if len(row_values) > 5 else ""  # F column
            
            cafe_name_key = row_values[6] if len(row_values) > 6 else "" # G column
            board_name = row_values[7] if len(row_values) > 7 else ""    # H column
            title = row_values[8] if len(row_values) > 8 else ""         # I column
            body_text = row_values[9] if len(row_values) > 9 else ""     # J column
            image_folder = row_values[10] if len(row_values) > 10 else "" # K column
            
            if not user_id or not cafe_name_key:
                self.log(f"[건너뜀] 행 {row_index}: ID 또는 카페명이 누락되었습니다.")
                return
            
            if not user_id or not cafe_name_key:
                self.log(f"[건너뜀] 행 {row_index}: ID 또는 카페명이 누락되었습니다.")
                return

            self.log(f"▶ 작업 시작: {cafe_name_key} - {title} (행 {row_index})")

            # 1. Login
            self.login_naver(user_id, user_pw)

            # 2. Get Cafe URL
            cafe_url = self.get_cafe_url(cafe_name_key)
            if not cafe_url:
                self.log(f"[오류] 카페 URL을 찾을 수 없음: {cafe_name_key}")
                return

            # 3. Navigate to Cafe
            self.driver.get(cafe_url)
            time.sleep(2)

            # 4. Switch Iframe (IMMEDIATE)
            self.log("[시스템] 메인 프레임(cafe_main) 진입 시도...")
            try:
                WebDriverWait(self.driver, 15).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
                self.log("[시스템] 메인 프레임(cafe_main) 진입 완료")
            except:
                self.log("[오류] cafe_main 프레임 전환 실패. (메뉴가 바깥에 있을 수 있음)")
                self.driver.switch_to.default_content()
                
            # 5. Click Board Name
            self.log(f"[진행] 게시판 목록에서 '{board_name}' 탐색 중...")
            board_found = False
            
            # 1st try: Inside current frame
            try:
                board_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, board_name)
                board_link.click()
                board_found = True
                self.log(f"[진행] 게시판 접속 성공: '{board_name}'")
            except NoSuchElementException:
                # 2nd try: Outside frame (Top/Side menu)
                self.log(f"[정보] '{board_name}'을 프레임 안에서 못 찾음. 바깥쪽 재탐색...")
                self.driver.switch_to.default_content()
                try:
                    board_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, board_name)
                    board_link.click()
                    board_found = True
                    self.log(f"[진행] 게시판 접속 성공 (사이드 메뉴): '{board_name}'")
                except NoSuchElementException:
                     self.log(f"[오류] '{board_name}' 게시판을 카페 어디에서도 찾을 수 없습니다.")
                     return

            # After clicking, we usually need to re-enter cafe_main to find the 'Write' button
            if board_found:
                time.sleep(1.5)
                try:
                    self.driver.switch_to.default_content()
                    WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
                    self.log("[시스템] 게시판 이동 후 cafe_main 재진입 성공")
                except:
                    self.log("[경고] 게시판 이동 후 cafe_main 진입 실패")

            time.sleep(1) # Sleep reduced

            # 6. Click '글쓰기'
            write_selectors = [
                 # User provided
                (By.CSS_SELECTOR, "a.BaseButtonLink.BaseButton--skinGreen"),
                (By.CLASS_NAME, "BaseButtonLink"),
                (By.XPATH, "//a[contains(@class, 'BaseButtonLink')]"),
                (By.XPATH, "//a[contains(@class, 'BaseButton')]"), # Broader check
                # Fallbacks
                (By.XPATH, "//span[@class='BaseButton__txt' and contains(text(), '글쓰기')]"),
                (By.CSS_SELECTOR, "a.btn_write"),
                (By.ID, "write-btn"),
                (By.LINK_TEXT, "글쓰기")
            ]
            
            def find_write_btn():
                for by, val in write_selectors:
                    try:
                        ele = self.driver.find_element(by, val)
                        if ele and ele.is_displayed(): return ele
                    except: continue
                return None

            # 1st Try: Current context
            write_btn = find_write_btn()

            # 2nd Try: Force switch to cafe_main
            if not write_btn:
                self.log("[재시도] 버튼 못찾음 -> cafe_main 프레임 전환 시도")
                self.driver.switch_to.default_content()
                time.sleep(1)
                
                frame_switched = False
                try:
                    # Method 1: Wait for frame
                    WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
                    frame_switched = True
                    self.log("[시스템] cafe_main 진입 성공 (Method 1)")
                except:
                    # Method 2: Find element directly
                    try:
                        self.log("[경고] Wait 실패 -> 직접 프레임 찾기 시도")
                        frame_elem = self.driver.find_element(By.ID, "cafe_main")
                        self.driver.switch_to.frame(frame_elem)
                        frame_switched = True
                        self.log("[시스템] cafe_main 진입 성공 (Method 2)")
                    except Exception as e:
                        self.log(f"[치명적 오류] 프레임 전환 불가: {e}")
                
                if frame_switched:
                    time.sleep(2) # Wait for internal render
                    write_btn = find_write_btn()

            if write_btn:
                 try:
                    write_btn.click()
                    self.log("[진행] '글쓰기' 버튼 클릭 성공")
                 except Exception as e:
                    self.log(f"[오류] 버튼 클릭 에러 (JS 시도): {e}")
                    self.driver.execute_script("arguments[0].click();", write_btn)
            else:
                self.log("[오류] '글쓰기' 버튼 최종 발견 실패")
                self.driver.save_screenshot("debug_write_final_fail.png")
                return

            time.sleep(3)

            # 7. Switch to new window
            current_window = self.driver.current_window_handle
            window_handles = self.driver.window_handles
            if len(window_handles) > 1:
                new_window = [w for w in window_handles if w != current_window][-1]
                self.driver.switch_to.window(new_window)
            
            time.sleep(3)

            # 8. Title Entry
            try:
                 title_area = self.driver.find_element(By.CLASS_NAME, "textarea_input")
                 title_area.click()
                 title_area.send_keys(title)
            except NoSuchElementException:
                self.log("[오류] 제목 입력칸 찾기 실패")

            time.sleep(1)

            # Define Logic
            def append_text(text):
                if not text: return
                try:
                    body_elem = self.driver.find_element(By.XPATH, "//div[contains(@class, 'se-content')] | //div[contains(@class, 'se-main_container')]")
                    body_elem.click()
                    time.sleep(0.5)
                    webdriver.ActionChains(self.driver).key_down(Keys.CONTROL).send_keys(Keys.END).key_up(Keys.CONTROL).perform()
                    time.sleep(0.2)
                    pyperclip.copy(text)
                    actions = webdriver.ActionChains(self.driver)
                    actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    time.sleep(0.5)
                except Exception as e:
                    self.log(f"[오류] 본문 입력 실패: {e}")

            def upload_image(path):
                if not path: return
                self.log(f"[이미지] 업로드 시도: {path}...")
                uploaded = False
                try:
                    for _ in range(3):
                        try:
                            img_btn = self.driver.find_element(By.CSS_SELECTOR, ".se-image-toolbar-button")
                            img_btn.click()
                            time.sleep(1)
                            break
                        except: time.sleep(1)

                    file_input = None
                    for _ in range(3):
                        try:
                             file_inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                             if file_inputs:
                                 file_input = file_inputs[0]
                                 break
                        except: time.sleep(1)
                            
                    if file_input:
                        try:
                            self.driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible'; arguments[0].style.opacity = '1';", file_input)
                            file_input.send_keys(path)
                            uploaded = True
                            time.sleep(4)
                            try: webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                            except: pass
                        except Exception as inner_e:
                             self.log(f"[경고] 이미지 입력 오류: {inner_e}")
                    else:
                        self.log("[오류] 파일 입력창 못찾음")
                except Exception as e:
                    self.log(f"[오류] 이미지 업로드 실패: {e}")

            def insert_newlines(count=1):
                try:
                    actions = webdriver.ActionChains(self.driver)
                    actions.send_keys(Keys.END)
                    for _ in range(count):
                        actions.key_down(Keys.ENTER).key_up(Keys.ENTER)
                    actions.perform()
                    time.sleep(0.5)
                except: pass

            # 9. Sequential Image & Text Input
            def upload_folder_images(folder):
                if not folder or not os.path.isdir(folder): return
                files = [f for f in glob.glob(os.path.join(folder, "*")) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
                if not files: return
                self.log(f"[이미지] '{folder}' 내 이미지 {len(files)}개 업로드 중...")
                for f in files:
                    upload_image(f)
                    time.sleep(1)

            # Sequence: Title already entered.
            # 1. Before Surgery
            if before_folder:
                upload_folder_images(before_folder)
                insert_newlines(1)
            
            # 2. After Surgery
            if after_folder:
                upload_folder_images(after_folder)
                insert_newlines(1)
            
            # 3. Body Text
            if body_text:
                self.log(f"[본문] 내용 입력 중 ({len(body_text)}자)...")
                append_text(body_text)

            time.sleep(2)

            # 10. Adjust settings before registration
            try:
                self.log("[진행] 게시글 설정(전체공개 등) 조정 중...")
                open_set_btn = self.driver.find_element(By.CSS_SELECTOR, "button.btn_open_set")
                open_set_btn.click()
                time.sleep(1)
                
                # Set to Public (전체공개)
                all_radio = self.driver.find_element(By.ID, "all")
                if not all_radio.is_selected():
                    all_radio.click() # This might need label click depending on UI
                    self.log("[시스템] '전체공개' 설정 확인")
            except Exception as e:
                self.log(f"[경고] 설정 조정 실패 (이미 설정되어 있을 수 있음): {e}")

            # 11. Click Register
            try:
                register_btn = self.driver.find_element(By.XPATH, "//span[@class='BaseButton__txt' and text()='등록']")
                register_btn.click()
                self.log("[진행] '등록' 버튼 클릭 마침")
            except NoSuchElementException:
                self.log("[오류] 등록 버튼 못찾음")
                return 

            # 12. Post-Processing
            self.log("[대기] 게시글 등록 처리 중...")
            time.sleep(5) 
            
            try:
                url_btn = None
                # Try finding URL button
                try:
                    self.driver.switch_to.default_content()
                    WebDriverWait(self.driver, 5).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
                    url_btn = self.driver.find_element(By.CLASS_NAME, "button_url")
                except: pass
                
                if not url_btn:
                    try:
                        self.driver.switch_to.default_content()
                        url_btn = self.driver.find_element(By.CLASS_NAME, "button_url")
                    except: pass
                
                if url_btn:
                    # Clear clipboard BEFORE click
                    pyperclip.copy("") 
                    
                    url_btn.click()
                    self.log("[진행] URL 복사 버튼 클릭 완료")
                    time.sleep(2) # Wait for clipboard
                    
                    post_url = pyperclip.paste().strip()
                    
                    # Retry if empty
                    if not post_url:
                        self.log("[정보] 클립보드가 비어있음. 재시도 중...")
                        url_btn.click() # One more try
                        time.sleep(2)
                        post_url = pyperclip.paste().strip()
                    
                    if not post_url:
                        self.log("[경고] 클립보드에서 URL을 가져오지 못했습니다. (수동 입력 필요)")
                    else:
                        self.log(f"[성공] 게시글 URL 확인: {post_url}")
                        
                        now = datetime.datetime.now()
                        days = ["월", "화", "수", "목", "금", "토", "일"]
                        day_str = days[now.weekday()]
                        timestamp = now.strftime(f"%Y-%m-%d ({day_str}) %H:%M")
                        
                        try:
                            # Update Sheet
                            self.log(f"[상태] 시트 업데이트 중 (행 {row_index})...")
                            self.main_sheet.update_cell(row_index, 12, post_url) # L column
                            self.main_sheet.update_cell(row_index, 13, timestamp) # M column
                            self.log(f"[기록] 시트 업데이트 완료: {post_url} / {timestamp}")
                        except Exception as sheet_e:
                            self.log(f"[오류] 시트 기록 실패: {sheet_e}")
                            self.main_sheet.update_cell(row_index, 12, timestamp)
                            self.log(f"[기록] 시트 업데이트 완료 (행 {row_index})")
                        except Exception as sheet_e:
                            self.log(f"[오류] 시트 기록 실패: {sheet_e}")
                else:
                    self.log("[오류] URL 복사 버튼을 찾지 못했습니다.")
            except Exception as e:
                self.log(f"[오류] 마무리 처리 중 에러: {e}")


        except Exception as e:
            print(f"Error processing row {row_index}: {e}")

    def get_pending_rows(self):
        """Fetches rows from Main sheet where URL (Col K / Index 10) is empty."""
        if not self.connect_to_sheets():
            return []
            
        all_values = self.main_sheet.get_all_values()
        pending_rows = []
        
        # Start from row 4 (index 3)
        for i in range(3, len(all_values)):
            row = all_values[i]
            # Check if sufficient columns (L is index 11)
            if len(row) < 12:
                 if len(row) > 1 and row[1].strip(): # Has Name (B column)
                     pending_rows.append({
                         'index': i + 1,
                         'name': row[1] if len(row) > 1 else "",           # Col B (Index 1)
                         'cafe': row[6] if len(row) > 6 else "",           # Col G (Index 6)
                         'board': row[7] if len(row) > 7 else "",          # Col H (Index 7)
                         'title': row[8] if len(row) > 8 else "",          # Col I (Index 8)
                         'review_text': row[4] if len(row) > 4 else ""     # Col E (Index 4)
                     })
            else:
                # Check Col L (index 11)
                url = row[11].strip()
                if not url and len(row) > 1 and row[1].strip(): # Has Name (B column)
                     pending_rows.append({
                         'index': i + 1,
                         'name': row[1] if len(row) > 1 else "", 
                         'cafe': row[6] if len(row) > 6 else "",
                         'board': row[7] if len(row) > 7 else "",
                         'title': row[8] if len(row) > 8 else "",
                         'review_text': row[4] if len(row) > 4 else ""
                     })
                     
        return pending_rows

    def run(self, target_rows=None):
        """
        Runs the automation.
        :param target_rows: List of 1-based row indices to process. If None, processes all valid rows from 4.
        """
        if not self.connect_to_sheets():
            return
        
        self.setup_driver()
        
        if target_rows:
            print(f"[INFO] Processing specific rows: {target_rows}")
            for row_idx in target_rows:
                self.process_row(row_idx)
                time.sleep(2)
        else:
            # Default behavior (legacy)
            start_row = 4
            all_values = self.main_sheet.get_all_values()
            for i in range(start_row - 1, len(all_values)):
                if not all_values[i][2]: 
                    break 
                self.process_row(i + 1)
                time.sleep(2)

        print("Done.")
        if self.driver:
            self.driver.quit()

if __name__ == "__main__":
    bot = NaverCafePoster()
    # bot.run() # Disable auto-run for import safety

