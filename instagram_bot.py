import os
import sys
import time
import base64
import hashlib
import hmac
import struct
import json
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

# The target Facebook Business Suite login page url - exactly from your script
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
        """Setup Chrome driver - exactly like your script"""
        try:
            options = Options()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Disable notifications - exactly like your script
            prefs = {"profile.default_content_setting_values.notifications": 2}
            options.add_experimental_option("prefs", prefs)
            
            if self.headless:
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--lang=en-US")
                options.add_argument("--window-size=1920,1080")
            
            # Use Chromium for Railway
            chromium_paths = ['/usr/bin/chromium', '/usr/bin/chromium-browser']
            for path in chromium_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    break
            
            # ChromeDriver path
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
            
            # Hide webdriver - exactly like your script
            self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })
            
            logger.info("ChromeDriver initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Chrome Driver: {e}")
            raise
    
    def perform_cookie_login(self, cookies):
        """Perform cookie login - exactly like your script"""
        try:
            logger.info("Attempting cookie-based login...")
            
            # Step 1: Navigate to Instagram - exactly like your script
            logger.info("Navigating to Instagram to establish domain context...")
            self.driver.get("https://www.instagram.com")
            time.sleep(3)
            
            # Step 2: Inject cookies - exactly like your script
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
            
            # Step 3: Reload page - exactly like your script
            logger.info("Reloading page with injected session...")
            self.driver.refresh()
            time.sleep(5)
            
            # Step 4: Handle One-Tap 'Continue' screen - exactly like your script
            self._handle_continue_screen()
            
            # Step 5: Verify login - exactly like your script
            current_url = self.driver.current_url.lower()
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            
            nav_elements = self.driver.find_elements(By.XPATH, 
                "//a[contains(@href, 'direct/inbox') or contains(@href, 'explore') or @aria-label='Home']")
            
            is_logged_in = False
            if any(kw in current_url for kw in ["accounts/onetap", "instagram.com/direct", "instagram.com/explore"]) or len(nav_elements) > 0:
                is_logged_in = True
            elif "login" not in current_url and "phone number, username, or email" not in body_text:
                is_logged_in = True
            
            if is_logged_in:
                logger.info("STATUS: SUCCESS ✅ - Authenticated via cookies!")
                return True
            else:
                logger.error("STATUS: FAILED ❌ - Cookie expired or invalid.")
                return False
                
        except Exception as e:
            logger.error(f"Error during cookie login: {e}")
            return False
    
    def connect_to_business_suite(self):
        """Connect to Facebook Business Suite - exactly like your script"""
        try:
            # Step 1: Navigate to Facebook Business Suite - exactly like your script
            logger.info("Navigating to Facebook Business login page...")
            self.driver.get(FB_LOGIN_URL)
            
            time.sleep(3)
            self._handle_cookies()
            
            logger.info("Looking for the 'Continue with Instagram' button...")
            time.sleep(3)
            
            # Check for redirect to Facebook Login - exactly like your script
            current_url = self.driver.current_url.lower()
            if "facebook.com/login" in current_url or "facebook.com/login.php" in current_url:
                logger.warning("Redirected to Facebook Login page instead of Meta for Business login page!")
                logger.warning("This usually happens when Meta's security/bot detection triggers and redirects guest sessions.")
                logger.info(f"Current URL: {self.driver.current_url}")
            
            # Find and click 'Continue with Instagram' - exactly like your script
            ig_btn = self._find_continue_with_instagram_button()
            
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
                        return False
                
                # Handle popup and professional setup - exactly like your script
                self._handle_popup_and_professional_setup()
                
                # Handle post-login landing page - exactly like your script
                self._handle_post_login_landing()
                
                # Step 4: Ad Account Connection - exactly like your script
                self._handle_ad_account_connection()
                
                return True
            
            logger.error("Could not find 'Continue with Instagram' button")
            return False
            
        except Exception as e:
            logger.error(f"Error connecting to Business Suite: {e}")
            return False
    
    def navigate_to_ad_picker(self, asset_id, business_id=None):
        """Navigate to ad picker - exactly like your script"""
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
    
    def _find_continue_with_instagram_button(self):
        """Find 'Continue with Instagram' button - exactly like your script"""
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
        """Handle popup and professional setup - exactly like your script"""
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
            
            # Handle popup page flow - exactly like your script
            if popup_window:
                popup_start_time = time.time()
                step_attempts = {}
                
                while time.time() - popup_start_time < 90:
                    time.sleep(1)
                    
                    # Check if popup closed
                    if len(self.driver.window_handles) == 1:
                        logger.info("Popup window closed automatically.")
                        break
                    
                    try:
                        current_url = self.driver.current_url.lower()
                    except:
                        break
                    
                    # Case E: Professional Account Conversion - exactly like your script
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
                        # Detect active state - exactly like your script
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
                        
                        logger.info("[PROFESSIONAL SETUP DETECTED] Running state-driven screen recognition...")
                        handled = self._handle_professional_conversion_step()
                        if handled:
                            continue
                    
                    # Case A: Login Page - exactly like your script
                    if "accounts/login" in current_url:
                        logger.info("[INFO] Instagram login page detected in popup. Logging in...")
                        self._handle_cookies()
                        continue
                    
                    # FIXED: Case C - "Log in as" / "Continue as" (EXACTLY LIKE YOUR 099.py)
                    login_as_btn = None
                    try:
                        # Look for "Log in as" buttons - exactly like your script
                        login_as_elems = self.driver.find_elements(By.XPATH, 
                            "//*[contains(text(), 'Log in as') or contains(text(), 'Switch to a professional')]")
                        for el in login_as_elems:
                            if el.is_displayed() and "Log in as" in el.text:
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
                        time.sleep(3)
                        continue
                    
                    # Case D: General Authorization confirmation (click Allow/Authorize/Continue)
                    auth_btn = self._find_authorization_button()
                    if auth_btn:
                        logger.info(f"[AUTHORIZATION DETECTED] Clicking '{auth_btn.text}' button in popup...")
                        try:
                            auth_btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", auth_btn)
                        time.sleep(5)
                        continue
                    
                    # If window handles are back to 1, popup closed
                    if len(self.driver.window_handles) == 1:
                        logger.info("Popup window closed automatically.")
                        break
                    
                    time.sleep(2)
                
                # Switch back to main window - exactly like your script
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
        """Handle post-login landing page - exactly like your script"""
        logger.info("=== Post-Login Landing Page Controller ===")
        controller_start = time.time()
        last_activity_time = time.time()
        onboarding_completed = False
        
        while time.time() - controller_start < 70:
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
            
            # Direct Navigation to Boost post picker - exactly like your script
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
            
            # Check for Page Blackout - exactly like your script
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
            
            # State E: "Create ad" Dashboard Button - exactly like your script
            create_ad_btn = self._find_create_ad_button()
            if create_ad_btn:
                logger.info("[STATE RECOGNIZED] On Dashboard. Clicking 'Create ad' to begin connection flow...")
                try:
                    create_ad_btn.click()
                except:
                    self.driver.execute_script("arguments[0].click();", create_ad_btn)
                time.sleep(5)
                onboarding_completed = True
                break
            
            # State C: "Continue on Meta Business Suite" Modal - exactly like your script
            continue_mbs = self._find_continue_mbs_button()
            if continue_mbs:
                logger.info("[STATE RECOGNIZED] On Onboarding dialog. Clicking 'Continue on Meta Business Suite'...")
                try:
                    continue_mbs.click()
                except:
                    self.driver.execute_script("arguments[0].click();", continue_mbs)
                time.sleep(3)
                continue
            
            # State D: "Confirm" Modal - exactly like your script
            confirm_msg = self._find_confirm_button()
            if confirm_msg:
                logger.info("[STATE RECOGNIZED] On Onboarding dialog. Clicking 'Confirm'...")
                try:
                    confirm_msg.click()
                except:
                    self.driver.execute_script("arguments[0].click();", confirm_msg)
                time.sleep(3)
                continue
            
            # State B: Accept Terms Page - exactly like your script
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
        
        if not onboarding_completed:
            logger.warning("Exited controller loop without finding 'Create ad' button. Trying to proceed anyway...")
    
    def _handle_ad_account_connection(self):
        """Handle ad account connection - exactly like your script"""
        main_window = self.driver.current_window_handle
        
        for attempt in range(1, 3):
            logger.info(f"--- Ad Account Connection: Attempt {attempt} of 2 ---")
            
            # Click "Continue" button on booster page - exactly like your script
            continue_boost = self._find_continue_boost_button()
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
                            logger.info("Instagram and Ad Account connection is already active (Boost buttons visible).")
                            return True
                    except:
                        pass
            
            # Click "Continue" on Connect Meta ad account modal - exactly like your script
            continue_connect = self._find_continue_connect_button()
            if continue_connect:
                logger.info(f"[Attempt {attempt}] Clicking 'Continue' on Connect Meta ad account modal...")
                try:
                    continue_connect.click()
                except:
                    self.driver.execute_script("arguments[0].click();", continue_connect)
                time.sleep(8)
            else:
                logger.info(f"[Attempt {attempt}] Warning: 'Continue' button on Connect Meta ad account modal not found.")
            
            # Handle "Continue as [Name]" button - exactly like your script
            self._handle_continue_as_button(main_window)
            
            # Refresh main page - exactly like your script
            try:
                logger.info(f"[Attempt {attempt}] Refreshing the main backend page...")
                self.driver.refresh()
                time.sleep(10)
            except Exception as refresh_err:
                logger.error(f"Could not refresh driver: {refresh_err}")
    
    def _handle_continue_as_button(self, main_window):
        """Handle 'Continue as [Name]' button - exactly like your script"""
        try:
            # Ensure main window exists
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
                    logger.warning("No active window handles left! Aborting attempt.")
                    return
            
            popup_window = None
            # Check for new window handle
            start_wait = time.time()
            while time.time() - start_wait < 10:
                try:
                    current_handles = self.driver.window_handles
                    if len(current_handles) > 1:
                        for handle in current_handles:
                            if handle != main_window:
                                popup_window = handle
                                self.driver.switch_to.window(popup_window)
                                logger.info("Switched to Login with Facebook popup/tab.")
                                break
                        break
                except Exception as handle_err:
                    logger.error(f"Error checking window handles: {handle_err}")
                time.sleep(0.5)
            
            if popup_window:
                time.sleep(5)
                
                # Verify window is still open
                window_still_open = False
                try:
                    if popup_window in self.driver.window_handles:
                        window_still_open = True
                except:
                    pass
                
                if window_still_open:
                    continue_as_btn = self._find_continue_as_button()
                    
                    if continue_as_btn:
                        logger.info(f"Clicking '{continue_as_btn.text}' button...")
                        try:
                            continue_as_btn.click()
                        except:
                            try:
                                self.driver.execute_script("arguments[0].click();", continue_as_btn)
                            except:
                                pass
                        time.sleep(10)
                    else:
                        logger.warning("'Continue as [Name]' button not found in popup.")
                    
                    # Close the popup window - exactly like your script
                    logger.info("Closing the popup window/tab...")
                    try:
                        if popup_window in self.driver.window_handles:
                            self.driver.close()
                    except Exception as close_err:
                        logger.error(f"Could not close popup window handle: {close_err}")
            
            # Switch back to main window
            try:
                if main_window in self.driver.window_handles:
                    self.driver.switch_to.window(main_window)
                    logger.info("Switched back to main window.")
                else:
                    if self.driver.window_handles:
                        self.driver.switch_to.window(self.driver.window_handles[0])
                        logger.info("Main window lost, switched to first active handle.")
            except Exception as win_err:
                logger.error(f"Failed to switch back: {win_err}")
                
        except Exception as e:
            logger.error(f"Error handling continue as button: {e}")
    
    def _handle_professional_conversion_step(self):
        """Handle professional conversion steps - EXACTLY LIKE YOUR 099.py"""
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

        # FIXED: Case C - "Log in as" (EXACTLY LIKE YOUR 099.py)
        try:
            login_as_btn = None
            login_as_elems = self.driver.find_elements(By.XPATH, 
                "//*[contains(text(), 'Log in as') or contains(text(), 'Switch to a professional')]")
            for el in login_as_elems:
                if el.is_displayed() and "Log in as" in el.text:
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
            time.sleep(3)
            
            # After clicking, check for and click any confirmation/continue buttons (EXACTLY LIKE 099.py)
            try:
                auth_btn = None
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
                
                if auth_btn:
                    logger.info(f"[AUTHORIZATION DETECTED] Clicking '{auth_btn.text}' button...")
                    try:
                        auth_btn.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", auth_btn)
                    time.sleep(3)
            except:
                pass
            
            return True
        
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
    
    # Helper methods - exactly from your script
    
    def _sanitize_cookie(self, cookie):
        """Sanitize cookie - exactly like your script"""
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
        """Handle continue screen - exactly like your script"""
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
            except Exception:
                continue
        
        logger.info("No active 'Continue' button detected.")
        return False
    
    def _handle_cookies(self):
        """Handle cookies - exactly like your script"""
        try:
            cookie_texts = [
                "Allow all cookies", "Allow essential and optional cookies",
                "Decline optional cookies", "Accept All", "Accept", "Allow", "Agree",
                "Allow essential", "Accept cookies"
            ]
            for text in cookie_texts:
                btns = self.driver.find_elements(By.XPATH, 
                    f"//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text.lower()}')]")
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        logger.info(f"Clicked cookie/consent dialog button: '{text}'")
                        time.sleep(2)
                        return
        except Exception:
            pass
    
    def _find_continue_boost_button(self):
        """Find continue boost button - exactly like your script"""
        selectors = [
            "//div[contains(., 'Ad account needed to boost posts')]//button[contains(text(), 'Continue')]",
            "//div[contains(., 'boost posts')]//button[contains(text(), 'Continue')]",
            "//button[text()='Continue' or contains(text(), 'Continue')]",
            "//a[contains(text(), 'Continue')]",
            "//*[text()='Continue']"
        ]
        
        for sel in selectors:
            try:
                elems = self.driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed() and "continue" in el.text.lower():
                        return el
            except:
                continue
        
        return None
    
    def _find_continue_connect_button(self):
        """Find continue connect button - exactly like your script"""
        selectors = [
            "//div[contains(., 'Connect a Meta ad account')]//button[contains(text(), 'Continue')]",
            "//div[contains(., 'Connect a Meta ad account')]//*[contains(text(), 'Continue')]",
            "//div[@role='dialog']//button[text()='Continue' or contains(text(), 'Continue')]",
            "//div[contains(@class, 'dialog')]//button[text()='Continue' or contains(text(), 'Continue')]",
            "//button[text()='Continue' or contains(text(), 'Continue')]"
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
    
    def _find_continue_as_button(self):
        """Find continue as button - exactly like your script"""
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
                        return el
            except:
                continue
        
        return None
    
    def _find_create_ad_button(self):
        """Find create ad button - exactly like your script"""
        selectors = [
            "//button[contains(., 'Create ad') or contains(text(), 'Create ad')]",
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
    
    def _find_continue_mbs_button(self):
        """Find continue MBS button - exactly like your script"""
        selectors = [
            "//button[contains(text(), 'Continue on Meta Business Suite')]",
            "//*[contains(text(), 'Continue on Meta Business Suite')]"
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
    
    def _find_confirm_button(self):
        """Find confirm button - exactly like your script"""
        selectors = [
            "//button[text()='Confirm' or contains(text(), 'Confirm')]",
            "//*[text()='Confirm' or contains(text(), 'Confirm')]"
        ]
        
        for sel in selectors:
            try:
                elems = self.driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed() and "confirm" in el.text.lower():
                        return el
            except:
                continue
        
        return None
    
    def _find_authorization_button(self):
        """Find authorization button - exactly like your script"""
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
                            return el
        except:
            pass
        
        return None
    
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
        """Quit driver"""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None
