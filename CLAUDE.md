# CLAUDE.md - PySearchZips Development Instructions

## Project Overview
PySearchZips is a high-performance Python tool for scanning and indexing files within ZIP archives. It uses a modular architecture with real-time progress tracking and SQLite database storage.

## Architecture Guidelines

### Modular Design
- **Keep modules focused**: Each module has a single responsibility
  - `zip_scanner.py` - Main CLI and orchestration
  - `database.py` - SQLite operations only
  - `scanner.py` - Drive and ZIP file scanning
  - `progress.py` - Progress display and heartbeat
- **Maintain clean interfaces** between modules
- **Avoid circular imports** - modules should have clear dependency hierarchy

### Code Standards
- Use descriptive variable names and clear function signatures
- Add type hints where helpful for complex functions
- Keep functions focused and under 50 lines when possible
- Use docstrings for public methods and classes

## Performance Considerations

### Database Operations
- All database operations must be thread-safe
- Use batch insertions for large datasets
- Always close database connections properly
- Use heartbeat callbacks for long operations to show progress

### Memory Management
- Avoid loading entire ZIP contents into memory
- Process files in batches where possible
- Use generators for large file lists
- Clean up resources in finally blocks

### Progress Feedback
- Always show progress for operations > 5 seconds
- Use heartbeat indicators every 2-3 seconds
- Display file sizes and ETAs when processing large files
- Use colored output for better user experience

## Testing Guidelines

### Before Committing
- Run the scanner on a small test dataset
- Verify database growth and integrity
- Test both GoogleTakeout mode and all-zip mode
- Check progress indicators work properly
- Ensure all modules import correctly

### Test Commands
```bash
# Quick functionality test
./zip_scanner.py --stats
./zip_scanner.py --list-videos --limit 10

# Small scan test
./zip_scanner.py --scan --quiet

# Search functionality test  
./zip_scanner.py --search "test" --limit 5
```

## Common Pitfalls

### Threading Issues
- Never share SQLite connections between threads
- Always create new connections for threaded operations
- Use proper locking for console output
- Be careful with progress callbacks in threads

### File System Operations
- Always handle file not found errors gracefully
- Check file permissions before attempting operations
- Use proper path separators for cross-platform compatibility
- Handle network drives and mounted volumes correctly

## Development Workflow

### Making Changes
1. Test changes with small datasets first
2. Verify progress indicators still work
3. Check database operations complete successfully
4. Run basic functionality tests before committing

### Adding Features
- Keep the modular architecture intact
- Add comprehensive progress feedback for long operations
- Update help text and documentation
- Consider cross-platform compatibility

### Performance Improvements
- Profile before optimizing
- Focus on database operations and file I/O first
- Maintain user feedback during optimizations
- Test with large datasets to verify improvements

## Configuration Management

### Config Files
- `config.json` is auto-created from defaults on first run
- Users can customize their local config without affecting git
- Always provide sensible defaults in code
- Validate config values and provide helpful error messages

### Default Behavior
- GoogleTakeout mode should be the default (most common use case)
- Video files are the primary target (but support all file types)
- Always show progress for long operations
- Provide helpful status messages and summaries

## Documentation Standards

### Code Comments
- Focus on WHY, not WHAT
- Explain complex algorithms and business logic
- Document performance-critical sections
- Note any platform-specific behavior

### User Documentation  
- Keep examples practical and real-world
- Update help text when adding new features
- Maintain README.md with current feature set
- Include performance expectations and file size limits

## Error Handling

### User-Facing Errors
- Provide clear, actionable error messages
- Include suggestions for common problems
- Handle interruption (Ctrl+C) gracefully
- Log detailed errors for debugging while showing simple messages to users

### Database Errors
- Always check database integrity on startup
- Handle database corruption gracefully
- Provide recovery suggestions for database issues
- Never leave database in inconsistent state