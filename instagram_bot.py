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
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

# The target Facebook Business Suite login page url
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
        self._setup_driver()
    
    def _setup_driver(self):
        """Setup Chrome driver with optimized settings for Railway"""
        try:
            options = Options()
            
            # Critical: Reduce memory usage
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-setuid-sandbox')
            
            # Additional memory optimization
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')
            options.add_argument('--disable-javascript')  # Only if not needed
            
            # Headless mode
            if self.headless:
                options.add_argument('--headless=new')
                options.add_argument('--window-size=1280,720')  # Smaller window
            
            # Anti-detection
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Disable notifications
            prefs = {
                "profile.default_content_setting_values.notifications": 2,
                "profile.default_content_setting_values.images": 2,  # Block images
                "profile.managed_default_content_settings.images": 2
            }
            options.add_experimental_option("prefs", prefs)
            
            # Use Chromium for Railway
            chromium_paths = ['/usr/bin/chromium', '/usr/bin/chromium-browser', '/usr/bin/google-chrome']
            for path in chromium_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    break
            
            # ChromeDriver path
            chromedriver_paths = ['/usr/bin/chromedriver', '/usr/local/bin/chromedriver']
            service = None
            for path in chromedriver_paths:
                if os.path.exists(path):
                    service = Service(
                        path,
                        service_args=['--verbose', '--log-path=chromedriver.log']
                    )
                    break
            
            # Set memory limits
            options.add_argument('--memory-pressure-off')
            options.add_argument('--max_old_space_size=256')  # Reduce memory
            
            if service:
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                self.driver = webdriver.Chrome(options=options)
            
            # Set timeouts
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
            
            # Hide webdriver
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
            })
            
            logger.info("ChromeDriver initialized successfully with optimized settings")
            
        except Exception as e:
            logger.error(f"Failed to initialize Chrome Driver: {e}")
            raise
    
    def perform_cookie_login(self, cookies):
        """Perform cookie login with better error handling"""
        try:
            logger.info("Attempting cookie-based login...")
            
            # Clear any existing session
            self.driver.delete_all_cookies()
            
            # Step 1: Navigate to Instagram
            logger.info("Navigating to Instagram...")
            self.driver.get("https://www.instagram.com")
            time.sleep(2)
            
            # Step 2: Inject cookies
            logger.info(f"Injecting {len(cookies)} cookies...")
            injected_count = 0
            for cookie in cookies:
                try:
                    clean_cookie = self._sanitize_cookie(cookie)
                    self.driver.add_cookie(clean_cookie)
                    injected_count += 1
                except Exception as e:
                    logger.warning(f"Skipped cookie ({cookie.get('name')}): {e}")
            
            logger.info(f"Successfully injected {injected_count} cookies.")
            
            # Step 3: Reload page
            logger.info("Reloading page with injected session...")
            self.driver.refresh()
            time.sleep(3)
            
            # Step 4: Handle One-Tap 'Continue' screen
            self._handle_continue_screen()
            
            # Step 5: Verify login
            current_url = self.driver.current_url.lower()
            
            is_logged_in = False
            if "login" not in current_url:
                is_logged_in = True
                logger.info("STATUS: SUCCESS ✅ - Authenticated via cookies!")
            else:
                logger.error("STATUS: FAILED ❌ - Cookie expired or invalid.")
            
            return is_logged_in
                
        except Exception as e:
            logger.error(f"Error during cookie login: {e}")
            return False
    
    def connect_to_business_suite(self):
        """Connect to Facebook Business Suite with better error handling"""
        try:
            logger.info("Navigating to Facebook Business login page...")
            self.driver.get(FB_LOGIN_URL)
            time.sleep(2)
            
            self._handle_cookies()
            
            logger.info("Looking for the 'Continue with Instagram' button...")
            time.sleep(2)
            
            # Check for redirect
            current_url = self.driver.current_url.lower()
            if "facebook.com/login" in current_url:
                logger.warning("Redirected to Facebook Login page!")
            
            # Find and click 'Continue with Instagram'
            ig_btn = self._find_continue_with_instagram_button()
            
            if ig_btn:
                logger.info("Clicking 'Continue with Instagram' button...")
                try:
                    ig_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", ig_btn)
                
                # Handle popup and professional setup
                self._handle_popup_and_professional_setup()
                
                # Handle post-login landing page
                self._handle_post_login_landing()
                
                # Ad Account Connection
                self._handle_ad_account_connection()
                
                return True
            
            logger.error("Could not find 'Continue with Instagram' button")
            return False
            
        except Exception as e:
            logger.error(f"Error connecting to Business Suite: {e}")
            return False
    
    def navigate_to_ad_picker(self, asset_id, business_id=None):
        """Navigate to ad picker"""
        try:
            target_url = f"https://business.facebook.com/latest/boosted_item_picker/?asset_id={asset_id}"
            if business_id:
                target_url += f"&business_id={business_id}"
            target_url += "&ir_qe_exposed=1&content_filter=All&entry_point=bizweb_home_header&nav_ref=internal_nav&selected_item=boosted_instagram_media_picker"
            
            logger.info(f"Navigating to ad booster page...")
            self.driver.get(target_url)
            time.sleep(4)
            
            return self.driver.current_url
            
        except Exception as e:
            logger.error(f"Error navigating to ad picker: {e}")
            return None
    
    def _find_continue_with_instagram_button(self):
        """Find 'Continue with Instagram' button"""
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
    
    def _handle_popup_and_professional_setup(self):
        """Handle popup and professional setup"""
        try:
            main_window = self.driver.current_window_handle
            popup_window = None
            
            # Wait for popup
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
            
            if popup_window:
                popup_start_time = time.time()
                step_attempts = {}
                
                while time.time() - popup_start_time < 60:  # Reduced timeout
                    time.sleep(1)
                    
                    if len(self.driver.window_handles) == 1:
                        logger.info("Popup window closed automatically.")
                        break
                    
                    try:
                        current_url = self.driver.current_url.lower()
                    except:
                        break
                    
                    # Check for professional conversion
                    is_professional = any(kw in current_url for kw in ["convert", "professional"])
                    is_conversion_screen = False
                    try:
                        is_conversion_screen = len(self.driver.find_elements(By.XPATH, 
                            "//*[contains(text(), 'Which best describes you')] | "
                            "//*[contains(text(), 'Best for public figures')] | "
                            "//*[contains(text(), 'Select a category')] | "
                            "//*[contains(text(), 'Switch to a professional')] | "
                            "//*[contains(text(), 'is ready')]"
                        )) > 0
                    except:
                        pass
                    
                    if is_professional or is_conversion_screen:
                        # Detect and handle states
                        active_state = None
                        try:
                            if self.driver.find_elements(By.XPATH, "//*[contains(text(), 'account is ready')]"):
                                active_state = "Ready"
                            elif self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Switch to a professional')]"):
                                active_state = "SwitchConfirmation"
                            elif self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Select a category')]"):
                                active_state = "CategorySelection"
                            elif self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Which best describes you')]"):
                                active_state = "CreatorSelection"
                        except:
                            pass
                        
                        if active_state:
                            step_attempts[active_state] = step_attempts.get(active_state, 0) + 1
                            if step_attempts[active_state] > 2:
                                logger.info(f"State {active_state} is stuck. Closing...")
                                try:
                                    self.driver.close()
                                except:
                                    pass
                                break
                        
                        handled = self._handle_professional_conversion_step()
                        if handled:
                            continue
                    
                    # Check for login page
                    if "accounts/login" in current_url:
                        logger.info("Login page detected in popup.")
                        self._handle_cookies()
                        continue
                    
                    # Check for "Log in as" button
                    login_as_btn = None
                    try:
                        login_as_elems = self.driver.find_elements(By.XPATH, 
                            "//*[contains(text(), 'Log in as')]")
                        for el in login_as_elems:
                            if el.is_displayed() and "Log in as" in el.text:
                                login_as_btn = el
                                break
                    except:
                        pass
                        
                    if login_as_btn:
                        logger.info(f"NON-PROFESSIONAL ACCOUNT DETECTED: {login_as_btn.text}")
                        try:
                            login_as_btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", login_as_btn)
                        time.sleep(2)
                        continue
                    
                    # Check for authorization button
                    auth_btn = self._find_authorization_button()
                    if auth_btn:
                        logger.info(f"AUTHORIZATION: Clicking {auth_btn.text}")
                        try:
                            auth_btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", auth_btn)
                        time.sleep(3)
                        continue
                    
                    if len(self.driver.window_handles) == 1:
                        logger.info("Popup closed automatically.")
                        break
                    
                    time.sleep(1)
                
                # Switch back to main window
                if popup_window:
                    try:
                        if main_window in self.driver.window_handles:
                            self.driver.switch_to.window(main_window)
                            logger.info("Switched back to main window.")
                            self.driver.refresh()
                            time.sleep(3)
                    except Exception as win_err:
                        logger.error(f"Failed to switch back: {win_err}")
                        
        except Exception as e:
            logger.error(f"Error in popup handling: {e}")
    
    def _handle_professional_conversion_step(self):
        """Handle professional conversion steps - optimized"""
        # State 5: Ready screen
        try:
            ready_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'account is ready')]")
            if ready_elems:
                done_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Done')]")
                for btn in done_btns:
                    if btn.is_displayed():
                        logger.info("Ready screen - Clicking Done...")
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(3)
                        try:
                            self.driver.close()
                        except:
                            pass
                        return True
        except:
            pass
        
        # State 4: Switch confirmation
        try:
            switch_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Switch to a professional')]")
            if switch_elems:
                continue_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Continue')]")
                for btn in continue_btns:
                    if btn.is_displayed():
                        logger.info("Switch confirmation - Clicking Continue...")
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(3)
                        return True
        except:
            pass
        
        # State 3: Category selection
        try:
            cat_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Select a category')]")
            if cat_elems:
                logger.info("Category selection - Selecting Art...")
                art_opt = self.driver.find_elements(By.XPATH, "//*[text()='Art']")
                for el in art_opt:
                    if el.is_displayed():
                        try:
                            el.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", el)
                        break
                
                done_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Done')]")
                for btn in done_btns:
                    if btn.is_displayed():
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(3)
                        return True
        except:
            pass
        
        # State 1: Creator selection
        try:
            desc_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Which best describes you')]")
            if desc_elems:
                creator_opt = self.driver.find_elements(By.XPATH, "//*[text()='Creator']")
                for el in creator_opt:
                    if el.is_displayed():
                        logger.info("Creator selection - Selecting Creator...")
                        try:
                            el.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(1)
                        break
                
                next_btns = self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')]")
                for btn in next_btns:
                    if btn.is_displayed():
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(3)
                        return True
        except:
            pass
        
        return False
    
    def _handle_post_login_landing(self):
        """Handle post-login landing page"""
        logger.info("Post-Login Landing Page Controller")
        controller_start = time.time()
        
        while time.time() - controller_start < 30:  # Reduced timeout
            time.sleep(2)
            
            try:
                if len(self.driver.window_handles) == 0:
                    break
            except:
                pass
            
            try:
                current_url = self.driver.current_url.lower()
            except:
                continue
            
            # Check for ad picker
            if "/latest/" in current_url and "asset_id=" in current_url:
                logger.info("Already on boosted post picker page.")
                return True
            
            # Check for "Create ad" button
            create_ad_btn = self._find_create_ad_button()
            if create_ad_btn:
                logger.info("Found Create ad button - clicking...")
                try:
                    create_ad_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", create_ad_btn)
                time.sleep(3)
                return True
            
            # Check for continue buttons
            continue_btn = self._find_continue_button()
            if continue_btn:
                logger.info("Found Continue button - clicking...")
                try:
                    continue_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", continue_btn)
                time.sleep(2)
                continue
        
        return False
    
    def _handle_ad_account_connection(self):
        """Handle ad account connection"""
        main_window = self.driver.current_window_handle
        
        for attempt in range(1, 3):
            logger.info(f"Ad Account Connection: Attempt {attempt}")
            
            # Find Continue button
            continue_btn = self._find_continue_button()
            if continue_btn:
                logger.info(f"Clicking Continue...")
                try:
                    continue_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", continue_btn)
                time.sleep(3)
            
            # Handle Continue as button
            self._handle_continue_as_button(main_window)
            
            # Refresh
            try:
                self.driver.refresh()
                time.sleep(5)
            except:
                pass
    
    def _handle_continue_as_button(self, main_window):
        """Handle Continue as button"""
        try:
            # Check for popup
            popup_window = None
            start_wait = time.time()
            while time.time() - start_wait < 5:
                try:
                    if len(self.driver.window_handles) > 1:
                        for handle in self.driver.window_handles:
                            if handle != main_window:
                                popup_window = handle
                                self.driver.switch_to.window(popup_window)
                                break
                        break
                except:
                    pass
                time.sleep(0.5)
            
            if popup_window:
                time.sleep(3)
                
                # Find Continue as button
                continue_as_btn = None
                selectors = [
                    "//button[contains(text(), 'Continue as')]",
                    "//*[contains(text(), 'Continue as')]"
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
                    logger.info(f"Clicking {continue_as_btn.text}")
                    try:
                        continue_as_btn.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", continue_as_btn)
                    time.sleep(5)
                
                # Close popup
                try:
                    if popup_window in self.driver.window_handles:
                        self.driver.close()
                except:
                    pass
                
                # Switch back
                try:
                    if main_window in self.driver.window_handles:
                        self.driver.switch_to.window(main_window)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Error in continue as handler: {e}")
    
    # Helper methods
    def _sanitize_cookie(self, cookie):
        """Sanitize cookie"""
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
    
    def _handle_continue_screen(self):
        """Handle continue screen"""
        logger.info("Checking for Continue button...")
        
        continue_selectors = [
            "//button[contains(text(), 'Continue')]",
            "//button[contains(., 'Continue')]",
            "//a[contains(text(), 'Continue')]",
            "//div[@role='button' and contains(., 'Continue')]"
        ]
        
        for selector in continue_selectors:
            try:
                elements = self.driver.find_elements(By.XPATH, selector)
                for el in elements:
                    if el.is_displayed():
                        logger.info(f"Clicking Continue: {el.text.strip()}")
                        try:
                            el.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(3)
                        return True
            except:
                continue
        
        return False
    
    def _handle_cookies(self):
        """Handle cookie consent"""
        try:
            cookie_texts = ["Accept All", "Accept", "Allow", "Agree"]
            for text in cookie_texts:
                btns = self.driver.find_elements(By.XPATH, f"//button[contains(text(), '{text}')]")
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        logger.info(f"Clicked cookie button: {text}")
                        time.sleep(1)
                        return
        except:
            pass
    
    def _find_continue_button(self):
        """Find any Continue button"""
        selectors = [
            "//button[contains(text(), 'Continue')]",
            "//a[contains(text(), 'Continue')]",
            "//*[text()='Continue']"
        ]
        
        for sel in selectors:
            try:
                elems = self.driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        return el
            except:
                continue
        
        return None
    
    def _find_create_ad_button(self):
        """Find Create ad button"""
        selectors = [
            "//button[contains(., 'Create ad')]",
            "//*[contains(text(), 'Create ad')]",
            "//span[contains(text(), 'Create ad')]"
        ]
        
        for sel in selectors:
            try:
                elems = self.driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        return el
            except:
                continue
        
        return None
    
    def _find_authorization_button(self):
        """Find authorization button"""
        try:
            auth_selectors = [
                "//button[text()='Allow']",
                "//button[contains(text(), 'Authorize')]",
                "//button[contains(text(), 'Confirm')]",
                "//button[contains(text(), 'Continue')]"
            ]
            for selector in auth_selectors:
                elems = self.driver.find_elements(By.XPATH, selector)
                for el in elems:
                    if el.is_displayed():
                        text_lower = el.text.lower()
                        if not any(word in text_lower for word in ["cancel", "decline", "not now", "back"]):
                            return el
        except:
            pass
        
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
                self.driver.quit()
            except:
                pass
            self.driver = None
            gc.collect()
def get_current_url(self):
    """Get current URL"""
    try:
        return self.driver.current_url if self.driver else None
    except:
        return None

def get_page_title(self):
    """Get page title"""
    try:
        return self.driver.title if self.driver else None
    except:
        return None

def quit(self):
    """Clean quit with memory cleanup"""
    if self.driver:
        try:
            self.driver.quit()
        except:
            pass
        self.driver = None
        gc.collect()
