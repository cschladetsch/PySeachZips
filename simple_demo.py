#!/usr/bin/env python3
"""
Simple demo showing the new threaded database approach
"""

import os
import tempfile
import time
from colorama import init, Fore, Style
from database import DatabaseManager

# Initialize colorama
init(autoreset=True)

def demo_database_per_thread():
    """Demonstrate separate databases per thread and merging"""
    print(f"{Style.BRIGHT}{Fore.CYAN}Database Per Thread Demo{Style.RESET_ALL}")
    print("This demonstrates how each thread uses its own database file.\n")
    
    # Create main database
    main_db_path = tempfile.mktemp(suffix='.db')
    main_db = DatabaseManager(main_db_path)
    
    # Create thread databases (simulate 3 threads)
    thread_dbs = []
    thread_db_paths = []
    
    for i in range(3):
        thread_db_path = tempfile.mktemp(suffix=f'_thread_{i}.db')
        thread_db = DatabaseManager(thread_db_path)
        thread_dbs.append(thread_db)
        thread_db_paths.append(thread_db_path)
        
        print(f"{Fore.GREEN}Thread {i+1}{Style.RESET_ALL}: Created database {os.path.basename(thread_db_path)}")
    
    # Simulate each thread adding data
    print(f"\n{Style.BRIGHT}Simulating thread work...{Style.RESET_ALL}")
    
    for i, thread_db in enumerate(thread_dbs):
        # Add mock data to each thread database
        mock_zip_path = f"/mock/drive_{i}/test.zip"
        mock_files = [
            (f"video_{j}.mp4", 1024*1024*10, f"path/video_{j}.mp4", None)
            for j in range(2)  # 2 files per thread
        ]
        
        thread_db.insert_zip_data(
            mock_zip_path, 
            mock_files, 
            lambda msg: print(f"  {Fore.BLUE}Thread {i+1}{Style.RESET_ALL}: {msg}"),
            f"Drive{i}"
        )
        
        print(f"  {Fore.GREEN}Thread {i+1}{Style.RESET_ALL}: Added {len(mock_files)} files")
    
    # Close thread databases
    for thread_db in thread_dbs:
        thread_db.close()
    
    print(f"\n{Style.BRIGHT}Before merge - Main database status:{Style.RESET_ALL}")
    stats = main_db.get_database_summary()
    print(f"  Zip files: {stats['zip_files']}, Video files: {stats['video_files']}")
    
    # Merge all thread databases
    print(f"\n{Style.BRIGHT}Merging thread databases...{Style.RESET_ALL}")
    
    def merge_progress(msg):
        print(f"  {Fore.CYAN}[MERGE]{Style.RESET_ALL} {msg}")
    
    main_db.merge_databases(thread_db_paths, merge_progress)
    
    print(f"\n{Style.BRIGHT}After merge - Main database status:{Style.RESET_ALL}")
    stats = main_db.get_database_summary()
    print(f"  Zip files: {stats['zip_files']}, Video files: {stats['video_files']}")
    
    # Clean up
    main_db.close()
    
    print(f"\n{Style.BRIGHT}Cleaning up temporary files...{Style.RESET_ALL}")
    for thread_db_path in thread_db_paths:
        os.unlink(thread_db_path)
        print(f"  {Fore.RED}Removed{Style.RESET_ALL}: {os.path.basename(thread_db_path)}")
    
    os.unlink(main_db_path)
    print(f"  {Fore.RED}Removed{Style.RESET_ALL}: {os.path.basename(main_db_path)}")
    
    print(f"\n{Style.BRIGHT}{Fore.GREEN}✓ Demo completed successfully!{Style.RESET_ALL}")

def show_usage_examples():
    """Show usage examples"""
    print(f"\n{Style.BRIGHT}{Fore.CYAN}PySearchZips Threading Usage Examples:{Style.RESET_ALL}")
    print(f"\n{Style.BRIGHT}Basic Usage:{Style.RESET_ALL}")
    print(f"  ./zip_scanner.py --scan                    # Default: threaded scanning")
    print(f"  ./zip_scanner.py --scan --sequential       # Force sequential scanning")
    
    print(f"\n{Style.BRIGHT}Comparison and Testing:{Style.RESET_ALL}")
    print(f"  ./zip_scanner.py --scan --compare-threaded # Run both methods for comparison")
    print(f"  ./zip_scanner.py --test-threading quick    # Quick simulated test")
    print(f"  ./zip_scanner.py --test-threading comprehensive # Multiple test scenarios")
    
    print(f"\n{Style.BRIGHT}Key Benefits:{Style.RESET_ALL}")
    print(f"  • True parallelism: one thread per drive")
    print(f"  • No database locking bottlenecks")
    print(f"  • Automatic database merging and cleanup")
    print(f"  • Significant speedup on multi-drive systems")
    
    print(f"\n{Style.BRIGHT}Performance Expectations:{Style.RESET_ALL}")
    print(f"  • 2 drives: ~1.5-2x speedup")
    print(f"  • 4 drives: ~2-3x speedup") 
    print(f"  • 6+ drives: ~3-4x speedup")
    print(f"  • Actual results depend on drive speeds and ZIP file sizes")

if __name__ == "__main__":
    demo_database_per_thread()
    show_usage_examples()