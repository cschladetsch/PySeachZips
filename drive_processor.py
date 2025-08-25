#!/usr/bin/env python3
"""
Drive processing base classes and common functionality
Refactored from zip_scanner.py to eliminate code duplication
"""

import os
import time
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Callable
from colorama import Fore, Style

from database import DatabaseManager
from scanner import DriveScanner, ZipFileScanner
from progress import ProgressDisplay


class DriveProcessingResult:
    """Data class to hold drive processing results"""
    
    def __init__(self, drive: str, zip_count: int = 0, video_count: int = 0, 
                 processing_time: float = 0.0, error: Optional[str] = None):
        self.drive = drive
        self.zip_count = zip_count
        self.video_count = video_count
        self.processing_time = processing_time
        self.error = error
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    def __repr__(self) -> str:
        if self.error:
            return f"DriveProcessingResult(drive={self.drive}, error={self.error})"
        return f"DriveProcessingResult(drive={self.drive}, zips={self.zip_count}, videos={self.video_count}, time={self.processing_time:.2f}s)"


class BaseDriveProcessor(ABC):
    """Base class for drive processing operations"""
    
    def __init__(self, config: dict):
        self.config = config
        self.drive_scanner = DriveScanner(config)
        self.zip_scanner = ZipFileScanner(config)
        self.progress = ProgressDisplay()
        
        # Configuration flags
        self.root_folders_only = config.get('google_takeout_mode', True)
        self.all_files_mode = config.get('scan_all_files', False)
        self.quiet_mode = config.get('quiet_mode', False)
    
    def get_drive_info(self, drive: str) -> Tuple[str, float]:
        """Get drive label and size information"""
        return self.drive_scanner.get_drive_info(drive)
    
    def get_drive_letter(self, path: str) -> str:
        """Extract drive letter or mount point from a path"""
        return self.drive_scanner.get_drive_letter(path)
    
    def find_zip_files_for_drive(self, drive: str) -> List[str]:
        """Find ZIP files for a drive based on scanning mode"""
        if self.root_folders_only:
            # GoogleTakeout mode
            takeout_folders = list(self.drive_scanner.find_google_takeout_folders([drive]))
            if not takeout_folders:
                return []
            
            zip_files = []
            for takeout_path, _ in takeout_folders:
                folder_zips = [
                    os.path.join(takeout_path, f) 
                    for f in os.listdir(takeout_path)
                    if f.lower().endswith('.zip') and os.path.isfile(os.path.join(takeout_path, f))
                ]
                zip_files.extend(folder_zips)
            return zip_files
        else:
            # All ZIP files mode
            return list(self.drive_scanner.find_all_zip_files_on_drive(drive))
    
    def process_zip_file(self, zip_path: str, db: DatabaseManager, 
                        progress_callback: Optional[Callable[[str], None]] = None) -> Tuple[int, int]:
        """Process a single ZIP file and return (zip_count, video_count)"""
        zip_name = os.path.basename(zip_path)
        if len(zip_name) > 35:
            zip_name = zip_name[:32] + "..."
        
        # Get file size
        try:
            zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
            size_str = f"({zip_size_mb:.1f} MB)"
        except:
            size_str = "(size unknown)"
        
        if progress_callback:
            progress_callback(f"Processing: {zip_name} {size_str}")
        
        # Scan ZIP file
        video_files = self.zip_scanner.scan_zip_for_videos(
            zip_path, self.all_files_mode, progress_callback
        )
        
        if video_files:
            if progress_callback:
                progress_callback(f"Inserting {len(video_files)} files from {zip_name}")
            
            drive_letter = self.get_drive_letter(zip_path)
            db.insert_zip_data(zip_path, video_files, progress_callback, drive_letter)
            return 1, len(video_files)
        
        return 0, 0
    
    def show_drive_scan_start(self, drive: str, zip_count: int, thread_prefix: str = "") -> str:
        """Show drive scan start message and return color for this drive"""
        drive_colors = [Fore.GREEN, Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.YELLOW]
        drive_index = hash(drive) % len(drive_colors)
        drive_color = drive_colors[drive_index]
        
        label, size_gb = self.get_drive_info(drive)
        mode_str = "GoogleTakeout mode" if self.root_folders_only else "all zip files"
        
        print(f"\n{drive_color}{thread_prefix}Scanning drive ({mode_str}): {drive} [{label}, {size_gb:.1f} GB]{Style.RESET_ALL}")
        if zip_count > 0:
            print(f"{drive_color}{thread_prefix}Found {zip_count} zip files to process{Style.RESET_ALL}")
        else:
            print(f"{drive_color}{thread_prefix}No ZIP files found{Style.RESET_ALL}")
        
        return drive_color
    
    def show_drive_scan_complete(self, result: DriveProcessingResult, thread_prefix: str = ""):
        """Show drive scan completion message"""
        drive_colors = [Fore.GREEN, Fore.BLUE, Fore.MAGENTA, Fore.CYAN, Fore.YELLOW]
        drive_index = hash(result.drive) % len(drive_colors)
        drive_color = drive_colors[drive_index]
        
        if result.success:
            if result.video_count > 0:
                print(f"{drive_color}{thread_prefix}{result.drive} COMPLETE: {result.zip_count} zip files, {result.video_count:,} videos ({result.processing_time:.1f}s){Style.RESET_ALL}")
            else:
                print(f"{drive_color}{thread_prefix}{result.drive} COMPLETE: No video files found in {result.zip_count} zip files ({result.processing_time:.1f}s){Style.RESET_ALL}")
        else:
            print(f"{drive_color}{thread_prefix}{result.drive} FAILED: {result.error}{Style.RESET_ALL}")
    
    @abstractmethod
    def process_drive(self, drive: str, db: DatabaseManager) -> DriveProcessingResult:
        """Process a single drive - implemented by subclasses"""
        pass
    
    @abstractmethod
    def process_all_drives(self, drives: List[str], main_db: DatabaseManager) -> Tuple[int, int]:
        """Process all drives - implemented by subclasses"""
        pass


class SequentialDriveProcessor(BaseDriveProcessor):
    """Sequential drive processor - processes drives one at a time"""
    
    def process_drive(self, drive: str, db: DatabaseManager) -> DriveProcessingResult:
        """Process a single drive sequentially"""
        start_time = time.time()
        
        try:
            # Find ZIP files
            zip_files = self.find_zip_files_for_drive(drive)
            drive_color = self.show_drive_scan_start(drive, len(zip_files))
            
            if not zip_files:
                processing_time = time.time() - start_time
                return DriveProcessingResult(drive, 0, 0, processing_time)
            
            # Process ZIP files
            total_zips = 0
            total_videos = 0
            
            for i, zip_path in enumerate(zip_files):
                def progress_callback(msg):
                    print(f"{drive_color}[{drive:<8}] {msg}{Style.RESET_ALL}", flush=True)
                
                zip_count, video_count = self.process_zip_file(zip_path, db, progress_callback)
                total_zips += zip_count
                total_videos += video_count
                
                # Show progress
                progress = (i + 1) / len(zip_files)
                self.progress.print_progress_bar_enhanced(
                    progress, 35, drive, i + 1, len(zip_files), drive_color,
                    "COMPLETE" if i == len(zip_files) - 1 else os.path.basename(zip_path),
                    f"ETA: 00:00" if i == len(zip_files) - 1 else "Processing..."
                )
            
            processing_time = time.time() - start_time
            result = DriveProcessingResult(drive, total_zips, total_videos, processing_time)
            self.show_drive_scan_complete(result)
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            return DriveProcessingResult(drive, 0, 0, processing_time, str(e))
    
    def process_all_drives(self, drives: List[str], main_db: DatabaseManager) -> Tuple[int, int]:
        """Process all drives sequentially"""
        total_zips = 0
        total_videos = 0
        
        for drive in drives:
            result = self.process_drive(drive, main_db)
            if result.success:
                total_zips += result.zip_count
                total_videos += result.video_count
        
        return total_zips, total_videos


class ThreadedDriveProcessor(BaseDriveProcessor):
    """Threaded drive processor - processes drives in parallel"""
    
    def __init__(self, config: dict, console_lock=None):
        super().__init__(config)
        self.console_lock = console_lock
    
    def process_drive(self, drive: str, db: DatabaseManager) -> DriveProcessingResult:
        """Process a single drive in a thread-safe manner"""
        start_time = time.time()
        thread_prefix = "[THREAD] "
        
        try:
            # Find ZIP files
            zip_files = self.find_zip_files_for_drive(drive)
            
            with self.console_lock if self.console_lock else contextlib.nullcontext():
                drive_color = self.show_drive_scan_start(drive, len(zip_files), thread_prefix)
            
            if not zip_files:
                processing_time = time.time() - start_time
                return DriveProcessingResult(drive, 0, 0, processing_time)
            
            # Process ZIP files
            total_zips = 0
            total_videos = 0
            
            for i, zip_path in enumerate(zip_files):
                def progress_callback(msg):
                    with self.console_lock if self.console_lock else contextlib.nullcontext():
                        print(f"{drive_color}{thread_prefix}[{drive:<8}] {msg}{Style.RESET_ALL}", flush=True)
                
                zip_count, video_count = self.process_zip_file(zip_path, db, progress_callback)
                total_zips += zip_count
                total_videos += video_count
                
                # Show progress
                progress_pct = ((i + 1) / len(zip_files)) * 100
                with self.console_lock if self.console_lock else contextlib.nullcontext():
                    print(f"{drive_color}{thread_prefix}[{drive:<8}] Progress: {progress_pct:.1f}% ({i + 1}/{len(zip_files)}){Style.RESET_ALL}")
            
            processing_time = time.time() - start_time
            result = DriveProcessingResult(drive, total_zips, total_videos, processing_time)
            
            with self.console_lock if self.console_lock else contextlib.nullcontext():
                self.show_drive_scan_complete(result, thread_prefix)
            
            return result
            
        except Exception as e:
            processing_time = time.time() - start_time
            return DriveProcessingResult(drive, 0, 0, processing_time, str(e))
    
    def process_all_drives(self, drives: List[str], main_db: DatabaseManager) -> Tuple[int, int]:
        """Process all drives using threading with separate databases"""
        import threading
        import tempfile
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # Create temporary database files for each thread
        temp_db_files = []
        for i, drive in enumerate(drives):
            temp_db_path = f"{main_db.database_path}.thread_{i}_{drive.replace('/', '_').replace(':', '_')}.tmp"
            temp_db_files.append(temp_db_path)
        
        # Process drives in parallel
        drive_results = {}
        thread_db_files = []
        
        with ThreadPoolExecutor(max_workers=len(drives)) as executor:
            # Submit all drive scan jobs with their own database files
            future_to_drive = {}
            for i, drive in enumerate(drives):
                temp_db_path = temp_db_files[i]
                future = executor.submit(self._process_drive_with_db, drive, temp_db_path)
                future_to_drive[future] = (drive, temp_db_path)
            
            # Collect results as they complete
            for future in as_completed(future_to_drive):
                drive, temp_db_path = future_to_drive[future]
                try:
                    result = future.result()
                    drive_results[drive] = result
                    if os.path.exists(temp_db_path):
                        thread_db_files.append(temp_db_path)
                except Exception as exc:
                    print(f"{Fore.RED}Drive {drive} generated an exception: {exc}{Style.RESET_ALL}")
                    drive_results[drive] = DriveProcessingResult(drive, 0, 0, 0, str(exc))
        
        # Merge all thread databases into the main database
        if thread_db_files:
            print(f"\n{Style.BRIGHT}{Fore.WHITE}Merging thread databases...{Style.RESET_ALL}")
            
            def merge_progress_callback(msg):
                print(f"{Fore.CYAN}[MERGE] {msg}{Style.RESET_ALL}")
            
            main_db.merge_databases(thread_db_files, merge_progress_callback)
            
            # Clean up temporary database files
            for temp_db_path in thread_db_files:
                try:
                    os.unlink(temp_db_path)
                    print(f"{Fore.GREEN}[CLEANUP] Removed {os.path.basename(temp_db_path)}{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.YELLOW}Warning: Could not remove {temp_db_path}: {e}{Style.RESET_ALL}")
        
        # Calculate totals
        total_zips = sum(result.zip_count for result in drive_results.values() if result.success)
        total_videos = sum(result.video_count for result in drive_results.values() if result.success)
        
        return total_zips, total_videos
    
    def _process_drive_with_db(self, drive: str, thread_db_path: str) -> DriveProcessingResult:
        """Process a drive with its own database file"""
        thread_db = DatabaseManager(thread_db_path)
        try:
            result = self.process_drive(drive, thread_db)
            return result
        finally:
            thread_db.close()


# Import contextlib for nullcontext
import contextlib