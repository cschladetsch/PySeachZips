#!/usr/bin/env python3
"""
Progress display utilities for PySearchZips
Handles progress bars, spinners, and heartbeat indicators
"""

import time
import threading
from colorama import Fore, Style

class ProgressDisplay:
    """Handles all progress display functionality"""
    
    def __init__(self):
        self.spinner_chars = "|/-\\|/-\\"
    
    def print_progress_bar(self, progress: float, width: int = 50, drive_name: str = "", 
                          current: int = 0, total: int = 0, color: str = Fore.GREEN):
        """Print a colored progress bar"""
        filled_length = int(width * progress)
        bar = '█' * filled_length + '░' * (width - filled_length)
        
        percentage = progress * 100
        status_text = f"{current}/{total}" if total > 0 else ""
        
        # Clear the line and print progress bar
        print(f"\r{color}[{drive_name:<8}] |{bar}| {percentage:6.1f}% {status_text}", end="", flush=True)
    
    def print_progress_bar_enhanced(self, progress: float, width: int = 35, drive_name: str = "", 
                                  current: int = 0, total: int = 0, color: str = Fore.GREEN,
                                  current_file: str = "", eta: str = ""):
        """Print an enhanced progress bar with current file and ETA"""
        filled_length = int(width * progress)
        bar = '█' * filled_length + '░' * (width - filled_length)
        
        percentage = progress * 100
        status_text = f"{current}/{total}"
        
        # Truncate current file if too long
        if len(current_file) > 25:
            current_file = current_file[:22] + "..."
        
        # Print progress bar with newline for thread safety
        if progress >= 1.0 or current_file == "COMPLETE":
            print(f"{color}[{drive_name:<8}] |{bar}| {percentage:5.1f}% {status_text} | {current_file:<25} | {eta}{Style.RESET_ALL}", 
                  flush=True)
    
    def spinner_animation(self, message: str, color: str = Fore.CYAN, stop_event=None):
        """Display spinning animation with message"""
        i = 0
        while not (stop_event and stop_event.is_set()):
            print(f"\r{color}{self.spinner_chars[i % len(self.spinner_chars)]} {message}{Style.RESET_ALL}", end="", flush=True)
            i += 1
            time.sleep(0.1)
    
    def start_spinner(self, message: str, color: str = Fore.CYAN):
        """Start spinner in background thread"""
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=self.spinner_animation, args=(message, color, stop_event))
        spinner_thread.daemon = True
        spinner_thread.start()
        return stop_event, spinner_thread

class HeartbeatManager:
    """Manages heartbeat indicators for long-running operations"""
    
    def __init__(self, interval: float = 2.0):
        self.interval = interval
        self.last_heartbeat = {}
    
    def should_show_heartbeat(self, operation_id: str) -> bool:
        """Check if heartbeat should be shown for this operation"""
        current_time = time.time()
        if operation_id not in self.last_heartbeat:
            self.last_heartbeat[operation_id] = current_time
            return False
        
        if current_time - self.last_heartbeat[operation_id] >= self.interval:
            self.last_heartbeat[operation_id] = current_time
            return True
        
        return False
    
    def reset(self, operation_id: str = None):
        """Reset heartbeat timer for operation or all operations"""
        if operation_id:
            self.last_heartbeat.pop(operation_id, None)
        else:
            self.last_heartbeat.clear()

class StatusReporter:
    """Reports status updates with consistent formatting"""
    
    def __init__(self, drive_color: str = Fore.GREEN):
        self.drive_color = drive_color
    
    def report_processing(self, drive: str, message: str):
        """Report a processing status message"""
        print(f"{self.drive_color}[{drive:<8}] {message}{Style.RESET_ALL}", flush=True)
    
    def report_completion(self, drive: str, message: str):
        """Report a completion message"""
        print(f"{Fore.GREEN}[{drive:<8}] {message}{Style.RESET_ALL}", flush=True)
    
    def report_error(self, drive: str, message: str):
        """Report an error message"""
        print(f"{Fore.RED}[{drive:<8}] ERROR: {message}{Style.RESET_ALL}", flush=True)
    
    def report_warning(self, drive: str, message: str):
        """Report a warning message"""
        print(f"{Fore.YELLOW}[{drive:<8}] WARNING: {message}{Style.RESET_ALL}", flush=True)