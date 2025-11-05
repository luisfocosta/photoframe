import os
import logging
import time
from functools import wraps
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Load environment variables from .env file
load_dotenv()

edge_options = Options()
edge_options.binary_location = os.getenv("EDGE_BINARY")

# Use a separate Edge profile for automation to avoid conflicts with existing instances
# This prevents "Chrome instance exited" errors when Edge is already running
user_data_dir = r"C:\Users\Photo frame\AppData\Local\Microsoft\Edge\User Data Automation"
edge_options.add_argument(f"--user-data-dir={user_data_dir}")
edge_options.add_argument("--profile-directory=Default")  # Use the default profile within automation directory

# Enable remote debugging for reconnection capability
edge_options.add_argument("--remote-debugging-port=9222")

# Suppress Edge logging and disable unnecessary features
edge_options.add_argument("--log-level=3")  # Suppress INFO, WARNING, and ERROR logs
edge_options.add_argument("--disable-logging")
edge_options.add_argument("--disable-dev-shm-usage")
edge_options.add_argument("--no-sandbox")
edge_options.add_argument("--disable-gpu")
edge_options.add_argument("--disable-web-security")
edge_options.add_experimental_option("excludeSwitches", ["enable-logging"])
edge_options.add_experimental_option('useAutomationExtension', False)
edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])

# Global driver instance to keep browser windows open
_driver_instance = None
_driver_state = {
    'initialized': False,
    'current_url': None,
    'session_id': None
}

def preserve_window_state(func):
    """
    Decorator that preserves the browser window state (fullscreen, size, position)
    before and after executing a function that interacts with the browser.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        driver = get_driver() if _driver_instance else None

        # Store current window state before function execution
        was_fullscreen = False
        window_size = None
        window_position = None

        if driver:
            try:
                was_fullscreen = driver.execute_script("return document.fullscreenElement !== null")
                window_size = driver.get_window_size()
                window_position = driver.get_window_position()
            except Exception as e:
                logging.debug(f"Could not capture window state: {e}")

        # Execute the original function
        result = func(*args, **kwargs)

        # Restore window state after function execution
        if driver:
            try:
                if was_fullscreen:
                    driver.fullscreen_window()
                    logging.debug("Restored fullscreen state")
                elif window_size:
                    driver.set_window_size(window_size['width'], window_size['height'])
                    driver.set_window_position(window_position['x'], window_position['y'])
                    logging.debug("Restored window size and position")
            except Exception as e:
                logging.debug(f"Could not restore window state: {e}")

        return result

    return wrapper

def get_driver():
    global _driver_instance, _driver_state

    # If we already have a driver instance, check if it's still alive
    if _driver_instance is not None:
        try:
            # Test if the driver is still alive by accessing current_url
            current_url = _driver_instance.current_url
            _driver_state['current_url'] = current_url
            # logging.info(f"Reusing existing driver instance. Current URL: {current_url}")
            return _driver_instance
        except Exception as e:
            # Driver is dead, attempt to reconnect to existing windows
            logging.warning(f"Existing driver instance is dead: {e}. Attempting to reconnect to existing browser windows...")
            reconnected = _try_reconnect_to_existing_browser()
            if reconnected:
                logging.info("Successfully reconnected to existing browser window")
                return _driver_instance

            # If reconnection failed, clean up and create a new instance
            logging.warning("Could not reconnect to existing browser. Creating new instance.")
            _driver_instance = None
            _driver_state['initialized'] = False

    # No driver instance exists - try to connect to existing browser first
    logging.info("No driver instance found. Checking for existing browser windows...")
    reconnected = _try_reconnect_to_existing_browser()
    if reconnected:
        logging.info("Successfully connected to existing browser window")
        return _driver_instance

    # No existing browser found, create new driver instance
    logging.info("No existing browser found. Creating new driver instance...")
    local_driver_path = os.getenv("WEBDRIVER_PATH")
    if local_driver_path and os.path.exists(local_driver_path):
        service = Service(local_driver_path)
        try:
            _driver_instance = webdriver.Edge(service=service, options=edge_options)
            _driver_state['initialized'] = True
            _driver_state['session_id'] = _driver_instance.session_id
            _driver_state['current_url'] = _driver_instance.current_url
            logging.info(f"New driver instance created successfully. Session ID: {_driver_state['session_id']}")
            return _driver_instance
        except Exception as local_error:
            logging.error(f"Local EdgeDriver failed: {local_error}")
            raise Exception(f"EdgeDriver failed: {local_error}")
    else:
        # Fallback: try webdriver-manager if local driver not found
        try:
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            logging.info("Local EdgeDriver not found, trying webdriver-manager...")
            service = Service(EdgeChromiumDriverManager().install())
            _driver_instance = webdriver.Edge(service=service, options=edge_options)
            _driver_state['initialized'] = True
            _driver_state['session_id'] = _driver_instance.session_id
            _driver_state['current_url'] = _driver_instance.current_url
            logging.info(f"New driver instance created with webdriver-manager. Session ID: {_driver_state['session_id']}")
            return _driver_instance
        except Exception as e:
            raise Exception(f"Both local EdgeDriver and webdriver-manager failed. No EdgeDriver available. Error: {e}")

def _try_reconnect_to_existing_browser():
    """
    Attempts to reconnect to an existing Edge browser window that matches our automation profile.
    Returns True if successful, False otherwise.
    """
    global _driver_instance, _driver_state

    try:
        import psutil
        import json
        import requests

        # Find all running Edge processes
        edge_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'msedge.exe' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('--remote-debugging-port' in arg for arg in cmdline):
                        # Extract debugging port
                        for arg in cmdline:
                            if '--remote-debugging-port=' in arg:
                                port = arg.split('=')[1]
                                edge_processes.append(int(port))
                                break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # If we found processes with debugging ports, try to connect
        if edge_processes:
            logging.info(f"Found Edge processes with debugging ports: {edge_processes}")
            for port in edge_processes:
                try:
                    # Get list of available sessions
                    response = requests.get(f'http://localhost:{port}/json', timeout=2)
                    sessions = response.json()

                    if sessions:
                        # Use the first available session
                        session_id = sessions[0]['id']
                        debugger_url = sessions[0]['webSocketDebuggerUrl']

                        # Try to create a driver that connects to this session
                        # Only use minimal options when connecting to existing browser
                        options = Options()
                        edge_binary = os.getenv("EDGE_BINARY")
                        if edge_binary:
                            options.binary_location = edge_binary
                        options.add_experimental_option("debuggerAddress", f"localhost:{port}")

                        local_driver_path = os.getenv("WEBDRIVER_PATH")
                        if local_driver_path and os.path.exists(local_driver_path):
                            service = Service(local_driver_path)
                        else:
                            from webdriver_manager.microsoft import EdgeChromiumDriverManager
                            service = Service(EdgeChromiumDriverManager().install())

                        _driver_instance = webdriver.Edge(service=service, options=options)
                        _driver_state['initialized'] = True
                        _driver_state['session_id'] = _driver_instance.session_id
                        _driver_state['current_url'] = _driver_instance.current_url

                        logging.info(f"Successfully reconnected to existing browser on port {port}")
                        return True
                except Exception as e:
                    logging.debug(f"Could not connect to Edge on port {port}: {e}")
                    continue

        logging.info("No existing Edge browser windows found with debugging enabled")
        return False

    except ImportError as e:
        logging.debug(f"Missing required library for reconnection (psutil or requests): {e}")
        return False
    except Exception as e:
        logging.debug(f"Error attempting to reconnect to existing browser: {e}")
        return False

def get_driver_state():
    """Get current driver state information"""
    global _driver_instance, _driver_state

    state_info = _driver_state.copy()

    if _driver_instance is not None:
        try:
            state_info['is_alive'] = True
            state_info['current_url'] = _driver_instance.current_url
            state_info['window_handles'] = len(_driver_instance.window_handles)
            state_info['title'] = _driver_instance.title
        except:
            state_info['is_alive'] = False
    else:
        state_info['is_alive'] = False

    return state_info

def list_all_browser_windows():
    """
    Lists all Edge browser windows/tabs that are currently running.
    Returns a list of dictionaries containing window information.

    Returns:
        List[dict]: List of browser windows with their details, or error info
    """
    global _driver_instance

    windows_info = []

    # First, try to get info from the current driver instance
    if _driver_instance is not None:
        try:
            current_handle = _driver_instance.current_window_handle
            all_handles = _driver_instance.window_handles

            for idx, handle in enumerate(all_handles):
                try:
                    _driver_instance.switch_to.window(handle)
                    windows_info.append({
                        'window_index': idx,
                        'handle': handle,
                        'url': _driver_instance.current_url,
                        'title': _driver_instance.title,
                        'is_current': handle == current_handle
                    })
                except Exception as e:
                    windows_info.append({
                        'window_index': idx,
                        'handle': handle,
                        'error': str(e)
                    })

            # Switch back to the original window
            _driver_instance.switch_to.window(current_handle)

            logging.info(f"Found {len(windows_info)} windows/tabs in current driver instance")
            return windows_info

        except Exception as e:
            logging.warning(f"Could not enumerate windows from current driver: {e}")

    # If current driver is not available, try to find running Edge processes
    try:
        import psutil
        import requests

        edge_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                if proc.info['name'] and 'msedge.exe' in proc.info['name'].lower():
                    cmdline = proc.info['cmdline']
                    if cmdline and any('--remote-debugging-port' in arg for arg in cmdline):
                        for arg in cmdline:
                            if '--remote-debugging-port=' in arg:
                                port = arg.split('=')[1]
                                edge_processes.append(int(port))
                                break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        if edge_processes:
            logging.info(f"Found Edge processes with debugging ports: {edge_processes}")
            all_tabs = []
            seen_tab_ids = set()  # Track unique tab IDs to avoid duplicates

            for port in edge_processes:
                try:
                    response = requests.get(f'http://localhost:{port}/json', timeout=2)
                    tabs = response.json()

                    for idx, tab in enumerate(tabs):
                        tab_id = tab.get('id')
                        # Only include actual pages, not background processes, and deduplicate by tab_id
                        if tab.get('type') == 'page' and tab_id not in seen_tab_ids:
                            seen_tab_ids.add(tab_id)
                            all_tabs.append({
                                'window_index': len(all_tabs),
                                'debugging_port': port,
                                'tab_id': tab_id,
                                'url': tab.get('url'),
                                'title': tab.get('title'),
                                'type': tab.get('type'),
                                'webSocketDebuggerUrl': tab.get('webSocketDebuggerUrl')
                            })
                except Exception as e:
                    logging.debug(f"Could not query Edge on port {port}: {e}")
                    continue

            if all_tabs:
                logging.info(f"Found {len(all_tabs)} unique tabs across all Edge processes")
                return all_tabs
            else:
                logging.info("No active page tabs found in Edge processes")
                return []
        else:
            logging.info("No Edge processes found with debugging enabled")
            return []

    except ImportError:
        error_msg = "Cannot list browser windows: psutil or requests library not installed"
        logging.warning(error_msg)
        return [{'error': error_msg}]
    except Exception as e:
        error_msg = f"Error listing browser windows: {str(e)}"
        logging.error(error_msg)
        return [{'error': error_msg}]

def connect_to_existing_window(debugging_port=9222):
    """
    Connects to an existing Edge browser window using the debugging port.
    This replaces the current driver instance with a connection to the existing browser.

    Args:
        debugging_port (int): The debugging port to connect to (default: 9222)

    Returns:
        bool: True if connection successful, False otherwise
    """
    global _driver_instance, _driver_state

    try:
        import requests

        # First, verify there's a browser on this port
        try:
            response = requests.get(f'http://localhost:{debugging_port}/json', timeout=2)
            tabs = response.json()

            if not tabs:
                logging.error(f"No tabs found on debugging port {debugging_port}")
                return False

            logging.info(f"Found {len(tabs)} tabs on port {debugging_port}")

        except Exception as e:
            logging.error(f"Cannot connect to debugging port {debugging_port}: {e}")
            return False

        # Close existing driver if any
        if _driver_instance is not None:
            try:
                _driver_instance.quit()
            except:
                pass

        # Create new driver connected to existing browser
        # Only use minimal options when connecting to existing browser
        options = Options()
        edge_binary = os.getenv("EDGE_BINARY")
        if edge_binary:
            options.binary_location = edge_binary
        options.add_experimental_option("debuggerAddress", f"localhost:{debugging_port}")

        local_driver_path = os.getenv("WEBDRIVER_PATH")
        if local_driver_path and os.path.exists(local_driver_path):
            service = Service(local_driver_path)
        else:
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            service = Service(EdgeChromiumDriverManager().install())

        _driver_instance = webdriver.Edge(service=service, options=options)
        _driver_state['initialized'] = True
        _driver_state['session_id'] = _driver_instance.session_id
        _driver_state['current_url'] = _driver_instance.current_url

        logging.info(f"Successfully connected to existing browser on port {debugging_port}")
        logging.info(f"Current URL: {_driver_state['current_url']}")
        return True

    except ImportError:
        logging.error("Cannot connect to existing window: requests library not installed")
        return False
    except Exception as e:
        logging.error(f"Error connecting to existing window: {e}")
        return False

def reset_driver():
    """Force reset the driver instance"""
    global _driver_instance, _driver_state
    
    if _driver_instance is not None:
        try:
            _driver_instance.quit()
        except:
            pass
    
    _driver_instance = None
    _driver_state = {
        'initialized': False,
        'current_url': None,
        'session_id': None
    }
    logging.info("Driver instance has been reset")

def close_all_windows():
    global _driver_instance, _driver_state
    if _driver_instance is not None:
        try:
            _driver_instance.quit()
            logging.info("All browser windows closed successfully")
        except Exception as e:
            logging.warning(f"Error closing browser windows: {e}")
        _driver_instance = None
        _driver_state = {
            'initialized': False,
            'current_url': None,
            'session_id': None
        }

def set_fullscreen():
    driver = get_driver()
    driver.fullscreen_window()
    logging.info(f"Edge window maximized")
    return driver

@preserve_window_state
def open_new_window(url):
    driver = get_driver()

    # Check if we already have tabs open
    driver.get(url)
    logging.info(f"Successfully opened new Edge window/tab")
    # Maximize and fullscreen the window
    driver.fullscreen_window()
    return driver

@preserve_window_state
def navigate_to_url(url):
    driver = get_driver()
    try:
        driver.get(url)
    except Exception as e:
        logging.error(f"Error navigating to URL {url}: {e}")
        raise e
        return None
    logging.info(f"Successfully navigated to URL: {url}")
    return driver

@preserve_window_state
def click_button(button_id):
    driver = get_driver()
    wait = WebDriverWait(driver, 10)

    try:
        # Wait a bit for the page to load
        time.sleep(1)

        # Try multiple strategies to find the button
        button = None

        # Strategy 1: Try by ID
        try:
            button = wait.until(EC.element_to_be_clickable((By.ID, button_id)))
            logging.info(f"Found button by ID: {button_id}")
        except:
            logging.info(f"Could not find button by ID: {button_id}, trying other methods...")

        # Strategy 2: Try by name attribute
        if button is None:
            try:
                button = wait.until(EC.element_to_be_clickable((By.NAME, button_id)))
                logging.info(f"Found button by NAME: {button_id}")
            except:
                logging.debug(f"Could not find button by NAME: {button_id}")

        # Strategy 3: Try by CSS selector
        if button is None:
            try:
                # Common CSS selectors for buttons
                selectors = [
                    # f'button[id="{button_id}"]',
                    # f'button[name="{button_id}"]',
                    # f'button[class*="{button_id}" i]',
                    # f'input[type="button"][id="{button_id}"]',
                    # f'input[type="submit"][id="{button_id}"]',
                    # f'a[id="{button_id}"]',  # Sometimes links are styled as buttons
                    # f'[role="button"][id="{button_id}"]',
                    # f'button:contains("{button_id}")',  # Button containing text
                    # f'button.{button_id}',
                    f'{button_id}'
                ]

                for selector in selectors:
                    try:
                        button = driver.find_element(By.CSS_SELECTOR, selector)
                        if button.is_displayed() and button.is_enabled():
                            logging.info(f"Found button using CSS selector: {selector}")
                            break
                        else:
                            button = None
                    except:
                        continue
            except:
                pass

        # Strategy 4: Try by XPath
        # if button is None:
        #     try:
        #         xpath_selectors = [
        #             f"//button[@id='{button_id}']",
        #             f"//button[@name='{button_id}']",
        #             f"//button[contains(text(), '{button_id}')]",
        #             f"//input[@type='button' and @id='{button_id}']",
        #             f"//input[@type='submit' and @id='{button_id}']",
        #             f"//a[@id='{button_id}']",
        #             f"//*[@role='button' and @id='{button_id}']",
        #         ]

        #         for xpath in xpath_selectors:
        #             try:
        #                 button = driver.find_element(By.XPATH, xpath)
        #                 if button.is_displayed() and button.is_enabled():
        #                     logging.info(f"Found button using XPath: {xpath}")
        #                     break
        #                 else:
        #                     button = None
        #             except:
        #                 continue
        #     except:
        #         pass

        if button is not None:
            button.click()
            logging.info(f"Successfully clicked button: {button_id}")
        else:
            logging.error(f"Button '{button_id}' not found using any strategy. Skipping click action.")
            logging.debug(f"Current URL: {driver.current_url}")
            return None

    except Exception as e:
        logging.warning(f"Failed to click button '{button_id}'. Skipping action.")
        logging.error(f"Error details: {e}")
        logging.debug(f"Current URL: {driver.current_url}")
        return None

    return driver

@preserve_window_state
def input_text(element_id, text):
    driver = get_driver()
    wait = WebDriverWait(driver, 10)  # Wait up to 10 seconds
    
    try:
        # First, wait a bit for the page to load
        time.sleep(2)
        
        # Try multiple strategies to find the element
        element = None
        
        # Strategy 1: Try by ID
        try:
            element = wait.until(EC.presence_of_element_located((By.ID, element_id)))
            logging.info(f"Found element by ID: {element_id}")
        except:
            logging.info(f"Could not find element by ID: {element_id}, trying other methods...")
        
        # Strategy 2: Try by name attribute
        if element is None:
            try:
                element = wait.until(EC.presence_of_element_located((By.NAME, element_id)))
                logging.info(f"Found element by NAME: {element_id}")
            except:
                logging.info(f"Could not find element by NAME: {element_id}")
        
        # # Strategy 3: Try by CSS selector for input with placeholder or type
        # if element is None:
        #     try:
        #         if 'username' in element_id.lower():
        #             # Try to find username field by type or placeholder
        #             selectors = [
        #                 'input[type="text"]',
        #                 'input[type="email"]',
        #                 'input[placeholder*="username" i]',
        #                 'input[placeholder*="email" i]',
        #                 'input[name*="username" i]',
        #                 'input[name*="email" i]'
        #             ]
        #         elif 'password' in element_id.lower():
        #             # Try to find password field
        #             selectors = [
        #                 'input[type="password"]',
        #                 'input[placeholder*="password" i]',
        #                 'input[name*="password" i]'
        #             ]
        #         else:
        #             selectors = [f'input[name*="{element_id}" i]']
                
        #         for selector in selectors:
        #             try:
        #                 element = driver.find_element(By.CSS_SELECTOR, selector)
        #                 logging.info(f"Found element using CSS selector: {selector}")
        #                 break
        #             except:
        #                 continue
        #     except:
        #         pass
        
        # # Strategy 4: Try XPath
        # if element is None:
        #     try:
        #         xpath_selectors = [
        #             f"//input[@id='{element_id}']",
        #             f"//input[@name='{element_id}']",
        #             f"//input[contains(@placeholder, '{element_id.replace('-', '').replace('auth', '')}')]"
        #         ]
                
        #         for xpath in xpath_selectors:
        #             try:
        #                 element = driver.find_element(By.XPATH, xpath)
        #                 logging.info(f"Found element using XPath: {xpath}")
        #                 break
        #             except:
        #                 continue
        #     except:
        #         pass
        
        if element is not None:
            # Clear the field first, then input text
            element.clear()
            element.send_keys(text)
            logging.info(f"Successfully input text into element: {element_id}")
        else:
            logging.warning(f"Element '{element_id}' not found using any strategy. Skipping input action.")
            logging.debug(f"Current URL: {driver.current_url}")
            logging.debug(f"Page source snippet: {driver.page_source[:500]}")

    except Exception as e:
        logging.warning(f"Failed to input text into element '{element_id}'. Skipping action.")
        logging.error(f"Error details: {e}")
        logging.debug(f"Current URL: {driver.current_url}")
    
    return driver

@preserve_window_state
def send_enter_key():
    driver = get_driver()
    driver.switch_to.active_element.send_keys(Keys.ENTER)
    logging.info(f"Successfully sent 'ENTER' key")
    return driver

@preserve_window_state
def send_tab_key():
    driver = get_driver()
    driver.switch_to.active_element.send_keys(Keys.TAB)
    logging.info(f"Successfully sent 'TAB' key")
    return driver

@preserve_window_state
def open_first_photo():
    driver = get_driver()
    wait = WebDriverWait(driver, 4)
    first_photo = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "div[data-index='0']")))
    first_photo.click()
    logging.info(f"Successfully clicked on first album photo")
    return driver

def debug_page_elements():
    """Debug function to print all input elements on the page"""
    driver = get_driver()
    try:
        # Wait a bit for page to load
        time.sleep(3)
        
        # Find all input elements
        inputs = driver.find_elements(By.TAG_NAME, "input")
        logging.info(f"Found {len(inputs)} input elements:")
        
        for i, input_elem in enumerate(inputs):
            try:
                elem_id = input_elem.get_attribute("id") or "NO_ID"
                elem_name = input_elem.get_attribute("name") or "NO_NAME"
                elem_type = input_elem.get_attribute("type") or "NO_TYPE"
                elem_placeholder = input_elem.get_attribute("placeholder") or "NO_PLACEHOLDER"
                elem_class = input_elem.get_attribute("class") or "NO_CLASS"
                
                logging.info(f"Input {i+1}: ID='{elem_id}', NAME='{elem_name}', TYPE='{elem_type}', PLACEHOLDER='{elem_placeholder}', CLASS='{elem_class}'")
            except Exception as e:
                logging.error(f"Error getting attributes for input {i+1}: {e}")
                
        # Also find buttons
        buttons = driver.find_elements(By.TAG_NAME, "button")
        logging.info(f"Found {len(buttons)} button elements:")
        
        for i, button in enumerate(buttons):
            try:
                btn_id = button.get_attribute("id") or "NO_ID"
                btn_text = button.text or "NO_TEXT"
                btn_type = button.get_attribute("type") or "NO_TYPE"
                
                logging.info(f"Button {i+1}: ID='{btn_id}', TEXT='{btn_text}', TYPE='{btn_type}'")
            except Exception as e:
                logging.error(f"Error getting attributes for button {i+1}: {e}")
                
    except Exception as e:
        logging.exception(f"Error in debug_page_elements: {e}")
    
    return driver