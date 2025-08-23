#!/usr/bin/env python3
"""
Video Archive Scanner

Scans all available drives for zip files containing videos. Two modes available:
- Root folder mode (default): Scans zip files in root folders of drives
- All-zip mode: Scans all zip files across entire drives
Provides a searchable SQLite database with case-insensitive regex support.
"""

import os
import sys
import sqlite3
import zipfile
import uuid
import re
import argparse
import platform
import time
import threading
import hashlib
import json
import csv
from pathlib import Path
from typing import List, Tuple, Generator, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import logging

try:
    from colorama import Fore, Back, Style, init
    init(autoreset=True)  # Auto-reset colors
    COLORAMA_AVAILABLE = True
except ImportError:
    # Fallback if colorama is not available
    class MockColorama:
        def __getattr__(self, name):
            return ""
    
    Fore = Back = Style = MockColorama()
    COLORAMA_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Common video file extensions
VIDEO_EXTENSIONS = {
    '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v',
    '.3gp', '.3g2', '.asf', '.divx', '.f4v', '.m2ts', '.mts', '.ogv',
    '.rm', '.rmvb', '.vob', '.xvid', '.mpg', '.mpeg', '.m1v', '.m2v'
}

class VideoArchiveScanner:
    def __init__(self, database_path: str = 'zip_files.db', root_folders_only: bool = True, config_file: str = None):
        self.database_path = database_path
        self.root_folders_only = root_folders_only
        self.connection = None
        
        # Load configuration
        self.config = self.load_config(config_file)
        
        # Override defaults with config
        if config_file and 'database_path' in self.config:
            self.database_path = self.config['database_path']
        
        self.setup_database()
    
    def load_config(self, config_file: str = None) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        default_config = {
            "video_extensions": [
                ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v",
                ".3gp", ".3g2", ".asf", ".divx", ".f4v", ".m2ts", ".mts", ".ogv",
                ".rm", ".rmvb", ".vob", ".xvid", ".mpg", ".mpeg", ".m1v", ".m2v"
            ],
            "excluded_directories": [
                "System Volume Information", "$RECYCLE.BIN", "Windows", 
                "node_modules", ".git", "__pycache__"
            ],
            "batch_size": 1000,
            "max_memory_mb": 100,
            "max_workers": 4,
            "enable_thumbnails": False,
            "enable_hashing": True,
            "quiet_mode": False,
            "dry_run": False
        }
        
        if config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
                    logger.info(f"Loaded configuration from {config_file}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config file {config_file}: {e}")
        
        return default_config
    
    def setup_database(self):
        """Initialize SQLite database with required tables"""
        self.connection = sqlite3.connect(self.database_path)
        cursor = self.connection.cursor()
        
        # Create zip_files table with enhanced schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zip_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_letter TEXT NOT NULL,
                zip_file_name TEXT NOT NULL,
                zip_file_path TEXT NOT NULL,
                uuid TEXT UNIQUE NOT NULL,
                file_size INTEGER DEFAULT 0,
                file_hash TEXT,
                last_modified TIMESTAMP,
                scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create file_contents table with enhanced schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zip_uuid TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_path_in_zip TEXT NOT NULL,
                file_hash TEXT,
                video_duration REAL,
                video_resolution TEXT,
                last_modified TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zip_uuid) REFERENCES zip_files (uuid)
            )
        ''')
        
        # Create scan_progress table for resume capability
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_letter TEXT NOT NULL,
                last_processed_path TEXT,
                scan_start TIMESTAMP,
                scan_status TEXT DEFAULT 'in_progress',
                total_folders INTEGER DEFAULT 0,
                processed_folders INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create scan_metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scan_mode TEXT NOT NULL,
                drives_scanned INTEGER,
                zip_files_found INTEGER,
                video_files_found INTEGER,
                total_size_bytes INTEGER,
                scan_duration_seconds REAL,
                errors_encountered INTEGER DEFAULT 0
            )
        ''')
        
        # Add new columns to existing tables if they don't exist (must be before creating indexes)
        self._add_missing_columns()
        
        # Create indexes for better search performance (after columns exist)
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_zip_uuid ON file_contents(zip_uuid)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_name ON file_contents(file_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_drive_letter ON zip_files(drive_letter)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_size ON file_contents(file_size)')
            
            # Only create hash and scan_date indexes if columns exist
            cursor.execute("PRAGMA table_info(file_contents)")
            file_columns = {row[1] for row in cursor.fetchall()}
            if 'file_hash' in file_columns:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_hash ON file_contents(file_hash)')
            
            cursor.execute("PRAGMA table_info(zip_files)")
            zip_columns = {row[1] for row in cursor.fetchall()}
            if 'file_hash' in zip_columns:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_zip_hash ON zip_files(file_hash)')
            if 'scan_date' in zip_columns:
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_date ON zip_files(scan_date)')
                
        except sqlite3.Error as e:
            logger.warning(f"Failed to create some indexes: {e}")
        
        self.connection.commit()
        logger.info(f"Database initialized at: {self.database_path}")
    
    def _add_missing_columns(self):
        """Add missing columns to existing tables for backwards compatibility"""
        cursor = self.connection.cursor()
        
        try:
            # Get existing columns for zip_files table
            cursor.execute("PRAGMA table_info(zip_files)")
            existing_zip_columns = {row[1] for row in cursor.fetchall()}
            
            # Get existing columns for file_contents table  
            cursor.execute("PRAGMA table_info(file_contents)")
            existing_file_columns = {row[1] for row in cursor.fetchall()}
            
            # Add missing columns to zip_files
            new_zip_columns = [
                ('file_size', 'INTEGER DEFAULT 0'),
                ('file_hash', 'TEXT'),
                ('last_modified', 'TIMESTAMP'),
                ('scan_date', 'TIMESTAMP')
            ]
            
            for col_name, col_def in new_zip_columns:
                if col_name not in existing_zip_columns:
                    try:
                        cursor.execute(f'ALTER TABLE zip_files ADD COLUMN {col_name} {col_def}')
                        logger.info(f"Added column {col_name} to zip_files table")
                    except sqlite3.Error as e:
                        logger.warning(f"Failed to add column {col_name} to zip_files: {e}")
            
            # Add missing columns to file_contents
            new_file_columns = [
                ('file_hash', 'TEXT'),
                ('video_duration', 'REAL'),
                ('video_resolution', 'TEXT'),
                ('last_modified', 'TIMESTAMP')
            ]
            
            for col_name, col_def in new_file_columns:
                if col_name not in existing_file_columns:
                    try:
                        cursor.execute(f'ALTER TABLE file_contents ADD COLUMN {col_name} {col_def}')
                        logger.info(f"Added column {col_name} to file_contents table")
                    except sqlite3.Error as e:
                        logger.warning(f"Failed to add column {col_name} to file_contents: {e}")
                        
        except sqlite3.Error as e:
            logger.error(f"Error during schema migration: {e}")
            # Continue anyway - the database might still be usable
    
    def get_available_drives(self) -> List[str]:
        """Get list of available drives based on the operating system"""
        drives = []
        
        # Check if running in WSL
        is_wsl = self.is_wsl()
        
        if platform.system() == 'Windows':
            # Windows drive detection
            import string
            for letter in string.ascii_uppercase:
                drive_path = f"{letter}:\\"
                if os.path.exists(drive_path):
                    drives.append(drive_path)
        else:
            # Unix-like systems (Linux, macOS)
            # Check common mount points
            mount_points = ['/']
            
            # If running in WSL, also check for Windows drives mounted at /mnt/c, /mnt/d, etc.
            if is_wsl:
                import string
                for letter in string.ascii_lowercase:
                    wsl_drive_path = f"/mnt/{letter}"
                    if os.path.exists(wsl_drive_path) and os.path.ismount(wsl_drive_path):
                        mount_points.append(wsl_drive_path)
                        logger.info(f"Found WSL Windows drive: {wsl_drive_path}")
            
            # Check /mnt and /media directories for other mounted drives
            for mount_dir in ['/mnt', '/media']:
                if os.path.exists(mount_dir):
                    try:
                        for item in os.listdir(mount_dir):
                            mount_path = os.path.join(mount_dir, item)
                            if os.path.ismount(mount_path) and mount_path not in mount_points:
                                mount_points.append(mount_path)
                    except PermissionError:
                        logger.warning(f"Permission denied accessing {mount_dir}")
            
            drives = mount_points
        
        logger.info(f"Found {len(drives)} available drives: {drives}")
        return drives
    
    def is_wsl(self) -> bool:
        """Check if running in Windows Subsystem for Linux (WSL)"""
        try:
            # Check for WSL-specific files or environment variables
            if os.path.exists('/proc/version'):
                with open('/proc/version', 'r') as f:
                    version_info = f.read().lower()
                    return 'microsoft' in version_info or 'wsl' in version_info
            
            # Alternative check: WSL_DISTRO_NAME environment variable
            if os.getenv('WSL_DISTRO_NAME'):
                return True
                
            return False
        except Exception:
            return False
    
    def find_google_takeout_folders(self, drives: List[str]) -> Generator[Tuple[str, int], None, None]:
        """Find GoogleTakeout folders in root directories of drives"""
        for drive in drives:
            logger.info(f"Scanning drive: {drive}")
            folders_scanned = 0
            takeout_folders = []
            
            try:
                # Only scan root folder of the drive for GoogleTakeout folders
                if os.path.exists(drive):
                    try:
                        items = os.listdir(drive)
                        folders_scanned = len([item for item in items if os.path.isdir(os.path.join(drive, item))])
                        
                        # Look specifically for GoogleTakeout folders
                        if 'GoogleTakeout' in items:
                            takeout_path = os.path.join(drive, 'GoogleTakeout')
                            if os.path.isdir(takeout_path):
                                takeout_folders.append(takeout_path)
                                logger.info(f"Found GoogleTakeout folder: {takeout_path}")
                    except PermissionError:
                        logger.warning(f"Permission denied accessing {drive}")
                        continue
                
                # Yield each found GoogleTakeout folder with total folders scanned for this drive
                for takeout_path in takeout_folders:
                    yield takeout_path, folders_scanned
                    
            except (PermissionError, OSError) as e:
                logger.warning(f"Cannot access {drive}: {e}")
                continue
    
    def find_zip_files_in_folder(self, folder_path: str) -> Generator[str, None, None]:
        """Find all zip files in a given folder"""
        try:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith('.zip'):
                        zip_path = os.path.join(root, file)
                        yield zip_path
        except (PermissionError, OSError) as e:
            logger.warning(f"Cannot access {folder_path}: {e}")
    
    def find_all_zip_files_on_drive(self, drive: str) -> Generator[str, None, None]:
        """Find all zip files on a drive (scans entire drive)"""
        try:
            for root, dirs, files in os.walk(drive):
                # Skip system and hidden directories to avoid issues
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['System Volume Information', '$RECYCLE.BIN', 'Windows']]
                
                for file in files:
                    if file.lower().endswith('.zip'):
                        zip_path = os.path.join(root, file)
                        yield zip_path
        except (PermissionError, OSError) as e:
            logger.warning(f"Cannot access {drive}: {e}")
    
    def is_video_file(self, filename: str) -> bool:
        """Check if a file is a video file based on its extension"""
        video_extensions = set(self.config.get('video_extensions', VIDEO_EXTENSIONS))
        return Path(filename).suffix.lower() in video_extensions
    
    def calculate_file_hash(self, zip_path: str, file_path_in_zip: str) -> Optional[str]:
        """Calculate MD5 hash of a file within a ZIP archive"""
        if not self.config.get('enable_hashing', True):
            return None
            
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                with zip_file.open(file_path_in_zip) as file_data:
                    hash_md5 = hashlib.md5()
                    # Read in chunks to avoid memory issues with large files
                    max_size = self.config.get('max_memory_mb', 100) * 1024 * 1024
                    bytes_read = 0
                    
                    for chunk in iter(lambda: file_data.read(4096), b""):
                        if bytes_read + len(chunk) > max_size:
                            logger.warning(f"File {file_path_in_zip} too large for hashing, skipping")
                            return None
                        hash_md5.update(chunk)
                        bytes_read += len(chunk)
                    
                    return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash file {file_path_in_zip} in {zip_path}: {e}")
            return None
    
    def calculate_zip_hash(self, zip_path: str) -> Optional[str]:
        """Calculate hash of ZIP file itself"""
        if not self.config.get('enable_hashing', True):
            return None
            
        try:
            hash_md5 = hashlib.md5()
            with open(zip_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to hash ZIP file {zip_path}: {e}")
            return None
    
    def scan_zip_for_videos(self, zip_path: str) -> List[Tuple[str, int, str, Optional[str]]]:
        """Scan a zip file for video files and return (name, size, path_in_zip, hash) tuples"""
        video_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                for file_info in zip_file.infolist():
                    if not file_info.is_dir() and self.is_video_file(file_info.filename):
                        file_hash = self.calculate_file_hash(zip_path, file_info.filename)
                        video_files.append((
                            os.path.basename(file_info.filename),
                            file_info.file_size,
                            file_info.filename,
                            file_hash
                        ))
        except (zipfile.BadZipFile, PermissionError, OSError) as e:
            logger.warning(f"Cannot read zip file {zip_path}: {e}")
            return []
        
        return video_files
    
    def get_drive_letter(self, path: str) -> str:
        """Extract drive letter or mount point from a path"""
        if platform.system() == 'Windows':
            return path.split(':')[0] + ':'
        else:
            # For Unix-like systems, return the mount point
            path_obj = Path(path)
            
            # Handle WSL Windows drives (e.g., /mnt/c -> c:)
            if self.is_wsl() and len(path_obj.parts) >= 3 and path_obj.parts[1] == 'mnt':
                drive_letter = path_obj.parts[2]
                if len(drive_letter) == 1 and drive_letter.isalpha():
                    return f"{drive_letter.upper()}:"
            
            # For other Unix paths, return the first non-root part
            for part in path_obj.parts:
                if part != '/':
                    return part
            return '/'
    
    def insert_zip_data(self, zip_path: str, video_files: List[Tuple[str, int, str, Optional[str]]]) -> str:
        """Insert zip file and its video files into the database with enhanced data"""
        if not video_files:
            return None
        
        zip_uuid = str(uuid.uuid4())
        drive_letter = self.get_drive_letter(zip_path)
        zip_file_name = os.path.basename(zip_path)
        
        # Get ZIP file metadata
        zip_file_size = 0
        zip_last_modified = None
        zip_hash = None
        
        try:
            stat_info = os.stat(zip_path)
            zip_file_size = stat_info.st_size
            zip_last_modified = datetime.fromtimestamp(stat_info.st_mtime)
            zip_hash = self.calculate_zip_hash(zip_path)
        except OSError as e:
            logger.warning(f"Could not get metadata for {zip_path}: {e}")
        
        cursor = self.connection.cursor()
        
        # Insert zip file record with enhanced data
        cursor.execute('''
            INSERT INTO zip_files (drive_letter, zip_file_name, zip_file_path, uuid, 
                                 file_size, file_hash, last_modified, scan_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (drive_letter, zip_file_name, zip_path, zip_uuid, 
              zip_file_size, zip_hash, zip_last_modified, datetime.now()))
        
        # Batch insert video files
        video_data = []
        for file_name, file_size, file_path_in_zip, file_hash in video_files:
            video_data.append((zip_uuid, file_name, file_size, file_path_in_zip, file_hash, datetime.now()))
        
        cursor.executemany('''
            INSERT INTO file_contents (zip_uuid, file_name, file_size, file_path_in_zip, file_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', video_data)
        
        self.connection.commit()
        
        if not self.config.get('quiet_mode', False):
            logger.info(f"Inserted {len(video_files)} video files from {zip_file_name}")
        return zip_uuid
    
    def batch_insert_zip_data(self, zip_data_list: List[Tuple[str, List[Tuple]]]) -> int:
        """Batch insert multiple ZIP files and their contents"""
        if not zip_data_list:
            return 0
        
        cursor = self.connection.cursor()
        zip_records = []
        video_records = []
        
        for zip_path, video_files in zip_data_list:
            if not video_files:
                continue
                
            zip_uuid = str(uuid.uuid4())
            drive_letter = self.get_drive_letter(zip_path)
            zip_file_name = os.path.basename(zip_path)
            
            # Get ZIP metadata
            zip_file_size = 0
            zip_last_modified = None
            zip_hash = None
            
            try:
                stat_info = os.stat(zip_path)
                zip_file_size = stat_info.st_size
                zip_last_modified = datetime.fromtimestamp(stat_info.st_mtime)
                zip_hash = self.calculate_zip_hash(zip_path)
            except OSError:
                pass
            
            zip_records.append((
                drive_letter, zip_file_name, zip_path, zip_uuid,
                zip_file_size, zip_hash, zip_last_modified, datetime.now()
            ))
            
            for file_name, file_size, file_path_in_zip, file_hash in video_files:
                video_records.append((
                    zip_uuid, file_name, file_size, file_path_in_zip, file_hash, datetime.now()
                ))
        
        # Batch insert ZIP files
        cursor.executemany('''
            INSERT INTO zip_files (drive_letter, zip_file_name, zip_file_path, uuid,
                                 file_size, file_hash, last_modified, scan_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', zip_records)
        
        # Batch insert video files
        cursor.executemany('''
            INSERT INTO file_contents (zip_uuid, file_name, file_size, file_path_in_zip, file_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', video_records)
        
        self.connection.commit()
        
        if not self.config.get('quiet_mode', False):
            logger.info(f"Batch inserted {len(zip_records)} ZIP files with {len(video_records)} video files")
        
        return len(zip_records)
    
    def print_progress_bar(self, progress: float, width: int = 50, drive_name: str = "", 
                          current: int = 0, total: int = 0, color: str = Fore.GREEN):
        """Print a colored progress bar"""
        filled_length = int(width * progress)
        bar = '█' * filled_length + '░' * (width - filled_length)
        
        percentage = progress * 100
        status_text = f"{current}/{total}" if total > 0 else ""
        
        # Clear the line and print progress bar
        print(f"\r{color}[{drive_name:<8}] |{bar}| {percentage:6.1f}% {status_text}", end="", flush=True)
    
    def spinner_animation(self, message: str, color: str = Fore.CYAN, stop_event=None):
        """Display spinning animation with message"""
        spinner_chars = "|/-\\|/-\\"
        i = 0
        while not (stop_event and stop_event.is_set()):
            print(f"\r{color}{spinner_chars[i % len(spinner_chars)]} {message}{Style.RESET_ALL}", end="", flush=True)
            i += 1
            time.sleep(0.1)
    
    def start_spinner(self, message: str, color: str = Fore.CYAN):
        """Start spinner in background thread"""
        stop_event = threading.Event()
        spinner_thread = threading.Thread(target=self.spinner_animation, args=(message, color, stop_event))
        spinner_thread.daemon = True
        spinner_thread.start()
        return stop_event, spinner_thread
    
    def scan_drive_with_progress(self, drive: str, drive_color: str) -> Tuple[int, int, int]:
        """Scan a single drive with progress display"""
        if self.root_folders_only:
            return self._scan_drive_google_takeout_mode(drive, drive_color)
        else:
            return self._scan_drive_all_zip_mode(drive, drive_color)
    
    def _scan_drive_google_takeout_mode(self, drive: str, drive_color: str) -> Tuple[int, int, int]:
        """Scan drive in GoogleTakeout mode - only scan GoogleTakeout folders in root directories"""
        folders_scanned = 0
        takeout_folders_found = 0
        
        print(f"\n{drive_color}Scanning drive (GoogleTakeout mode): {drive}{Style.RESET_ALL}")
        
        # Start spinner for folder scanning
        stop_event, spinner_thread = self.start_spinner(f"Scanning for GoogleTakeout folders on {drive}...", drive_color)
        
        # First pass: find GoogleTakeout folders and their zip files
        all_zips = []
        takeout_paths = []
        
        for takeout_path, folder_count in self.find_google_takeout_folders([drive]):
            folders_scanned = folder_count
            takeout_folders_found += 1
            takeout_paths.append(takeout_path)
            
            for zip_path in self.find_zip_files_in_folder(takeout_path):
                all_zips.append(zip_path)
        
        # Stop spinner
        stop_event.set()
        spinner_thread.join(timeout=0.5)
        print(f"\r{' ' * 80}\r", end="")  # Clear spinner line
        
        # Display scan results
        if folders_scanned > 0:
            print(f"{drive_color}   Scanned {folders_scanned:,} root folders{Style.RESET_ALL}")
        
        if takeout_folders_found == 0:
            print(f"{Fore.YELLOW}   No GoogleTakeout folders found on {drive}")
            return 0, 0, folders_scanned
        
        # Highlight found GoogleTakeout folders
        for takeout_path in takeout_paths:
            short_path = takeout_path.replace(drive, "").lstrip(os.sep)
            print(f"{Fore.GREEN}   Found GoogleTakeout: {Style.BRIGHT}{short_path}{Style.RESET_ALL}")
        
        total_zip_files = len(all_zips)
        
        if total_zip_files == 0:
            print(f"{Fore.YELLOW}   No zip files found in GoogleTakeout folders")
            return 0, 0, folders_scanned
        
        print(f"{Fore.CYAN}   Found {total_zip_files} zip files to process")
        
        return self._process_zip_files(all_zips, drive, drive_color, total_zip_files)
    
    def _scan_drive_all_zip_mode(self, drive: str, drive_color: str) -> Tuple[int, int, int]:
        """Scan drive in all-zip mode (scan all zip files on drive)"""
        total_zips = 0
        total_videos = 0
        zip_count = 0
        
        print(f"\n{drive_color}Scanning drive (all zip files): {drive}{Style.RESET_ALL}")
        
        # Start spinner for zip file discovery
        stop_event, spinner_thread = self.start_spinner(f"Finding all zip files on {drive}...", drive_color)
        
        # Find all zip files on the drive
        all_zips = []
        for zip_path in self.find_all_zip_files_on_drive(drive):
            all_zips.append(zip_path)
        
        # Stop spinner
        stop_event.set()
        spinner_thread.join(timeout=0.5)
        print(f"\r{' ' * 80}\r", end="")  # Clear spinner line
        
        total_zip_files = len(all_zips)
        
        if total_zip_files == 0:
            print(f"{Fore.YELLOW}   No zip files found on {drive}")
            return 0, 0, 0
        
        print(f"{Fore.CYAN}   Found {total_zip_files} zip files to process")
        
        return self._process_zip_files(all_zips, drive, drive_color, total_zip_files)
    
    def _process_zip_files(self, all_zips: List[str], drive: str, drive_color: str, total_zip_files: int) -> Tuple[int, int, int]:
        """Process a list of zip files and return statistics"""
        total_zips = 0
        total_videos = 0
        zip_count = 0
        
        # Process with progress bar
        for zip_path in all_zips:
            zip_count += 1
            progress = zip_count / total_zip_files
            
            # Show progress bar
            zip_name = os.path.basename(zip_path)[:30]
            self.print_progress_bar(progress, 40, drive, zip_count, total_zip_files, drive_color)
            
            # Process the zip file
            video_files = self.scan_zip_for_videos(zip_path)
            
            if video_files:
                self.insert_zip_data(zip_path, video_files)
                total_zips += 1
                total_videos += len(video_files)
        
        # Complete the progress bar
        self.print_progress_bar(1.0, 40, drive, total_zip_files, total_zip_files, drive_color)
        
        if total_videos > 0:
            print(f"\n{Fore.GREEN}   Processed {total_zips} zip files, found {total_videos:,} videos")
        else:
            print(f"\n{Fore.YELLOW}   No video files found in {total_zips} zip files")
        
        return total_zips, total_videos, 0
    
    def get_database_summary(self):
        """Get current database summary"""
        cursor = self.connection.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM zip_files")
        zip_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM file_contents")
        video_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(file_size) FROM file_contents")
        total_size = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(DISTINCT drive_letter) FROM zip_files")
        drive_count = cursor.fetchone()[0]
        
        return {
            'drives': drive_count,
            'zip_files': zip_count,
            'video_files': video_count,
            'total_size_gb': total_size / (1024**3)
        }

    def scan_all_drives(self):
        """Main scanning function to process all drives with colored progress bars"""
        drives = self.get_available_drives()
        total_zips = 0
        total_videos = 0
        total_folders_scanned = 0
        
        # Get initial database state
        initial_stats = self.get_database_summary()
        
        # Define colors for different drives
        drive_colors = [
            Fore.GREEN, Fore.BLUE, Fore.MAGENTA, Fore.CYAN, 
            Fore.RED, Fore.YELLOW, Fore.WHITE, Fore.LIGHTGREEN_EX,
            Fore.LIGHTBLUE_EX, Fore.LIGHTMAGENTA_EX, Fore.LIGHTCYAN_EX,
            Fore.LIGHTRED_EX, Fore.LIGHTYELLOW_EX, Fore.LIGHTWHITE_EX
        ]
        
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.CYAN}DATABASE STATUS (BEFORE SCAN){Style.RESET_ALL}")
        print(f"   Drives indexed: {Fore.YELLOW}{initial_stats['drives']}{Style.RESET_ALL}")
        print(f"   Zip files: {Fore.YELLOW}{initial_stats['zip_files']}{Style.RESET_ALL}")
        print(f"   Video files: {Fore.YELLOW}{initial_stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{initial_stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        
        scan_mode_desc = "GoogleTakeout folders only" if self.root_folders_only else "all zip files on drives"
        print(f"\n{Style.BRIGHT}{Fore.WHITE}Starting scan of {len(drives)} drives ({scan_mode_desc})...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Drive scan order: {', '.join(drives)}{Style.RESET_ALL}")
        
        start_time = time.time()
        
        for i, drive in enumerate(drives):
            drive_color = drive_colors[i % len(drive_colors)]
            drive_zips, drive_videos, folders_scanned = self.scan_drive_with_progress(drive, drive_color)
            total_zips += drive_zips
            total_videos += drive_videos
            total_folders_scanned += folders_scanned
        
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)
        
        # Get final database state
        final_stats = self.get_database_summary()
        
        # Calculate differences
        new_zip_files = final_stats['zip_files'] - initial_stats['zip_files']
        new_video_files = final_stats['video_files'] - initial_stats['video_files']
        new_size_gb = final_stats['total_size_gb'] - initial_stats['total_size_gb']
        
        # Final summary
        print(f"\n{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.GREEN}SCAN COMPLETE!{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.CYAN}SCAN RESULTS:{Style.RESET_ALL}")
        print(f"   Drives scanned: {Fore.YELLOW}{len(drives)}{Style.RESET_ALL}")
        print(f"   Folders examined: {Fore.YELLOW}{total_folders_scanned:,}{Style.RESET_ALL}")
        print(f"   Zip files processed: {Fore.YELLOW}{total_zips}{Style.RESET_ALL}")
        print(f"   Video files found: {Fore.YELLOW}{total_videos:,}{Style.RESET_ALL}")
        print(f"   Time elapsed: {Fore.YELLOW}{int(minutes):02d}:{int(seconds):02d}{Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}DATABASE STATUS (AFTER SCAN){Style.RESET_ALL}")
        print(f"   Total drives indexed: {Fore.YELLOW}{final_stats['drives']}{Style.RESET_ALL}")
        print(f"   Total zip files: {Fore.YELLOW}{final_stats['zip_files']}{Style.RESET_ALL} {Fore.GREEN}(+{new_zip_files}){Style.RESET_ALL}")
        print(f"   Total video files: {Fore.YELLOW}{final_stats['video_files']:,}{Style.RESET_ALL} {Fore.GREEN}(+{new_video_files:,}){Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{final_stats['total_size_gb']:.2f} GB{Style.RESET_ALL} {Fore.GREEN}(+{new_size_gb:.2f} GB){Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        
        logger.info(f"Scan complete. Processed {total_zips} zip files containing {total_videos} video files")
    
    def search_videos(self, pattern: str, regex: bool = False) -> List[Tuple]:
        """Search for video files using case-insensitive matching"""
        cursor = self.connection.cursor()
        
        if regex:
            # Use SQLite's regexp function (requires regex support)
            query = '''
                SELECT z.drive_letter, z.zip_file_name, z.zip_file_path, 
                       f.file_name, f.file_size, f.file_path_in_zip
                FROM zip_files z
                JOIN file_contents f ON z.uuid = f.zip_uuid
                WHERE f.file_name REGEXP ?
                ORDER BY z.drive_letter, z.zip_file_name, f.file_name
            '''
            try:
                cursor.execute(query, (f"(?i){pattern}",))
            except sqlite3.OperationalError:
                logger.error("Regex search requires SQLite with regex support. Using LIKE instead.")
                return self.search_videos(pattern, regex=False)
        else:
            # Use LIKE for simple pattern matching
            query = '''
                SELECT z.drive_letter, z.zip_file_name, z.zip_file_path,
                       f.file_name, f.file_size, f.file_path_in_zip
                FROM zip_files z
                JOIN file_contents f ON z.uuid = f.zip_uuid
                WHERE f.file_name LIKE ? COLLATE NOCASE
                ORDER BY z.drive_letter, z.zip_file_name, f.file_name
            '''
            cursor.execute(query, (f"%{pattern}%",))
        
        return cursor.fetchall()
    
    def print_search_results(self, results: List[Tuple]):
        """Pretty print search results with full paths"""
        if not results:
            print("No matching video files found.")
            return
        
        print(f"{Style.BRIGHT}{Fore.GREEN}Found {len(results)} matching video files:{Style.RESET_ALL}\n")
        
        for i, (drive, zip_name, zip_path, file_name, file_size, file_path_in_zip) in enumerate(results, 1):
            size_mb = file_size / (1024 * 1024) if file_size else 0
            
            print(f"{Style.BRIGHT}{Fore.CYAN}Result #{i}{Style.RESET_ALL}")
            print(f"   {Fore.YELLOW}Drive:{Style.RESET_ALL} {drive}")
            print(f"   {Fore.YELLOW}Zip File:{Style.RESET_ALL} {zip_name}")
            print(f"   {Fore.YELLOW}Full Zip Path:{Style.RESET_ALL} {zip_path}")
            print(f"   {Fore.YELLOW}Video File:{Style.RESET_ALL} {file_name}")
            print(f"   {Fore.YELLOW}Size:{Style.RESET_ALL} {size_mb:.1f} MB")
            print(f"   {Fore.YELLOW}Path in Zip:{Style.RESET_ALL} {file_path_in_zip}")
            print()
    
    def get_database_stats(self):
        """Get statistics about the database contents"""
        cursor = self.connection.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM zip_files")
        zip_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM file_contents")
        video_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(file_size) FROM file_contents")
        total_size = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(DISTINCT drive_letter) FROM zip_files")
        drive_count = cursor.fetchone()[0]
        
        print(f"\nDatabase Statistics:")
        print(f"  Drives scanned: {drive_count}")
        print(f"  Zip files indexed: {zip_count}")
        print(f"  Video files found: {video_count}")
        print(f"  Total video size: {total_size / (1024**3):.2f} GB")
    
    def list_drives_in_database(self):
        """List all drive names stored in the database with their statistics"""
        cursor = self.connection.cursor()
        
        query = '''
            SELECT z.drive_letter,
                   COUNT(DISTINCT z.id) as zip_count,
                   COUNT(f.id) as video_count,
                   COALESCE(SUM(f.file_size), 0) as total_size
            FROM zip_files z
            LEFT JOIN file_contents f ON z.uuid = f.zip_uuid
            GROUP BY z.drive_letter
            ORDER BY z.drive_letter
        '''
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        if not results:
            print("No drives found in database. Run with --scan to populate the database.")
            return
        
        print(f"\nDrives in Database:")
        print(f"{'Drive':<15} {'Zip Files':<12} {'Video Files':<15} {'Total Size (GB)':<15}")
        print("-" * 60)
        
        for drive, zip_count, video_count, total_size in results:
            size_gb = total_size / (1024**3) if total_size else 0
            print(f"{drive:<15} {zip_count:<12} {video_count:<15} {size_gb:>12.2f}")
        
        total_drives = len(results)
        total_zips = sum(row[1] for row in results)
        total_videos = sum(row[2] for row in results)
        total_size_all = sum(row[3] for row in results) / (1024**3)
        
        print("-" * 60)
        print(f"{'TOTAL':<15} {total_zips:<12} {total_videos:<15} {total_size_all:>12.2f}")
        print(f"\nTotal drives: {total_drives}")
    
    def validate_database(self) -> List[str]:
        """Validate database integrity and return list of issues"""
        issues = []
        cursor = self.connection.cursor()
        
        try:
            # Check for ZIP files that no longer exist
            cursor.execute("SELECT zip_file_path FROM zip_files")
            zip_paths = cursor.fetchall()
            
            missing_zips = 0
            for (zip_path,) in zip_paths:
                if not os.path.exists(zip_path):
                    missing_zips += 1
            
            if missing_zips > 0:
                issues.append(f"{missing_zips} ZIP files in database no longer exist on disk")
            
            # Check for orphaned file_contents records
            cursor.execute('''
                SELECT COUNT(*) FROM file_contents fc 
                LEFT JOIN zip_files zf ON fc.zip_uuid = zf.uuid 
                WHERE zf.uuid IS NULL
            ''')
            orphaned = cursor.fetchone()[0]
            if orphaned > 0:
                issues.append(f"{orphaned} orphaned video file records")
            
            # Check database integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            if integrity_result != 'ok':
                issues.append(f"Database integrity issue: {integrity_result}")
                
        except sqlite3.Error as e:
            issues.append(f"Database error during validation: {e}")
        
        return issues
    
    def find_duplicate_videos(self) -> List[List[Dict[str, Any]]]:
        """Find duplicate video files based on hash"""
        cursor = self.connection.cursor()
        
        # Find files with the same hash
        cursor.execute('''
            SELECT fc.file_hash, zf.zip_file_path, fc.file_name, fc.file_size
            FROM file_contents fc
            JOIN zip_files zf ON fc.zip_uuid = zf.uuid
            WHERE fc.file_hash IS NOT NULL
            GROUP BY fc.file_hash
            HAVING COUNT(*) > 1
            ORDER BY fc.file_hash, fc.file_size DESC
        ''')
        
        duplicates = {}
        for file_hash, zip_path, file_name, file_size in cursor.fetchall():
            if file_hash not in duplicates:
                duplicates[file_hash] = []
            duplicates[file_hash].append({
                'hash': file_hash,
                'zip_path': zip_path,
                'file_name': file_name,
                'file_size': file_size
            })
        
        return list(duplicates.values())
    
    def export_search_results_to_csv(self, results: List[Tuple], filename: str):
        """Export search results to CSV file"""
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['Drive', 'ZIP File', 'ZIP Path', 'Video File', 'Size (MB)', 'Path in ZIP'])
            
            for drive, zip_name, zip_path, file_name, file_size, file_path_in_zip in results:
                size_mb = file_size / (1024 * 1024) if file_size else 0
                writer.writerow([drive, zip_name, zip_path, file_name, f"{size_mb:.1f}", file_path_in_zip])
        
        print(f"Exported {len(results)} search results to {filename}")
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()


def main():
    parser = argparse.ArgumentParser(description='Video Archive Scanner - Scan root folders or all zip files for videos')
    parser.add_argument('--database', '-db', default='zip_files.db',
                       help='SQLite database path (default: zip_files.db)')
    parser.add_argument('--config', '-c', type=str,
                       help='Configuration file path (JSON format)')
    parser.add_argument('--scan', action='store_true',
                       help='Scan drives for video files (root folders by default, or all zip files with --no-google-takeout)')
    parser.add_argument('--search', '-s', type=str,
                       help='Search for video files by name')
    parser.add_argument('--regex', action='store_true',
                       help='Use regex for search pattern')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--drives', action='store_true',
                       help='List all drive names in database with statistics')
    parser.add_argument('--google-takeout', action='store_true', default=True,
                       help='Search only GoogleTakeout folders in root directories (default: True)')
    parser.add_argument('--no-google-takeout', dest='google_takeout', action='store_false',
                       help='Scan all zip files on all drives instead of just GoogleTakeout folders')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Quiet mode - minimal output')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be scanned without actually scanning')
    parser.add_argument('--exclude-paths', nargs='*',
                       help='Additional paths to exclude from scanning')
    parser.add_argument('--export-csv', type=str,
                       help='Export search results to CSV file')
    parser.add_argument('--find-duplicates', action='store_true',
                       help='Find and display duplicate video files')
    parser.add_argument('--validate-db', action='store_true',
                       help='Validate database integrity')
    
    args = parser.parse_args()
    
    scanner = VideoArchiveScanner(args.database, args.google_takeout, args.config)
    
    # Override config with command line arguments
    if args.quiet:
        scanner.config['quiet_mode'] = True
    if args.dry_run:
        scanner.config['dry_run'] = True
    if args.exclude_paths:
        scanner.config['excluded_directories'].extend(args.exclude_paths)
    
    try:
        if args.scan:
            scan_mode = "GoogleTakeout folders" if args.google_takeout else "all zip files on all drives"
            logger.info(f"Starting drive scan in {scan_mode} mode...")
            scanner.scan_all_drives()
        elif args.validate_db:
            issues = scanner.validate_database()
            if issues:
                print(f"Database validation found {len(issues)} issues:")
                for issue in issues:
                    print(f"  - {issue}")
            else:
                print("Database validation passed - no issues found.")
        elif args.find_duplicates:
            duplicates = scanner.find_duplicate_videos()
            if duplicates:
                print(f"Found {len(duplicates)} sets of duplicate videos:")
                for dup_group in duplicates:
                    print(f"\nDuplicate group (hash: {dup_group[0]['hash']}):")
                    for video in dup_group:
                        print(f"  - {video['zip_path']} -> {video['file_name']} ({video['file_size']} bytes)")
            else:
                print("No duplicate videos found.")
        elif args.search:
            results = scanner.search_videos(args.search, args.regex)
            scanner.print_search_results(results)
            
            # Export to CSV if requested
            if args.export_csv:
                scanner.export_search_results_to_csv(results, args.export_csv)
        elif args.stats:
            scanner.get_database_stats()
        elif args.drives:
            scanner.list_drives_in_database()
        else:
            parser.print_help()
    except KeyboardInterrupt:
        logger.info("Scan interrupted by user")
    finally:
        scanner.close()


if __name__ == "__main__":
    main()