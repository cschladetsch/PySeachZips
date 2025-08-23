# PySearchZips - Usage Examples

This document provides comprehensive examples for using PySearchZips, a high-performance tool for scanning and indexing files within ZIP archives.

## Quick Start Examples

```bash
# Basic scan of GoogleTakeout folders (default behavior)
./zip_scanner.py --scan

# Search for files containing "vacation" in the name
./zip_scanner.py --search "vacation"

# List all indexed files in database
./zip_scanner.py --list-videos

# View database statistics
./zip_scanner.py --stats
```

## File Type Scanning

### Video Files (Default)
```bash
# Scan GoogleTakeout folders for video files
./zip_scanner.py --scan

# Scan all ZIP files across all drives for videos
./zip_scanner.py --scan --no-google-takeout
```

### All File Types
```bash
# Scan ALL file types in GoogleTakeout ZIP archives
./zip_scanner.py --scan --all-files

# Scan ALL file types in ALL ZIP archives on all drives  
./zip_scanner.py --scan --no-google-takeout --all-files

# Search for specific file types
./zip_scanner.py --search ".txt" --all-files --file-types txt
./zip_scanner.py --search ".pdf" --all-files --file-types pdf --min-size 1048576
```

## Advanced Search Examples

### Pattern Matching
```bash
# Simple text search
./zip_scanner.py --search "vacation"

# Regex search for specific patterns
./zip_scanner.py --search "IMG_\d{4}\.mp4" --regex

# Case-insensitive search
./zip_scanner.py --search "VACATION" --regex -i

# Find files with dates in filename
./zip_scanner.py --search "202[0-4]-\d{2}-\d{2}" --regex
```

### Size-Based Filtering
```bash
# Find large files (>100MB)
./zip_scanner.py --search ".*" --min-size 104857600 --regex

# Find small config files (<10KB)
./zip_scanner.py --search "config" --max-size 10240

# Find files in size range (1MB - 50MB)
./zip_scanner.py --search ".*" --min-size 1048576 --max-size 52428800 --regex
```

### File Type Filtering
```bash
# Search for documents
./zip_scanner.py --search "document" --file-types pdf docx txt --all-files

# Find image files from specific year
./zip_scanner.py --search "2023" --file-types jpg jpeg png gif --all-files

# Search for source code files
./zip_scanner.py --search "\.py$|\.js$|\.cpp$" --regex --file-types py js cpp --all-files
```

## Database Operations

### Viewing Data
```bash
# Show database statistics
./zip_scanner.py --stats

# List all indexed files
./zip_scanner.py --list-videos

# List only first 50 files
./zip_scanner.py --list-videos --limit 50

# List first 100 files
./zip_scanner.py --list-videos --limit 100
```

### Custom Database Location
```bash
# Use custom database file
./zip_scanner.py --scan --database /path/to/my_archives.db

# Search in custom database
./zip_scanner.py --search "vacation" --database /path/to/my_archives.db
```

## Real-World Use Cases

### 1. Google Takeout Archive Management
```bash
# Initial scan of Google Takeout archives
./zip_scanner.py --scan

# Find all photos from 2023
./zip_scanner.py --search "2023" --all-files --file-types jpg jpeg png heic

# Find all videos larger than 100MB
./zip_scanner.py --search ".*" --regex --min-size 104857600

# List all indexed files to see what was found
./zip_scanner.py --list-videos --limit 100
```

### 2. Document Archive Search
```bash
# Scan all ZIP files for documents
./zip_scanner.py --scan --all-files --no-google-takeout

# Find all PDF documents
./zip_scanner.py --search "\.pdf$" --regex --file-types pdf --all-files

# Find documents containing "contract" in filename
./zip_scanner.py --search "contract" --file-types pdf doc docx txt --all-files

# Export results to CSV for analysis
./zip_scanner.py --search "contract" --file-types pdf doc docx --all-files > contracts.txt
```

### 3. Source Code Repository Analysis
```bash
# Scan for all file types
./zip_scanner.py --scan --all-files --no-google-takeout

# Find Python source files
./zip_scanner.py --search "\.py$" --regex --file-types py --all-files

# Find configuration files
./zip_scanner.py --search "config|settings" --regex --file-types json xml yml ini --all-files

# Find large source files (>1MB - might be generated files)
./zip_scanner.py --search "\.py$|\.js$|\.cpp$" --regex --min-size 1048576 --all-files
```

### 4. Media Collection Management
```bash
# Scan for all media files
./zip_scanner.py --scan --all-files

# Find high-resolution images (>5MB)
./zip_scanner.py --search ".*" --regex --min-size 5242880 --file-types jpg jpeg png tiff --all-files

# Find video files from specific cameras
./zip_scanner.py --search "DSC|IMG|VID" --regex --file-types mp4 avi mov

# Find audio files
./zip_scanner.py --search ".*" --regex --file-types mp3 wav flac aac --all-files
```

### 5. Archive Cleanup and Organization
```bash
# Find duplicate file names (not content-based)
./zip_scanner.py --search "copy|duplicate|\(\d+\)" --regex

# Find temporary files
./zip_scanner.py --search "temp|tmp|~" --regex --all-files

# Find very large files that might need attention
./zip_scanner.py --search ".*" --regex --min-size 1073741824 --all-files  # >1GB

# Find very old files (by name pattern)
./zip_scanner.py --search "199\d|200\d|201[0-5]" --regex --all-files
```

## Performance and Configuration

### Quiet Operation
```bash
# Run in quiet mode for scripts
./zip_scanner.py --scan --quiet

# Quiet search with output redirect
./zip_scanner.py --search "important" --quiet --all-files > important_files.txt
```

### Configuration Management
```bash
# Use specific configuration file
./zip_scanner.py --scan --config high_performance.json

# Configuration automatically loaded from config.json if present
./zip_scanner.py --scan
```

### Example Configuration Files

#### High Performance Config (`high_perf.json`):
```json
{
    "max_workers": 4,
    "batch_size": 2000,
    "google_takeout_mode": true,
    "scan_all_files": false,
    "quiet_mode": false,
    "excluded_directories": [
        "System Volume Information", "$RECYCLE.BIN", "Windows",
        "Program Files", "Program Files (x86)", "temp", "cache"
    ]
}
```

#### Document Scanning Config (`docs.json`):
```json
{
    "scan_all_files": true,
    "google_takeout_mode": false,
    "excluded_directories": [
        "System Volume Information", "$RECYCLE.BIN", "Windows",
        "temp", "cache", "node_modules", ".git", "__pycache__"
    ]
}
```

Use with:
```bash
./zip_scanner.py --config high_perf.json --scan
./zip_scanner.py --config docs.json --scan
```

## Combining Commands for Workflows

### Complete Archive Analysis Workflow
```bash
# 1. Initial scan
./zip_scanner.py --scan --all-files

# 2. Get overview
./zip_scanner.py --stats

# 3. Find large files
./zip_scanner.py --search ".*" --regex --min-size 104857600 --all-files

# 4. Find specific file types
./zip_scanner.py --search ".*" --regex --file-types pdf doc docx --all-files

# 5. List sample of all indexed files
./zip_scanner.py --list-videos --limit 20
```

### Photo Archive Organization
```bash
# 1. Scan for all file types
./zip_scanner.py --scan --all-files

# 2. Find all image files
./zip_scanner.py --search ".*" --regex --file-types jpg jpeg png gif tiff bmp --all-files

# 3. Find images by year
./zip_scanner.py --search "2023" --file-types jpg jpeg png --all-files
./zip_scanner.py --search "2022" --file-types jpg jpeg png --all-files

# 4. Find high-resolution images
./zip_scanner.py --search ".*" --regex --min-size 2097152 --file-types jpg jpeg png --all-files
```

## Error Handling and Troubleshooting

### Common Issues and Solutions
```bash
# If scan seems to hang, it's likely processing large files
# The tool shows real-time progress with heartbeat indicators

# Check what's in the database if scan completed
./zip_scanner.py --stats
./zip_scanner.py --list-videos --limit 10

# Use quiet mode to reduce output for large operations
./zip_scanner.py --scan --quiet

# For very large archives, ensure you have enough disk space for the database
# Database size is typically 1-2% of total indexed file size
```

## Integration Examples

### Script Integration
```bash
#!/bin/bash
# Automated archive scanning script

echo "Starting archive scan..."
./zip_scanner.py --scan --quiet

echo "Archive statistics:"
./zip_scanner.py --stats

echo "Finding large files..."
./zip_scanner.py --search ".*" --regex --min-size 104857600 --quiet > large_files.txt

echo "Scan complete. Results saved to large_files.txt"
```

### Cron Job Example
```bash
# Add to crontab for weekly archive scanning
# 0 2 * * 0 /path/to/zip_scanner.py --scan --quiet >> /var/log/archive_scan.log 2>&1
```

## File Extraction Examples

### Basic File Extraction
```bash
# Extract a specific file by name
./zip_scanner.py --extract "vacation"

# Extract with custom output directory
./zip_scanner.py --extract "Go Game" --output-dir "/home/user/extracted"

# Extract to Windows temp directory (cross-platform)
./zip_scanner.py --extract "Chess" --output-dir "c:\temp"
```

### UUID-Based Extraction
```bash
# First, list ZIP archives to find UUIDs
./zip_scanner.py --list-zips --limit 10

# Extract all files from a specific ZIP archive
./zip_scanner.py --extract-uuid "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# Extract only files matching a pattern from specific ZIP
./zip_scanner.py --extract-uuid "a1b2c3d4-e5f6-7890-abcd-ef1234567890" --file-filter "2023"

# Extract specific file type from ZIP
./zip_scanner.py --extract-uuid "a1b2c3d4-e5f6-7890-abcd-ef1234567890" --file-filter ".mp4"
```

### Bulk Extraction Operations
```bash
# WARNING: This extracts ALL files from ALL ZIP archives!
# Only use if you have sufficient disk space and need everything
./zip_scanner.py --extract-all --output-dir "/backup/full_extraction"

# Extract all, but let system prompt for confirmation
./zip_scanner.py --extract-all
```

### Extraction Workflow Examples

#### Workflow 1: Find and Extract Specific Content
```bash
# 1. Search for files of interest
./zip_scanner.py --search "vacation" --min-size 10485760  # >10MB files

# 2. Extract the found files
./zip_scanner.py --extract "vacation" --output-dir "/home/user/vacation_videos"

# 3. Verify extraction
ls -la /home/user/vacation_videos/
```

#### Workflow 2: Extract from Specific Archive
```bash
# 1. List archives to find the one you want
./zip_scanner.py --list-zips --limit 20

# 2. Get the UUID from the output, then extract specific content
./zip_scanner.py --extract-uuid "12345678-abcd-efgh-ijkl-123456789012" --file-filter "important"

# 3. Or extract everything from that archive
./zip_scanner.py --extract-uuid "12345678-abcd-efgh-ijkl-123456789012"
```

#### Workflow 3: Selective Bulk Extraction
```bash
# 1. Extract all video files larger than 100MB
./zip_scanner.py --search ".*\.(mp4|avi|mov|mkv)$" --regex --min-size 104857600

# 2. Use the search results to identify files, then extract by pattern
./zip_scanner.py --extract "large_video" --output-dir "/media/extracted_videos"

# 3. Extract by file types found in search
./zip_scanner.py --extract ".mp4" --output-dir "/media/mp4_files"
```

### Interactive Extraction Examples

When you run extraction commands, the tool provides interactive menus:

```bash
# Example: Multiple matches found
$ ./zip_scanner.py --extract "game"

MULTIPLE FILES FOUND (3 matches)
#   File Name                                          Size (MB)  ZIP File                      
--- -------------------------------------------------- ---------- ------------------------------
1   19x19 Go Game with AI Analysis.mp4                      40.2 takeout-20250206T053943Z-001. 
2   Chess Game Analysis.mp4                                 120.5 takeout-20250206T053943Z-174. 
3   Game of Thrones S01E01.mp4                            1250.3 takeout-20250206T053943Z-089. 

Select file number to extract (1-3, or 'all' for all): 1

EXTRACTING FILE
   File: 19x19 Go Game with AI Analysis.mp4
   Size: 40.2 MB
   From: takeout-20250206T053943Z-001.zip
   To: /tmp

[EXTRACT] Opening ZIP archive: takeout-20250206T053943Z-001.zip
[EXTRACT] Extracting 19x19 Go Game with AI Analysis.mp4 (40.2 MB)...
[EXTRACT] Extraction complete: 19x19 Go Game with AI Analysis.mp4 (40.2MB in 2.3s)

SUCCESS!
   Extracted to: /tmp/19x19 Go Game with AI Analysis.mp4
```

### Advanced Extraction Scenarios

#### Large File Extraction
```bash
# For very large files (>1GB), the tool shows progress
./zip_scanner.py --extract "large_movie" --output-dir "/external_drive/movies"

# Output shows:
# [EXTRACT] Extracting large_movie.mp4 (3840.8 MB)...
# [EXTRACT] Extracted 512.0MB @ 45.2MB/s...
# [EXTRACT] Extracted 1024.0MB @ 48.1MB/s...
# [EXTRACT] Extraction complete: large_movie.mp4 (3840.8MB in 85.2s)
```

#### Error Handling
```bash
# If extraction fails, you get clear error messages:
$ ./zip_scanner.py --extract "missing_file"
ERROR: File 'path/missing_file.mp4' not found in ZIP archive

$ ./zip_scanner.py --extract "protected" --output-dir "/read_only_dir"
PERMISSION ERROR: [Errno 13] Permission denied: '/read_only_dir/protected.mp4'
```

#### Recovery and Retry
```bash
# If extraction is interrupted, files are not left in partial state
# You can safely retry the same extraction command
./zip_scanner.py --extract "interrupted_file" --output-dir "/safe/location"
```

This comprehensive examples file covers most use cases you'll encounter when working with ZIP archives, file searching, and extraction!