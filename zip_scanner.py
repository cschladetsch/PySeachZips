#!/usr/bin/env python3
"""
PySearchZips - High-performance ZIP archive scanner and indexer
Refactored version with modular architecture
"""

import argparse
import json
import logging
import os
import sys
import time
import threading
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import our modules
from database import DatabaseManager
from scanner import DriveScanner, ZipFileScanner
from progress import ProgressDisplay, StatusReporter
from drive_processor import SequentialDriveProcessor, ThreadedDriveProcessor
from colorama import init, Fore, Back, Style

# Initialize colorama
init(autoreset=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class PySearchZips:
    """Main application class for ZIP archive scanning"""
    
    def __init__(self, database_path: str = 'zipped_files.db', config_path: str = None):
        self.database_path = database_path
        self.config = self.load_config(config_path)
        
        # Initialize components
        self.db = DatabaseManager(database_path)
        self.drive_scanner = DriveScanner(self.config)
        self.zip_scanner = ZipFileScanner(self.config)
        self.progress = ProgressDisplay()
        
        # Thread synchronization
        self.db_lock = threading.Lock()
        self.console_lock = threading.Lock()
        
        # Configuration flags
        self.root_folders_only = self.config.get('google_takeout_mode', True)
        self.all_files_mode = self.config.get('scan_all_files', False)
        self.quiet_mode = self.config.get('quiet_mode', False)
    
    @property
    def processor_config(self) -> Dict[str, Any]:
        """Build configuration dict for drive processors"""
        return {
            'max_workers': self.config.get('max_workers', 4),
            'batch_size': self.config.get('batch_size', 1000),
            'google_takeout_mode': self.root_folders_only,
            'scan_all_files': self.all_files_mode,
            'quiet_mode': self.quiet_mode,
            'excluded_directories': self.config.get('excluded_directories', []),
            'video_extensions': self.config.get('video_extensions', [])
        }
    
    def load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        default_config = {
            'max_workers': 4,
            'batch_size': 1000,
            'google_takeout_mode': True,
            'scan_all_files': False,
            'quiet_mode': False,
            'excluded_directories': [
                'System Volume Information', '$RECYCLE.BIN', 'Windows',
                'Program Files', 'Program Files (x86)', '.git', '__pycache__'
            ],
            'video_extensions': [
                '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'
            ]
        }
        
        # Try to load config file
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
                    logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        elif os.path.exists('config.json'):
            try:
                with open('config.json', 'r') as f:
                    user_config = json.load(f)
                    default_config.update(user_config)
                    logger.info("Loaded configuration from config.json")
            except Exception as e:
                logger.warning(f"Failed to load config.json: {e}")
        
        return default_config
    
    def scan_drives(self, use_threading: bool = True, compare_methods: bool = False):
        """Scan all available drives for ZIP files with threading support (refactored)"""
        if compare_methods:
            self._run_comparison_scan()
        elif use_threading:
            self._run_threaded_scan()
        else:
            self._run_sequential_scan()
    
    def _run_comparison_scan(self):
        """Run both sequential and threaded scans for performance comparison"""
        print(f"{Style.BRIGHT}{Fore.CYAN}PERFORMANCE COMPARISON MODE{Style.RESET_ALL}")
        print("Running both sequential and threaded scans for comparison...")
        print(f"{Fore.YELLOW}Note: Using temporary databases to avoid conflicts{Style.RESET_ALL}\n")
        
        import tempfile
        
        # Create temporary databases for comparison
        temp_db_sequential = tempfile.mktemp(suffix='_sequential.db')
        temp_db_threaded = tempfile.mktemp(suffix='_threaded.db')
        
        try:
            # Run sequential first
            print(f"{Style.BRIGHT}{Fore.YELLOW}=== SEQUENTIAL SCAN ==={Style.RESET_ALL}")
            seq_time = self._run_single_comparison_scan(temp_db_sequential, use_threading=False)
            
            print(f"\n{Style.BRIGHT}{Fore.YELLOW}=== THREADED SCAN ==={Style.RESET_ALL}")
            threaded_time = self._run_single_comparison_scan(temp_db_threaded, use_threading=True)
            
            # Show comparison
            self._show_comparison_results(seq_time, threaded_time)
            
        finally:
            # Clean up temporary databases
            for temp_db in [temp_db_sequential, temp_db_threaded]:
                if os.path.exists(temp_db):
                    os.unlink(temp_db)
                    print(f"   {Fore.GREEN}Cleaned up: {os.path.basename(temp_db)}{Style.RESET_ALL}")
    
    def _run_single_comparison_scan(self, temp_db_path: str, use_threading: bool) -> float:
        """Run a single scan for comparison purposes"""
        temp_scanner = PySearchZips(temp_db_path, None)
        temp_scanner.root_folders_only = self.root_folders_only
        temp_scanner.all_files_mode = self.all_files_mode
        temp_scanner.quiet_mode = self.quiet_mode
        
        try:
            start_time = time.time()
            if use_threading:
                temp_scanner._run_threaded_scan()
            else:
                temp_scanner._run_sequential_scan()
            return time.time() - start_time
        finally:
            temp_scanner.close()
    
    def _show_comparison_results(self, seq_time: float, threaded_time: float):
        """Show performance comparison results"""
        print(f"\n{Style.BRIGHT}{Fore.CYAN}PERFORMANCE COMPARISON RESULTS{Style.RESET_ALL}")
        print(f"   Sequential time: {Fore.YELLOW}{seq_time:.1f}s{Style.RESET_ALL}")
        print(f"   Threaded time: {Fore.YELLOW}{threaded_time:.1f}s{Style.RESET_ALL}")
        
        if seq_time > 0 and threaded_time > 0:
            speedup = seq_time / threaded_time
            print(f"   Speedup: {Fore.GREEN}{speedup:.2f}x{Style.RESET_ALL}")
            
            if speedup > 1.5:
                print(f"   {Fore.GREEN}✓ Threading provides significant performance improvement!{Style.RESET_ALL}")
            elif speedup > 1.1:
                print(f"   {Fore.YELLOW}~ Threading provides moderate performance improvement{Style.RESET_ALL}")
            else:
                print(f"   {Fore.RED}⚠ Threading overhead may be limiting benefits{Style.RESET_ALL}")
    
    def _run_sequential_scan(self):
        """Run sequential scan using the new processor architecture"""
        drives = self.drive_scanner.get_available_drives()
        logger.info(f"Found {len(drives)} available drives: {drives}")
        
        # Show initial database state
        self._show_scan_header("SEQUENTIAL", drives)
        
        # Create processor and run scan
        processor_config = self._get_processor_config()
        processor = SequentialDriveProcessor(processor_config)
        
        start_time = time.time()
        total_zips, total_videos = processor.process_all_drives(drives, self.db)
        elapsed_time = time.time() - start_time
        
        # Show final results
        self._show_scan_results("SEQUENTIAL", elapsed_time, total_zips, total_videos)
    
    def _run_threaded_scan(self):
        """Run threaded scan using the new processor architecture"""
        drives = self.drive_scanner.get_available_drives()
        logger.info(f"Found {len(drives)} available drives: {drives}")
        
        # Show initial database state
        self._show_scan_header("THREADED", drives)
        
        # Create processor and run scan
        processor_config = self._get_processor_config()
        processor = ThreadedDriveProcessor(processor_config, self.console_lock)
        
        start_time = time.time()
        total_zips, total_videos = processor.process_all_drives(drives, self.db)
        elapsed_time = time.time() - start_time
        
        # Show final results
        self._show_scan_results("THREADED", elapsed_time, total_zips, total_videos)
    
    def _get_processor_config(self) -> Dict[str, Any]:
        """Get configuration for drive processors"""
        return {
            'max_workers': self.config.get('max_workers', 4),
            'batch_size': self.config.get('batch_size', 1000),
            'google_takeout_mode': self.root_folders_only,
            'scan_all_files': self.all_files_mode,
            'quiet_mode': self.quiet_mode,
            'excluded_directories': self.config.get('excluded_directories', []),
            'video_extensions': self.config.get('video_extensions', [])
        }
    
    def _show_scan_header(self, scan_type: str, drives: List[str]):
        """Show scan header with initial database state"""
        initial_stats = self.db.get_database_summary()
        
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.CYAN}DATABASE STATUS (BEFORE {scan_type} SCAN){Style.RESET_ALL}")
        print(f"   Drives indexed: {Fore.YELLOW}{initial_stats['drives']}{Style.RESET_ALL}")
        print(f"   Zip files: {Fore.YELLOW}{initial_stats['zip_files']}{Style.RESET_ALL}")
        print(f"   Video files: {Fore.YELLOW}{initial_stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{initial_stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        
        scan_mode_desc = "GoogleTakeout folders only" if self.root_folders_only else "all zip files on drives"
        print(f"\n{Style.BRIGHT}{Fore.WHITE}Starting {scan_type} scan of {len(drives)} drives ({scan_mode_desc})...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Drive scan order: {', '.join(drives)}{Style.RESET_ALL}")
    
    def _show_scan_results(self, scan_type: str, elapsed_time: float, total_zips: int, total_videos: int):
        """Show scan results with final database state"""
        minutes, seconds = divmod(elapsed_time, 60)
        final_stats = self.db.get_database_summary()
        
        print(f"\n{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.GREEN}{scan_type} SCAN COMPLETE!{Style.RESET_ALL}")
        print(f"   Time elapsed: {Fore.YELLOW}{int(minutes):02d}:{int(seconds):02d}{Style.RESET_ALL}")
        print(f"   Zip files processed: {Fore.YELLOW}{total_zips}{Style.RESET_ALL}")
        print(f"   Video files found: {Fore.YELLOW}{total_videos:,}{Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}DATABASE STATUS (AFTER {scan_type} SCAN){Style.RESET_ALL}")
        print(f"   Total drives indexed: {Fore.YELLOW}{final_stats['drives']}{Style.RESET_ALL}")
        print(f"   Total zip files: {Fore.YELLOW}{final_stats['zip_files']}{Style.RESET_ALL}")
        print(f"   Total video files: {Fore.YELLOW}{final_stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{final_stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")

    def scan_drives_sequential(self):
        """Scan all available drives for ZIP files sequentially using new processor"""
        from drive_processor import SequentialDriveProcessor
        
        drives = self.drive_scanner.get_available_drives()
        logger.info(f"Found {len(drives)} available drives: {drives}")
        
        # Get initial database state
        initial_stats = self.db.get_database_summary()
        
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.CYAN}DATABASE STATUS (BEFORE SEQUENTIAL SCAN){Style.RESET_ALL}")
        print(f"   Drives indexed: {Fore.YELLOW}{initial_stats['drives']}{Style.RESET_ALL}")
        print(f"   Zip files: {Fore.YELLOW}{initial_stats['zip_files']}{Style.RESET_ALL}")
        print(f"   Video files: {Fore.YELLOW}{initial_stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{initial_stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        
        scan_mode_desc = "GoogleTakeout folders only" if self.root_folders_only else "all zip files on drives"
        print(f"\n{Style.BRIGHT}{Fore.WHITE}Starting SEQUENTIAL scan of {len(drives)} drives ({scan_mode_desc})...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Drive scan order: {', '.join(drives)}{Style.RESET_ALL}")
        
        start_time = time.time()
        
        # Create processor and process all drives
        processor = SequentialDriveProcessor(self.processor_config)
        total_zips, total_videos = processor.process_all_drives(drives, self.db)
        
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)
        
        # Get final database state
        final_stats = self.db.get_database_summary()
        
        # Final summary
        print(f"\n{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.GREEN}SEQUENTIAL SCAN COMPLETE!{Style.RESET_ALL}")
        print(f"   Time elapsed: {Fore.YELLOW}{int(minutes):02d}:{int(seconds):02d}{Style.RESET_ALL}")
        print(f"   Zip files processed: {Fore.YELLOW}{total_zips}{Style.RESET_ALL}")
        print(f"   Video files found: {Fore.YELLOW}{total_videos:,}{Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}DATABASE STATUS (AFTER SEQUENTIAL SCAN){Style.RESET_ALL}")
        print(f"   Total drives indexed: {Fore.YELLOW}{final_stats['drives']}{Style.RESET_ALL}")
        print(f"   Total zip files: {Fore.YELLOW}{final_stats['zip_files']}{Style.RESET_ALL}")
        print(f"   Total video files: {Fore.YELLOW}{final_stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{final_stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
    
    def scan_drives_threaded(self):
        """Scan all available drives for ZIP files using threading (one thread per drive)"""
        from drive_processor import ThreadedDriveProcessor
        
        drives = self.drive_scanner.get_available_drives()
        logger.info(f"Found {len(drives)} available drives: {drives}")
        
        # Get initial database state
        initial_stats = self.db.get_database_summary()
        
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.CYAN}DATABASE STATUS (BEFORE THREADED SCAN){Style.RESET_ALL}")
        print(f"   Drives indexed: {Fore.YELLOW}{initial_stats['drives']}{Style.RESET_ALL}")
        print(f"   Zip files: {Fore.YELLOW}{initial_stats['zip_files']}{Style.RESET_ALL}")
        print(f"   Video files: {Fore.YELLOW}{initial_stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{initial_stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        
        scan_mode_desc = "GoogleTakeout folders only" if self.root_folders_only else "all zip files on drives"
        print(f"\n{Style.BRIGHT}{Fore.WHITE}Starting THREADED scan of {len(drives)} drives ({scan_mode_desc})...{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Drive scan order: {', '.join(drives)}{Style.RESET_ALL}")
        
        start_time = time.time()
        
        # Create threaded processor with console lock and process all drives
        processor = ThreadedDriveProcessor(self.processor_config, self.console_lock)
        total_zips, total_videos = processor.process_all_drives(drives, self.db)
        
        elapsed_time = time.time() - start_time
        minutes, seconds = divmod(elapsed_time, 60)
        
        # Get final database state
        final_stats = self.db.get_database_summary()
        
        # Final summary
        print(f"\n{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.GREEN}THREADED SCAN COMPLETE!{Style.RESET_ALL}")
        print(f"   Time elapsed: {Fore.YELLOW}{int(minutes):02d}:{int(seconds):02d}{Style.RESET_ALL}")
        print(f"   Zip files processed: {Fore.YELLOW}{total_zips}{Style.RESET_ALL}")
        print(f"   Video files found: {Fore.YELLOW}{total_videos:,}{Style.RESET_ALL}")
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}DATABASE STATUS (AFTER THREADED SCAN){Style.RESET_ALL}")
        print(f"   Total drives indexed: {Fore.YELLOW}{final_stats['drives']}{Style.RESET_ALL}")
        print(f"   Total zip files: {Fore.YELLOW}{final_stats['zip_files']}{Style.RESET_ALL}")
        print(f"   Total video files: {Fore.YELLOW}{final_stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{final_stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*70}{Style.RESET_ALL}")
    
    def search_files(self, pattern: str, regex: bool = False, min_size: int = None,
                    max_size: int = None, file_types: List[str] = None):
        """Search for files matching pattern"""
        results = self.db.search_files(pattern, regex, min_size, max_size, file_types)
        
        if not results:
            print(f"{Fore.YELLOW}No files found matching pattern: {pattern}")
            return
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}SEARCH RESULTS ({len(results)} files found){Style.RESET_ALL}")
        print(f"{'Drive':<8} {'ZIP File':<30} {'Video File':<40} {'Size (MB)':<10}")
        print(f"{'-'*8} {'-'*30} {'-'*40} {'-'*10}")
        
        for drive, zip_name, zip_path, file_name, file_size, file_path_in_zip in results:
            size_mb = file_size / (1024 * 1024) if file_size else 0
            print(f"{drive:<8} {zip_name[:29]:<30} {file_name[:39]:<40} {size_mb:>9.1f}")
    
    def list_videos(self, limit: int = None):
        """List all video files in the database"""
        videos = self.db.list_all_videos(limit)
        
        if not videos:
            print(f"{Fore.YELLOW}No video files found in database")
            return
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}VIDEO FILES IN DATABASE ({len(videos)} files){Style.RESET_ALL}")
        if limit:
            print(f"{Fore.YELLOW}(Showing first {limit} files){Style.RESET_ALL}")
        
        print(f"{'Video File':<50} {'ZIP File':<30} {'Size (MB)':<10} {'Drive':<8}")
        print(f"{'-'*50} {'-'*30} {'-'*10} {'-'*8}")
        
        for file_name, zip_name, file_size, drive_letter in videos:
            size_mb = file_size / (1024 * 1024) if file_size else 0
            print(f"{file_name[:49]:<50} {zip_name[:29]:<30} {size_mb:>9.1f} {drive_letter:<8}")
    
    def show_stats(self):
        """Show database statistics"""
        stats = self.db.get_database_summary()
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}DATABASE STATISTICS{Style.RESET_ALL}")
        print(f"   Drives indexed: {Fore.YELLOW}{stats['drives']}{Style.RESET_ALL}")
        print(f"   Zip files: {Fore.YELLOW}{stats['zip_files']}{Style.RESET_ALL}")
        print(f"   Video files: {Fore.YELLOW}{stats['video_files']:,}{Style.RESET_ALL}")
        print(f"   Total size: {Fore.YELLOW}{stats['total_size_gb']:.2f} GB{Style.RESET_ALL}")
    
    def extract_file(self, file_name: str, output_dir: str = "."):
        """Extract a file from ZIP archives based on database metadata"""
        # Search for files matching the name
        matches = self.db.get_file_extraction_info(file_name)
        
        if not matches:
            print(f"{Fore.YELLOW}No files found matching: {file_name}")
            return
        
        if len(matches) == 1:
            # Single match - extract directly
            zip_path, file_path_in_zip, actual_name, file_size = matches[0]
            self._extract_single_file(zip_path, file_path_in_zip, actual_name, file_size, output_dir)
        else:
            # Multiple matches - show options
            print(f"\n{Style.BRIGHT}{Fore.CYAN}MULTIPLE FILES FOUND ({len(matches)} matches){Style.RESET_ALL}")
            print(f"{'#':<3} {'File Name':<50} {'Size (MB)':<10} {'ZIP File':<30}")
            print(f"{'-'*3} {'-'*50} {'-'*10} {'-'*30}")
            
            for i, (zip_path, file_path_in_zip, actual_name, file_size) in enumerate(matches, 1):
                size_mb = file_size / (1024 * 1024) if file_size else 0
                zip_name = os.path.basename(zip_path)
                print(f"{i:<3} {actual_name[:49]:<50} {size_mb:>9.1f} {zip_name[:29]:<30}")
            
            # Ask user to select
            try:
                choice = input(f"\n{Fore.CYAN}Select file number to extract (1-{len(matches)}, or 'all' for all): {Style.RESET_ALL}")
                
                if choice.lower() == 'all':
                    # Extract all files
                    for i, (zip_path, file_path_in_zip, actual_name, file_size) in enumerate(matches, 1):
                        print(f"\n{Fore.CYAN}Extracting file {i}/{len(matches)}: {actual_name}{Style.RESET_ALL}")
                        self._extract_single_file(zip_path, file_path_in_zip, actual_name, file_size, output_dir)
                else:
                    # Extract single selected file
                    selection = int(choice)
                    if 1 <= selection <= len(matches):
                        zip_path, file_path_in_zip, actual_name, file_size = matches[selection - 1]
                        self._extract_single_file(zip_path, file_path_in_zip, actual_name, file_size, output_dir)
                    else:
                        print(f"{Fore.RED}Invalid selection. Please choose 1-{len(matches)}{Style.RESET_ALL}")
                        
            except (ValueError, KeyboardInterrupt):
                print(f"\n{Fore.YELLOW}Extraction cancelled{Style.RESET_ALL}")
    
    def _extract_single_file(self, zip_path: str, file_path_in_zip: str, file_name: str, 
                           file_size: int, output_dir: str):
        """Extract a single file with progress feedback"""
        size_mb = file_size / (1024 * 1024) if file_size else 0
        
        print(f"\n{Style.BRIGHT}{Fore.GREEN}EXTRACTING FILE{Style.RESET_ALL}")
        print(f"   File: {Fore.YELLOW}{file_name}{Style.RESET_ALL}")
        print(f"   Size: {Fore.YELLOW}{size_mb:.1f} MB{Style.RESET_ALL}")
        print(f"   From: {Fore.YELLOW}{os.path.basename(zip_path)}{Style.RESET_ALL}")
        print(f"   To: {Fore.YELLOW}{output_dir}{Style.RESET_ALL}")
        
        # Progress callback
        def extraction_progress(msg):
            print(f"{Fore.CYAN}[EXTRACT] {msg}{Style.RESET_ALL}")
        
        try:
            # Extract the file
            extracted_path = self.zip_scanner.extract_file_from_zip(
                zip_path, file_path_in_zip, output_dir, extraction_progress
            )
            
            print(f"\n{Style.BRIGHT}{Fore.GREEN}SUCCESS!{Style.RESET_ALL}")
            print(f"   Extracted to: {Fore.YELLOW}{extracted_path}{Style.RESET_ALL}")
            
        except FileNotFoundError as e:
            print(f"\n{Fore.RED}ERROR: {e}{Style.RESET_ALL}")
        except PermissionError as e:
            print(f"\n{Fore.RED}PERMISSION ERROR: {e}{Style.RESET_ALL}")
        except Exception as e:
            print(f"\n{Fore.RED}EXTRACTION FAILED: {e}{Style.RESET_ALL}")
    
    def extract_file_by_uuid(self, zip_uuid: str, file_name: str = None, output_dir: str = "."):
        """Extract files from a specific ZIP by UUID"""
        # Get ZIP info first
        zip_info = self.db.get_zip_info_by_uuid(zip_uuid)
        if not zip_info:
            print(f"{Fore.RED}No ZIP found with UUID: {zip_uuid}{Style.RESET_ALL}")
            return
        
        zip_file_path, zip_file_name, drive_letter, file_count = zip_info
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}ZIP ARCHIVE INFO{Style.RESET_ALL}")
        print(f"   ZIP File: {Fore.YELLOW}{zip_file_name}{Style.RESET_ALL}")
        print(f"   Drive: {Fore.YELLOW}{drive_letter}{Style.RESET_ALL}")
        print(f"   UUID: {Fore.YELLOW}{zip_uuid}{Style.RESET_ALL}")
        print(f"   Total Files: {Fore.YELLOW}{file_count:,}{Style.RESET_ALL}")
        
        # Get files to extract
        matches = self.db.get_file_by_uuid(zip_uuid, file_name)
        
        if not matches:
            if file_name:
                print(f"{Fore.YELLOW}No files found matching '{file_name}' in ZIP {zip_file_name}")
            else:
                print(f"{Fore.YELLOW}No files found in ZIP {zip_file_name}")
            return
        
        if len(matches) == 1:
            # Single file - extract directly
            zip_path, file_path_in_zip, actual_name, file_size, _ = matches[0]
            self._extract_single_file(zip_path, file_path_in_zip, actual_name, file_size, output_dir)
        else:
            # Multiple files - show options
            if file_name:
                print(f"\n{Style.BRIGHT}{Fore.CYAN}MATCHING FILES ({len(matches)} matches for '{file_name}'){Style.RESET_ALL}")
            else:
                print(f"\n{Style.BRIGHT}{Fore.CYAN}ALL FILES IN ZIP ({len(matches)} files){Style.RESET_ALL}")
            
            print(f"{'#':<3} {'File Name':<50} {'Size (MB)':<10} {'Path in ZIP':<30}")
            print(f"{'-'*3} {'-'*50} {'-'*10} {'-'*30}")
            
            for i, (zip_path, file_path_in_zip, actual_name, file_size, _) in enumerate(matches, 1):
                size_mb = file_size / (1024 * 1024) if file_size else 0
                path_short = file_path_in_zip[:29] if len(file_path_in_zip) > 29 else file_path_in_zip
                print(f"{i:<3} {actual_name[:49]:<50} {size_mb:>9.1f} {path_short:<30}")
            
            # Handle extraction selection
            try:
                if len(matches) <= 10:  # Auto-suggest 'all' for smaller lists
                    choice = input(f"\n{Fore.CYAN}Select file number to extract (1-{len(matches)}, or 'all' for all): {Style.RESET_ALL}")
                else:
                    choice = input(f"\n{Fore.CYAN}Select file number to extract (1-{len(matches)}): {Style.RESET_ALL}")
                
                if choice.lower() == 'all' and len(matches) <= 10:
                    # Extract all files (only for smaller lists)
                    for i, (zip_path, file_path_in_zip, actual_name, file_size, _) in enumerate(matches, 1):
                        print(f"\n{Fore.CYAN}Extracting file {i}/{len(matches)}: {actual_name}{Style.RESET_ALL}")
                        self._extract_single_file(zip_path, file_path_in_zip, actual_name, file_size, output_dir)
                else:
                    # Extract single selected file
                    selection = int(choice)
                    if 1 <= selection <= len(matches):
                        zip_path, file_path_in_zip, actual_name, file_size, _ = matches[selection - 1]
                        self._extract_single_file(zip_path, file_path_in_zip, actual_name, file_size, output_dir)
                    else:
                        print(f"{Fore.RED}Invalid selection. Please choose 1-{len(matches)}{Style.RESET_ALL}")
                        
            except (ValueError, KeyboardInterrupt):
                print(f"\n{Fore.YELLOW}Extraction cancelled{Style.RESET_ALL}")
    
    def list_zip_archives(self, limit: int = None):
        """List all ZIP archives with their UUIDs"""
        archives = self.db.list_zip_archives(limit)
        
        if not archives:
            print(f"{Fore.YELLOW}No ZIP archives found in database")
            return
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}ZIP ARCHIVES ({len(archives)} archives){Style.RESET_ALL}")
        if limit:
            print(f"{Fore.YELLOW}(Showing first {limit} archives){Style.RESET_ALL}")
        
        print(f"{'ZIP File':<40} {'Drive':<6} {'Files':<8} {'UUID':<36}")
        print(f"{'-'*40} {'-'*6} {'-'*8} {'-'*36}")
        
        for zip_name, drive, uuid, file_count, zip_path in archives:
            print(f"{zip_name[:39]:<40} {drive:<6} {file_count:>7,} {uuid:<36}")
    
    def extract_all_files(self, output_dir: str = "."):
        """Extract all files from all ZIP archives"""
        archives = self.db.list_zip_archives()
        
        if not archives:
            print(f"{Fore.YELLOW}No ZIP archives found in database")
            return
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}EXTRACTING ALL FILES{Style.RESET_ALL}")
        print(f"   Total archives: {Fore.YELLOW}{len(archives)}{Style.RESET_ALL}")
        print(f"   Output directory: {Fore.YELLOW}{output_dir}{Style.RESET_ALL}")
        
        # Confirm with user
        try:
            confirm = input(f"\n{Fore.YELLOW}This will extract ALL files from ALL ZIP archives. Continue? (y/N): {Style.RESET_ALL}")
            if confirm.lower() != 'y':
                print(f"{Fore.YELLOW}Extraction cancelled{Style.RESET_ALL}")
                return
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Extraction cancelled{Style.RESET_ALL}")
            return
        
        total_extracted = 0
        total_errors = 0
        
        for i, (zip_name, drive, uuid, file_count, zip_path) in enumerate(archives, 1):
            print(f"\n{Style.BRIGHT}{Fore.CYAN}Archive {i}/{len(archives)}: {zip_name}{Style.RESET_ALL}")
            print(f"   Drive: {drive}, Files: {file_count:,}")
            
            # Get all files from this ZIP
            matches = self.db.get_file_by_uuid(uuid)
            
            if not matches:
                print(f"   {Fore.YELLOW}No files found in this archive{Style.RESET_ALL}")
                continue
            
            # Extract each file
            archive_extracted = 0
            archive_errors = 0
            
            for j, (zip_file_path, file_path_in_zip, file_name, file_size, _) in enumerate(matches, 1):
                try:
                    print(f"   {Fore.CYAN}[{j}/{len(matches)}] Extracting: {file_name[:50]}{'...' if len(file_name) > 50 else ''}{Style.RESET_ALL}")
                    
                    # Extract without progress callback for bulk operations
                    extracted_path = self.zip_scanner.extract_file_from_zip(
                        zip_file_path, file_path_in_zip, output_dir, None
                    )
                    archive_extracted += 1
                    total_extracted += 1
                    
                except Exception as e:
                    print(f"   {Fore.RED}ERROR extracting {file_name}: {e}{Style.RESET_ALL}")
                    archive_errors += 1
                    total_errors += 1
            
            print(f"   {Fore.GREEN}Archive complete: {archive_extracted} extracted, {archive_errors} errors{Style.RESET_ALL}")
        
        # Final summary
        print(f"\n{Style.BRIGHT}{Fore.GREEN}EXTRACTION COMPLETE!{Style.RESET_ALL}")
        print(f"   Total files extracted: {Fore.YELLOW}{total_extracted:,}{Style.RESET_ALL}")
        if total_errors > 0:
            print(f"   Total errors: {Fore.RED}{total_errors}{Style.RESET_ALL}")
        print(f"   Output directory: {Fore.YELLOW}{output_dir}{Style.RESET_ALL}")
    
    def close(self):
        """Clean up resources"""
        self.db.close()

def resolve_output_path(path: str) -> str:
    """Resolve output path for cross-platform compatibility"""
    import platform
    import os
    
    # Handle Windows paths in WSL
    if path.startswith('c:\\') or path.startswith('C:\\'):
        # Check if we're in WSL
        try:
            with open('/proc/version', 'r') as f:
                if 'microsoft' in f.read().lower():
                    # Convert Windows path to WSL path
                    drive = path[0].lower()
                    rest = path[3:].replace('\\', '/')
                    return f'/mnt/{drive}/{rest}'
        except:
            pass
    
    # For other cases, normalize path separators
    return os.path.normpath(path)

def main():
    """Main entry point"""
    # Set platform-appropriate default extraction directory
    import platform
    if platform.system() == 'Windows':
        default_output_dir = 'c:\\temp'
    else:
        # Check if we're in WSL - if so, use Windows temp via WSL mount
        try:
            with open('/proc/version', 'r') as f:
                if 'microsoft' in f.read().lower():
                    default_output_dir = '/mnt/c/temp'
                else:
                    default_output_dir = '/tmp'
        except:
            default_output_dir = '/tmp'
    
    parser = argparse.ArgumentParser(description='PySearchZips - High-performance ZIP archive scanner')
    parser.add_argument('--database', '-db', default='zipped_files.db',
                       help='SQLite database path (default: zipped_files.db)')
    parser.add_argument('--config', '-c', type=str,
                       help='Configuration file path')
    
    # Operations
    parser.add_argument('--scan', action='store_true',
                       help='Scan drives for ZIP files')
    parser.add_argument('--search', type=str,
                       help='Search for files by name pattern')
    parser.add_argument('--regex', action='store_true',
                       help='Use regex patterns for search')
    parser.add_argument('--stats', action='store_true',
                       help='Show database statistics')
    parser.add_argument('--list-videos', action='store_true',
                       help='List all video files in database')
    parser.add_argument('--list-zips', action='store_true',
                       help='List all ZIP archives with UUIDs')
    parser.add_argument('--extract', type=str,
                       help='Extract file(s) matching name pattern from ZIP archives')
    parser.add_argument('--extract-uuid', type=str,
                       help='Extract files from ZIP archive by UUID')
    parser.add_argument('--extract-all', action='store_true',
                       help='Extract ALL files from ALL ZIP archives (use with caution!)')
    parser.add_argument('--file-filter', type=str,
                       help='Filter files when using --extract-uuid (optional)')
    parser.add_argument('--output-dir', type=str, default=default_output_dir,
                       help=f'Output directory for extracted files (default: {default_output_dir})')
    parser.add_argument('--limit', type=int,
                       help='Limit number of results shown')
    
    # Scanning options
    parser.add_argument('--google-takeout', action='store_true', default=True,
                       help='Search only GoogleTakeout folders (default)')
    parser.add_argument('--no-google-takeout', action='store_true',
                       help='Scan all zip files (overrides --google-takeout)')
    parser.add_argument('--all-files', action='store_true',
                       help='Scan all file types, not just videos')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Quiet mode - minimal output')
    parser.add_argument('--compare-threaded', action='store_true',
                       help='Run both sequential and threaded scans for performance comparison')
    parser.add_argument('--sequential', action='store_true',
                       help='Use sequential scanning instead of threaded (default is threaded)')
    parser.add_argument('--test-threading', choices=['quick', 'comprehensive', 'stress'],
                       help='Run simulated tests: quick (default), comprehensive (multiple configs), or stress (multiple iterations)')
    
    # Search filters
    parser.add_argument('--min-size', type=int,
                       help='Minimum file size in bytes')
    parser.add_argument('--max-size', type=int,
                       help='Maximum file size in bytes')
    parser.add_argument('--file-types', nargs='+',
                       help='Filter by file extensions (e.g., mp4 avi)')
    
    args = parser.parse_args()
    
    # Create scanner instance
    scanner = PySearchZips(args.database, args.config)
    
    # Update configuration based on arguments
    if args.no_google_takeout:
        scanner.root_folders_only = False
    if args.all_files:
        scanner.all_files_mode = True
    if args.quiet:
        scanner.quiet_mode = True
        logging.getLogger().setLevel(logging.WARNING)
    
    try:
        if args.scan:
            # Determine threading mode
            use_threading = not args.sequential  # Default is threaded unless --sequential is used
            compare_methods = args.compare_threaded
            scanner.scan_drives(use_threading=use_threading, compare_methods=compare_methods)
        elif args.search:
            scanner.search_files(args.search, args.regex, args.min_size, 
                               args.max_size, args.file_types)
        elif args.list_videos:
            scanner.list_videos(args.limit)
        elif args.list_zips:
            scanner.list_zip_archives(args.limit)
        elif args.extract:
            resolved_dir = resolve_output_path(args.output_dir)
            scanner.extract_file(args.extract, resolved_dir)
        elif args.extract_uuid:
            resolved_dir = resolve_output_path(args.output_dir)
            scanner.extract_file_by_uuid(args.extract_uuid, args.file_filter, resolved_dir)
        elif args.extract_all:
            resolved_dir = resolve_output_path(args.output_dir)
            scanner.extract_all_files(resolved_dir)
        elif args.test_threading:
            # Import and run threading tests
            try:
                from test_threading import ThreadingTester, run_quick_test, run_comprehensive_test
                
                if args.test_threading == 'quick':
                    print(f"{Style.BRIGHT}{Fore.CYAN}Running quick threading test...{Style.RESET_ALL}")
                    run_quick_test()
                elif args.test_threading == 'comprehensive':
                    print(f"{Style.BRIGHT}{Fore.CYAN}Running comprehensive threading tests...{Style.RESET_ALL}")
                    run_comprehensive_test()
                elif args.test_threading == 'stress':
                    print(f"{Style.BRIGHT}{Fore.CYAN}Running stress test...{Style.RESET_ALL}")
                    tester = ThreadingTester()
                    try:
                        tester.run_stress_test(num_drives=6, num_iterations=3)
                    finally:
                        tester.cleanup()
                        
            except ImportError as e:
                print(f"{Fore.RED}Error: Could not import test_threading module: {e}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}Error running tests: {e}{Style.RESET_ALL}")
        elif args.stats:
            scanner.show_stats()
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Operation interrupted by user{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        logger.exception("Unexpected error occurred")
    finally:
        scanner.close()

if __name__ == "__main__":
    main()