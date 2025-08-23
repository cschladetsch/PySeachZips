# PySearchVideos

A Python tool for scanning and indexing video files within Google Takeout archives across multiple drives and storage locations.

## Features

- **Multi-drive scanning**: Automatically detects available drives on Windows, Linux, macOS, and WSL environments
- **Google Takeout focus**: Specifically searches for GoogleTakeout folders in drive root directories
- **Video file indexing**: Scans zip archives for video files with support for 20+ video formats
- **SQLite database**: Stores file metadata in a searchable database
- **Search functionality**: Find videos by filename with optional regex support
- **Progress tracking**: Real-time progress bars and colored output for better user experience
- **Cross-platform**: Works on Windows, Linux, macOS, and Windows Subsystem for Linux (WSL)

## Workflow

```mermaid
flowchart TD
    A[Start PySearchVideos] --> B{Operation Mode}
    
    B -->|--scan| C[Detect Available Drives]
    B -->|--search| D[Query Database]
    B -->|--stats| E[Show Statistics]
    B -->|--drives| F[List Indexed Drives]
    
    C --> G[Scan for GoogleTakeout Folders]
    G --> H[Find ZIP Archives]
    H --> I[Extract Video File Metadata]
    I --> J[Store in SQLite Database]
    J --> K[Display Progress & Results]
    
    D --> L{Search Type}
    L -->|Text| M[Simple Text Search]
    L -->|Regex| N[Regex Pattern Search]
    M --> O[Display Search Results]
    N --> O
    
    E --> P[Show Database Statistics]
    F --> Q[List Available Drives]
    
    K --> R[End]
    O --> R
    P --> R
    Q --> R
    
    style A fill:#e1f5fe
    style J fill:#c8e6c9
    style O fill:#fff3e0
    style R fill:#ffebee
```

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

### Scan drives for Google Takeout archives

```bash
./google_takeout_scanner.py --scan
```

This will:
- Scan all available drives for GoogleTakeout folders
- Index all video files found in zip archives
- Store results in `google_takeout_videos.db`

### Search for video files

```bash
# Simple text search
./google_takeout_scanner.py --search "vacation"

# Regex search
./google_takeout_scanner.py --search "IMG_\d{4}\.mp4" --regex
```

### View database statistics

```bash
./google_takeout_scanner.py --stats
```

### List indexed drives

```bash
./google_takeout_scanner.py --drives
```

### Custom database location

```bash
./google_takeout_scanner.py --database /path/to/custom.db --scan
```

## Database Schema

The tool creates two main tables:

- `zip_files`: Stores information about zip archives
- `file_contents`: Stores metadata for individual video files within archives

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

- `google_takeout_scanner.py`: Main scanner application
- `test_drives.py`: Test script for drive detection functionality
- `google_takeout_videos.db`: SQLite database (created automatically)