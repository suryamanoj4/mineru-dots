"""
VParse Heavy - SQLite Task Database Manager
Heavy任务数据库管理器

Responsible for persistent storage of tasks, status management, and atomic operations.
"""
import sqlite3
import json
import uuid
from contextlib import contextmanager
from typing import Optional, List, Dict
from pathlib import Path


class TaskDB:
    """Task database management class."""
    
    def __init__(self, db_path='vparse_heavy.db'):
        self.db_path = db_path
        self._init_db()
    
    def _get_conn(self):
        """Get database connection (new connection per call to avoid pickle issues).
        
        Concurrency safety note:
            - Setting check_same_thread=False is safe because:
              1. Each call creates a new connection, not shared across threads.
              2. Connections are closed immediately after use (in get_cursor context manager).
              3. No connection pooling, avoiding cross-thread sharing.
            - timeout=30.0 prevents deadlocks; an exception is raised if a lock wait exceeds 30 seconds.
        """
        conn = sqlite3.connect(
            self.db_path, 
            check_same_thread=False,
            timeout=30.0
        )
        conn.row_factory = sqlite3.Row
        return conn
    
    @contextmanager
    def get_cursor(self):
        """Context manager for automatic commit and error handling."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()  # Close connection
    
    def _init_db(self):
        """Initialize database tables."""
        with self.get_cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT,
                    status TEXT DEFAULT 'pending',
                    priority INTEGER DEFAULT 0,
                    backend TEXT DEFAULT 'pipeline',
                    options TEXT,
                    result_path TEXT,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    worker_id TEXT,
                    retry_count INTEGER DEFAULT 0
                )
            ''')
            
            # Create indices to speed up queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_priority ON tasks(priority DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON tasks(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_worker_id ON tasks(worker_id)')
    
    def create_task(self, file_name: str, file_path: str, 
                   backend: str = 'pipeline', options: dict = None,
                   priority: int = 0) -> str:
        """
        Create a new task.
        
        Args:
            file_name: Filename.
            file_path: File path.
            backend: Processing backend (pipeline/vlm-transformers/vlm-vllm-engine).
            options: Processing options (dict).
            priority: Priority level (higher numbers are processed first).
            
        Returns:
            task_id: Task ID.
        """
        task_id = str(uuid.uuid4())
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO tasks (task_id, file_name, file_path, backend, options, priority)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (task_id, file_name, file_path, backend, json.dumps(options or {}), priority))
        return task_id
    
    def get_next_task(self, worker_id: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Get the next pending task (atomic operation to prevent concurrency conflicts).
        
        Args:
            worker_id: Worker ID.
            max_retries: Max retries if the task is claimed by another worker (default: 3).
            
        Returns:
            task: Task dictionary, or None if no tasks.
            
        Concurrency safety:
            1. Uses BEGIN IMMEDIATE to acquire write lock.
            2. Checks status='pending' during UPDATE to prevent duplicate claims.
            3. Verifies rowcount for update success.
            4. If claimed by another, retries immediately instead of returning None (avoids unnecessary waits).
        """
        for attempt in range(max_retries):
            with self.get_cursor() as cursor:
                # Use transaction to ensure atomicity
                cursor.execute('BEGIN IMMEDIATE')
                
                # Get tasks by priority and creation time
                cursor.execute('''
                    SELECT * FROM tasks 
                    WHERE status = 'pending' 
                    ORDER BY priority DESC, created_at ASC 
                    LIMIT 1
                ''')
                
                task = cursor.fetchone()
                if task:
                    # Mark as 'processing' immediately and ensure status is still 'pending'
                    cursor.execute('''
                        UPDATE tasks 
                        SET status = 'processing', 
                            started_at = CURRENT_TIMESTAMP, 
                            worker_id = ?
                        WHERE task_id = ? AND status = 'pending'
                    ''', (worker_id, task['task_id']))
                    
                    # Check if update succeeded (prevent claim by another worker)
                    if cursor.rowcount == 0:
                        # Task claimed by another process; retry immediately
                        # Because other pending tasks might exist in the queue
                        continue
                    
                    return dict(task)
                else:
                    # No pending tasks in queue; return None
                    return None
            
        # Retries exhausted without getting a task (high concurrency scenario)
        return None
    
    def _build_update_clauses(self, status: str, result_path: str = None, 
                             error_message: str = None, worker_id: str = None, 
                             task_id: str = None):
        """
        Helper method to build UPDATE and WHERE clauses.
        
        Args:
            status: New status.
            result_path: Result path (optional).
            error_message: Error message (optional).
            worker_id: Worker ID (optional).
            task_id: Task ID (optional).
            
        Returns:
            tuple: (update_clauses, update_params, where_clauses, where_params)
        """
        update_clauses = ['status = ?']
        update_params = [status]
        where_clauses = []
        where_params = []
        
        # Add task_id condition if provided
        if task_id:
            where_clauses.append('task_id = ?')
            where_params.append(task_id)
        
        # Handle 'completed' status
        if status == 'completed':
            update_clauses.append('completed_at = CURRENT_TIMESTAMP')
            if result_path:
                update_clauses.append('result_path = ?')
                update_params.append(result_path)
            # Only update tasks that are currently processing
            where_clauses.append("status = 'processing'")
            if worker_id:
                where_clauses.append('worker_id = ?')
                where_params.append(worker_id)
        
        # Handle 'failed' status
        elif status == 'failed':
            update_clauses.append('completed_at = CURRENT_TIMESTAMP')
            if error_message:
                update_clauses.append('error_message = ?')
                update_params.append(error_message)
            # Only update tasks that are currently processing
            where_clauses.append("status = 'processing'")
            if worker_id:
                where_clauses.append('worker_id = ?')
                where_params.append(worker_id)
        
        return update_clauses, update_params, where_clauses, where_params
    
    def update_task_status(self, task_id: str, status: str, 
                          result_path: str = None, error_message: str = None,
                          worker_id: str = None):
        """
        Update task status.
        
        Args:
            task_id: Task ID.
            status: New status (pending/processing/completed/failed/cancelled).
            result_path: Result path (optional).
            error_message: Error message (optional).
            worker_id: Worker ID (optional, for concurrency check).
            
        Returns:
            bool: Whether update succeeded.
            
        Concurrency safety:
            1. Checks status='processing' when updating to completed/failed.
            2. If worker_id provided, verifies task belongs to that worker.
            3. Returns False if task was modified by another process.
        """
        with self.get_cursor() as cursor:
            # Build clauses using helper method
            update_clauses, update_params, where_clauses, where_params = \
                self._build_update_clauses(status, result_path, error_message, worker_id, task_id)
            
            # Merge parameters: UPDATE part first, then WHERE part
            all_params = update_params + where_params
            
            sql = f'''
                UPDATE tasks 
                SET {', '.join(update_clauses)}
                WHERE {' AND '.join(where_clauses)}
            '''
            
            cursor.execute(sql, all_params)
            
            # Check if update succeeded
            success = cursor.rowcount > 0
            
            # Debug log (only on failure)
            if not success and status in ['completed', 'failed']:
                from loguru import logger
                logger.debug(
                    f"Status update failed: task_id={task_id}, status={status}, "
                    f"worker_id={worker_id}, SQL: {sql}, params: {all_params}"
                )
            
            return success
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """
        Query task details.
        
        Args:
            task_id: Task ID
            
        Returns:
            task: Task dictionary, or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
            task = cursor.fetchone()
            return dict(task) if task else None
    
    def get_queue_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.
        
        Returns:
            stats: Task counts per status
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT status, COUNT(*) as count 
                FROM tasks 
                GROUP BY status
            ''')
            stats = {row['status']: row['count'] for row in cursor.fetchall()}
            return stats
    
    def get_tasks_by_status(self, status: str, limit: int = 100) -> List[Dict]:
        """
        Get list of tasks by status.
        
        Args:
            status: Task status
            limit: Result limit
            
        Returns:
            tasks: List of tasks
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM tasks 
                WHERE status = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (status, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_task_files(self, days: int = 7):
        """
        Clean up result files of old tasks (keeping DB records).
        
        Args:
            days: Clean up task files older than N days
            
        Returns:
            int: Number of deleted directories
            
        Note:
            - Only result files are deleted, DB records are preserved
            - result_path field in DB will be cleared
            - Users can still query task status and history
        """
        from pathlib import Path
        import shutil
        
        with self.get_cursor() as cursor:
            # Query tasks to be cleaned up
            cursor.execute('''
                SELECT task_id, result_path FROM tasks 
                WHERE completed_at < datetime('now', '-' || ? || ' days')
                AND status IN ('completed', 'failed')
                AND result_path IS NOT NULL
            ''', (days,))
            
            old_tasks = cursor.fetchall()
            file_count = 0
            
            # Delete result files
            for task in old_tasks:
                if task['result_path']:
                    result_path = Path(task['result_path'])
                    if result_path.exists() and result_path.is_dir():
                        try:
                            shutil.rmtree(result_path)
                            file_count += 1
                            
                            # Clear result_path in DB, indicating files are cleaned up
                            cursor.execute('''
                                UPDATE tasks 
                                SET result_path = NULL
                                WHERE task_id = ?
                            ''', (task['task_id'],))
                            
                        except Exception as e:
                            from loguru import logger
                            logger.warning(f"Failed to delete result files for task {task['task_id']}: {e}")
            
            return file_count
    
    def cleanup_old_task_records(self, days: int = 30):
        """
        Clean up very old task records (optional feature).
        
        Args:
            days: Delete task records older than N days
            
        Returns:
            int: Number of deleted records
            
        Note:
            - This method permanently deletes DB records
            - Long retention periods (e.g., 30-90 days) are recommended
            - Typically not needed
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                DELETE FROM tasks 
                WHERE completed_at < datetime('now', '-' || ? || ' days')
                AND status IN ('completed', 'failed')
            ''', (days,))
            
            deleted_count = cursor.rowcount
            return deleted_count
    
    def reset_stale_tasks(self, timeout_minutes: int = 60):
        """
        Reset timed-out 'processing' tasks back to 'pending'
        
        Args:
            timeout_minutes: Timeout in minutes
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                UPDATE tasks 
                SET status = 'pending',
                    worker_id = NULL,
                    retry_count = retry_count + 1
                WHERE status = 'processing' 
                AND started_at < datetime('now', '-' || ? || ' minutes')
            ''', (timeout_minutes,))
            reset_count = cursor.rowcount
            return reset_count


if __name__ == '__main__':
    # 测试代码
    db = TaskDB('test_heavy.db')
    
    # Create test task
    task_id = db.create_task(
        file_name='test.pdf',
        file_path='/tmp/test.pdf',
        backend='pipeline',
        options={'lang': 'ch', 'formula_enable': True},
        priority=1
    )
    print(f"Created task: {task_id}")
    
    # Query task
    task = db.get_task(task_id)
    print(f"Task details: {task}")
    
    # Get stats
    stats = db.get_queue_stats()
    print(f"Queue stats: {stats}")
    
    # 清理测试数据库
    Path('test_heavy.db').unlink(missing_ok=True)
    print("Test completed!")
