import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response, stream_with_context
from browser import (close_all_windows, open_new_window, navigate_to_url,
                    click_button, input_text, send_enter_key, debug_page_elements,
                    open_first_photo,
                    set_fullscreen, get_driver_state, reset_driver, list_all_browser_windows,
                    connect_to_existing_window, get_driver)
import logging
import queue
import threading

app = Flask(__name__)

load_dotenv()

# Global queue for log messages
log_queue = queue.Queue()

class SSELogHandler(logging.Handler):
    """Custom logging handler that broadcasts log messages to SSE clients via a queue"""

    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            message = self.format(record)
            # Put the formatted log message in the queue for SSE clients
            self.log_queue.put(message)
        except Exception:
            self.handleError(record)

logging.basicConfig(level=logging.INFO)

# Create and add SSE handler to the root logger
sse_handler = SSELogHandler(log_queue)
sse_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
sse_handler.setFormatter(formatter)
logging.getLogger().addHandler(sse_handler)

@app.route('/logs/stream')
def stream_logs():
    """SSE endpoint that streams log messages to clients in real-time"""
    def generate():
        # Send initial connection message
        yield f'data: {{"type": "connected", "message": "Log stream connected"}}\n\n'

        # Create a local queue for this client to avoid blocking other clients
        client_queue = queue.Queue()

        # Background thread to copy from global queue to client queue
        def queue_copier():
            while True:
                try:
                    msg = log_queue.get(timeout=1)
                    client_queue.put(msg)
                except queue.Empty:
                    continue
                except Exception:
                    break

        copier_thread = threading.Thread(target=queue_copier, daemon=True)
        copier_thread.start()

        # Stream messages to the client
        try:
            while True:
                try:
                    # Get message from client queue with timeout
                    message = client_queue.get(timeout=30)
                    # Format as SSE
                    yield f'data: {message}\n\n'
                except queue.Empty:
                    # Send keepalive comment to prevent connection timeout
                    yield f': keepalive\n\n'
                except Exception as e:
                    logging.error(f"Error streaming log: {e}")
                    break
        except GeneratorExit:
            # Client disconnected
            logging.info("Log stream client disconnected")

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/close_windows', methods=['POST'])
def handle_close_windows():
    close_all_windows()
    return jsonify({"message": "All Edge windows closed"})

@app.route('/fullscreen',methods=['POST'])
def handle_fullscreen():
    try:
        # set_fullscreen() calls get_driver() which handles reconnection
        set_fullscreen()
        return jsonify({"message": "Edge window in fullscreen now"})
    except Exception as e:
        logging.error(f"Error in handle_fullscreen: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/open_window', methods=['POST'])
def handle_open_window():
    # Check if we already have a driver with the PhotoPrism site loaded
    state = get_driver_state()
    
    # if state.get('is_alive') and 'photoprism' in str(state.get('current_url', '')).lower():
        # logging.info("Driver already has PhotoPrism loaded, reusing existing session")
    
    # Open new window/navigate to PhotoPrism
    driver = open_new_window('https://photoprism.augmentedbytech.com')
    
    # Debug: Print all available elements on the page
    # debug_page_elements()
    
    # Attempt login
    # input_text('auth-username', os.getenv('PHOTOPRISM_USERNAME'))
    # input_text('auth-password', os.getenv('PHOTOPRISM_PASSWORD'))
    # driver.implicitly_wait(4)  # Wait for 5 seconds to ensure fields are populated
    # send_enter_key()
    # driver.implicitly_wait(3)
    return jsonify({"message": "New Edge window opened and logged in"})

@app.route('/navigate', methods=['POST'])
def handle_navigate():
    state = get_driver_state()

    url = request.json['url']
    logging.info(f"Navigating to URL: {url}")
    navigate_to_url(url)
    return jsonify({"message": f"Navigated to {url}"})

@app.route('/click_button', methods=['POST'])
def handle_click_button():
    try:
        button_id = request.json['button_id']
        # click_button() calls get_driver() which handles reconnection
        click_button(button_id)
        return jsonify({"message": f"Clicked button with ID {button_id}"})
    except Exception as e:
        logging.error(f"Error in handle_click_button: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/input_text', methods=['POST'])
def handle_input_text():
    try:
        element_id = request.json['element_id']
        text = request.json['text']
        # input_text() calls get_driver() which handles reconnection
        input_text(element_id, text)
        return jsonify({"message": f"Inputted text '{text}' in element with ID {element_id}"})
    except Exception as e:
        logging.error(f"Error in handle_input_text: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/send_enter', methods=['POST'])
def handle_send_enter():
    state = get_driver_state()
    
    # if state.get('is_alive') and 'photoprism' in str(state.get('current_url', '')).lower():
        # logging.info("Driver already has PhotoPrism loaded, reusing existing session")
        # fullscreen()

    send_enter_key()
    return jsonify({"message": "Sent 'ENTER' key"})

@app.route('/driver_state', methods=['GET'])
def handle_driver_state():
    state = get_driver_state()

    return jsonify({"driver_state": state})

@app.route('/reset_driver', methods=['POST'])
def handle_reset_driver():
    reset_driver()
    return jsonify({"message": "Driver has been reset"})

@app.route('/list_windows', methods=['GET'])
def handle_list_windows():
    """
    Lists all Edge browser windows/tabs and their URLs.
    Returns information about all open browser windows/tabs.
    """
    windows = list_all_browser_windows()
    return jsonify({
        "windows": windows,
        "total_count": len(windows)
    })

@app.route('/debug_elements', methods=['POST'])
def handle_debug_elements():
    try:
        # debug_page_elements() calls get_driver() which handles reconnection
        debug_page_elements()
        return jsonify({"message": "Debug information logged - check console output"})
    except Exception as e:
        logging.error(f"Error in handle_debug_elements: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/open_first_photo', methods=['POST'])
def handle_open_first_photo():
    try:
        # Call open_first_photo which will trigger get_driver() and handle reconnection
        # But first validate we're on the correct URL
        # This triggers reconnection if needed
        try:
            driver = get_driver()
            current_url = driver.current_url
        except Exception as e:
            return jsonify({"error": f"Could not connect to browser: {str(e)}"}), 500

        # Validate that we're on the correct URL before opening first photo
        # Valid URLs: /library/browse or /library/albums/{album_id}/view
        valid_paths = ['/library/browse', '/library/albums/']

        if not any(path in current_url for path in valid_paths):
            return jsonify({
                "error": "Cannot open first photo. Must be on /library/browse or /library/albums/{album_id}/view",
                "current_url": current_url
            }), 400

        # Additional check for albums path - must end with /view
        if '/library/albums/' in current_url and not current_url.endswith('/view'):
            return jsonify({
                "error": "Cannot open first photo. Album URL must end with /view",
                "current_url": current_url
            }), 400

        # Now call the function to open first photo
        open_first_photo()
        return jsonify({"message": "First album photo opened"})
    except Exception as e:
        logging.error(f"Error in handle_open_first_photo: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/start_slideshow', methods=['POST'])
def handle_start_slideshow():
    try:
        # Trigger driver initialization/reconnection and validate URL
        # This triggers reconnection if needed
        try:
            driver = get_driver()
            current_url = driver.current_url
        except Exception as e:
            return jsonify({"error": f"Could not connect to browser: {str(e)}"}), 500

        # Validate that we're on the correct URL before starting slideshow
        # Valid URLs: /library/browse or /library/albums/{album_id}/view
        # valid_paths = ['/library/browse', '/library/albums/']

        # Additional check for albums path - must end with /view
        # logging.info(f"Current url:{current_url}")
        # logging.info(f"{'/library/albums' in current_url and not current_url.endswith('/view')}")
        if '/library/albums' in current_url:
            if not current_url.endswith('/view'):
                # browser open on album root view: we need to have at least one album open
                return jsonify({"error": "Slideshow not started - Open an album first!"})
            else:
                # open first photo
                logging.info("Opening first photo")
                open_first_photo()

        if '/library/browse' in current_url:
            logging.info("Opening first photo")
            open_first_photo()

        # Now start the slideshow
        result = click_button("button.pswp__button.pswp__button--slideshow-toggle")
        if result:
            return jsonify({"message": "Slideshow started"})
        else:
            return jsonify({"error": "Slideshow not started - slideshow button not found in page"})
    except Exception as e:
        logging.error(f"Error in handle_start_slideshow: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Generic webhook endpoint that receives data from external services.

    Expected JSON payload:
    {
        "action": "navigate|open_window|click_button|input_text|fullscreen|close_windows|search_photos|...",
        "data": {
            // action-specific parameters
        }
    }

    Examples:
    - Navigate: {"action": "navigate", "data": {"url": "https://example.com"}}
    - Click button: {"action": "click_button", "data": {"button_id": "my-button"}}
    - Input text: {"action": "input_text", "data": {"element_id": "username", "text": "myuser"}}
    - Fullscreen: {"action": "fullscreen", "data": {}}
    - Search photos: {"action": "search_photos", "data": {"album-name": "Vacation", "date-period": "2023-01-01:2023-12-31", "geo-country": "US"}}
    """
    try:
        # Get JSON payload from webhook
        payload = request.get_json()

        if not payload:
            logging.warning("Webhook received with no JSON payload")
            return jsonify({"error": "No JSON payload provided"}), 400

        logging.info(f"Webhook received: {payload}")

        action = payload.get('action')
        data = payload.get('data', {})

        if not action:
            return jsonify({"error": "No action specified"}), 400

        # Route to appropriate handler based on action
        # if action == 'navigate':
        #     url = data.get('url')
        #     if not url:
        #         return jsonify({"error": "No URL provided for navigate action"}), 400
        #     navigate_to_url(url)
        #     return jsonify({"message": f"Navigated to {url}", "action": action})

        # elif action == 'open_window':
        #     url = data.get('url', 'https://photoprism.augmentedbytech.com')
        #     driver = open_new_window(url)
        #     # Optionally handle login
        #     if data.get('login', False):
        #         input_text('auth-username', os.getenv('PHOTOPRISM_USERNAME'))
        #         input_text('auth-password', os.getenv('PHOTOPRISM_PASSWORD'))
        #         driver.implicitly_wait(4)
        #         send_enter_key()
        #         driver.implicitly_wait(3)
        #     return jsonify({"message": f"Opened window to {url}", "action": action})

        # elif action == 'click_button':
        #     button_id = data.get('button_id')
        #     if not button_id:
        #         return jsonify({"error": "No button_id provided"}), 400
        #     click_button(button_id)
        #     return jsonify({"message": f"Clicked button {button_id}", "action": action})

        # elif action == 'input_text':
        #     element_id = data.get('element_id')
        #     text = data.get('text')
        #     if not element_id or text is None:
        #         return jsonify({"error": "element_id and text are required"}), 400
        #     input_text(element_id, text)
        #     return jsonify({"message": f"Input text to {element_id}", "action": action})

        # elif action == 'send_enter':
        #     send_enter_key()
        #     return jsonify({"message": "Sent ENTER key", "action": action})

        # elif action == 'fullscreen':
        #     set_fullscreen()
        #     return jsonify({"message": "Set fullscreen", "action": action})

        # elif action == 'close_windows':
        #     close_all_windows()
        #     return jsonify({"message": "Closed all windows", "action": action})

        # elif action == 'reset_driver':
        #     reset_driver()
        #     return jsonify({"message": "Driver reset", "action": action})

        # elif action == 'open_first_photo':
        #     open_first_photo()
        #     return jsonify({"message": "Opened first photo", "action": action})

        # elif action == 'start_slideshow':
        #     click_button("button.pswp__button.pswp__button--slideshow-toggle")
        #     return jsonify({"message": "Slideshow started", "action": action})

        if action == 'search_photos':
            album_name = data.get('album-name')
            date_period = data.get('date-period')
            geo_country = data.get('geo-country')
            tags = data.get('tag')

            # Build search query using PhotoPrism filter syntax
            search_filters = []

            # Add album filter if provided
            if album_name:
                search_filters.append(f'album:"{album_name}"')

            # Add date filter if provided
            # Expected format: "YYYY-MM-DD:YYYY-MM-DD" or "YYYY-MM-DD" or "YYYY"
            if date_period:
                if ':' in date_period:
                    # Range format: start:end
                    start_date, end_date = date_period.split(':', 1)
                    search_filters.append(f'after:"{start_date}"')
                    search_filters.append(f'before:"{end_date}"')
                elif '-' in date_period and len(date_period) == 4:
                    # Year only
                    search_filters.append(f'year:{date_period}')
                else:
                    # Single date
                    search_filters.append(f'taken:"{date_period}"')

            # Add country filter if provided
            if geo_country:
                search_filters.append(f'country:"{geo_country}"')

            # Add tag filter if provided
            # Supports: single string, list of strings, or pipe-separated string
            if tags:
                if isinstance(tags, list):
                    # List of tags: join with | for OR logic
                    tag_query = '|'.join(tags)
                    search_filters.append(f'label:{tag_query}')
                elif '|' in tags:
                    # Already pipe-separated
                    search_filters.append(f'label:{tags}')
                else:
                    # Single tag
                    search_filters.append(f'label:{tags}')

            # Combine filters with space (AND logic)
            search_query = ' '.join(search_filters)

            # Build PhotoPrism API URL
            photoprism_base_url = os.getenv('PHOTOPRISM_BASE_URL', 'https://photoprism.augmentedbytech.com')
            api_url = f"{photoprism_base_url}/api/v1/photos"

            # Build query parameters
            query_params = {
                'q': search_query,
                'count': data.get('count', 100),
                'offset': data.get('offset', 0),
                'order': data.get('order', 'newest'),
                'merged': data.get('merged', True)
            }

            # Add query parameters to URL
            from urllib.parse import urlencode
            full_url = f"{api_url}?{urlencode(query_params)}"

            logging.info(f"Built PhotoPrism search URL: {full_url}")
            logging.info(f"Search query: {search_query}")

            return jsonify({
                "message": "Photo search query built",
                "action": action,
                "api_url": full_url,
                "search_query": search_query,
                "filters": {
                    "album": album_name,
                    "date_period": date_period,
                    "country": geo_country,
                    "tags": tags
                }
            })

        else:
            return jsonify({"error": f"Unknown action: {action}"}), 400

    except Exception as e:
        logging.exception(f"Error processing webhook: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Enable debug mode if FLASK_ENV is set to development
    debug_mode = os.getenv('FLASK_ENV') == 'development' or os.getenv('FLASK_DEBUG') == '1'
    app.run(host="0.0.0.0", port=8000, debug=debug_mode)