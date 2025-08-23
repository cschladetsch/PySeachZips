#!/usr/bin/env python3
"""
Database operations for PySearchZips
Handles SQLite database initialization, insertions, and queries
"""

import sqlite3
import os
import uuid
from datetime import datetime
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Handles all database operations for ZIP file scanning"""
    
    def __init__(self, database_path: str):
        self.database_path = database_path
        self.connection = None
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        self.connection = sqlite3.connect(self.database_path)
        cursor = self.connection.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS zip_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_letter TEXT NOT NULL,
                zip_file_name TEXT NOT NULL,
                zip_file_path TEXT NOT NULL UNIQUE,
                uuid TEXT NOT NULL UNIQUE,
                file_size INTEGER,
                file_hash TEXT,
                last_modified TIMESTAMP,
                scan_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS file_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zip_uuid TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_path_in_zip TEXT NOT NULL,
                file_hash TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (zip_uuid) REFERENCES zip_files (uuid)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_progress (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                drive_letter TEXT NOT NULL,
                scan_start_time TIMESTAMP NOT NULL,
                scan_end_time TIMESTAMP,
                files_scanned INTEGER DEFAULT 0,
                status TEXT DEFAULT 'in_progress'
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                total_drives INTEGER,
                total_zip_files INTEGER,
                total_video_files INTEGER,
                total_size_bytes INTEGER,
                scan_duration_seconds REAL
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_zip_files_drive ON zip_files(drive_letter)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_contents_zip_uuid ON file_contents(zip_uuid)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_file_contents_name ON file_contents(file_name)')
        
        self.connection.commit()
        logger.info(f"Database initialized at: {self.database_path}")
    
    def insert_zip_data(self, zip_path: str, video_files: List[Tuple[str, int, str, Optional[str]]], 
                       heartbeat_callback=None, drive_letter: str = None) -> str:
        """Insert zip file and its video files into the database"""
        if not video_files:
            return None
        
        if heartbeat_callback:
            heartbeat_callback("Starting database insertion...")
        
        zip_uuid = str(uuid.uuid4())
        zip_file_name = os.path.basename(zip_path)
        
        # Get ZIP file metadata
        zip_file_size = 0
        zip_last_modified = None
        
        try:
            stat_info = os.stat(zip_path)
            zip_file_size = stat_info.st_size
            zip_last_modified = datetime.fromtimestamp(stat_info.st_mtime)
        except OSError as e:
            logger.warning(f"Could not get metadata for {zip_path}: {e}")
        
        cursor = self.connection.cursor()
        
        if heartbeat_callback:
            heartbeat_callback("Inserting ZIP metadata...")
        
        # Insert zip file record
        cursor.execute('''
            INSERT INTO zip_files (drive_letter, zip_file_name, zip_file_path, uuid, 
                                 file_size, file_hash, last_modified, scan_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (drive_letter or "", zip_file_name, zip_path, zip_uuid, 
              zip_file_size, None, zip_last_modified, datetime.now()))
        
        if heartbeat_callback:
            heartbeat_callback(f"Inserting {len(video_files)} file records...")
        
        # Batch insert video files
        video_data = []
        for file_name, file_size, file_path_in_zip, file_hash in video_files:
            video_data.append((zip_uuid, file_name, file_size, file_path_in_zip, file_hash, datetime.now()))
        
        cursor.executemany('''
            INSERT INTO file_contents (zip_uuid, file_name, file_size, file_path_in_zip, file_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', video_data)
        
        if heartbeat_callback:
            heartbeat_callback("Committing transaction...")
        
        self.connection.commit()
        logger.info(f"Inserted {len(video_files)} video files from {zip_file_name}")
        return zip_uuid
    
    def get_database_summary(self):
        """Get current database summary with thread-safe connection"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM zip_files")
            zip_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM file_contents")
            video_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(file_size) FROM file_contents")
            total_size = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(DISTINCT drive_letter) FROM zip_files")
            drive_count = cursor.fetchone()[0]
            
            return {
                'drives': drive_count,
                'zip_files': zip_count,
                'video_files': video_count,
                'total_size_gb': total_size / (1024**3)
            }
        finally:
            conn.close()
    
    def search_files(self, pattern: str, regex: bool = False, min_size: int = None, 
                    max_size: int = None, file_types: List[str] = None):
        """Search for files matching pattern"""
        cursor = self.connection.cursor()
        
        base_query = '''
            SELECT z.drive_letter, z.zip_file_name, z.zip_file_path, 
                   f.file_name, f.file_size, f.file_path_in_zip
            FROM zip_files z
            JOIN file_contents f ON z.uuid = f.zip_uuid
            WHERE 1=1
        '''
        
        params = []
        
        if regex:
            base_query += " AND f.file_name REGEXP ?"
            params.append(pattern)
        else:
            base_query += " AND f.file_name LIKE ?"
            params.append(f"%{pattern}%")
        
        if min_size is not None:
            base_query += " AND f.file_size >= ?"
            params.append(min_size)
        
        if max_size is not None:
            base_query += " AND f.file_size <= ?"
            params.append(max_size)
        
        if file_types:
            type_conditions = []
            for file_type in file_types:
                type_conditions.append("f.file_name LIKE ?")
                params.append(f"%.{file_type}")
            base_query += f" AND ({' OR '.join(type_conditions)})"
        
        base_query += " ORDER BY f.file_size DESC"
        
        cursor.execute(base_query, params)
        return cursor.fetchall()
    
    def list_all_videos(self, limit: int = None) -> List[Tuple[str, str, int, str]]:
        """List all video files in the database"""
        cursor = self.connection.cursor()
        
        query = '''
            SELECT f.file_name, z.zip_file_name, f.file_size, z.drive_letter
            FROM file_contents f
            JOIN zip_files z ON f.zip_uuid = z.uuid
            ORDER BY f.file_name
        '''
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query)
        return cursor.fetchall()
    
    def get_file_extraction_info(self, file_name: str) -> List[Tuple[str, str, str, int]]:
        """Get extraction information for a specific file
        
        Args:
            file_name: Name of the file to find
            
        Returns:
            List of tuples: (zip_file_path, file_path_in_zip, file_name, file_size)
        """
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT z.zip_file_path, f.file_path_in_zip, f.file_name, f.file_size
                FROM file_contents f
                JOIN zip_files z ON f.zip_uuid = z.uuid
                WHERE f.file_name LIKE ?
                ORDER BY f.file_size DESC
            ''', (f'%{file_name}%',))
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_file_by_uuid(self, zip_uuid: str, file_name: str = None) -> List[Tuple[str, str, str, int, str]]:
        """Get file extraction information by ZIP UUID
        
        Args:
            zip_uuid: UUID of the ZIP file
            file_name: Optional specific file name within the ZIP
            
        Returns:
            List of tuples: (zip_file_path, file_path_in_zip, file_name, file_size, zip_uuid)
        """
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        try:
            if file_name:
                # Get specific file from specific ZIP
                cursor.execute('''
                    SELECT z.zip_file_path, f.file_path_in_zip, f.file_name, f.file_size, z.uuid
                    FROM file_contents f
                    JOIN zip_files z ON f.zip_uuid = z.uuid
                    WHERE z.uuid = ? AND f.file_name LIKE ?
                    ORDER BY f.file_size DESC
                ''', (zip_uuid, f'%{file_name}%'))
            else:
                # Get all files from specific ZIP
                cursor.execute('''
                    SELECT z.zip_file_path, f.file_path_in_zip, f.file_name, f.file_size, z.uuid
                    FROM file_contents f
                    JOIN zip_files z ON f.zip_uuid = z.uuid
                    WHERE z.uuid = ?
                    ORDER BY f.file_name
                ''', (zip_uuid,))
            return cursor.fetchall()
        finally:
            conn.close()
    
    def get_zip_info_by_uuid(self, zip_uuid: str) -> Optional[Tuple[str, str, str, int]]:
        """Get ZIP file information by UUID
        
        Args:
            zip_uuid: UUID of the ZIP file
            
        Returns:
            Tuple: (zip_file_path, zip_file_name, drive_letter, file_count) or None if not found
        """
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                SELECT z.zip_file_path, z.zip_file_name, z.drive_letter,
                       (SELECT COUNT(*) FROM file_contents f WHERE f.zip_uuid = z.uuid) as file_count
                FROM zip_files z
                WHERE z.uuid = ?
            ''', (zip_uuid,))
            result = cursor.fetchone()
            return result
        finally:
            conn.close()
    
    def list_zip_archives(self, limit: int = None) -> List[Tuple[str, str, str, int, str]]:
        """List all ZIP archives with their UUIDs
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of tuples: (zip_file_name, drive_letter, uuid, file_count, zip_file_path)
        """
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        try:
            query = '''
                SELECT z.zip_file_name, z.drive_letter, z.uuid,
                       (SELECT COUNT(*) FROM file_contents f WHERE f.zip_uuid = z.uuid) as file_count,
                       z.zip_file_path
                FROM zip_files z
                ORDER BY z.zip_file_name
            '''
            
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return cursor.fetchall()
        finally:
            conn.close()
    
    def close(self):
        """Close database connection with thread safety"""
        if self.connection:
            try:
                self.connection.close()
            except sqlite3.ProgrammingError:
                # Connection was created in a different thread, ignore the error
                pass