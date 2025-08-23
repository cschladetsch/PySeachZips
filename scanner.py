#!/usr/bin/env python3
"""
Drive and ZIP file scanning logic for PySearchZips
Handles file system operations and ZIP content scanning
"""

import os
import platform
import zipfile
import time
import shutil
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional, Generator
import logging
from progress import ProgressDisplay, StatusReporter, HeartbeatManager

logger = logging.getLogger(__name__)

class DriveScanner:
    """Handles drive detection and scanning operations"""
    
    def __init__(self, config: dict):
        self.config = config
        self.progress = ProgressDisplay()
        self.heartbeat = HeartbeatManager()
        
        # Video file extensions
        self.video_extensions = {
            '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v',
            '.3gp', '.3g2', '.asf', '.divx', '.f4v', '.m2ts', '.mts', '.ogv',
            '.rm', '.rmvb', '.vob', '.xvid', '.mpg', '.mpeg', '.m1v', '.m2v'
        }
    
    def get_available_drives(self, exclude_drives: List[str] = None) -> List[str]:
        """Get list of available drives on the system"""
        drives = []
        exclude_drives = exclude_drives or []
        
        if platform.system() == 'Windows':
            # Windows: Check drive letters A-Z
            import string
            for letter in string.ascii_uppercase:
                drive_path = f"{letter}:\\"
                if os.path.exists(drive_path) and drive_path.rstrip('\\') not in exclude_drives:
                    drives.append(drive_path.rstrip('\\'))
        else:
            # Unix-like systems: Check root and common mount points
            potential_drives = ['/']
            
            # Add common mount points
            mount_points = ['/mnt', '/media', '/Volumes']
            for mount_point in mount_points:
                if os.path.exists(mount_point):
                    try:
                        for item in os.listdir(mount_point):
                            item_path = os.path.join(mount_point, item)
                            if os.path.ismount(item_path):
                                potential_drives.append(item_path)
                    except PermissionError:
                        pass
            
            # Filter out excluded drives and verify they exist
            for drive in potential_drives:
                if drive not in exclude_drives and os.path.exists(drive):
                    drives.append(drive)
            
            # Log WSL Windows drives
            for drive in drives:
                if self.is_wsl() and drive.startswith('/mnt/') and len(drive.split('/')) == 3:
                    logger.info(f"Found WSL Windows drive: {drive}")
        
        return drives
    
    def is_wsl(self) -> bool:
        """Check if running under Windows Subsystem for Linux"""
        try:
            with open('/proc/version', 'r') as f:
                return 'microsoft' in f.read().lower()
        except:
            return False
    
    def get_drive_info(self, drive_path: str) -> tuple:
        """Get drive label and size information"""
        try:
            # Get drive size using shutil.disk_usage
            total, used, free = shutil.disk_usage(drive_path)
            total_gb = total / (1024**3)
            
            # Get volume label
            label = "Unknown"
            if platform.system() == 'Windows':
                try:
                    import win32api
                    volume_info = win32api.GetVolumeInformation(drive_path)
                    label = volume_info[0] if volume_info[0] else "No Label"
                except:
                    pass
            else:
                # For Unix-like systems
                if drive_path.startswith('/mnt/') and len(drive_path.split('/')) == 3:
                    # WSL Windows drive
                    drive_letter = drive_path.split('/')[-1].upper()
                    try:
                        result = subprocess.run(
                            ['powershell.exe', '-Command', f'(Get-Volume -DriveLetter {drive_letter}).FileSystemLabel'],
                            capture_output=True, text=True, timeout=3
                        )
                        if result.returncode == 0 and result.stdout.strip():
                            label = result.stdout.strip()
                        else:
                            label = f"Drive {drive_letter}"
                    except:
                        label = f"Drive {drive_letter}"
                else:
                    # Try to get mount info for Linux
                    try:
                        result = subprocess.run(['findmnt', '-n', '-o', 'LABEL', drive_path], 
                                              capture_output=True, text=True, timeout=2)
                        if result.returncode == 0 and result.stdout.strip():
                            label = result.stdout.strip()
                        else:
                            label = drive_path.split('/')[-1] or "Root"
                    except:
                        label = drive_path.split('/')[-1] or "Root"
            
            return label, total_gb
        except Exception:
            return "Unknown", 0.0
    
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
    
    def find_google_takeout_folders(self, drives: List[str]) -> Generator[Tuple[str, int], None, None]:
        """Find GoogleTakeout folders in root directories of drives"""
        for drive in drives:
            logger.info(f"Scanning drive: {drive}")
            folder_count = 0
            
            try:
                # Look for GoogleTakeout folders in root directory
                items = list(os.listdir(drive))
                folder_count = len([item for item in items if os.path.isdir(os.path.join(drive, item))])
                
                for item in items:
                    if item.lower() == 'googletakeout':
                        takeout_path = os.path.join(drive, item)
                        if os.path.isdir(takeout_path):
                            logger.info(f"Found GoogleTakeout folder: {takeout_path}")
                            yield takeout_path, folder_count
                            
            except (PermissionError, FileNotFoundError) as e:
                logger.warning(f"Cannot access drive {drive}: {e}")
                continue
    
    def find_all_zip_files_on_drive(self, drive: str) -> Generator[str, None, None]:
        """Find all ZIP files on a drive (recursive)"""
        excluded_dirs = set(self.config.get('excluded_directories', [
            'System Volume Information', '$RECYCLE.BIN', 'Windows', 'Program Files',
            'Program Files (x86)', '.git', '__pycache__', 'node_modules'
        ]))
        
        try:
            for root, dirs, files in os.walk(drive):
                # Skip excluded directories
                dirs[:] = [d for d in dirs if d not in excluded_dirs]
                
                for file in files:
                    if file.lower().endswith('.zip'):
                        yield os.path.join(root, file)
                        
        except (PermissionError, FileNotFoundError) as e:
            logger.warning(f"Cannot access some paths on drive {drive}: {e}")

class ZipFileScanner:
    """Handles ZIP file content scanning"""
    
    def __init__(self, config: dict):
        self.config = config
        self.heartbeat = HeartbeatManager()
        
        # Video file extensions
        self.video_extensions = {
            '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v',
            '.3gp', '.3g2', '.asf', '.divx', '.f4v', '.m2ts', '.mts', '.ogv',
            '.rm', '.rmvb', '.vob', '.xvid', '.mpg', '.mpeg', '.m1v', '.m2v'
        }
    
    def is_target_file(self, filename: str, all_files: bool = False) -> bool:
        """Check if file is a target file (video by default, or any file if all_files=True)"""
        if all_files:
            return True
        
        # Check if file has video extension
        file_ext = os.path.splitext(filename.lower())[1]
        return file_ext in self.video_extensions
    
    def scan_zip_for_videos(self, zip_path: str, all_files: bool = False, 
                          progress_callback=None) -> List[Tuple[str, int, str, Optional[str]]]:
        """Scan a zip file for target files and return (name, size, path_in_zip, None) tuples"""
        target_files = []
        files_scanned = 0
        start_time = time.time()
        operation_id = f"zip_scan_{zip_path}"
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                total_files = len(zip_file.infolist())
                
                # Show initial status for large zip files
                if progress_callback and total_files > 1000:
                    progress_callback(f"Scanning large zip ({total_files:,} files)...")
                
                for file_info in zip_file.infolist():
                    files_scanned += 1
                    
                    # Show heartbeat for long operations
                    if progress_callback and self.heartbeat.should_show_heartbeat(operation_id):
                        elapsed = time.time() - start_time
                        if total_files > 1000:
                            progress_callback(f"Scanned {files_scanned:,}/{total_files:,} files ({elapsed:.1f}s)...")
                        else:
                            progress_callback(f"Processing... {elapsed:.1f}s elapsed")
                    
                    if not file_info.is_dir() and self.is_target_file(file_info.filename, all_files):
                        target_files.append((
                            os.path.basename(file_info.filename),
                            file_info.file_size,
                            file_info.filename,
                            None  # No hashing for performance
                        ))
                
                # Final status
                if progress_callback:
                    elapsed = time.time() - start_time
                    if target_files:
                        progress_callback(f"Found {len(target_files)} target files in {elapsed:.1f}s")
                    else:
                        progress_callback(f"No target files found ({files_scanned:,} files scanned in {elapsed:.1f}s)")
                        
        except (zipfile.BadZipFile, PermissionError, OSError) as e:
            logger.warning(f"Cannot read zip file {zip_path}: {e}")
            return []
        finally:
            self.heartbeat.reset(operation_id)
        
        return target_files
    
    def extract_file_from_zip(self, zip_path: str, file_path_in_zip: str, 
                             output_dir: str = ".", progress_callback=None) -> str:
        """Extract a specific file from a ZIP archive
        
        Args:
            zip_path: Path to the ZIP file
            file_path_in_zip: Path of the file inside the ZIP
            output_dir: Directory to extract to (default: current directory)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Path to the extracted file
            
        Raises:
            FileNotFoundError: If ZIP file or file in ZIP doesn't exist
            PermissionError: If cannot write to output directory
        """
        operation_id = f"extract_{zip_path}_{file_path_in_zip}"
        
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Get the filename for the output
            filename = os.path.basename(file_path_in_zip)
            output_path = os.path.join(output_dir, filename)
            
            # Check if file already exists and create unique name if needed
            counter = 1
            original_output_path = output_path
            while os.path.exists(output_path):
                name, ext = os.path.splitext(original_output_path)
                output_path = f"{name}_{counter}{ext}"
                counter += 1
            
            if progress_callback:
                progress_callback(f"Opening ZIP archive: {os.path.basename(zip_path)}")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # Check if file exists in ZIP
                try:
                    file_info = zip_file.getinfo(file_path_in_zip)
                except KeyError:
                    raise FileNotFoundError(f"File '{file_path_in_zip}' not found in ZIP archive")
                
                if progress_callback:
                    file_size_mb = file_info.file_size / (1024 * 1024)
                    progress_callback(f"Extracting {filename} ({file_size_mb:.1f} MB)...")
                
                # Extract the file
                with zip_file.open(file_path_in_zip) as source, open(output_path, 'wb') as target:
                    # Copy in chunks to show progress for large files
                    chunk_size = 1024 * 1024  # 1MB chunks
                    bytes_copied = 0
                    start_time = time.time()
                    
                    while True:
                        # Show heartbeat for large files
                        if progress_callback and file_info.file_size > 50 * 1024 * 1024:  # >50MB
                            if self.heartbeat.should_show_heartbeat(operation_id):
                                progress_mb = bytes_copied / (1024 * 1024)
                                elapsed = time.time() - start_time
                                if elapsed > 0:
                                    speed_mbps = progress_mb / elapsed
                                    progress_callback(f"Extracted {progress_mb:.1f}MB @ {speed_mbps:.1f}MB/s...")
                        
                        chunk = source.read(chunk_size)
                        if not chunk:
                            break
                        target.write(chunk)
                        bytes_copied += len(chunk)
                
                if progress_callback:
                    elapsed = time.time() - start_time
                    final_size_mb = bytes_copied / (1024 * 1024)
                    progress_callback(f"Extraction complete: {filename} ({final_size_mb:.1f}MB in {elapsed:.1f}s)")
            
            return output_path
            
        except (zipfile.BadZipFile, PermissionError, OSError) as e:
            error_msg = f"Failed to extract {file_path_in_zip} from {zip_path}: {e}"
            logger.error(error_msg)
            if progress_callback:
                progress_callback(f"ERROR: {error_msg}")
            raise
        finally:
            self.heartbeat.reset(operation_id)