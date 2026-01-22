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
    def __init__(self):
        self.driver = None
        self.sheet_client = None
        self.main_sheet = None
        self.board_sheet = None

    def setup_driver(self):
        """Initializes the Chrome driver with options."""
        options = Options()
        # Headless Mode Settings
        options.add_argument("--headless=new") # Modern headless mode
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        options.add_experimental_option("detach", True)
        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0
        })
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.maximize_window()
        self.driver.implicitly_wait(10)

    def connect_to_sheets(self):
        """Connects to Google Sheets using service account."""
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"Error: {CREDENTIALS_FILE} not found. Please place it in the script directory.")
            return False

        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/spreadsheets",
                 "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
        
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        self.sheet_client = gspread.authorize(creds)
        
        try:
            full_sheet = self.sheet_client.open_by_url(SHEET_URL)
            self.main_sheet = full_sheet.get_worksheet(0) # First sheet
            self.board_sheet = full_sheet.worksheet("게시판") # Sheet named "게시판"
            print("Successfully connected to Google Sheets.")
            return True
        except Exception as e:
            print(f"Failed to open sheets: {e}")
            return False

    def get_cafe_url(self, cafe_name):
        """Finds the Cafe URL from the '게시판' sheet based on cafe name."""
        try:
            # Assuming Cafe Name is in Col B (index 2) and URL is in Col A (index 1)
            # data_range = self.board_sheet.get_all_values()
            # Iterating to find match. Creating a map might be more efficient for multiple, 
            # but for simplicity we search linearly or fetch all.
            records = self.board_sheet.get_all_values()
            
            # Skip header if row 1 is header, user said A2:A contains URL, B2:B contains Name
            for row in records[1:]: # Starting from row 2 (index 1)
                if len(row) >= 2:
                    url = row[0] # A column
                    name = row[1] # B column
                    if name.strip() == cafe_name.strip():
                        return url
            return None
        except Exception as e:
            print(f"Error finding cafe URL: {e}")
            return None

    def login_naver(self, user_id, user_pw):
        """Logs into Naver using clipboard method."""
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
        
        # Check for "new device" warning or captcha (simple wait for now)
        # If user interaction is needed, 
        # normally we might need to wait for manual intervention or handle specific cases.
        # For this script we assume login succeeds or user handles hiccups manually if watching.
        
        # Verify login (optional check, e.g. finding logout button)

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
                print(f"Skipping row {row_index}: Missing ID, PW, or Cafe Name.")
                return

            print(f"Processing Row {row_index}: {cafe_name_key} - {title}")

            # 1. Login
            # Note: This simple logic re-logs in every time. 
            # Optimization: Check if already logged in as correct user.
            # But for safety and clearing state, we might restart or re-login.
            # Let's try to just go to login page.
            self.login_naver(user_id, user_pw)

            # 2. Get Cafe URL
            cafe_url = self.get_cafe_url(cafe_name_key)
            if not cafe_url:
                print(f"Cafe URL not found for: {cafe_name_key}")
                return

            # 3. Navigate to Cafe
            self.driver.get(cafe_url)
            time.sleep(2)

            # 4. Switch Iframe
            try:
                WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
                print("Switched to cafe_main frame")
            except TimeoutException:
                print("Could not switch to cafe_main frame (Timeout)")
                return
            except Exception as e:
                print(f"Could not switch to cafe_main frame: {e}")
                return
                
            # 5. Click Board Name (G4 from request -> board_name)
            # 5. Click Board Name (G4 from request -> board_name)
            # Try finding in iframe first
            board_found = False
            try:
                board_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, board_name)
                board_link.click()
                board_found = True
                print(f"Clicked board '{board_name}' inside iframe.")
            except NoSuchElementException:
                print(f"Board '{board_name}' not found in iframe. Checking default content...")
            
            if not board_found:
                # Switch back to default content and try
                self.driver.switch_to.default_content()
                try:
                    board_link = self.driver.find_element(By.PARTIAL_LINK_TEXT, board_name)
                    board_link.click()
                    board_found = True
                    print(f"Clicked board '{board_name}' in default content.")
                    
                    # If clicked in default content, we usually need to switch BACK to cafe_main for content
                    # But wait, did the click cause a navigation?
                    time.sleep(2)
                    # Re-switch to cafe_main for the "Write" button later
                    try:
                         WebDriverWait(self.driver, 10).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
                    except:
                         print("Could not switch back to cafe_main after board click")
                         
                except NoSuchElementException:
                    print(f"[INFO] Board '{board_name}' not found in default content either.")
                    return

            print(f"[INFO] Board selection complete. Waiting for editor...")
            time.sleep(3)

            # Re-verify we are in the editor window/frame
            # Sometimes clicking board opens a new window, sometimes just navigation.
            # If we are here, we assume we are ready to find 'Write' button.


            # 6. Click '글쓰기' (span class='BaseButton__txt')
            try:
                # Using XPath for exact class match or text
                # User specified class 'BaseButton__txt', usually it's inside a button or link
                # Trying to find the "글쓰기" button specifically
                # XPath: //span[@class='BaseButton__txt' and text()='글쓰기']
                 write_btn = self.driver.find_element(By.XPATH, "//span[@class='BaseButton__txt' and contains(text(), '글쓰기')]")
                 write_btn.click()
            except NoSuchElementException:
                print("'글쓰기' button not found.")
                return

            time.sleep(3)

            # 7. Switch to new window
            # The editor opens in a new tab/window usually
            current_window = self.driver.current_window_handle
            window_handles = self.driver.window_handles
            if len(window_handles) > 1:
                new_window = [w for w in window_handles if w != current_window][-1]
                self.driver.switch_to.window(new_window)
                print("Switched to editor window.")
            else:
                print("New window did not appear?")
                # Sometimes it might stay in same window depending on settings, but usually new.

            time.sleep(3)

            # 8. Title Entry (textarea class='textarea_input')
            # 8. Title Entry
            try:
                 title_area = self.driver.find_element(By.CLASS_NAME, "textarea_input")
                 title_area.click()
                 title_area.send_keys(title)
            except NoSuchElementException:
                print("Title input not found.")

            time.sleep(1)

            # Define Helper for Body Text
            def append_text(text):
                if not text: return
                try:
                    # Focus body
                    # Try clicking the main content area wrapper to ensure focus
                    body_elem = self.driver.find_element(By.XPATH, "//div[contains(@class, 'se-content')] | //div[contains(@class, 'se-main_container')]")
                    body_elem.click()
                    time.sleep(0.5)
                    
                    # Move to END of DOCUMENT before pasting
                    webdriver.ActionChains(self.driver).key_down(Keys.CONTROL).send_keys(Keys.END).key_up(Keys.CONTROL).perform()
                    time.sleep(0.2)
                    
                    # Copy & Paste
                    pyperclip.copy(text)
                    actions = webdriver.ActionChains(self.driver)
                    actions.key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
                    time.sleep(0.5)
                except Exception as e:
                    print(f"[ERROR] text append failed: {e}")

            # Define Helper for Image Upload (Try No-Click first)
            def upload_image(path):
                if not path: return
                print(f"[INFO] Uploading image: {path}")
                uploaded = False
                
                # Try 1: Find existing input and send keys (Invisible or Visible)
                try:
                    # Strategy: Click Button -> Send Keys to Input
                    # We add retries and re-fetches to handle StaleElementReferenceException
                    
                    # 1. Click Button (Retry loop)
                    for _ in range(3):
                        try:
                            # Re-find button each time
                            img_btn = self.driver.find_element(By.CSS_SELECTOR, ".se-image-toolbar-button")
                            img_btn.click()
                            time.sleep(1)
                            break
                        except Exception:
                            time.sleep(1)

                    # 2. Find Input and Send Keys
                    # Re-find input carefully
                    file_input = None
                    for _ in range(3):
                        try:
                             file_inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
                             if file_inputs:
                                 file_input = file_inputs[0]
                                 break
                        except:
                            time.sleep(1)
                            
                    if file_input:
                        try:
                            # Make visible just in case
                            self.driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible'; arguments[0].style.opacity = '1';", file_input)
                            
                            file_input.send_keys(path)
                            
                            # Trigger change - Wrap in try-catch in JS to avoid crash
                            try:
                                self.driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", file_input)
                            except: pass
                            
                            print("[SUCCESS] Image sent to input.")
                            uploaded = True
                            time.sleep(4) # Increased wait to avoid StaleElement on rapid DOM changes
                            
                            # 3. Try closing dialog blindly (best effort)
                            try:
                                 webdriver.ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                            except: pass
                        except Exception as inner_e:
                             print(f"[WARN] Error interacting with input: {inner_e}")
                    else:
                        print("[ERROR] File input not found after click.")
                    
                except Exception as e:
                    print(f"[WARN] Upload failed: {e}")

                if not uploaded:
                    print("[ERROR] Failed to upload image.")
            
            # Helper to insert newlines
            def insert_newlines(count=1):
                try:
                    actions = webdriver.ActionChains(self.driver)
                    actions.send_keys(Keys.END) # Ensure at end
                    for _ in range(count):
                        actions.key_down(Keys.ENTER).key_up(Keys.ENTER)
                    actions.perform()
                    time.sleep(0.5)
                except: pass

            # --- SEQUENCE START ---
            
            # 1. Before Image
            img_before = self.find_image_file(image_folder, "전")
            if img_before:
                upload_image(img_before)
                append_text("수술전")
                insert_newlines(1) # Start new line
            
            # 2. After Image
            img_after = self.find_image_file(image_folder, "후")
            if img_after:
                upload_image(img_after)
                
            # 3. Column E Text (Review Text) + 4. Main Body Content (Col I)
            # Combine them to strictly ensure order
            review_text = row_values[4] if len(row_values) > 4 else ""
            final_text = ""
            
            if review_text:
                final_text += review_text + "\n\n"
            
            # 4. Main Body Content (Col I)
            if content:
                final_text += content

            if final_text:
                print(f"[INFO] Appending Final Combined Text ({len(final_text)} chars)...")
                append_text(final_text)

            # --- SEQUENCE END ---

            time.sleep(2)

            # 11. Click Register (Post)
            try:
                print("[INFO] Attempting to click Register button...")
                register_btn = self.driver.find_element(By.XPATH, "//span[@class='BaseButton__txt' and text()='등록']")
                register_btn.click()
                print("[SUCCESS] Clicked Register.")
            except NoSuchElementException:
                print("[ERROR] Register button not found.")
                return 

            # 12. Post-Registration Processing
            print("[INFO] Waiting for post completion...")
            time.sleep(5) 
            
            try:
                # Need to find the success URL button.
                # It could be in default content OR cafe_main.
                # Process: Check cafe_main first (most likely), then default.
                
                url_btn = None
                
                # Try 1: Inside cafe_main (often the case after refresh)
                try:
                    self.driver.switch_to.default_content()
                    WebDriverWait(self.driver, 5).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "cafe_main")))
                    url_btn = self.driver.find_element(By.CLASS_NAME, "button_url")
                    print("[INFO] Found URL button in cafe_main.")
                except:
                     pass

                # Try 2: Default content (if not in iframe)
                if not url_btn:
                    try:
                        self.driver.switch_to.default_content()
                        url_btn = self.driver.find_element(By.CLASS_NAME, "button_url")
                        print("[INFO] Found URL button in default content.")
                    except:
                        pass
                
                if url_btn:
                    url_btn.click()
                    time.sleep(1)
                    
                    # Get URL from clipboard
                    post_url = pyperclip.paste()
                    print(f"[SUCCESS] Post URL: {post_url}")
                    
                    # Timestamp
                    now = datetime.datetime.now()
                    days = ["월", "화", "수", "목", "금", "토", "일"]
                    day_str = days[now.weekday()]
                    timestamp = now.strftime(f"%Y-%m-%d ({day_str}) %H:%M")
                    
                    # Update Sheet
                    try:
                        self.main_sheet.update_cell(row_index, 11, post_url)
                        self.main_sheet.update_cell(row_index, 12, timestamp)
                        print(f"[SUCCESS] Updated sheet for row {row_index}")
                    except Exception as sheet_e:
                        print(f"[ERROR] Failed to write to sheet: {sheet_e}")

                else:
                    print("[ERROR] Could not find URL copy button.")
                    self.driver.save_screenshot("debug_post_fail.png")
            except Exception as e:
                print(f"[ERROR] Error in post-processing: {e}")


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

