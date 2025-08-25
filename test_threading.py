#!/usr/bin/env python3
"""
Simulated tests for PySearchZips threading functionality
Creates mock drives and ZIP files to test sequential vs threaded performance
"""

import os
import time
import random
import tempfile
import sqlite3
from typing import List, Tuple, Optional, Generator
from unittest.mock import patch, MagicMock
from colorama import init, Fore, Back, Style

# Import our modules
from zip_scanner import PySearchZips
from scanner import DriveScanner, ZipFileScanner
from database import DatabaseManager

# Initialize colorama
init(autoreset=True)

class MockDriveScanner:
    """Mock drive scanner that simulates multiple drives with controlled timing"""
    
    def __init__(self, config: dict, num_drives: int = 4, scan_delay: float = 1.0):
        self.config = config
        self.num_drives = num_drives
        self.scan_delay = scan_delay  # Base delay per drive
        
        # Create mock drive data
        self.mock_drives = [f"/mock/drive_{i}" for i in range(num_drives)]
        self.drive_info = {
            drive: (f"Mock Drive {i}", random.uniform(100.0, 2000.0)) 
            for i, drive in enumerate(self.mock_drives)
        }
        
        # Mock GoogleTakeout folders and ZIP files per drive
        self.takeout_data = {}
        self.zip_data = {}
        
        for drive in self.mock_drives:
            # Some drives have GoogleTakeout, some don't
            if random.random() < 0.7:  # 70% chance of having GoogleTakeout
                takeout_path = os.path.join(drive, "GoogleTakeout")
                zip_count = random.randint(5, 20)
                zip_files = [f"takeout-{j:03d}.zip" for j in range(zip_count)]
                self.takeout_data[drive] = (takeout_path, zip_files)
            
            # All drives have some random ZIP files
            all_zip_count = random.randint(10, 50)
            all_zips = [f"{drive}/path/to/archive-{j:03d}.zip" for j in range(all_zip_count)]
            self.zip_data[drive] = all_zips
    
    def get_available_drives(self, exclude_drives: List[str] = None) -> List[str]:
        """Return mock drives"""
        return self.mock_drives
    
    def get_drive_info(self, drive_path: str) -> tuple:
        """Return mock drive info with simulated delay"""
        time.sleep(0.1)  # Simulate drive info lookup delay
        return self.drive_info.get(drive_path, ("Unknown", 0.0))
    
    def get_drive_letter(self, path: str) -> str:
        """Extract mock drive letter"""
        for drive in self.mock_drives:
            if path.startswith(drive):
                return f"Mock{drive.split('_')[1]}"
        return "MockX"
    
    def find_google_takeout_folders(self, drives: List[str]) -> Generator[Tuple[str, int], None, None]:
        """Find mock GoogleTakeout folders with simulated scanning delay"""
        for drive in drives:
            # Simulate drive scanning time
            time.sleep(self.scan_delay * random.uniform(0.5, 1.5))
            
            if drive in self.takeout_data:
                takeout_path, zip_files = self.takeout_data[drive]
                yield takeout_path, len(zip_files)
    
    def find_all_zip_files_on_drive(self, drive: str) -> Generator[str, None, None]:
        """Find all mock ZIP files on a drive with simulated scanning delay"""
        # Simulate drive scanning time
        time.sleep(self.scan_delay * random.uniform(0.8, 1.2))
        
        if drive in self.zip_data:
            for zip_path in self.zip_data[drive]:
                yield zip_path

class MockZipFileScanner:
    """Mock ZIP file scanner that simulates ZIP file processing with controlled timing"""
    
    def __init__(self, config: dict, process_delay: float = 0.2):
        self.config = config
        self.process_delay = process_delay
        
        # Mock video file extensions
        self.video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv'}
    
    def scan_zip_for_videos(self, zip_path: str, all_files: bool = False, 
                          progress_callback=None) -> List[Tuple[str, int, str, Optional[str]]]:
        """Simulate ZIP file scanning with realistic delays and progress"""
        
        # Simulate ZIP processing time
        base_delay = self.process_delay
        zip_size_factor = random.uniform(0.5, 2.0)  # Simulate different ZIP sizes
        processing_time = base_delay * zip_size_factor
        
        # Simulate scanning with progress callbacks
        if progress_callback:
            progress_callback(f"Opening ZIP file: {os.path.basename(zip_path)}")
        
        # Simulate processing time in chunks to show progress
        chunks = max(1, int(processing_time / 0.1))
        for i in range(chunks):
            time.sleep(0.1)
            if progress_callback and i % 3 == 0:
                progress_callback(f"Scanning... {(i+1)/chunks*100:.0f}% complete")
        
        # Generate mock video files
        video_count = random.randint(0, 25)  # Some ZIPs have no videos
        video_files = []
        
        for i in range(video_count):
            file_name = f"video_{i:03d}{random.choice(list(self.video_extensions))}"
            file_size = random.randint(1024*1024, 500*1024*1024)  # 1MB to 500MB
            file_path_in_zip = f"photos/2023/{file_name}"
            video_files.append((file_name, file_size, file_path_in_zip, None))
        
        if progress_callback:
            if video_files:
                progress_callback(f"Found {len(video_files)} video files")
            else:
                progress_callback("No video files found")
        
        return video_files

class ThreadingTester:
    """Test harness for comparing sequential vs threaded performance"""
    
    def __init__(self, num_drives: int = 4, scan_delay: float = 1.0, process_delay: float = 0.2):
        self.num_drives = num_drives
        self.scan_delay = scan_delay
        self.process_delay = process_delay
        
        # Create test database
        self.test_db_path = tempfile.mktemp(suffix='.db')
        
    def cleanup(self):
        """Clean up test database"""
        if os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
    
    def run_performance_test(self) -> dict:
        """Run both sequential and threaded scans and compare performance"""
        print(f"{Style.BRIGHT}{Fore.CYAN}THREADING PERFORMANCE TEST{Style.RESET_ALL}")
        print(f"Testing with {self.num_drives} mock drives")
        print(f"Drive scan delay: {self.scan_delay}s, ZIP process delay: {self.process_delay}s")
        print(f"{Style.BRIGHT}{Fore.WHITE}{'='*60}{Style.RESET_ALL}")
        
        results = {}
        
        # Test sequential scanning
        print(f"\n{Style.BRIGHT}{Fore.YELLOW}=== SEQUENTIAL TEST ==={Style.RESET_ALL}")
        sequential_time = self._run_single_test(use_threading=False)
        results['sequential'] = sequential_time
        
        # Clean up and recreate database for second test
        if os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
        
        # Test threaded scanning
        print(f"\n{Style.BRIGHT}{Fore.YELLOW}=== THREADED TEST ==={Style.RESET_ALL}")
        threaded_time = self._run_single_test(use_threading=True)
        results['threaded'] = threaded_time
        
        # Calculate and display results
        print(f"\n{Style.BRIGHT}{Fore.CYAN}PERFORMANCE TEST RESULTS{Style.RESET_ALL}")
        print(f"   Sequential time: {Fore.YELLOW}{sequential_time:.2f}s{Style.RESET_ALL}")
        print(f"   Threaded time: {Fore.YELLOW}{threaded_time:.2f}s{Style.RESET_ALL}")
        
        if sequential_time > 0 and threaded_time > 0:
            speedup = sequential_time / threaded_time
            efficiency = (speedup / self.num_drives) * 100
            
            print(f"   Speedup: {Fore.GREEN}{speedup:.2f}x{Style.RESET_ALL}")
            print(f"   Parallel efficiency: {Fore.GREEN}{efficiency:.1f}%{Style.RESET_ALL}")
            
            if speedup > 1.5:
                print(f"   {Fore.GREEN}✓ Threading provides significant performance improvement!{Style.RESET_ALL}")
            elif speedup > 1.1:
                print(f"   {Fore.YELLOW}~ Threading provides moderate performance improvement{Style.RESET_ALL}")
            else:
                print(f"   {Fore.RED}⚠ Threading overhead may be limiting benefits{Style.RESET_ALL}")
        
        results['speedup'] = speedup if sequential_time > 0 and threaded_time > 0 else 0
        return results
    
    def _run_single_test(self, use_threading: bool) -> float:
        """Run a single test (sequential or threaded)"""
        config = {
            'max_workers': 4,
            'batch_size': 1000,
            'google_takeout_mode': True,
            'scan_all_files': False,
            'quiet_mode': False
        }
        
        # Create PySearchZips instance with test database
        scanner = PySearchZips(self.test_db_path)
        scanner.config = config
        scanner.root_folders_only = True
        scanner.all_files_mode = False
        scanner.quiet_mode = False
        
        # Replace scanners with mock versions
        mock_drive_scanner = MockDriveScanner(config, self.num_drives, self.scan_delay)
        mock_zip_scanner = MockZipFileScanner(config, self.process_delay)
        
        scanner.drive_scanner = mock_drive_scanner
        scanner.zip_scanner = mock_zip_scanner
        
        # Patch os.listdir to return mock zip files
        original_listdir = os.listdir
        def mock_listdir(path):
            for drive in mock_drive_scanner.takeout_data:
                takeout_path, zip_files = mock_drive_scanner.takeout_data[drive]
                if path == takeout_path:
                    return zip_files
            return []
        
        # Patch os.path.isfile to return True for mock files
        original_isfile = os.path.isfile
        def mock_isfile(path):
            for drive in mock_drive_scanner.takeout_data:
                takeout_path, zip_files = mock_drive_scanner.takeout_data[drive]
                for zip_file in zip_files:
                    if path == os.path.join(takeout_path, zip_file):
                        return True
            return False
        
        # Run the test
        start_time = time.time()
        
        try:
            scanner.scan_drives(use_threading=use_threading, compare_methods=False)
        except Exception as e:
            print(f"{Fore.RED}Error during test: {e}{Style.RESET_ALL}")
            return 0.0
        finally:
            scanner.close()
        
        end_time = time.time()
        return end_time - start_time
    
    def run_stress_test(self, num_drives: int = 8, num_iterations: int = 3):
        """Run multiple test iterations to check consistency"""
        print(f"\n{Style.BRIGHT}{Fore.MAGENTA}STRESS TEST ({num_iterations} iterations, {num_drives} drives){Style.RESET_ALL}")
        
        sequential_times = []
        threaded_times = []
        
        for i in range(num_iterations):
            print(f"\n{Style.BRIGHT}Iteration {i+1}/{num_iterations}{Style.RESET_ALL}")
            
            # Update test parameters
            self.num_drives = num_drives
            
            # Run single iteration
            results = self.run_performance_test()
            sequential_times.append(results['sequential'])
            threaded_times.append(results['threaded'])
            
            # Clean up between iterations
            if os.path.exists(self.test_db_path):
                os.unlink(self.test_db_path)
        
        # Calculate averages
        avg_sequential = sum(sequential_times) / len(sequential_times)
        avg_threaded = sum(threaded_times) / len(threaded_times)
        avg_speedup = avg_sequential / avg_threaded if avg_threaded > 0 else 0
        
        print(f"\n{Style.BRIGHT}{Fore.CYAN}STRESS TEST SUMMARY{Style.RESET_ALL}")
        print(f"   Average sequential time: {Fore.YELLOW}{avg_sequential:.2f}s{Style.RESET_ALL}")
        print(f"   Average threaded time: {Fore.YELLOW}{avg_threaded:.2f}s{Style.RESET_ALL}")
        print(f"   Average speedup: {Fore.GREEN}{avg_speedup:.2f}x{Style.RESET_ALL}")
        print(f"   Consistency: Sequential ±{max(sequential_times)-min(sequential_times):.2f}s, Threaded ±{max(threaded_times)-min(threaded_times):.2f}s")

def run_quick_test():
    """Run a quick test with default parameters"""
    tester = ThreadingTester(num_drives=3, scan_delay=0.5, process_delay=0.1)
    try:
        results = tester.run_performance_test()
        return results
    finally:
        tester.cleanup()

def run_comprehensive_test():
    """Run a comprehensive test with multiple configurations"""
    print(f"{Style.BRIGHT}{Fore.CYAN}COMPREHENSIVE THREADING TESTS{Style.RESET_ALL}")
    
    test_configs = [
        {"name": "Light Load", "num_drives": 2, "scan_delay": 0.3, "process_delay": 0.05},
        {"name": "Medium Load", "num_drives": 4, "scan_delay": 0.8, "process_delay": 0.15},
        {"name": "Heavy Load", "num_drives": 6, "scan_delay": 1.2, "process_delay": 0.25},
    ]
    
    all_results = []
    
    for config in test_configs:
        print(f"\n{Style.BRIGHT}{Fore.WHITE}{'='*60}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}Testing: {config['name']}{Style.RESET_ALL}")
        
        tester = ThreadingTester(
            num_drives=config['num_drives'],
            scan_delay=config['scan_delay'], 
            process_delay=config['process_delay']
        )
        
        try:
            results = tester.run_performance_test()
            results['config'] = config['name']
            all_results.append(results)
        finally:
            tester.cleanup()
    
    # Summary of all tests
    print(f"\n{Style.BRIGHT}{Fore.WHITE}{'='*60}{Style.RESET_ALL}")
    print(f"{Style.BRIGHT}{Fore.CYAN}COMPREHENSIVE TEST SUMMARY{Style.RESET_ALL}")
    print(f"{'Test':<12} {'Sequential':<12} {'Threaded':<12} {'Speedup':<12}")
    print(f"{'-'*12} {'-'*12} {'-'*12} {'-'*12}")
    
    for result in all_results:
        speedup = result.get('speedup', 0)
        print(f"{result['config']:<12} {result['sequential']:<11.2f}s {result['threaded']:<11.2f}s {speedup:<11.2f}x")
    
    return all_results

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--comprehensive":
        run_comprehensive_test()
    elif len(sys.argv) > 1 and sys.argv[1] == "--stress":
        tester = ThreadingTester()
        try:
            tester.run_stress_test(num_drives=6, num_iterations=3)
        finally:
            tester.cleanup()
    else:
        run_quick_test()