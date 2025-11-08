# PhotoFrame App

A Flask-based REST API for automating Microsoft Edge browser interactions with PhotoPrism. This app allows remote control of a photo display system through HTTP endpoints.

## Features

- **Browser Automation**: Control Edge browser via Selenium WebDriver
- **Profile Persistence**: Uses your existing Edge profile with saved passwords and settings
- **REST API**: Full HTTP REST interface for all browser operations
- **Session Management**: Automatically reconnects to existing browser instances
- **Logging & Monitoring**: Real-time log streaming via Server-Sent Events (SSE)
- **System Control**: Put the system to sleep via REST endpoint

## Installation

### Prerequisites
- Python 3.8+
- Microsoft Edge browser installed
- EdgeDriver (WebDriver for Edge)

### Setup

1. Clone/download the repository:
```bash
cd photoframe
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env`:
```env
EDGE_BINARY="C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
WEBDRIVER_PATH="C:\path\to\msedgedriver.exe"
PHOTOPRISM_BASE_URL="https://photoprism.augmentedbytech.com"
PHOTOPRISM_USERNAME="your_username"
PHOTOPRISM_PASSWORD="your_password"
FLASK_ENV=development
FLASK_DEBUG=1
```

4. Run the Flask server:
```bash
python src/main.py
```

The server will start on `http://localhost:8123`

## API Endpoints

### Window Management

#### Open Window
```bash
POST /open_window
```
Opens PhotoPrism in Edge browser with your saved profile and settings.

#### Close Windows
```bash
POST /close_windows
```
Closes all Edge browser windows.

#### Fullscreen
```bash
POST /fullscreen
```
Makes the current Edge window fullscreen.

### Navigation

#### Navigate to URL
```bash
POST /navigate
Content-Type: application/json

{
  "url": "https://photoprism.augmentedbytech.com/library/albums/at3la41gjbn7auu9/view"
}
```

### Page Interaction

#### Click Button
```bash
POST /click_button
Content-Type: application/json

{
  "button_id": "button-id-or-css-selector"
}
```

#### Input Text
```bash
POST /input_text
Content-Type: application/json

{
  "element_id": "field-id",
  "text": "text to input"
}
```

#### Send Enter Key
```bash
POST /send_enter
```

#### Send Tab Key
```bash
POST /send_tab
```

### Photo Features

#### Open First Photo
```bash
POST /open_first_photo
```
Opens the first photo in the current album view. Must be on `/library/browse` or `/library/albums/{id}/view`.

#### Start Slideshow
```bash
POST /start_slideshow
```
Starts a photo slideshow. First opens the first photo, then starts slideshow.

### System Control

#### Put System to Sleep
```bash
POST /sleep
```
Puts the Windows host to sleep.

### Monitoring

#### Get Driver State
```bash
GET /driver_state
```
Returns current browser driver state:
```json
{
  "driver_state": {
    "initialized": true,
    "current_url": "https://photoprism.augmentedbytech.com",
    "session_id": "abc123...",
    "is_alive": true,
    "window_handles": 1,
    "title": "PhotoPrism"
  }
}
```

#### List Browser Windows
```bash
GET /list_windows
```
Lists all open Edge browser windows/tabs:
```json
{
  "windows": [
    {
      "window_index": 0,
      "url": "https://photoprism.augmentedbytech.com",
      "title": "PhotoPrism",
      "is_current": true
    }
  ],
  "total_count": 1
}
```

#### Stream Logs (SSE)
```bash
GET /logs/stream
```
Streams server logs in real-time via Server-Sent Events.

### Webhooks

#### Generic Webhook
```bash
POST /webhook
Content-Type: application/json

{
  "action": "search_photos",
  "data": {
    "album-name": "Vacation",
    "date-period": "2023-01-01:2023-12-31",
    "geo-country": "US",
    "tag": "beach"
  }
}
```

## Testing

Basic curl examples for testing endpoints:

### Test Open Window
```bash
curl -X POST http://localhost:8123/open_window
```

### Test Navigation
```bash
curl -X POST http://localhost:8123/navigate \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://photoprism.augmentedbytech.com/library/browse\"}"
```

### Test Get Driver State
```bash
curl -X GET http://localhost:8123/driver_state
```

### Test List Windows
```bash
curl -X GET http://localhost:8123/list_windows
```

### Test Fullscreen
```bash
curl -X POST http://localhost:8123/fullscreen
```

### Test Sleep
```bash
curl -X POST http://localhost:8123/sleep
```

### Test Photo Search
```bash
curl -X POST http://localhost:8123/webhook \
  -H "Content-Type: application/json" \
  -d "{\"action\": \"search_photos\", \"data\": {\"album-name\": \"Vacation\", \"date-period\": \"2023-01\"}}"
```

See [doc/REST_examples.txt](doc/REST_examples.txt) for more examples.

## File Structure

```
photoframe/
├── src/
│   ├── main.py          # Flask app and REST endpoints
│   └── browser.py       # Selenium WebDriver wrapper
├── doc/
│   └── REST_examples.txt # Additional API examples
├── .vscode/
│   └── settings.json    # VS Code workspace settings
├── .env                 # Environment configuration
└── README.md            # This file
```

## Architecture

### main.py
Flask application with REST endpoints. Each route handles a specific browser operation.

### browser.py
Selenium WebDriver wrapper that:
- Maintains a global driver instance to keep browser windows open between requests
- Automatically reconnects to existing browser instances if the driver crashes
- Preserves browser window state (fullscreen, size, position) during interactions
- Supports multiple browser windows/tabs
- Uses your existing Edge profile for saved settings and passwords

## Features Explained

### Profile Persistence
The app uses your Edge user profile directory, which means:
- ✅ Saved passwords and password manager settings
- ✅ Bookmarks and browsing history
- ✅ Custom start page
- ✅ Extensions and add-ons
- ✅ Autofill data

### Session Reuse
Once opened, the browser session is reused for all subsequent operations. The driver instance is cached globally and only recreated if it crashes.

### Auto-Reconnection
If the driver loses connection to the browser (e.g., if the browser window is manually moved or resized), the app automatically attempts to reconnect to the existing browser instance via remote debugging.

## Troubleshooting

### Browser won't open
- Verify `EDGE_BINARY` and `WEBDRIVER_PATH` in `.env` are correct
- Make sure no existing Edge processes are blocking the port

### Driver keeps resetting
- Check that `--user-data-dir` path exists and is writable
- Verify Edge isn't running multiple instances

### Can't find elements
- Use the `/debug_elements` endpoint to see all available page elements
- Check that you're on the correct page/URL

## License

MIT
