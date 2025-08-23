# PySearchZips

A high-performance Python tool for scanning and indexing files within ZIP archives across multiple drives and storage locations. Scan ANY file type with advanced pattern matching, regex support, real-time progress tracking, and a clean modular architecture.

## Demo

![Demo](resources/Demo.jpg)

## Features

### Performance & Scanning
- **High-speed processing**: Optimized for large ZIP archives (4GB+ files)
- **Real-time progress**: Live status updates with heartbeat indicators
- **Memory-efficient**: Smart processing without expensive hashing operations
- **Batch operations**: Optimized database insertions for maximum speed

### Flexible File Support
- **Any file type**: Videos (default) or ALL file types in ZIP archives (`--all-files`)
- **Multiple scanning modes**:
  - **GoogleTakeout mode** (default): Scans GoogleTakeout folders in root directories
  - **All-zip mode**: Comprehensive scanning of all ZIP files across drives
- **Smart filtering**: Filter by file extensions, size ranges, and pattern matching

### Advanced Search & Analysis
- **Powerful search**: Text patterns, regex support, and multi-criteria filtering
- **File listing**: List all indexed files with `--list-videos`
- **Size-based filtering**: Min/max file size constraints for search results
- **Drive information**: Shows volume labels and sizes during scanning

### Configuration & Customization
- **Modular architecture**: Clean separation of database, scanning, and progress modules
- **Auto-configuration**: Load settings from `config.json` 
- **Drive/folder exclusion**: Skip specific drives or directory patterns
- **Extensible**: Custom video extensions and excluded directory patterns

### User Experience
- **Real-time progress**: Colored progress bars with heartbeat indicators for long operations
- **Cross-platform**: Windows, Linux, macOS, and Windows Subsystem for Linux (WSL)
- **Drive information**: Shows volume labels and total drive sizes
- **Quiet mode**: Silent operation with minimal output

## Workflow

```mermaid
flowchart TD
    A[Start PySearchZips] --> B{Operation Mode}
    
    B -->|--scan| C[Initialize Components]
    B -->|--search| D[Query Database]
    B -->|--stats| E[Show Statistics]
    B -->|--list-videos| F[List Video Files]
    B -->|--list-zips| G[List ZIP Archives]
    B -->|--extract| H[Extract Files by Name]
    B -->|--extract-uuid| I[Extract by ZIP UUID]
    B -->|--extract-all| J[Extract All Files]
    
    C --> C1[DriveScanner]
    C --> C2[ZipFileScanner]
    C --> C3[DatabaseManager]
    C --> C4[ProgressDisplay]
    
    C1 --> G[Detect Available Drives]
    G --> H{Scanning Mode}
    H -->|GoogleTakeout Mode<br/>default| I[Find GoogleTakeout Folders]
    H -->|All-Zip Mode<br/>--no-google-takeout| J[Find All ZIP Files]
    
    I --> K[Process ZIP Files with Progress]
    J --> K
    
    K --> L[Real-time Progress Updates]
    L --> M[Scan ZIP Contents]
    M --> N[Show Heartbeat Status]
    N --> O[Insert to Database]
    O --> P[Display Results]
    
    D --> Q{Search Type}
    Q -->|Text Pattern| R[Simple Text Search]
    Q -->|Regex Pattern| S[Regex Pattern Search]
    R --> T[Display Search Results]
    S --> T
    
    E --> U[Show Database Statistics]
    F --> V[List All Videos with Details]
    G --> W[Show ZIP Archives with UUIDs]
    
    H --> X[Search Files by Name Pattern]
    X --> Y[Interactive File Selection]
    Y --> Z[Extract Selected Files]
    
    I --> AA[Get ZIP Info by UUID]
    AA --> BB[List Files in ZIP]
    BB --> CC[Interactive File Selection]
    CC --> DD[Extract from Specific ZIP]
    
    J --> EE[Confirm Full Extraction]
    EE --> FF[Extract All Files from All ZIPs]
    
    P --> GG[End]
    T --> GG
    U --> GG
    V --> GG
    W --> GG
    Z --> GG
    DD --> GG
    FF --> GG
    
    style A fill:#e1f5fe
    style C fill:#f3e5f5
    style O fill:#c8e6c9
    style T fill:#fff3e0
    style W fill:#ffebee
    style H fill:#fce4ec
    style L fill:#e8f5e8
```

## Architecture

PySearchZips uses a clean modular architecture for maintainability and extensibility:

```mermaid
graph TB
    subgraph "Main Application"
        A[zip_scanner.py<br/>384 lines<br/>CLI & Orchestration]
    end
    
    subgraph "Core Modules"
        B[database.py<br/>179 lines<br/>SQLite Operations]
        C[scanner.py<br/>241 lines<br/>Drive & ZIP Scanning]
        D[progress.py<br/>86 lines<br/>Progress & Status Display]
    end
    
    subgraph "External Dependencies"
        E[SQLite Database<br/>zip_files.db]
        F[Configuration<br/>config.json]
        G[File System<br/>Drives & ZIP Files]
    end
    
    A --> B
    A --> C
    A --> D
    B --> E
    A --> F
    C --> G
    D --> G
    
    style A fill:#e1f5fe
    style B fill:#c8e6c9
    style C fill:#fff3e0
    style D fill:#f3e5f5
    style E fill:#ffebee
    style F fill:#fce4ec
    style G fill:#e8f5e8
```

### Module Responsibilities
- **`zip_scanner.py`**: Main application, CLI parsing, and component orchestration
- **`database.py`**: All SQLite operations, queries, and data management
- **`scanner.py`**: Drive detection, ZIP file discovery, and content scanning
- **`progress.py`**: Real-time progress display, heartbeat, and status reporting

## Supported Video Formats

mp4, avi, mov, mkv, wmv, flv, webm, m4v, 3gp, 3g2, asf, divx, f4v, m2ts, mts, ogv, rm, rmvb, vob, xvid, mpg, mpeg, m1v, m2v

## Requirements

- Python 3.6+
- Optional: `colorama` package for colored terminal output

## Installation

Clone the repository and optionally install colorama for enhanced output:

```bash
git clone <repository-url>
cd PySearchVideos
pip install colorama  # Optional, for colored output
```

## Usage

### Quick Start

```bash
# First run: Auto-creates config.json from defaults
./zip_scanner.py --scan

# Search for files with "vacation" in the name
./zip_scanner.py --search "vacation"

# List all indexed files
./zip_scanner.py --list-videos

# Find all .txt files in ZIP archives
./zip_scanner.py --search ".txt" --file-types txt --all-files
```

### Scanning Modes

#### GoogleTakeout Mode (Default)
```bash
./zip_scanner.py --scan
```
- Scans GoogleTakeout folders in root directories of all drives
- Fast, focused scanning for Google Takeout archives
- Stores results in `zip_files.db`

#### All-ZIP Mode  
```bash  
./zip_scanner.py --scan --no-google-takeout
```
- Comprehensive scan of ALL ZIP files across ALL drives
- **Warning**: Significantly longer scan time
- Useful for complete archive inventories

#### All File Types
```bash
./zip_scanner.py --scan --all-files --no-google-takeout
```
- Scans ALL file types in ZIP archives (not just videos)
- Perfect for document archives, code repositories, etc.

### Advanced Searching

```bash
# Simple text search
./zip_scanner.py --search "vacation"

# Regex search  
./zip_scanner.py --search "IMG_\d{4}\.mp4" --regex

# Size-based filtering (files > 100MB)
./zip_scanner.py --search ".*" --regex --min-size 104857600

# Search specific file types
./zip_scanner.py --search "document" --file-types pdf docx txt --all-files

```

### Database Operations

```bash
# View database statistics
./zip_scanner.py --stats

# List all files in database
./zip_scanner.py --list-videos

# List first 50 files only
./zip_scanner.py --list-videos --limit 50
```

### File Extraction

```bash
# Extract a specific file by name
./zip_scanner.py --extract "Go Game"

# Extract with custom output directory  
./zip_scanner.py --extract "Chess" --output-dir "/home/user/videos"

# List ZIP archives to find UUIDs
./zip_scanner.py --list-zips --limit 10

# Extract all files from a specific ZIP by UUID
./zip_scanner.py --extract-uuid "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# Extract specific files from ZIP by UUID with filter
./zip_scanner.py --extract-uuid "a1b2c3d4-e5f6-7890-abcd-ef1234567890" --file-filter "2023"

# Extract ALL files from ALL ZIP archives (WARNING: Large operation!)
./zip_scanner.py --extract-all --output-dir "/backup/extracted"
```

### Custom database location

```bash
./zip_scanner.py --database /path/to/custom.db --scan
```

### Advanced features

#### Configuration Management
```bash
# First run automatically creates config.json from defaults
./zip_scanner.py --scan

# Edit your local configuration (gitignored)
nano config.json

# Use automatically (no --config flag needed)
./zip_scanner.py --scan

# Use specific config file
./zip_scanner.py --config high_performance.json --scan
```

#### Find duplicate videos
```bash
# Find videos with identical content (based on file hash)
./zip_scanner.py --find-duplicates
```

#### Export search results
```bash
# Search and export results to CSV
./zip_scanner.py --search "vacation" --export-csv results.csv
```

#### Database validation
```bash
# Check database integrity and find missing files
./zip_scanner.py --validate-db
```

#### Quiet and dry-run modes
```bash
# Preview what would be scanned without actually scanning
./zip_scanner.py --scan --dry-run

# Run in quiet mode with minimal output
./zip_scanner.py --scan --quiet
```

### Command line options

```bash
./zip_scanner.py --help
```

Available options:

**Operations:**
- `--scan`: Start scanning drives for ZIP files
- `--search "pattern"`: Search for files by name pattern
- `--stats`: Show database statistics  
- `--list-videos`: List all indexed files in database
- `--list-zips`: List all ZIP archives with their UUIDs

**Extraction Operations:**
- `--extract "filename"`: Extract file(s) matching name pattern
- `--extract-uuid UUID`: Extract files from specific ZIP by UUID
- `--extract-all`: Extract ALL files from ALL ZIP archives (use with caution!)
- `--output-dir PATH`: Output directory for extracted files (default: c:\temp or /tmp)
- `--file-filter "pattern"`: Filter files when using --extract-uuid

**Search Options:**
- `--regex`: Use regex patterns for search
- `--min-size SIZE`: Minimum file size in bytes
- `--max-size SIZE`: Maximum file size in bytes
- `--file-types TYPE [TYPE...]`: Filter by file extensions (e.g., mp4 avi)
- `--limit N`: Limit number of results shown

**Scanning Options:**
- `--google-takeout`: Search only GoogleTakeout folders (default)
- `--no-google-takeout`: Scan all ZIP files on drives
- `--all-files`: Scan all file types (default scans video files only)
- `--quiet, -q`: Quiet mode - minimal output

**Configuration:**
- `--database PATH`: Specify database location (default: zip_files.db)
- `--config PATH`: Load configuration from JSON file

## Configuration

PySearchZips uses a JSON configuration file to customize scanning behavior and performance settings.

### Automatic Configuration Setup
On first run, the tool automatically copies `config_default.json` to `config.json` for local customization:

```bash
# First run automatically creates config.json
./zip_scanner.py --scan
```

### Configuration Options

The `config.json` file contains the following configurable sections:

#### Performance Settings
- `max_workers`: Number of parallel scanning threads (default: 4)
- `batch_size`: Database batch insertion size for performance (default: 1000)
- `memory_limit`: Maximum memory usage in bytes
- `progress_update_interval`: Progress display update frequency in seconds

#### Scanning Behavior
- `video_extensions`: List of video file extensions to scan
- `excluded_directories`: Directory patterns to skip during scanning
- `excluded_drives`: Specific drive letters or mount points to exclude
- `follow_symlinks`: Whether to follow symbolic links (default: false)

#### Search Settings
- `case_sensitive`: Default case sensitivity for searches (default: false)
- `regex_enabled`: Enable regex support by default (default: false)

### Using Custom Configuration

```bash
# Use the automatically created config.json (recommended)
./zip_scanner.py --scan

# Use a specific config file
./zip_scanner.py --config high_performance.json --scan

# Edit your local configuration
nano config.json
```

### Example Configuration Structure
```json
{
  "performance": {
    "max_workers": 6,
    "batch_size": 2000
  },
  "scanning": {
    "excluded_directories": ["System Volume Information", "$RECYCLE.BIN"],
    "video_extensions": [".mp4", ".avi", ".mov"]
  }
}
```

## Database Schema

The tool creates several tables for enhanced functionality:

- `zip_files`: Stores ZIP archive metadata including file paths, hashes, and modification dates
- `file_contents`: Stores video file metadata with hashing for duplicate detection
- `scan_progress`: Tracks scan progress for resume capability (future feature)
- `scan_metrics`: Stores scanning statistics and performance metrics

## Platform Support

- **Windows**: Scans all available drive letters (C:, D:, etc.)
- **Linux/macOS**: Scans root filesystem and common mount points (/mnt, /media)
- **WSL**: Automatically detects and scans Windows drives mounted at /mnt/c, /mnt/d, etc.

## Output

The tool provides colored terminal output with:
- Real-time progress bars for each drive
- Statistics on folders scanned and files found
- Before/after database comparisons
- Detailed search results with file locations and sizes

## Files

### Core Application
- `zip_scanner.py`: Main scanner application (384 lines) - CLI and orchestration
- `database.py`: Database operations module (179 lines) - SQLite management  
- `scanner.py`: Drive and ZIP scanning module (241 lines) - File system operations
- `progress.py`: Progress display module (86 lines) - Status and heartbeat display

### Configuration & Data
- `config.json`: Local configuration (auto-created from defaults)
- `zip_files.db`: SQLite database (created automatically)

### Legacy/Backup
- `zip_scanner_old.py`: Original monolithic version (backup)
