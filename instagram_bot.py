import os
import sys
import time
import base64
import hashlib
import hmac
import struct
import json
import logging
import gc
import shutil
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

logger = logging.getLogger(__name__)

# The target Facebook Business Suite login page url - EXACTLY FROM 099.py
FB_LOGIN_URL = (
    "https://business.facebook.com/business/loginpage/"
    "?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs"
    "&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO"
    "&config_ref=biz_login_tool_flavor_mbs"
)

class InstagramBot:
    def __init__(self, headless=True):
        self.driver = None
        self.headless = headless
        self.temp_dir = None
        self.username = None
        self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver - EXACTLY LIKE 099.py"""
        try:
            import tempfile
            self.temp_dir = tempfile.mkdtemp(prefix='chrome_profile_')
            
            options = Options()
            options.add_argument(f'--user-data-dir={self.temp_dir}')
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Auto-disable notification prompts - EXACTLY FROM 099.py
            prefs = {"profile.default_content_setting_values.notifications": 2}
            options.add_experimental_option("prefs", prefs)
            
            # Auto-detect headless - EXACTLY FROM 099.py
            is_linux = sys.platform.startswith('linux')
            is_headless = is_linux and not os.environ.get("DISPLAY")
            
            if self.headless or is_headless:
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--lang=en-US")
                options.add_argument("--window-size=1920,1080")
            else:
                options.add_argument("--start-maximized")
            
            # Use Chromium for Railway
            chromium_paths = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']
            for path in chromium_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    break
            
            chromedriver_paths = ['/usr/bin/chromedriver', '/usr/local/bin/chromedriver']
            service = None
            for path in chromedriver_paths:
                if os.path.exists(path):
                    service = Service(path)
                    break
            
            if service:
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
            
            # Set webdriver property to undefined - EXACTLY FROM 099.py
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
            logger.info("ChromeDriver initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize Chrome Driver: {e}")
            self._cleanup_temp_dir()
            raise
    
    def _cleanup_temp_dir(self):
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
            except Exception as e:
                logger.warning(f"Could not cleanup temp dir: {e}")
            finally:
                self.temp_dir = None
    
    def get_username(self):
        return self.username
    
    def parse_cookie_header_string(self, cookie_str):
        """Parses standard cookie header string format - EXACTLY FROM 099.py"""
        cookies = []
        pairs = cookie_str.strip().split(';')
        for pair in pairs:
            pair = pair.strip()
            if not pair or '=' not in pair:
                continue
            key, value = pair.split('=', 1)
            cookies.append({
                "name": key.strip(),
                "value": value.strip(),
                "domain": ".instagram.com",
                "path": "/"
            })
        return cookies
    
    def sanitize_cookie(self, cookie):
        """Sanitize cookie - EXACTLY FROM 099.py"""
        valid_cookie = {}
        if "name" in cookie:
            valid_cookie["name"] = str(cookie["name"])
        if "value" in cookie:
            valid_cookie["value"] = str(cookie["value"])
        
        domain = str(cookie.get("domain", ".instagram.com"))
        valid_cookie["domain"] = domain if domain.startswith(".") else f".{domain}"
        valid_cookie["path"] = str(cookie.get("path", "/"))
        
        if "secure" in cookie and isinstance(cookie["secure"], bool):
            valid_cookie["secure"] = cookie["secure"]
        if "httpOnly" in cookie and isinstance(cookie["httpOnly"], bool):
            valid_cookie["httpOnly"] = cookie["httpOnly"]
        
        return valid_cookie
    
    def handle_continue_screen(self):
        """Detects and clicks the blue 'Continue' button - EXACTLY FROM 099.py"""
        logger.info("Checking for 'Continue' button on One Tap screen...")
        
        continue_selectors = [
            "//button[contains(text(), 'Continue')]",
            "//button[contains(., 'Continue')]",
            "//a[contains(text(), 'Continue')]",
            "//div[@role='button' and contains(., 'Continue')]",
            "//button[type='button' and contains(., 'Continue')]"
        ]
        
        for selector in continue_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for el in elements:
                    if el.is_displayed():
                        logger.info(f"Found 'Continue' button with text: '{el.text.strip()}'. Clicking...")
                        try:
                            el.click()
                        except Exception as click_err:
                            logger.info(f"Standard click failed ({click_err}), using JS click...")
                            self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(5)
                        return True
            except Exception as e:
                continue
                
        logger.info("No active 'Continue' button detected.")
        return False
    
    def perform_cookie_login(self, cookies):
        """Performs login using cookies - EXACTLY FROM 099.py"""
        try:
            logger.info("\nAttempting cookie-based login...")
            
            # Step 1: Establish domain context
            logger.info("Navigating to Instagram to establish domain context...")
            self.driver.get("https://www.instagram.com")
            time.sleep(3)
            
            # Step 2: Inject cookies
            logger.info(f"Injecting {len(cookies)} cookies...")
            injected_count = 0
            for cookie in cookies:
                try:
                    clean_cookie = self.sanitize_cookie(cookie)
                    self.driver.add_cookie(clean_cookie)
                    injected_count += 1
                except Exception as e:
                    logger.warning(f"Skipped cookie ({cookie.get('name')}): {e}")
                    
            logger.info(f"Successfully injected {injected_count} cookies.")
            
            # Step 3: Reload page
            logger.info("Reloading page with injected session...")
            self.driver.refresh()
            time.sleep(5)
            
            # Step 4: Handle One-Tap 'Continue' screen
            self.handle_continue_screen()
            
            # Step 5: Verify final login status
            current_url = self.driver.current_url.lower()
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            nav_elements = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'direct/inbox') or contains(@href, 'explore') or @aria-label='Home']")
            
            is_logged_in = False
            if any(kw in current_url for kw in ["accounts/onetap", "instagram.com/direct", "instagram.com/explore"]) or len(nav_elements) > 0:
                is_logged_in = True
            elif "login" not in current_url and "phone number, username, or email" not in body_text:
                is_logged_in = True
            
            # Extract username
            if is_logged_in:
                try:
                    # Try to get username from URL
                    if "instagram.com" in current_url:
                        username_match = re.search(r'instagram\.com/([^/?]+)', current_url)
                        if username_match and username_match.group(1) not in ['direct', 'explore', 'accounts']:
                            self.username = username_match.group(1)
                            logger.info(f"Extracted username from URL: {self.username}")
                    
                    if not self.username:
                        # Try to get username from profile link
                        profile_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/') and contains(@href, '_')]")
                        for link in profile_links:
                            href = link.get_attribute('href')
                            if '/accounts/' not in href and '/p/' not in href and '/explore/' not in href:
                                username = href.split('/')[-1] if href.endswith('/') else href.split('/')[-1]
                                if username and len(username) > 3 and username not in ['direct', 'explore', 'accounts']:
                                    self.username = username
                                    logger.info(f"Extracted username from profile: {self.username}")
                                    break
                    
                    if not self.username:
                        body_text = self.driver.find_element(By.TAG_NAME, "body").text
                        username_match = re.search(r'@([a-zA-Z0-9_.]+)', body_text)
                        if username_match:
                            self.username = username_match.group(1)
                            logger.info(f"Extracted username from text: {self.username}")
                except Exception as e:
                    logger.warning(f"Could not extract username: {e}")
                    self.username = "Unknown"

            logger.info("\n================ LOGIN RESULT ================")
            if is_logged_in:
                logger.info(f"STATUS: SUCCESS ✅ - Authenticated via cookies! (Username: {self.username})")
                logger.info(f"Current URL: {self.driver.current_url}")
                return True
            else:
                logger.error("STATUS: FAILED ❌ - Cookie expired or invalid.")
                logger.info(f"Current URL: {self.driver.current_url}")
                return False
            logger.info("===============================================")
            
        except Exception as e:
            logger.error(f"Error during cookie login: {e}")
            return False
    
    def handle_cookies(self):
        """Handle cookie consent - EXACTLY FROM 099.py"""
        try:
            cookie_texts = [
                "Allow all cookies", "Allow essential and optional cookies", 
                "Decline optional cookies", "Accept All", "Accept", "Allow", "Agree",
                "Allow essential", "Accept cookies"
            ]
            for text in cookie_texts:
                btns = self.driver.find_elements(By.XPATH, f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        logger.info(f"Clicked cookie/consent dialog button: '{text}'")
                        time.sleep(2)
                        return
        except Exception:
            pass
    
    def perform_login_inputs(self, username, password):
        """Perform login inputs - EXACTLY FROM 099.py"""
        logger.info("Locating username and password fields...")
        username_field = None
        password_field = None
        
        start_wait = time.time()
        while time.time() - start_wait < 30:
            selectors_user = [
                (By.NAME, "username"),
                (By.NAME, "email"),
                (By.XPATH, "//input[@name='username' or @name='email']"),
                (By.XPATH, "//input[contains(@placeholder, 'username') or contains(@placeholder, 'Phone number') or contains(@placeholder, 'Email') or contains(@placeholder, 'Mobile number')]")
            ]
            for by_type, selector in selectors_user:
                try:
                    elems = self.driver.find_elements(by_type, selector)
                    if elems:
                        displayed_elems = [el for el in elems if el.is_displayed()]
                        username_field = displayed_elems[0] if displayed_elems else elems[0]
                        break
                except Exception:
                    continue
            
            selectors_pass = [
                (By.NAME, "password"),
                (By.NAME, "pass"),
                (By.XPATH, "//input[@name='password' or @name='pass']"),
                (By.XPATH, "//input[contains(@placeholder, 'Password') or contains(@placeholder, 'password')]")
            ]
            for by_type, selector in selectors_pass:
                try:
                    elems = self.driver.find_elements(by_type, selector)
                    if elems:
                        displayed_elems = [el for el in elems if el.is_displayed()]
                        password_field = displayed_elems[0] if displayed_elems else elems[0]
                        break
                except Exception:
                    continue
            
            if username_field and password_field:
                break
            time.sleep(1)
            
        if not username_field or not password_field:
            logger.error("Failed to locate login input fields.")
            return False
            
        logger.info("Submitting login credentials...")
        username_field.clear()
        username_field.send_keys(username)
        password_field.clear()
        password_field.send_keys(password)
        
        login_btn = None
        btn_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "//button[contains(text(), 'Log in') or contains(text(), 'Log In')]",
            "//input[@type='submit']",
            "button"
        ]
        for sel in btn_selectors:
            try:
                if sel.startswith("//"):
                    elems = self.driver.find_elements(By.XPATH, sel)
                else:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elems:
                    displayed_elems = [el for el in elems if el.is_displayed()]
                    login_btn = displayed_elems[0] if displayed_elems else elems[0]
                    break
            except:
                continue
                
        if login_btn:
            try:
                login_btn.click()
            except Exception as click_err:
                try:
                    self.driver.execute_script("arguments[0].click();", login_btn)
                except Exception as js_err:
                    username_field.submit()
        else:
            username_field.submit()
        return True
    
    def handle_interactive_verification(self, two_factor_key=None):
        """Handle interactive verification - EXACTLY FROM 099.py"""
        last_url = ""
        logger.info("\nEntering interactive verification check...")
        while True:
            try:
                current_url = self.driver.current_url.lower()
                logger.info(f"[STATUS] Verification Check... (URL: {self.driver.current_url})")
            except:
                break
                
            if len(self.driver.window_handles) == 1 and "business.facebook.com" in current_url:
                break
                
            if "accounts/onetap" in current_url or "accounts/onetap/" in current_url:
                logger.info("Successfully reached Instagram onetap/login page.")
                break
                
            if "instagram.com" in current_url and current_url.rstrip("/") == "https://www.instagram.com":
                logger.info("Successfully reached Instagram Home page.")
                break
                
            try:
                text_inputs = self.driver.find_elements(By.XPATH, "//input[@type='text' or @type='number' or not(@type)]")
                visible_inputs = [inp for inp in text_inputs if inp.is_displayed()]
            except:
                visible_inputs = []
                
            if not visible_inputs:
                try:
                    action_buttons = self.driver.find_elements(By.XPATH, "//button | //a[@role='button'] | //div[@role='button']")
                    visible_buttons = [btn for btn in action_buttons if btn.is_displayed() and btn.text.strip()]
                except:
                    visible_buttons = []
                    
                if visible_buttons:
                    body_text = ""
                    try:
                        body_text = self.driver.find_element(By.TAG_NAME, "body").text
                    except:
                        pass
                    logger.info(f"\n--- Verification Action Required ---")
                    logger.info(f"Current URL: {self.driver.current_url}")
                    logger.info(f"Page Message: {body_text[:500]}...")
                    logger.info("Available Action Buttons:")
                    for idx, btn in enumerate(visible_buttons):
                        logger.info(f"  {idx + 1}: '{btn.text}'")
                        
                    # Auto-click first button if it's "Continue" or "Confirm"
                    for btn in visible_buttons:
                        if btn.text.lower() in ['continue', 'confirm', 'ok', 'done']:
                            try:
                                btn.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", btn)
                            logger.info(f"Auto-clicked button: '{btn.text}'")
                            time.sleep(3)
                            continue
                
                time.sleep(2)
                if self.driver.current_url.lower() == last_url:
                    continue
                last_url = self.driver.current_url.lower()
                continue
                
            body_text = ""
            try:
                body_text = self.driver.find_element(By.TAG_NAME, "body").text
            except:
                pass
                
            logger.info(f"\n--- Verification Input Required ---")
            logger.info(f"Current URL: {self.driver.current_url}")
            
            if two_factor_key:
                body_text_lower = body_text.lower()
                if any(word in body_text_lower for word in ["code", "verification", "two-factor", "authenticator"]):
                    verification_code = self.get_totp_code(two_factor_key)
                    if verification_code:
                        logger.info(f"Automatically generated 2FA code: {verification_code}")
                        try:
                            visible_inputs[0].clear()
                            visible_inputs[0].send_keys(verification_code)
                            logger.info(f"Entered 2FA code")
                            time.sleep(2)
                            submit_selectors = [
                                "//button[contains(text(), 'Confirm') or contains(text(), 'Submit') or contains(text(), 'Continue') or contains(text(), 'Next') or contains(text(), 'Done')]",
                                "button[type='submit']",
                                "input[type='submit']"
                            ]
                            for sel in submit_selectors:
                                if sel.startswith("//"):
                                    btns = self.driver.find_elements(By.XPATH, sel)
                                else:
                                    btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                                if btns:
                                    disp_btns = [b for b in btns if b.is_displayed()]
                                    btn_to_click = disp_btns[0] if disp_btns else btns[0]
                                    try:
                                        btn_to_click.click()
                                    except:
                                        self.driver.execute_script("arguments[0].click();", btn_to_click)
                                    logger.info("Clicked submit button.")
                                    break
                        except Exception as e:
                            logger.error(f"Failed to enter code: {e}")
    
    def get_totp_code(self, secret):
        """Generate TOTP code - EXACTLY FROM 099.py"""
        if not secret:
            return None
        try:
            secret = secret.replace(" ", "").upper()
            padding = len(secret) % 8
            if padding != 0:
                secret += "=" * (8 - padding)
            key = base64.b32decode(secret)
            counter = struct.pack(">Q", int(time.time() / 30))
            mac = hmac.new(key, counter, hashlib.sha1).digest()
            offset = mac[-1] & 0x0F
            binary = struct.unpack(">I", mac[offset:offset+4])[0] & 0x7FFFFFFF
            code = binary % 1000000
            return f"{code:06d}"
        except Exception as e:
            logger.error(f"Error generating TOTP code: {e}")
            return None
    
    def handle_professional_conversion_step(self):
        """Handle professional conversion - EXACTLY FROM 099.py"""
        # State 5: "Your creator account is ready" Ready screen
        try:
            ready_elems = self.driver.find_elements(By.XPATH, "//*[contains(translate(., 'READY', 'ready'), 'is ready') or contains(translate(., 'READY', 'ready'), 'account is ready')]")
            if ready_elems:
                done_btns = self.driver.find_elements(By.XPATH, "//button[text()='Done' or contains(text(), 'Done')] | //*[text()='Done']")
                for btn in done_btns:
                    if btn.is_displayed():
                        logger.info("[STATE RECOGNIZED] On Ready Screen. Clicking final 'Done'...")
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(5)
                        logger.info("Closing professional conversion popup tab...")
                        try:
                            self.driver.close()
                        except Exception as close_err:
                            logger.error(f"Could not close popup tab: {close_err}")
                        return True
        except Exception as e:
            logger.error(f"Error in State 5: {e}")

        # State 4: "Switch to a professional account?" Confirmation Modal
        try:
            switch_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Switch to a professional account') or contains(text(), 'Switch to a professional')]")
            if switch_elems:
                continue_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Continue')] | //*[text()='Continue'] | //div[contains(text(), 'Continue')]")
                for btn in continue_btns:
                    if btn.is_displayed() and not any(word in btn.text.lower() for word in ["cancel", "decline", "back"]):
                        logger.info("[STATE RECOGNIZED] On Switch Confirmation Modal. Clicking 'Continue'...")
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(4)
                        return True
        except Exception as e:
            logger.error(f"Error in State 4: {e}")

        # State 3: Category Selection Screen
        try:
            cat_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Select a category') or contains(text(), 'What category best describes you') or .//input[contains(@placeholder, 'Search')]]")
            if cat_elems:
                logger.info("[STATE RECOGNIZED] On Category Selection Screen. Selecting 'Art'...")
                art_opt = self.driver.find_elements(By.XPATH, "//*[text()='Art'] | //*[contains(text(), 'Art')]/ancestor::div[1] | //div[contains(., 'Art')]")
                if art_opt:
                    for el in art_opt:
                        if el.is_displayed():
                            try:
                                el.click()
                            except:
                                pass
                            try:
                                self.driver.execute_script("arguments[0].click();", el)
                            except:
                                pass
                            logger.info("Selected category: Art")
                            break
                
                done_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Done')] | //div[contains(text(), 'Done')] | //*[text()='Done']")
                for btn in done_btns:
                    if btn.is_displayed() and "done" in btn.text.lower():
                        logger.info("Clicking 'Done' button...")
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(4)
                        return True
        except Exception as e:
            logger.error(f"Error in State 3: {e}")

        # State 2: Creator Benefits/Info Screen
        try:
            desc_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Which best describes you') or contains(text(), 'Which best describes')]")
            if not desc_elems:
                info_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Best for public figures') or contains(text(), 'Flexible profile controls') or contains(text(), 'More growth tools')]")
                if info_elems:
                    next_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')] | //div[contains(text(), 'Next')] | //*[text()='Next']")
                    for btn in next_btns:
                        if btn.is_displayed() and "next" in btn.text.lower():
                            logger.info("[STATE RECOGNIZED] On Creator Info Screen. Clicking 'Next'...")
                            try:
                                btn.click()
                            except:
                                self.driver.execute_script("arguments[0].click();", btn)
                            time.sleep(4)
                            return True
        except Exception as e:
            logger.error(f"Error in State 2: {e}")

        # State 1: "Which best describes you?" Selection Screen
        try:
            desc_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Which best describes you') or contains(text(), 'Which best describes')]")
            creator_opt = None
            if desc_elems:
                selectors = ["//*[text()='Creator']", "//div[contains(text(), 'Creator')]", "//span[contains(text(), 'Creator')]"]
                for sel in selectors:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed():
                            creator_opt = el
                            break
                    if creator_opt:
                        break
                
                if creator_opt:
                    logger.info("[STATE RECOGNIZED] On Creator Selection Screen. Selecting 'Creator'...")
                    try:
                        creator_opt.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", creator_opt)
                    time.sleep(1.5)
                
                next_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')] | //div[contains(text(), 'Next')] | //*[text()='Next']")
                for btn in next_btns:
                    if btn.is_displayed() and "next" in btn.text.lower():
                        logger.info("Clicking 'Next' button...")
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(4)
                        return True
        except Exception as e:
            logger.error(f"Error in State 1: {e}")
            
        return False
    
    def find_continue_with_instagram_button(self):
        """Find 'Continue with Instagram' button - EXACTLY FROM 099.py"""
        selectors = [
            "//button[contains(text(), 'Continue with Instagram')]",
            "//a[contains(text(), 'Continue with Instagram')]",
            "//div[contains(text(), 'Continue with Instagram')]",
            "//span[contains(text(), 'Continue with Instagram')]",
            "//*[contains(text(), 'Continue with Instagram')]"
        ]
        
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for el in elements:
                    href = el.get_attribute("href") or ""
                    if "instagram.com" in href and "loginpage" not in href and "continue" not in href.lower():
                        continue
                    if el.is_displayed():
                        return el
            except Exception:
                continue
        
        return None
    
    def connect_to_business_suite(self):
        """Connect to Business Suite - EXACTLY FROM 099.py"""
        try:
            # Step 1: Navigate to Facebook Business Suite
            logger.info("\nNavigating to Facebook Business login page...")
            self.driver.get(FB_LOGIN_URL)
            time.sleep(3)
            self.handle_cookies()
            
            logger.info("Looking for the 'Continue with Instagram' button...")
            time.sleep(3)
            
            # Check if we were redirected to standard Facebook Login page
            current_url = self.driver.current_url.lower()
            if "facebook.com/login" in current_url or "facebook.com/login.php" in current_url:
                logger.warning("\n[WARNING] Redirected to Facebook Login page instead of Meta for Business login page!")
                logger.warning("This usually happens when Meta's security/bot detection triggers and redirects guest sessions.")
                logger.info(f"Current URL: {self.driver.current_url}")
                
            ig_btn = self.find_continue_with_instagram_button()
            
            if ig_btn:
                logger.info("Clicking 'Continue with Instagram' button...")
                try:
                    ig_btn.click()
                except Exception as click_err:
                    logger.info(f"Click failed: {click_err}. Trying click via JavaScript...")
                    try:
                        self.driver.execute_script("arguments[0].click();", ig_btn)
                    except Exception as js_err:
                        logger.error(f"JS click failed: {js_err}")
                
                # Wait for popup and handle professional account setup/login
                self._handle_popup_and_professional_setup()
                
                # Handle post-login landing page
                self._handle_post_login_landing()
                
                # Ad Account Connection - EXACTLY FROM 099.py
                self._handle_ad_account_connection()
                
                return True
            
            logger.error("Could not find 'Continue with Instagram' button")
            return False
            
        except Exception as e:
            logger.error(f"Error connecting to Business Suite: {e}")
            return False
    
    def _handle_popup_and_professional_setup(self):
        """Handle popup and professional setup - EXACTLY FROM 099.py"""
        try:
            main_window = self.driver.current_window_handle
            popup_window = None
            
            # Poll for 5 seconds to see if a popup window opens
            start_wait = time.time()
            while time.time() - start_wait < 5:
                if len(self.driver.window_handles) > 1:
                    for handle in self.driver.window_handles:
                        if handle != main_window:
                            popup_window = handle
                            self.driver.switch_to.window(popup_window)
                            logger.info("Switched to Instagram authorization popup.")
                            break
                    break
                time.sleep(0.5)
            
            # Handle popup page flow
            if popup_window:
                popup_start_time = time.time()
                step_attempts = {}
                
                while time.time() - popup_start_time < 90:
                    time.sleep(1)
                    
                    if len(self.driver.window_handles) == 1:
                        logger.info("Popup window closed automatically.")
                        break
                    
                    try:
                        current_url = self.driver.current_url.lower()
                    except:
                        logger.info("Popup window appears to be closed or inaccessible.")
                        break
                    
                    # Check for security challenge / checkpoint
                    is_checkpoint = any(kw in current_url for kw in ["challenge", "checkpoint", "accountscenter", "codeentry", "auth_platform"])
                    if is_checkpoint:
                        logger.info("\n[SECURITY CHALLENGE DETECTED IN POPUP] Instagram requires account verification.")
                        self.handle_interactive_verification(None)
                        time.sleep(5)
                        continue
                    
                    # Case E: Professional Account Conversion Page
                    is_professional_url = any(kw in current_url for kw in ["convert", "professional"])
                    is_conversion_screen = False
                    try:
                        is_conversion_screen = len(self.driver.find_elements(By.XPATH, 
                            "//*[contains(text(), 'Which best describes you')] | "
                            "//*[contains(text(), 'Best for public figures')] | "
                            "//*[contains(text(), 'Select a category')] | "
                            "//*[contains(text(), 'Switch to a professional')] | "
                            "//*[contains(text(), 'is ready') or contains(text(), 'account is ready')]"
                        )) > 0
                    except:
                        pass
                        
                    if is_professional_url or is_conversion_screen:
                        # Detect and count attempts for the current state
                        active_state = None
                        try:
                            if self.driver.find_elements(By.XPATH, "//*[contains(translate(., 'READY', 'ready'), 'is ready') or contains(translate(., 'READY', 'ready'), 'account is ready')]"):
                                active_state = "State5_Ready"
                            elif self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Switch to a professional account') or contains(text(), 'Switch to a professional')]"):
                                active_state = "State4_SwitchConfirmation"
                            elif self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Select a category') or contains(text(), 'What category best describes you') or .//input[contains(@placeholder, 'Search')]]"):
                                active_state = "State3_CategorySelection"
                            elif self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Which best describes you') or contains(text(), 'Which best describes')]"):
                                active_state = "State1_CreatorSelection"
                            elif self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Best for public figures') or contains(text(), 'Flexible profile controls') or contains(text(), 'More growth tools')]"):
                                active_state = "State2_CreatorBenefits"
                        except:
                            pass
                            
                        if active_state:
                            step_attempts[active_state] = step_attempts.get(active_state, 0) + 1
                            logger.info(f"[POPUP MONITOR] Active State: {active_state} (Attempt {step_attempts[active_state]} of 2)")
                            if step_attempts[active_state] > 2:
                                logger.info(f"[POPUP MONITOR] State {active_state} is stuck. Closing companion window for recovery...")
                                try:
                                    self.driver.close()
                                except:
                                    pass
                                break

                        logger.info("\n[PROFESSIONAL SETUP DETECTED] Running state-driven screen recognition...")
                        handled = self.handle_professional_conversion_step()
                        if handled:
                            continue
                    
                    # Case A: Instagram Login Page
                    if "accounts/login" in current_url:
                        logger.info("\n[INFO] Instagram login page detected in popup. Logging in...")
                        self.handle_cookies()
                        continue
                    
                    # Case C: "Log in as" / "Continue as" button
                    login_as_btn = None
                    try:
                        login_as_elems = self.driver.find_elements(By.XPATH, 
                            "//*[contains(text(), 'Log in as') or contains(text(), 'Continue as') or contains(text(), 'Switch to a professional')]")
                        for el in login_as_elems:
                            if el.is_displayed() and ("Log in as" in el.text or "Continue as" in el.text):
                                login_as_btn = el
                                break
                    except:
                        pass
                        
                    if login_as_btn:
                        logger.info(f"[NON-PROFESSIONAL ACCOUNT DETECTED] Clicking '{login_as_btn.text}'...")
                        try:
                            login_as_btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", login_as_btn)
                        time.sleep(5)
                        
                        # Check for confirmation dialog after clicking "Log in as"
                        try:
                            confirm_btns = self.driver.find_elements(By.XPATH,
                                "//button[contains(text(), 'Confirm')] | "
                                "//button[contains(text(), 'Continue')] | "
                                "//*[@role='button' and contains(., 'Confirm')]")
                            for confirm_btn in confirm_btns:
                                if confirm_btn.is_displayed():
                                    logger.info("Found confirmation button, clicking...")
                                    try:
                                        confirm_btn.click()
                                    except:
                                        self.driver.execute_script("arguments[0].click();", confirm_btn)
                                    time.sleep(3)
                                    break
                        except:
                            pass
                        continue
                    
                    # Case D: General Authorization confirmation
                    auth_btn = None
                    try:
                        auth_selectors = [
                            "//button[text()='Allow' or contains(text(), 'Allow') or contains(text(), 'Authorize') or contains(text(), 'Confirm')]",
                            "//button[contains(text(), 'Continue')]",
                            "//button[contains(text(), 'Allow') or contains(text(), 'Authorize')]"
                        ]
                        for selector in auth_selectors:
                            elems = self.driver.find_elements(By.XPATH, selector)
                            for el in elems:
                                if el.is_displayed():
                                    text_lower = el.text.lower()
                                    if not any(word in text_lower for word in ["cancel", "decline", "not now", "back"]):
                                        auth_btn = el
                                        break
                            if auth_btn:
                                break
                    except:
                        pass
                        
                    if auth_btn:
                        logger.info(f"[AUTHORIZATION DETECTED] Clicking '{auth_btn.text}' button in popup...")
                        try:
                            auth_btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", auth_btn)
                        time.sleep(5)
                        continue
                    
                    if len(self.driver.window_handles) == 1:
                        logger.info("Popup window closed automatically.")
                        break
                    
                    time.sleep(2)
                
                # Switch back to main window
                if popup_window:
                    try:
                        if main_window in self.driver.window_handles:
                            self.driver.switch_to.window(main_window)
                            logger.info("Switched back to main window.")
                            logger.info("Refreshing backend page...")
                            self.driver.refresh()
                            time.sleep(5)
                        else:
                            if self.driver.window_handles:
                                self.driver.switch_to.window(self.driver.window_handles[0])
                                logger.info("Main window handle was lost, switched to first available window.")
                                logger.info("Refreshing backend page...")
                                self.driver.refresh()
                                time.sleep(5)
                    except Exception as win_err:
                        logger.error(f"Failed to switch back to main window: {win_err}")
                        
        except Exception as e:
            logger.error(f"Error in popup handling: {e}")
    
    def _handle_post_login_landing(self):
        """Handle post-login landing page - EXACTLY FROM 099.py"""
        logger.info("\n=== Post-Login Landing Page Controller ===")
        controller_start = time.time()
        last_activity_time = time.time()
        onboarding_completed = False
        
        while time.time() - controller_start < 70:
            time.sleep(2)
            
            try:
                if len(self.driver.window_handles) == 0:
                    break
                current_handles = self.driver.window_handles
                if self.driver.current_window_handle not in current_handles:
                    self.driver.switch_to.window(current_handles[0])
            except:
                pass
                
            try:
                current_url = self.driver.current_url.lower()
            except:
                continue
                
            # Direct Navigation to Boost post picker
            if "/latest/" in current_url and "asset_id=" in current_url:
                if "boosted_item_picker" in current_url:
                    logger.info("[SMART NAVIGATION] Already on boosted post picker page.")
                    onboarding_completed = True
                    break
                try:
                    from urllib.parse import urlparse, parse_qs, unquote
                    decoded_url = unquote(self.driver.current_url)
                    parsed = urlparse(decoded_url)
                    params = parse_qs(parsed.query)
                    asset_id = params.get('asset_id', [None])[0]
                    business_id = params.get('business_id', [None])[0]
                    
                    if asset_id:
                        logger.info(f"[SMART NAVIGATION] Detected asset_id={asset_id} in URL.")
                        target_url = f"https://business.facebook.com/latest/boosted_item_picker/?asset_id={asset_id}&business_id={business_id if business_id else ''}&ir_qe_exposed=1&content_filter=All&entry_point=bizweb_home_header&nav_ref=internal_nav&selected_item=boosted_instagram_media_picker"
                        logger.info(f"[SMART NAVIGATION] Navigating directly to ad booster page: {target_url}")
                        self.driver.get(target_url)
                        time.sleep(6)
                        onboarding_completed = True
                        break
                except Exception as parse_err:
                    logger.error(f"Error parsing asset_id from URL: {parse_err}")
                
            # Check for Page Blackout
            try:
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                body_text = body_elem.text.strip()
                visible_inputs = len([inp for inp in self.driver.find_elements(By.TAG_NAME, "input") if inp.is_displayed()])
                visible_buttons = len([btn for btn in self.driver.find_elements(By.TAG_NAME, "button") if btn.is_displayed()])
                
                if not body_text and visible_inputs == 0 and visible_buttons == 0:
                    if time.time() - last_activity_time > 10:
                        logger.info("[SMART RECOVERY] Main page appears blank/blacked out. Refreshing...")
                        self.driver.refresh()
                        last_activity_time = time.time()
                        time.sleep(5)
                        continue
                else:
                    last_activity_time = time.time()
            except:
                pass

            # State E: "Create ad" Dashboard Button
            try:
                create_ad_btn = None
                selectors = [
                    "//button[contains(., 'Create ad') or contains(text(), 'Create ad')]",
                    "//*[contains(text(), 'Create ad')]",
                    "//span[contains(text(), 'Create ad')]"
                ]
                for sel in selectors:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        try:
                            if el.is_displayed():
                                create_ad_btn = el
                                break
                        except:
                            continue
                    if create_ad_btn:
                        break
                
                if create_ad_btn:
                    logger.info("[STATE RECOGNIZED] On Dashboard. Clicking 'Create ad' to begin connection flow...")
                    try:
                        create_ad_btn.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", create_ad_btn)
                    time.sleep(5)
                    onboarding_completed = True
                    break
            except Exception as e:
                logger.error(f"Error in State E processing: {e}")

            # State C: "Continue on Meta Business Suite" Modal
            try:
                continue_mbs = None
                selectors = [
                    "//button[contains(text(), 'Continue on Meta Business Suite')]",
                    "//*[contains(text(), 'Continue on Meta Business Suite')]"
                ]
                for sel in selectors:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed():
                            continue_mbs = el
                            break
                    if continue_mbs:
                        break
                if continue_mbs:
                    logger.info("[STATE RECOGNIZED] On Onboarding dialog. Clicking 'Continue on Meta Business Suite'...")
                    try:
                        continue_mbs.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", continue_mbs)
                    time.sleep(3)
                    continue
            except:
                pass

            # State D: Instagram Message settings "Confirm" Modal
            try:
                confirm_msg = None
                selectors = [
                    "//button[text()='Confirm' or contains(text(), 'Confirm')]",
                    "//*[text()='Confirm' or contains(text(), 'Confirm')]"
                ]
                for sel in selectors:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed() and "confirm" in el.text.lower():
                            confirm_msg = el
                            break
                    if confirm_msg:
                        break
                if confirm_msg:
                    logger.info("[STATE RECOGNIZED] On Onboarding dialog. Clicking 'Confirm'...")
                    try:
                        confirm_msg.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", confirm_msg)
                    time.sleep(3)
                    continue
            except:
                pass

            # State B: Accept Terms Page
            if "collect_form" in current_url or "accept" in current_url:
                try:
                    accept_btn = None
                    selectors = [
                        "//button[contains(., 'Accept')]",
                        "//button[contains(., 'Agree')]",
                        "//*[@role='button' and contains(., 'Accept')]",
                        "button"
                    ]
                    for sel in selectors:
                        elems = self.driver.find_elements(By.XPATH, sel) if sel.startswith("//") else self.driver.find_elements(By.CSS_SELECTOR, sel)
                        for el in elems:
                            if el.is_displayed():
                                text_lower = el.text.strip().lower()
                                if text_lower in ["accept", "agree", "i accept", "i agree"]:
                                    accept_btn = el
                                    break
                        if accept_btn:
                            break
                    if accept_btn:
                        logger.info(f"[STATE RECOGNIZED] On Accept Terms page. Clicking '{accept_btn.text}' button...")
                        try:
                            accept_btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", accept_btn)
                        time.sleep(4)
                        continue
                except:
                    pass

            # State A: On standard Facebook Login page / Continue with Instagram page
            try:
                ig_btns = self.driver.find_elements(By.XPATH, 
                    "//button[contains(text(), 'Continue with Instagram')] | "
                    "//a[contains(text(), 'Continue with Instagram')] | "
                    "//*[contains(text(), 'Continue with Instagram')]"
                )
                displayed_ig_btn = None
                for btn in ig_btns:
                    href = btn.get_attribute("href") or ""
                    if "instagram.com" in href and "loginpage" not in href and "continue" not in href.lower():
                        continue
                    if btn.is_displayed():
                        displayed_ig_btn = btn
                        break
                if displayed_ig_btn:
                    logger.info("[STATE RECOGNIZED] On Login page. Clicking 'Continue with Instagram'...")
                    try:
                        displayed_ig_btn.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", displayed_ig_btn)
                    time.sleep(8)
                    
                    logger.info("[RECOVERY] Refreshing backend page to trigger Instagram redirection...")
                    self.driver.refresh()
                    time.sleep(5)
                    continue
            except:
                pass

        if not onboarding_completed:
            logger.warning("[WARNING] Exited controller loop without finding 'Create ad' button. Trying to proceed anyway...")
    
    def _handle_ad_account_connection(self):
        """Handle ad account connection - EXACTLY FROM 099.py"""
        main_window = self.driver.current_window_handle
        
        for attempt in range(1, 3):
            logger.info(f"\n--- Ad Account Connection: Attempt {attempt} of 2 ---")
            
            # Click the "Continue" button on the booster page
            try:
                continue_boost = None
                selectors = [
                    "//div[contains(., 'Ad account needed to boost posts')]//button[contains(text(), 'Continue')]",
                    "//div[contains(., 'boost posts')]//button[contains(text(), 'Continue')]",
                    "//button[text()='Continue' or contains(text(), 'Continue')]",
                    "//a[contains(text(), 'Continue')]",
                    "//*[text()='Continue']"
                ]
                start_wait = time.time()
                while time.time() - start_wait < 10:
                    for sel in selectors:
                        elems = self.driver.find_elements(By.XPATH, sel)
                        for el in elems:
                            if el.is_displayed() and "continue" in el.text.lower():
                                continue_boost = el
                                break
                        if continue_boost:
                            break
                    if continue_boost:
                        break
                    time.sleep(1)
                    
                if continue_boost:
                    logger.info(f"[Attempt {attempt}] Clicking 'Continue' on Boost/Ad screen...")
                    try:
                        continue_boost.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", continue_boost)
                    time.sleep(5)
                else:
                    logger.info(f"[Attempt {attempt}] Warning: 'Continue' button on Boost/Ad screen not found.")
                    if attempt == 1:
                        try:
                            body_text = self.driver.find_element(By.TAG_NAME, "body").text
                            boost_btn_present = len(self.driver.find_elements(By.XPATH, "//button[contains(., 'Boost')] | //span[contains(., 'Boost')]")) > 0
                            if boost_btn_present or "select a post to boost" in body_text.lower():
                                logger.info("\n=== Account Connected Successfully ===")
                                logger.info("Instagram and Ad Account connection is already active (Boost buttons visible).")
                                return True
                        except:
                            pass
            except Exception as e:
                logger.error(f"[Attempt {attempt}] Error clicking booster Continue button: {e}")
                
            # Click "Continue" on the Connect Meta ad account modal
            try:
                continue_connect = None
                selectors = [
                    "//div[contains(., 'Connect a Meta ad account')]//button[contains(text(), 'Continue')]",
                    "//div[contains(., 'Connect a Meta ad account')]//*[contains(text(), 'Continue')]",
                    "//div[@role='dialog']//button[text()='Continue' or contains(text(), 'Continue')]",
                    "//div[contains(@class, 'dialog')]//button[text()='Continue' or contains(text(), 'Continue')]",
                    "//button[text()='Continue' or contains(text(), 'Continue')]"
                ]
                time.sleep(4)
                for sel in selectors:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed():
                            continue_connect = el
                            break
                    if continue_connect:
                        break
                if continue_connect:
                    logger.info(f"[Attempt {attempt}] Clicking 'Continue' on Connect Meta ad account modal...")
                    try:
                        continue_connect.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", continue_connect)
                    time.sleep(8)
                else:
                    logger.info(f"[Attempt {attempt}] Warning: 'Continue' button on Connect Meta ad account modal not found.")
            except Exception as e:
                logger.error(f"[Attempt {attempt}] Error clicking connect modal Continue button: {e}")

            # Check for and handle the "Continue as [Name]" button inside the popup/tab
            try:
                main_window_exists = False
                try:
                    main_window_exists = main_window in self.driver.window_handles
                except:
                    pass
                
                if not main_window_exists:
                    if self.driver.window_handles:
                        main_window = self.driver.window_handles[0]
                        self.driver.switch_to.window(main_window)
                    else:
                        logger.info(f"[Attempt {attempt}] No active window handles left! Aborting attempt.")
                        continue

                popup_window = None
                start_wait = time.time()
                while time.time() - start_wait < 10:
                    try:
                        current_handles = self.driver.window_handles
                        if len(current_handles) > 1:
                            for handle in current_handles:
                                if handle != main_window:
                                    popup_window = handle
                                    self.driver.switch_to.window(popup_window)
                                    logger.info(f"[Attempt {attempt}] Switched to Login with Facebook popup/tab.")
                                    break
                            break
                    except Exception as handle_err:
                        logger.error(f"Error checking window handles: {handle_err}")
                    time.sleep(0.5)
                            
                if popup_window:
                    time.sleep(5)
                    
                    window_still_open = False
                    try:
                        if popup_window in self.driver.window_handles:
                            window_still_open = True
                    except:
                        pass
                        
                    if window_still_open:
                        continue_as_btn = None
                        selectors = [
                            "//button[contains(text(), 'Continue as')]",
                            "//*[contains(text(), 'Continue as')]",
                            "//div[contains(text(), 'Continue as')]"
                        ]
                        for sel in selectors:
                            try:
                                elems = self.driver.find_elements(By.XPATH, sel)
                                for el in elems:
                                    if el.is_displayed():
                                        continue_as_btn = el
                                        break
                                if continue_as_btn:
                                    break
                            except:
                                continue
                                
                        if continue_as_btn:
                            logger.info(f"[Attempt {attempt}] Clicking '{continue_as_btn.text}' button...")
                            try:
                                continue_as_btn.click()
                            except:
                                try:
                                    self.driver.execute_script("arguments[0].click();", continue_as_btn)
                                except:
                                    pass
                            time.sleep(10)
                        else:
                            logger.info(f"[Attempt {attempt}] Warning: 'Continue as [Name]' button not found in popup.")
                            
                        logger.info(f"[Attempt {attempt}] Closing the popup window/tab...")
                        try:
                            if popup_window in self.driver.window_handles:
                                self.driver.close()
                        except Exception as close_err:
                            logger.error(f"Could not close popup window handle: {close_err}")
                        
                try:
                    if main_window in self.driver.window_handles:
                        self.driver.switch_to.window(main_window)
                        logger.info(f"[Attempt {attempt}] Switched back to main window.")
                    else:
                        if self.driver.window_handles:
                            self.driver.switch_to.window(self.driver.window_handles[0])
                            logger.info(f"[Attempt {attempt}] Main window lost, switched to first active handle.")
                except Exception as win_err:
                    logger.error(f"Failed to switch back: {win_err}")
                    
                try:
                    logger.info(f"[Attempt {attempt}] Refreshing the main backend page...")
                    self.driver.refresh()
                    time.sleep(10)
                except Exception as refresh_err:
                    logger.error(f"Could not refresh driver: {refresh_err}")
                
            except Exception as e:
                logger.error(f"[Attempt {attempt}] Error handling popup and page refresh: {e}")
        
        logger.info("\n=== Landing Page Details ===")
        logger.info(f"Current URL: {self.driver.current_url}")
        logger.info(f"Page Title: {self.driver.title}")
        
        return True
    
    def navigate_to_ad_picker(self, asset_id, business_id=None):
        """Navigate to ad picker"""
        try:
            target_url = f"https://business.facebook.com/latest/boosted_item_picker/?asset_id={asset_id}"
            if business_id:
                target_url += f"&business_id={business_id}"
            target_url += "&ir_qe_exposed=1&content_filter=All&entry_point=bizweb_home_header&nav_ref=internal_nav&selected_item=boosted_instagram_media_picker"
            
            logger.info(f"Navigating directly to ad booster page: {target_url}")
            self.driver.get(target_url)
            time.sleep(6)
            
            return self.driver.current_url
            
        except Exception as e:
            logger.error(f"Error navigating to ad picker: {e}")
            return None
    
    def get_current_url(self):
        try:
            return self.driver.current_url if self.driver else None
        except:
            return None
    
    def get_page_title(self):
        try:
            return self.driver.title if self.driver else None
        except:
            return None
    
    def quit(self):
        """Clean quit with memory cleanup"""
        if self.driver:
            try:
                self.driver.delete_all_cookies()
                for handle in self.driver.window_handles:
                    try:
                        self.driver.switch_to.window(handle)
                        self.driver.close()
                    except:
                        pass
                self.driver.quit()
            except:
                pass
            self.driver = None
        
        self._cleanup_temp_dir()
        gc.collect()
        logger.info("Chrome driver cleaned up and memory freed")
