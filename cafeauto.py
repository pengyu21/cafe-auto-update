import time
import os
import glob
import pyperclip
import gspread
import datetime # Added for timestamp
import traceback # Added for detailed error logging
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

# Version logic
BOT_VERSION = "1.0.22"
if os.path.exists("version.txt"):
    try:
        with open("version.txt", "r", encoding="utf-8") as f:
            BOT_VERSION = f.read().strip()
    except: pass

class NaverCafePoster:
    def __init__(self, log_callback=None):
        self.driver = None
        self.sheet_client = None
        self.main_sheet = None
        self.board_sheet = None
        self.log_callback = log_callback # Function to send logs to GUI
        self.log(f"[부팅] NaverCafePoster v{BOT_VERSION} 로드됨")
        self.log(f"[부팅] 경로: {os.path.abspath(__file__)}")

    def log(self, message):
        """Logs message to console and GUI if callback provided."""
        try:
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            formatted = f"[{timestamp}] {message}"
            try:
                print(formatted)
            except UnicodeEncodeError:
                # Fallback for systems with non-UTF8 console
                print(formatted.encode('ascii', 'ignore').decode('ascii'))
        except: 
            pass # Never let logging crash the bot

        if self.log_callback:
            self.log_callback(message)

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
        self.driver.implicitly_wait(0.5) # Reduced from 10s to eliminate delays

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

    def find_image_files(self, folder_path, pattern_prefix):
        """Finds all files starting with the given prefix in the folder."""
        if not os.path.isdir(folder_path):
            print(f"[WARN] Directory not found: {folder_path}")
            return []
        
        search_pattern = os.path.join(folder_path, f"{pattern_prefix}*")
        files = [f for f in glob.glob(search_pattern) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        
        # Sort files to ensure 1, 2, 3 order if named that way
        files.sort()
        return files

    def process_row(self, row_index, sequence_str="전-E-후-F-J", stop_flag_callback=None):
        """Processes a single row from the main sheet with a specific sequence."""
        # Check stop flag at the beginning
        if stop_flag_callback and stop_flag_callback():
            self.log("[중단] 작업이 중단되었습니다.")
            return
        # Note: gspread uses 1-based indexing for rows/cols
        # C=3, D=4, F=6, G=7, H=8, I=9, J=10
        
        try:
            # Save Main Window Handle
            main_window = self.driver.current_window_handle
            
            # Fetch data for the specific row
            row_values = self.main_sheet.row_values(row_index)
            
            # Should have enough columns. Pad if necessary.
            if len(row_values) < 10:
                print(f"Row {row_index} does not have enough data.")
                # You might handle this more gracefully
                pass

            # Correct Mapping (0-indexed) based on LATEST structure:
            # B(1)=Name, C(2)=ID, D(3)=PW, E(4)=BeforeText, F(5)=AfterText, G(6)=Cafe, H(7)=Board, I(8)=Title, J(9)=Body, K(10)=Folder, L(11)=URL
            
            self.log(f"[디그버] 행 {row_index} 원본 데이터: {row_values}")
            
            user_id = row_values[2].strip() if len(row_values) > 2 else "" # C column
            user_pw = row_values[3].strip() if len(row_values) > 3 else "" # D column
            
            before_text = row_values[4].strip() if len(row_values) > 4 else "" # E column
            after_text = row_values[5].strip() if len(row_values) > 5 else ""  # F column
            
            cafe_name_key = row_values[6].strip() if len(row_values) > 6 else "" # G column
            board_name = row_values[7].strip() if len(row_values) > 7 else ""    # H column
            title = row_values[8].strip() if len(row_values) > 8 else ""         # I column
            body_text = row_values[9].strip() if len(row_values) > 9 else ""     # J column
            image_folder = row_values[10].strip() if len(row_values) > 10 else "" # K column
            
            self.log(f"[정보] 데이터 매핑: BeforeText='{before_text}', AfterText='{after_text}', Folder='{image_folder}'")

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

            time.sleep(0.3)  # Ultra fast

            # 7. Switch to new window
            current_window = self.driver.current_window_handle
            window_handles = self.driver.window_handles
            if len(window_handles) > 1:
                new_window = [w for w in window_handles if w != current_window][-1]
                self.driver.switch_to.window(new_window)
            
            time.sleep(0.3)  # Ultra fast

            # 8. Title Entry
            try:
                title_area = self.driver.find_element(By.CLASS_NAME, "textarea_input")
                title_area.click()
                
                # Use clipboard to support emojis (ChromeDriver BMP fix)
                pyperclip.copy(title)
                webdriver.ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                self.log(f"[진행] 제목 입력 완료: {title}")
            except NoSuchElementException:
                self.log("[오류] 제목 입력칸 찾기 실패")

            time.sleep(0.2)  # Ultra fast

            # Define Logic
            def append_text(text):
                if not text: return
                try:
                    # Click body and force cursor to the very bottom
                    body_elem = self.driver.find_element(By.XPATH, "//div[contains(@class, 'se-content')] | //div[contains(@class, 'se-main_container')]")
                    self.driver.execute_script("arguments[0].click();", body_elem)
                    
                    # More aggressive cursor movement to ensure absolute end
                    actions = webdriver.ActionChains(self.driver)
                    for _ in range(2):
                        actions.key_down(Keys.CONTROL).send_keys(Keys.END).key_up(Keys.CONTROL).perform()
                        actions.send_keys(Keys.END).perform()
                        time.sleep(0.01)
                    
                    pyperclip.copy(text)
                    webdriver.ActionChains(self.driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    time.sleep(0.05)
                except Exception as e:
                    self.log(f"[오류] 본문 입력 실패: {e}")

            def handle_attachment_popup():
                """Detects and clicks 'Individual Photo' in the attachment method popup if it appears."""
                try:
                    # Broader XPath for '개별사진' to handle different structures
                    popup_xpath = "//*[text()='개별사진' or contains(text(), '개별사진')]"
                    popups = self.driver.find_elements(By.XPATH, popup_xpath)
                    for p in popups:
                        if p.is_displayed():
                            self.log("[시스템] 사진 첨부 방식 팝업 감지. 즉시 선택 중...")
                            # Force click via JS for speed
                            self.driver.execute_script("arguments[0].click();", p)
                            time.sleep(0.1)  # Faster
                            return True
                except: pass
                return False

            def wait_for_ready():
                """Minimal wait for overlays."""
                for i in range(3): # Max 0.3 seconds
                    try:
                        handle_attachment_popup()
                        dims = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='dim'], div[class*='popup-dim']")
                        active_dims = [d for d in dims if d.is_displayed()]
                        if not active_dims:
                            break
                        time.sleep(0.1)
                    except: break

            def upload_images_batch(paths):
                if not paths: return
                self.log(f"[이미지] {len(paths)}개 일괄 업로드")
                
                try:
                    # Click image button ONCE
                    image_selectors = [
                        (By.CSS_SELECTOR, "button.se-image-toolbar-button"),
                        (By.CSS_SELECTOR, ".se-toolbar-button-image"),
                        (By.XPATH, "//button[contains(@class, 'se-image-toolbar-button')]"),
                        (By.XPATH, "//button[contains(@class, 'image')]")
                    ]
                    
                    img_btn = None
                    for by, val in image_selectors:
                        try:
                            img_btn = self.driver.find_element(by, val)
                            if img_btn and img_btn.is_displayed(): break
                        except: continue
                    
                    if img_btn:
                        self.driver.execute_script("arguments[0].click();", img_btn)
                        time.sleep(0.2)
                        handle_attachment_popup()
                        time.sleep(0.1)
                    
                    # Find file input
                    file_input = None
                    for attempt in range(5):
                        try:
                            file_inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                            for fi in file_inputs:
                                try:
                                    if fi.is_enabled():
                                        file_input = fi
                                        break
                                except: continue
                            if file_input: break
                            time.sleep(0.1)
                        except:
                            time.sleep(0.1)
                    
                    if file_input:
                        # Make visible
                        self.driver.execute_script("""
                            arguments[0].style.display = 'block';
                            arguments[0].style.visibility = 'visible';
                            arguments[0].style.opacity = '1';
                        """, file_input)
                        
                        # Upload ALL images at once with newline separator
                        abs_paths = [os.path.abspath(p) for p in paths if os.path.exists(os.path.abspath(p))]
                        if abs_paths:
                            joined_paths = "\n".join(abs_paths)
                            file_input.send_keys(joined_paths)
                            self.log(f"  ✓ {len(abs_paths)}개 일괄 전송 완료")
                            
                            # Wait for upload to process
                            time.sleep(0.3 * len(abs_paths))  # 0.3s per image
                        else:
                            self.log("  ✗ 유효한 파일 없음")
                    else:
                        self.log("  ✗ 파일 입력 요소 못찾음")
                    
                    # Final wait
                    time.sleep(0.3)
                    wait_for_ready()
                    
                    try:
                        webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                    except: pass
                    
                except Exception as e:
                    self.log(f"[오류] 이미지 업로드 실패: {e}")
                    import traceback
                    self.log(f"[상세] {traceback.format_exc()}")

            def insert_newlines(count=1):
                try:
                    # Ensure at end
                    webdriver.ActionChains(self.driver).send_keys(Keys.END).perform()
                    time.sleep(0.02)
                    webdriver.ActionChains(self.driver).key_down(Keys.CONTROL).send_keys(Keys.END).key_up(Keys.CONTROL).perform()
                    time.sleep(0.03)
                    for _ in range(count):
                        webdriver.ActionChains(self.driver).send_keys(Keys.ENTER).perform()
                        # Removed extra wait
                except: pass

            # 9. Dynamic Content Injection
            # sequence_str: e.g. "전-E-후-F-J"
            # 전: Before images, E: Before text, 후: After images, F: After text, J: Body text
            
            abs_folder = os.path.abspath(image_folder)
            self.log(f"[이미지관련] 통합 경로 확인: {abs_folder}")
            
            # Map codes to actions
            def action_before_img():
                imgs = self.find_image_files(abs_folder, "전")
                if imgs:
                    upload_images_batch(imgs)
                    insert_newlines(1)
                else: self.log("[정보] '전' 이미지 없음")

            def action_after_img():
                imgs = self.find_image_files(abs_folder, "후")
                if imgs:
                    upload_images_batch(imgs)
                    insert_newlines(1)
                else: self.log("[정보] '후' 이미지 없음")

            def action_before_text():
                if before_text:
                    self.log(f"[본문] E열(전 설명) 입력: {before_text}")
                    append_text(before_text)
                    insert_newlines(1)

            def action_after_text():
                if after_text:
                    self.log(f"[본문] F열(후 설명) 입력: {after_text}")
                    append_text(after_text)
                    insert_newlines(1)

            def action_body_text():
                if body_text:
                    self.log(f"[본문] J열(메인 본문) 입력 시작 ({len(body_text)}자)")
                    append_text(body_text)
                else: self.log("[경고] J열 본문 비어있음")

            dispatcher = {
                "전": action_before_img,
                "E": action_before_text,
                "후": action_after_img,
                "F": action_after_text,
                "J": action_body_text
            }

            self.log(f"[실행] 지정된 순서로 포스팅 시작: {sequence_str}")
            if not sequence_str or sequence_str.strip() == "":
                self.log("[치명적 오류] 실행할 순서가 지정되지 않았습니다.")
                self.log("[안내] GUI에서 드롭다운 메뉴로 순서를 선택해주세요.")
                return

            codes = sequence_str.split("-")
            valid_action_taken = False
            for code in codes:
                code = code.strip()
                if code in dispatcher:
                    dispatcher[code]()  # Execute action
                    time.sleep(0.1)  # Small delay after action
                    wait_for_ready()  # AFTER action, not before
                    valid_action_taken = True
                else:
                    self.log(f"[경고] 알 수 없는 순서 코드: {code}")

            if not valid_action_taken:
                self.log("[치명적 오류] 유효한 순서 코드가 없어 작업을 중단합니다.")
                self.log("[안내] 최소 하나 이상의 항목을 선택해주세요 (전사진, 수술전 문구, 후사진, 수술후 문구, 본문)")
                return

            time.sleep(0.5)  # Reduced from 2s

            # 10. Adjust settings before registration
            try:
                try:
                    self.log("[시스템] '전체공개' 설정 시도 (JS)...")
                    all_radio = self.driver.find_element(By.ID, "all")
                    self.driver.execute_script("arguments[0].click();", all_radio)
                    self.log("[시스템] '전체공개' 설정 완료")
                except Exception as inner_e:
                    self.log(f"[경고] 설정 클릭 실패: {inner_e}")
            except Exception as e:
                self.log(f"[경고] 설정 메뉴 열기 실패 (이미 열려있을 수 있음): {e}")

            # 11. Click Register
            try:
                # Scroll to bottom if needed
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                wait_for_ready() # Final check
                
                try:
                    register_btn = self.driver.find_element(By.XPATH, "//span[@class='BaseButton__txt' and text()='등록']")
                    self.driver.execute_script("arguments[0].click();", register_btn)
                    self.log("[성공] '등록' 버튼 클릭 완료 (JS)")
                except:
                    # Fallback
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
                        # Use English names to avoid Unicode/Locale encoding errors on some PCs
                        days_eng = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                        day_str = days_eng[now.weekday()]
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
            self.log(f"[치명적 오류] 행 {row_index} 처리 중 실패: {e}")
            traceback.print_exc()
        finally:
            # Cleanup Windows: Close any window that isn't the main handle
            try:
                all_handles = self.driver.window_handles
                for h in all_handles:
                    if h != main_window:
                        self.driver.switch_to.window(h)
                        self.driver.close()
                self.driver.switch_to.window(main_window)
                self.log(f"▶ 작업 종료: 행 {row_index} (세션 초기화 완료)")
            except: pass

    def get_pending_rows(self):
        """Fetches rows from Main sheet where URL (Col K / Index 10) is empty."""
        if not self.connect_to_sheets():
            return []
            
        all_values = self.main_sheet.get_all_values()
        pending_rows = []
        
        self.log(f"[디버그] 시트 전체 행 수: {len(all_values)}")
        if len(all_values) >= 4:
            test_row = all_values[3]
            self.log(f"[디버그] 4행 데이터 샘플: 이름={test_row[1] if len(test_row)>1 else 'N/A'}, URL필드={test_row[11] if len(test_row)>11 else 'N/A'}")

        # Start from row 4 (index 3)
        for i in range(3, len(all_values)):
            row = all_values[i]
            # Ensure row has at least Column B
            if len(row) <= 1: continue 
            
            name = row[1].strip()
            if not name: continue # Skip empty rows
            
            # Check Column L (index 11) for Post URL
            url = row[11].strip() if len(row) > 11 else ""
            
            if not url:
                 pending_rows.append({
                     'index': i + 1,
                     'name': name,
                     'cafe': row[6] if len(row) > 6 else "",
                     'board': row[7] if len(row) > 7 else "",
                     'title': row[8] if len(row) > 8 else "",
                     'schedule': row[13].strip() if len(row) > 13 else "" # N column
                 })
                     
        return pending_rows

    def run(self, target_rows=None, sequences=None, stop_flag_callback=None):
        """
        Runs the automation.
        :param target_rows: List of 1-based row indices to process.
        :param sequences: Dict mapping row index to sequence string.
        :param stop_flag_callback: Function that returns True if execution should stop.
        """
        if not self.connect_to_sheets():
            return
        
        self.setup_driver()
        
        if target_rows:
            print(f"[INFO] Processing specific rows: {target_rows}")
            for row_idx in target_rows:
                # Check stop flag before each row
                if stop_flag_callback and stop_flag_callback():
                    self.log("[중단] 사용자 요청으로 중단합니다.")
                    break
                    
                # Get specific sequence for this row if provided
                seq = "전-E-후-F-J" # Default
                if sequences and str(row_idx) in sequences:
                    seq = sequences[str(row_idx)]
                elif sequences and row_idx in sequences:
                    seq = sequences[row_idx]
                
                self.process_row(row_idx, sequence_str=seq, stop_flag_callback=stop_flag_callback)
                # Reduced sleep between rows
                time.sleep(0.5)
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

