#!/usr/bin/env python3
"""
Development runner with auto-restart on file changes
"""
import os
import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class RestartHandler(FileSystemEventHandler):
    def __init__(self, restart_callback):
        self.restart_callback = restart_callback
        self.last_restart = 0
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        # Only restart for Python files
        if not event.src_path.endswith('.py'):
            return
            
        # Debounce - don't restart too frequently
        current_time = time.time()
        if current_time - self.last_restart < 2:
            return
            
        print(f"\n🔄 File changed: {event.src_path}")
        print("🔄 Restarting application...")
        self.last_restart = current_time
        self.restart_callback()

class DevServer:
    def __init__(self):
        self.process = None
        self.observer = None
        
    def start_app(self):
        """Start the Flask application"""
        if self.process:
            self.stop_app()
            
        print("🚀 Starting Flask application...")
        self.process = subprocess.Popen([
            sys.executable, 
            os.path.join("src", "main.py")
        ], cwd=Path(__file__).parent)
        
    def stop_app(self):
        """Stop the Flask application"""
        if self.process:
            print("🛑 Stopping Flask application...")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            
    def setup_watcher(self):
        """Setup file system watcher"""
        handler = RestartHandler(self.start_app)
        self.observer = Observer()
        
        # Watch the src directory
        src_path = Path(__file__).parent / "src"
        self.observer.schedule(handler, str(src_path), recursive=True)
        
        # Also watch the root directory for changes to .env, requirements.txt, etc.
        self.observer.schedule(handler, str(Path(__file__).parent), recursive=False)
        
        self.observer.start()
        print(f"👀 Watching for changes in: {src_path}")
        
    def run(self):
        """Run the development server with auto-restart"""
        try:
            self.start_app()
            self.setup_watcher()
            
            print("\n" + "="*60)
            print("🔥 Development server running with auto-restart!")
            print("📝 Edit any .py file and it will automatically restart")
            print("⏹️  Press Ctrl+C to stop")
            print("="*60 + "\n")
            
            # Keep the script running
            while True:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n🛑 Shutting down development server...")
            self.stop_app()
            if self.observer:
                self.observer.stop()
                self.observer.join()
            print("✅ Development server stopped")

if __name__ == "__main__":
    dev_server = DevServer()
    dev_server.run()