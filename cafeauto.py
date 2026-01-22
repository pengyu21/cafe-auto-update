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
        options.add_argument("--headless=new") 
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

            # Adjust indices because row_values is 0-indexed list
            # C is index 2
            user_id = row_values[2] if len(row_values) > 2 else ""
            user_pw = row_values[3] if len(row_values) > 3 else ""
            cafe_name_key = row_values[5] if len(row_values) > 5 else "" # F column
            board_name = row_values[6] if len(row_values) > 6 else ""    # G column
            title = row_values[7] if len(row_values) > 7 else ""         # H column
            content = row_values[8] if len(row_values) > 8 else ""       # I column
            image_folder = row_values[9] if len(row_values) > 9 else ""  # J column

            if not user_id or not user_pw or not cafe_name_key:
                self.log(f"[건너뜀] 행 {row_index}: ID/PW/카페명 누락.")
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

            # 4. Switch Iframe
            try:
                WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
            except:
                self.log("[오류] cafe_main 프레임을 찾지 못했습니다.")
                return
                
            # 5. Click Board Name
            board_found = False
            try:
                board_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, board_name)
                board_link.click()
                board_found = True
                self.log(f"[진행] 게시판 접속: '{board_name}'")
            except NoSuchElementException:
                pass
            
            if not board_found:
                self.driver.switch_to.default_content()
                try:
                    board_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, board_name)
                    board_link.click()
                    board_found = True
                    self.log(f"[진행] 게시판 접속 (메인): '{board_name}'")
                    time.sleep(2)
                    try:
                         WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
                    except: pass
                except NoSuchElementException:
                    self.log(f"[오류] 게시판을 찾을 수 없음: '{board_name}'")
                    return

            time.sleep(3)

            # 6. Click '글쓰기'
            # Force switch to cafe_main if not already
            self.driver.switch_to.default_content()
            try:
                WebDriverWait(self.driver, 5).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
            except:
                self.log("[주의] cafe_main 프레임 전환 실패 (또는 이미 내부)")

            write_btn = None
            write_selectors = [
                (By.XPATH, "//span[@class='BaseButton__txt' and contains(text(), '글쓰기')]"),
                (By.ID, "write-btn"),
                (By.ID, "cafe-write-btn"),
                (By.CSS_SELECTOR, "a.btn_write"),
                (By.LINK_TEXT, "글쓰기")
            ]
            
            for by, val in write_selectors:
                try:
                    write_btn = self.driver.find_element(by, val)
                    if write_btn: break
                except: continue
                
            if write_btn:
                 try:
                    write_btn.click()
                    self.log("[진행] '글쓰기' 버튼 클릭")
                 except Exception as e:
                    self.log(f"[오류] 버튼 클릭 실패: {e}")
                    # Try JS click
                    self.driver.execute_script("arguments[0].click();", write_btn)
            else:
                self.log("[오류] '글쓰기' 버튼을 찾을 수 없음 (스크린샷 저장)")
                self.driver.save_screenshot("debug_write_btn_fail.png")
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

            img_before = self.find_image_file(image_folder, "전")
            if img_before:
                upload_image(img_before)
                append_text("수술전")
                insert_newlines(1)
            
            img_after = self.find_image_file(image_folder, "후")
            if img_after:
                upload_image(img_after)
                
            review_text = row_values[4] if len(row_values) > 4 else ""
            final_text = ""
            if review_text: final_text += review_text + "\n\n"
            if content: final_text += content
            if final_text:
                self.log(f"[본문] 내용 입력 중 ({len(final_text)}자)...")
                append_text(final_text)

            time.sleep(2)

            # 11. Click Register
            try:
                register_btn = self.driver.find_element(By.XPATH, "//span[@class='BaseButton__txt' and text()='등록']")
                register_btn.click()
                self.log("[진행] '등록' 버튼 클릭 완료")
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
                    url_btn.click()
                    time.sleep(1.5)
                    
                    # Ensure clipboard has new data
                    pyperclip.copy("") # Clear first
                    post_url = pyperclip.paste()
                    
                    # Retry if empty
                    if not post_url:
                        time.sleep(1)
                        post_url = pyperclip.paste()
                    
                    if not post_url:
                        self.log("[경고] 클립보드에서 URL을 가져오지 못했습니다.")
                        # Fallback: Current URL?
                        # Usually popup or modal.
                    else:
                        self.log(f"[성공] 게시글 URL 확인: {post_url}")
                        
                        now = datetime.datetime.now()
                        days = ["월", "화", "수", "목", "금", "토", "일"]
                        day_str = days[now.weekday()]
                        timestamp = now.strftime(f"%Y-%m-%d ({day_str}) %H:%M")
                        
                        try:
                            # Update Sheet
                            self.main_sheet.update_cell(row_index, 11, post_url)
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
            # Check if sufficient columns, or pad
            if len(row) < 11:
                 # If row is too short, it definitely has no URL
                 # Check if it has essential data (ID at index 2)
                 if len(row) > 2 and row[2].strip():
                     pending_rows.append({
                         'index': i + 1, # 1-based index for gspread
                         'name': row[1] if len(row) > 1 else "", # Col B (Index 1)
                         'cafe': row[5] if len(row) > 5 else "",
                         'board': row[6] if len(row) > 6 else "",
                         'title': row[7] if len(row) > 7 else "",
                         'review_text': row[4] if len(row) > 4 else "" # Col E (Index 4)
                     })
            else:
                # Check Col K (index 10)
                url = row[10].strip()
                if not url and row[2].strip(): # Empty URL and has ID
                     pending_rows.append({
                         'index': i + 1,
                         'name': row[1] if len(row) > 1 else "", # Col B (Index 1)
                         'cafe': row[5],
                         'board': row[6],
                         'title': row[7],
                         'review_text': row[4] if len(row) > 4 else "" # Col E (Index 4)
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

