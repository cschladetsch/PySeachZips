#!/usr/bin/env python3
"""
Google Takeout Video Scanner

Scans all available drives for GoogleTakeout folders, indexes video files from zip archives,
and provides a searchable SQLite database with case-insensitive regex support.
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
from pathlib import Path
from typing import List, Tuple, Generator, Optional
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

class GoogleTakeoutScanner:
    def __init__(self, database_path: str = 'google_takeout_videos.db'):
        self.database_path = database_path
        self.connection = None
        self.setup_database()
    
    def setup_database(self):
        """Initialize SQLite database with required tables"""
        self.connection = sqlite3.connect(self.database_path)
        cursor = self.connection.cursor()
        
        # Create zip_files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zip_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_letter TEXT NOT NULL,
                zip_file_name TEXT NOT NULL,
                zip_file_path TEXT NOT NULL,
                uuid TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create file_contents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zip_uuid TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_path_in_zip TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zip_uuid) REFERENCES zip_files (uuid)
            )
        ''')
        
        # Create indexes for better search performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_zip_uuid ON file_contents(zip_uuid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_name ON file_contents(file_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_drive_letter ON zip_files(drive_letter)')
        
        self.connection.commit()
        logger.info(f"Database initialized at: {self.database_path}")
    
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
        """Find all GoogleTakeout folders in root of drives only"""
        for drive in drives:
            logger.info(f"Scanning drive: {drive}")
            folders_scanned = 0
            takeout_folders = []
            
            try:
                # Only scan root folder of the drive
                if os.path.exists(drive):
                    try:
                        items = os.listdir(drive)
                        folders_scanned = len([item for item in items if os.path.isdir(os.path.join(drive, item))])
                        
                        if 'GoogleTakeout' in items:
                            takeout_path = os.path.join(drive, 'GoogleTakeout')
                            if os.path.isdir(takeout_path):
                                takeout_folders.append(takeout_path)
                                logger.info(f"Found GoogleTakeout folder: {takeout_path}")
                    except PermissionError:
                        logger.warning(f"Permission denied accessing {drive}")
                        continue
                
                # Yield each found takeout folder with total folders scanned for this drive
                for takeout_path in takeout_folders:
                    yield takeout_path, folders_scanned
                    
            except (PermissionError, OSError) as e:
                logger.warning(f"Cannot access {drive}: {e}")
                continue
    
    def find_zip_files(self, takeout_folder: str) -> Generator[str, None, None]:
        """Find all zip files in a GoogleTakeout folder"""
        try:
            for root, dirs, files in os.walk(takeout_folder):
                for file in files:
                    if file.lower().endswith('.zip'):
                        zip_path = os.path.join(root, file)
                        yield zip_path
        except (PermissionError, OSError) as e:
            logger.warning(f"Cannot access {takeout_folder}: {e}")
    
    def is_video_file(self, filename: str) -> bool:
        """Check if a file is a video file based on its extension"""
        return Path(filename).suffix.lower() in VIDEO_EXTENSIONS
    
    def scan_zip_for_videos(self, zip_path: str) -> List[Tuple[str, int, str]]:
        """Scan a zip file for video files and return (name, size, path_in_zip) tuples"""
        video_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                for file_info in zip_file.infolist():
                    if not file_info.is_dir() and self.is_video_file(file_info.filename):
                        video_files.append((
                            os.path.basename(file_info.filename),
                            file_info.file_size,
                            file_info.filename
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
    
    def insert_zip_data(self, zip_path: str, video_files: List[Tuple[str, int, str]]) -> str:
        """Insert zip file and its video files into the database"""
        if not video_files:
            return None
        
        zip_uuid = str(uuid.uuid4())
        drive_letter = self.get_drive_letter(zip_path)
        zip_file_name = os.path.basename(zip_path)
        
        cursor = self.connection.cursor()
        
        # Insert zip file record
        cursor.execute('''
            INSERT INTO zip_files (drive_letter, zip_file_name, zip_file_path, uuid)
            VALUES (?, ?, ?, ?)
        ''', (drive_letter, zip_file_name, zip_path, zip_uuid))
        
        # Insert video files
        for file_name, file_size, file_path_in_zip in video_files:
            cursor.execute('''
                INSERT INTO file_contents (zip_uuid, file_name, file_size, file_path_in_zip)
                VALUES (?, ?, ?, ?)
            ''', (zip_uuid, file_name, file_size, file_path_in_zip))
        
        self.connection.commit()
        logger.info(f"Inserted {len(video_files)} video files from {zip_file_name}")
        return zip_uuid
    
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
        spinner_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
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
        total_zips = 0
        total_videos = 0
        zip_count = 0
        folders_scanned = 0
        takeout_folders_found = 0
        
        print(f"\n{drive_color}📁 Scanning drive: {drive}{Style.RESET_ALL}")
        
        # Start spinner for folder scanning
        stop_event, spinner_thread = self.start_spinner(f"Scanning folders on {drive}...", drive_color)
        
        # First pass: find GoogleTakeout folders and count zip files
        all_zips = []
        takeout_paths = []
        
        for takeout_folder, folder_count in self.find_google_takeout_folders([drive]):
            folders_scanned = folder_count
            takeout_folders_found += 1
            takeout_paths.append(takeout_folder)
            
            for zip_path in self.find_zip_files(takeout_folder):
                all_zips.append(zip_path)
        
        # Stop spinner
        stop_event.set()
        spinner_thread.join(timeout=0.5)
        print(f"\r{' ' * 80}\r", end="")  # Clear spinner line
        
        # Display scan results
        if folders_scanned > 0:
            print(f"{drive_color}   📂 Scanned {folders_scanned:,} folders{Style.RESET_ALL}")
        
        if takeout_folders_found == 0:
            print(f"{Fore.YELLOW}   ⚠️  No GoogleTakeout folders found on {drive}")
            return 0, 0, folders_scanned
        
        # Highlight found GoogleTakeout folders
        for takeout_path in takeout_paths:
            short_path = takeout_path.replace(drive, "").lstrip(os.sep)
            print(f"{Fore.GREEN}   🎯 Found GoogleTakeout: {Style.BRIGHT}{short_path}{Style.RESET_ALL}")
        
        total_zip_files = len(all_zips)
        
        if total_zip_files == 0:
            print(f"{Fore.YELLOW}   ⚠️  No zip files found in GoogleTakeout folders")
            return 0, 0, folders_scanned
        
        print(f"{Fore.CYAN}   📦 Found {total_zip_files} zip files to process")
        
        # Second pass: process with progress bar
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
            print(f"\n{Fore.GREEN}   ✅ Processed {total_zips} zip files, found {total_videos:,} videos")
        else:
            print(f"\n{Fore.YELLOW}   ✅ No video files found in {total_zips} zip files")
        
        return total_zips, total_videos, folders_scanned
    
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
        print(f"{Style.BRIGHT}{Fore.CYAN}🗄️  DATABASE STATUS (BEFORE SCAN){Style.RESET_ALL}")
        print(f"   📁 Drives indexed: {Fore.YELLOW}{initial_stats['drives']}{Style.RESET_ALL}")
        print(f"   📦 Zip files: {Fore.YELLOW}{initial_stats['zip_files']}{Style.RESET_ALL}")
        print(f"   🎬 Video files: {Fore.YELLOW}{initial_stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   💾 Total size: {Fore.YELLOW}{initial_stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}{Fore.WHITE}🔍 Starting scan of {len(drives)} drives...{Style.RESET_ALL}")
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
        print(f"{Style.BRIGHT}{Fore.GREEN}🎉 SCAN COMPLETE!{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.CYAN}📊 SCAN RESULTS:{Style.RESET_ALL}")
        print(f"   🔍 Drives scanned: {Fore.YELLOW}{len(drives)}{Style.RESET_ALL}")
        print(f"   📂 Folders examined: {Fore.YELLOW}{total_folders_scanned:,}{Style.RESET_ALL}")
        print(f"   📦 Zip files processed: {Fore.YELLOW}{total_zips}{Style.RESET_ALL}")
        print(f"   🎬 Video files found: {Fore.YELLOW}{total_videos:,}{Style.RESET_ALL}")
        print(f"   ⏱️  Time elapsed: {Fore.YELLOW}{int(minutes):02d}:{int(seconds):02d}{Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}🗄️  DATABASE STATUS (AFTER SCAN){Style.RESET_ALL}")
        print(f"   📁 Total drives indexed: {Fore.YELLOW}{final_stats['drives']}{Style.RESET_ALL}")
        print(f"   📦 Total zip files: {Fore.YELLOW}{final_stats['zip_files']}{Style.RESET_ALL} {Fore.GREEN}(+{new_zip_files}){Style.RESET_ALL}")
        print(f"   🎬 Total video files: {Fore.YELLOW}{final_stats['video_files']:,}{Style.RESET_ALL} {Fore.GREEN}(+{new_video_files:,}){Style.RESET_ALL}")
        print(f"   💾 Total size: {Fore.YELLOW}{final_stats['total_size_gb']:.2f} GB{Style.RESET_ALL} {Fore.GREEN}(+{new_size_gb:.2f} GB){Style.RESET_ALL}")
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
            
            print(f"{Style.BRIGHT}{Fore.CYAN}📹 Result #{i}{Style.RESET_ALL}")
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
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()


def main():
    parser = argparse.ArgumentParser(description='Google Takeout Video Scanner')
    parser.add_argument('--database', '-db', default='google_takeout_videos.db',
                       help='SQLite database path (default: google_takeout_videos.db)')
    parser.add_argument('--scan', action='store_true',
                       help='Scan drives for GoogleTakeout folders and index video files')
    parser.add_argument('--search', '-s', type=str,
                       help='Search for video files by name')
    parser.add_argument('--regex', action='store_true',
                       help='Use regex for search pattern')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--drives', action='store_true',
                       help='List all drive names in database with statistics')
    
    args = parser.parse_args()
    
    scanner = GoogleTakeoutScanner(args.database)
    
    try:
        if args.scan:
            logger.info("Starting drive scan...")
            scanner.scan_all_drives()
        elif args.search:
            results = scanner.search_videos(args.search, args.regex)
            scanner.print_search_results(results)
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