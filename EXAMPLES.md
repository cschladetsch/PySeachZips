# PySearchVideos - Usage Examples

## Basic Video Scanning

```bash
# Scan GoogleTakeout folders for videos (default)
./py_zip_scanner.py --scan

# Scan all zip files on all drives for videos
./py_zip_scanner.py --scan --no-google-takeout

# Parallel scanning with 8 workers
./py_zip_scanner.py --scan --workers 8
```

## Scanning ALL File Types (not just videos)

```bash
# Scan ALL files in GoogleTakeout ZIP archives
./py_zip_scanner.py --scan --all-files

# Scan ALL files in ALL ZIP archives on all drives  
./py_zip_scanner.py --scan --no-google-takeout --all-files

# Search for all .txt files in ZIP archives on all drives
./py_zip_scanner.py --search ".txt" --all-files --file-types txt

# Search for all .pdf files larger than 1MB
./py_zip_scanner.py --search ".pdf" --all-files --file-types pdf --min-size 1048576
```

## Advanced Searching

```bash
# Search for vacation videos
./py_zip_scanner.py --search "vacation"

# Search with regex pattern
./py_zip_scanner.py --search "IMG_\d{4}\.mp4" --regex

# Search for large video files (>100MB)
./py_zip_scanner.py --search ".*" --min-size 104857600 --regex

# Search for specific file types
./py_zip_scanner.py --search "document" --file-types pdf docx txt

# Search and export results to CSV
./py_zip_scanner.py --search "vacation" --export-csv vacation_videos.csv
```

## Drive and Folder Exclusion

```bash
# Exclude specific drives from scanning
./py_zip_scanner.py --scan --exclude-drives "C:" "D:" "/mnt/backup"

# Exclude specific folder patterns
./py_zip_scanner.py --scan --exclude-paths "temp" "cache" "node_modules"

# Combined exclusions
./py_zip_scanner.py --scan --exclude-drives "/mnt/old" --exclude-paths ".git" "__pycache__"
```

## Incremental and Performance

```bash
# Incremental scan (only scan modified files)
./py_zip_scanner.py --incremental

# Quiet mode for scripts
./py_zip_scanner.py --scan --quiet

# Dry run to preview what would be scanned
./py_zip_scanner.py --scan --dry-run

# High-performance parallel scan with custom config
./py_zip_scanner.py --scan --config high_perf.json --workers 8 --quiet
```

## Database Management

```bash
# Validate database integrity
./py_zip_scanner.py --validate-db

# Find duplicate files
./py_zip_scanner.py --find-duplicates

# View database statistics
./py_zip_scanner.py --stats

# List indexed drives
./py_zip_scanner.py --drives

# Use custom database
./py_zip_scanner.py --scan --database my_archives.db
```

## Real-World Examples

### Find All Text Documents
```bash
# Find all text-related files in ZIP archives
./py_zip_scanner.py --scan --all-files --no-google-takeout
./py_zip_scanner.py --search "" --file-types txt doc docx pdf --export-csv text_documents.csv
```

### Archive Photo Collection
```bash
# Scan for image files in photo archives
./py_zip_scanner.py --scan --all-files --file-types jpg jpeg png gif bmp tiff
./py_zip_scanner.py --search "2023" --file-types jpg jpeg png
```

### Code Repository Search
```bash
# Find source code files
./py_zip_scanner.py --scan --all-files --exclude-drives "/mnt/temp"
./py_zip_scanner.py --search "\.py$|\.js$|\.cpp$" --regex --export-csv source_code.csv
```

### Large File Analysis
```bash
# Find files larger than 500MB
./py_zip_scanner.py --search ".*" --regex --min-size 524288000 --all-files

# Find small config files
./py_zip_scanner.py --search "config" --max-size 10240 --file-types json xml yml
```

## Configuration Examples

### Setup Local Configuration
```bash
# Copy default config to local (gitignored) config
cp config_default.json config.json

# Edit config.json with your preferences
nano config.json

# Use automatically (no --config needed)
./py_zip_scanner.py --scan
```

### High Performance Config (`high_perf.json`):
```json
{
    "batch_size": 2000,
    "max_memory_mb": 200,
    "max_workers": 8,
    "enable_hashing": true,
    "scan_all_files": false,
    "excluded_drives": ["/mnt/backup", "E:"],
    "excluded_directories": [
        "System Volume Information", "$RECYCLE.BIN", "Windows", 
        "temp", "cache", "node_modules", ".git"
    ]
}
```

### All-Files Scanning Config (`all_files.json`):
```json
{
    "scan_all_files": true,
    "max_workers": 6,
    "enable_hashing": true,
    "excluded_directories": [
        "System Volume Information", "$RECYCLE.BIN", "Windows",
        "temp", "cache", "__pycache__", ".git", ".svn"
    ]
}
```

Use with:
```bash
./py_zip_scanner.py --config high_perf.json --scan
./py_zip_scanner.py --config all_files.json --scan --no-google-takeout
```