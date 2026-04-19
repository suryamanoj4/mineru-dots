"""
VParse Heavy - LitServe Worker
Heavy LitServe Worker

Uses LitServe to implement automatic GPU resource load balancing.
Workers actively poll and process tasks in a loop.
"""
import os
import json
import sys
import time
import threading
import signal
import atexit
from pathlib import Path
import litserve as ls
from loguru import logger

# Add parent directory to path to import VParse
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from task_db import TaskDB
from vparse.cli.common import do_parse, read_fn
from vparse.utils.config_reader import get_device
from vparse.utils.model_utils import get_vram, clean_memory

# Attempt to import markitdown
try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    logger.warning("⚠️  markitdown not available, Office format parsing will be disabled")


class VParseWorkerAPI(ls.LitAPI):
    """
    LitServe API Worker
    
    Worker active loop pulling tasks, utilizing LitServe's auto GPU load balancing
    Supports two parsing methods:
    - PDF/Images -> VParse parsing (GPU accelerated)
    - All other formats -> MarkItDown parsing (Fast processing)
    
    New mode: Each worker continuously polls tasks after startup, picking up the next one immediately after completion.
    """
    
    # Define supported file formats
    # VParse exclusive formats: PDF and Images
    PDF_IMAGE_FORMATS = {'.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
    # All other formats use MarkItDown
    
    def __init__(self, output_dir='/tmp/vparse_heavy_output', worker_id_prefix='heavy', 
                 poll_interval=0.5, enable_worker_loop=True):
        super().__init__()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.worker_id_prefix = worker_id_prefix
        self.poll_interval = poll_interval  # Worker poll interval (seconds)
        self.enable_worker_loop = enable_worker_loop  # Whether to enable worker auto-loop polling
        self.db = TaskDB()
        self.worker_id = None
        self.markitdown = None
        self.running = False  # Worker running status
        self.worker_thread = None  # Worker thread
    
    def setup(self, device):
        """
        Initialize environment (called once per worker process).
        
        Key Fix: Uses CUDA_VISIBLE_DEVICES to ensure each process only uses its assigned GPU.
        
        Args:
            device: Device assigned by LitServe (cuda:0, cuda:1, etc.)
        """
        # Generate a unique worker_id
        import socket
        hostname = socket.gethostname()
        pid = os.getpid()
        self.worker_id = f"{self.worker_id_prefix}-{hostname}-{device}-{pid}"
        
        logger.info(f"⚙️  Worker {self.worker_id} setting up on device: {device}")
        
        # Key Fix: Set CUDA_VISIBLE_DEVICES to limit the process to its assigned GPU.
        # This prevents a single process from consuming VRAM across multiple cards.
        if device != 'auto' and device != 'cpu' and ':' in str(device):
            # Extract device ID '0' from 'cuda:0'
            device_id = str(device).split(':')[-1]
            os.environ['CUDA_VISIBLE_DEVICES'] = device_id
            # Set to cuda:0, as each process only sees one card (logical ID becomes 0)
            os.environ['VPARSE_DEVICE_MODE'] = 'cuda:0'
            device_mode = os.environ['VPARSE_DEVICE_MODE']
            logger.info(f"🔒 CUDA_VISIBLE_DEVICES={device_id} (Physical GPU {device_id} → Logical GPU 0)")
        else:
            # Configure VParse environment
            if os.getenv('VPARSE_DEVICE_MODE', None) is None:
                os.environ['VPARSE_DEVICE_MODE'] = device if device != 'auto' else get_device()
            device_mode = os.environ['VPARSE_DEVICE_MODE']
        
        # Configure VRAM
        if os.getenv('VPARSE_VIRTUAL_VRAM_SIZE', None) is None:
            if device_mode.startswith("cuda") or device_mode.startswith("npu"):
                try:
                    vram = get_vram(device_mode)
                    os.environ['VPARSE_VIRTUAL_VRAM_SIZE'] = str(vram)
                except:
                    os.environ['VPARSE_VIRTUAL_VRAM_SIZE'] = '8'  # Default value
            else:
                os.environ['VPARSE_VIRTUAL_VRAM_SIZE'] = '1'
        
        # Initialize MarkItDown (if available)
        if MARKITDOWN_AVAILABLE:
            self.markitdown = MarkItDown()
            logger.info(f"✅ MarkItDown initialized for Office format parsing")
        
        logger.info(f"✅ Worker {self.worker_id} ready")
        logger.info(f"   Device: {device_mode}")
        logger.info(f"   VRAM: {os.environ['VPARSE_VIRTUAL_VRAM_SIZE']}GB")
        
        # Start worker auto-loop polling (in a separate thread)
        if self.enable_worker_loop:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._worker_loop, 
                daemon=True,
                name=f"Worker-{self.worker_id}"
            )
            self.worker_thread.start()
            logger.info(f"🔄 Worker loop started (poll_interval={self.poll_interval}s)")
    
    def teardown(self):
        """
        Gracefully shut down worker.
        
        Sets running flag to False and waits for the worker thread to finish the current task.
        This prevents incomplete task processing or database inconsistencies caused by daemon threads.
        """
        if self.enable_worker_loop and self.worker_thread and self.worker_thread.is_alive():
            logger.info(f"🛑 Shutting down worker {self.worker_id}...")
            self.running = False
            
            # Wait for thread to finish current task (at most poll_interval * 2 seconds)
            timeout = self.poll_interval * 2
            self.worker_thread.join(timeout=timeout)
            
            if self.worker_thread.is_alive():
                logger.warning(f"⚠️  Worker thread did not stop within {timeout}s, forcing exit")
            else:
                logger.info(f"✅ Worker {self.worker_id} shut down gracefully")
    
    def _worker_loop(self):
        """
        Worker main loop: continuously poll and process tasks.
        
        Runs in a separate thread, allowing each worker to actively pull tasks
        instead of waiting for scheduler triggers.
        """
        logger.info(f"🔁 {self.worker_id} started task polling loop")
        
        idle_count = 0
        while self.running:
            try:
                # Get task from database
                task = self.db.get_next_task(self.worker_id)
                
                if task:
                    idle_count = 0  # Reset idle count
                    
                    # Process task
                    task_id = task['task_id']
                    logger.info(f"🔄 {self.worker_id} picked up task {task_id}")
                    
                    try:
                        self._process_task(task)
                    except Exception as e:
                        logger.error(f"❌ {self.worker_id} failed to process task {task_id}: {e}")
                        success = self.db.update_task_status(
                            task_id, 'failed', 
                            error_message=str(e), 
                            worker_id=self.worker_id
                        )
                        if not success:
                            logger.warning(f"⚠️  Task {task_id} was modified by another process during failure update")
                    
                else:
                    # No tasks available; increment idle count
                    idle_count += 1
                    
                    # Log only on the first idle cycle to avoid spamming
                    if idle_count == 1:
                        logger.debug(f"💤 {self.worker_id} is idle, waiting for tasks...")
                    
                    # Wait before polling again when idle
                    time.sleep(self.poll_interval)
                    
            except Exception as e:
                logger.error(f"❌ {self.worker_id} loop error: {e}")
                time.sleep(self.poll_interval)
        
        logger.info(f"⏹️  {self.worker_id} stopped task polling loop")
    
    def _process_task(self, task: dict):
        """
        Process a single task.
        
        Args:
            task: Task dictionary
        """
        task_id = task['task_id']
        file_path = task['file_path']
        file_name = task['file_name']
        backend = task['backend']
        options = json.loads(task['options'])
        
        logger.info(f"🔄 Processing task {task_id}: {file_name}")
        
        try:
            # Prepare output directory
            output_path = self.output_dir / task_id
            output_path.mkdir(parents=True, exist_ok=True)
            
            # Determine file type and select parsing method
            file_type = self._get_file_type(file_path)
            
            if file_type == 'pdf_image':
                # Use VParse to parse PDF and Images
                self._parse_with_vparse(
                    file_path=Path(file_path),
                    file_name=file_name,
                    task_id=task_id,
                    backend=backend,
                    options=options,
                    output_path=output_path
                )
                parse_method = 'VParse'
                
            else:  # file_type == 'markitdown'
                # Use MarkItDown to parse all other formats
                self._parse_with_markitdown(
                    file_path=Path(file_path),
                    file_name=file_name,
                    output_path=output_path
                )
                parse_method = 'MarkItDown'
            
            # Update status to completed
            success = self.db.update_task_status(
                task_id, 'completed', 
                result_path=str(output_path),
                worker_id=self.worker_id
            )
            
            if success:
                logger.info(f"✅ Task {task_id} completed by {self.worker_id}")
                logger.info(f"   Parser: {parse_method}")
                logger.info(f"   Output: {output_path}")
            else:
                logger.warning(
                    f"⚠️  Task {task_id} was modified by another process. "
                    f"Worker {self.worker_id} completed the work but status update was rejected."
                )
            
        finally:
            # Clean up temporary files
            try:
                if Path(file_path).exists():
                    Path(file_path).unlink()
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {file_path}: {e}")
    
    def decode_request(self, request):
        """
        Decode request.
        
        Primarily used for health checks and manual triggers (backward compatibility).
        """
        return request.get('action', 'poll')
    
    def _get_file_type(self, file_path: str) -> str:
        """
        Determine file type.
        
        Args:
            file_path: File path
            
        Returns:
            'pdf_image': PDF or Image format, parsed with VParse
            'markitdown': All other formats, parsed with markitdown
        """
        suffix = Path(file_path).suffix.lower()
        
        if suffix in self.PDF_IMAGE_FORMATS:
            return 'pdf_image'
        else:
            # All non-PDF/image formats use MarkItDown
            return 'markitdown'
    
    def _parse_with_vparse(self, file_path: Path, file_name: str, task_id: str, 
                           backend: str, options: dict, output_path: Path):
        """
        Parse PDF and Image formats using VParse
        
        Args:
            file_path: File path
            file_name: Filename
            task_id: Task ID
            backend: Backend type
            options: Parsing options
            output_path: Output path
        """
        logger.info(f"📄 Using VParse to parse: {file_name}")
        
        try:
            # Read file
            pdf_bytes = read_fn(file_path)
            
            # Execute parsing (VParse's ModelSingleton will reuse models automatically)
            do_parse(
                output_dir=str(output_path),
                pdf_file_names=[Path(file_name).stem],
                pdf_bytes_list=[pdf_bytes],
                p_lang_list=[options.get('lang', 'ch')],
                backend=backend,
                parse_method=options.get('method', 'auto'),
                formula_enable=options.get('formula_enable', True),
                table_enable=options.get('table_enable', True),
            )
        finally:
            # Use VParse's built-in memory cleanup function
            # This function only cleans intermediate results from inference, it won't unload the model
            try:
                clean_memory()
            except Exception as e:
                logger.debug(f"Memory cleanup failed for task {task_id}: {e}")
    
    def _parse_with_markitdown(self, file_path: Path, file_name: str, 
                               output_path: Path):
        """
        Use MarkItDown to parse documents (supports Office, HTML, text, etc.).
        
        Args:
            file_path: File path
            file_name: Filename
            output_path: Output path
        """
        if not MARKITDOWN_AVAILABLE or self.markitdown is None:
            raise RuntimeError("markitdown is not available. Please install it: pip install markitdown")
        
        logger.info(f"📊 Using MarkItDown to parse: {file_name}")
        
        # Convert document using MarkItDown
        result = self.markitdown.convert(str(file_path))
        
        # Save as markdown file
        output_file = output_path / f"{Path(file_name).stem}.md"
        output_file.write_text(result.text_content, encoding='utf-8')
        
        logger.info(f"📝 Markdown saved to: {output_file}")
    
    def predict(self, action):
        """
        HTTP interface (primarily for health checks and monitoring).
        
        Tasks are now auto-polled; this interface is used for:
        1. Health checks
        2. Worker status
        3. Backward compatibility for manual triggers (if enable_worker_loop=False)
        """
        if action == 'health':
            # Health check
            stats = self.db.get_queue_stats()
            return {
                'status': 'healthy',
                'worker_id': self.worker_id,
                'worker_loop_enabled': self.enable_worker_loop,
                'worker_running': self.running,
                'queue_stats': stats
            }
        
        elif action == 'poll':
            if not self.enable_worker_loop:
                # Compatibility mode: manual task polling trigger
                task = self.db.get_next_task(self.worker_id)
                
                if not task:
                    return {
                        'status': 'idle',
                        'message': 'No pending tasks in queue',
                        'worker_id': self.worker_id
                    }
                
                try:
                    self._process_task(task)
                    return {
                        'status': 'completed',
                        'task_id': task['task_id'],
                        'worker_id': self.worker_id
                    }
                except Exception as e:
                    return {
                        'status': 'failed',
                        'task_id': task['task_id'],
                        'error': str(e),
                        'worker_id': self.worker_id
                    }
            else:
                # Worker auto-loop mode: return status info
                return {
                    'status': 'auto_mode',
                    'message': 'Worker is running in auto-loop mode, tasks are processed automatically',
                    'worker_id': self.worker_id,
                    'worker_running': self.running
                }
        
        else:
            return {
                'status': 'error',
                'message': f'Invalid action: {action}. Use "health" or "poll".',
                'worker_id': self.worker_id
            }
    
    def encode_response(self, response):
        """Encode response"""
        return response


def start_litserve_workers(
    output_dir='/tmp/vparse_heavy_output',
    accelerator='auto',
    devices='auto',
    workers_per_device=1,
    port=9000,
    poll_interval=0.5,
    enable_worker_loop=True
):
    """
    Start LitServe Worker Pool
    
    Args:
        output_dir: Output directory
        accelerator: Accelerator type (auto/cuda/cpu/mps)
        devices: Devices to use (auto/[0,1,2])
        workers_per_device: Number of workers per GPU
        port: Service port
        poll_interval: Worker poll interval (seconds)
        enable_worker_loop: Whether to enable worker auto-loop polling
    """
    logger.info("=" * 60)
    logger.info("🚀 Starting VParse Heavy LitServe Worker Pool")
    logger.info("=" * 60)
    logger.info(f"📂 Output Directory: {output_dir}")
    logger.info(f"🎮 Accelerator: {accelerator}")
    logger.info(f"💾 Devices: {devices}")
    logger.info(f"👷 Workers per Device: {workers_per_device}")
    logger.info(f"🔌 Port: {port}")
    logger.info(f"🔄 Worker Loop: {'Enabled' if enable_worker_loop else 'Disabled'}")
    if enable_worker_loop:
        logger.info(f"⏱️  Poll Interval: {poll_interval}s")
    logger.info("=" * 60)
    
    # Create LitServe server
    api = VParseWorkerAPI(
        output_dir=output_dir,
        poll_interval=poll_interval,
        enable_worker_loop=enable_worker_loop
    )
    server = ls.LitServer(
        api,
        accelerator=accelerator,
        devices=devices,
        workers_per_device=workers_per_device,
        timeout=False,  # Disable timeout
    )
    
    # Register graceful shutdown handler
    def graceful_shutdown(signum=None, frame=None):
        """Handle shutdown signal, gracefully stop workers"""
        logger.info("🛑 Received shutdown signal, gracefully stopping workers...")
        # Note: LitServe creates multiple worker instances per device.
        # The 'api' here is a template; actual instances are managed by LitServe.
        # teardown is called per worker process.
        if hasattr(api, 'teardown'):
            api.teardown()
        sys.exit(0)
    
    # Register signal handlers (Ctrl+C, etc.)
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    
    # Register atexit handler (called on normal exit)
    atexit.register(lambda: api.teardown() if hasattr(api, 'teardown') else None)
    
    logger.info(f"✅ LitServe worker pool initialized")
    logger.info(f"📡 Listening on: http://0.0.0.0:{port}/predict")
    if enable_worker_loop:
        logger.info(f"🔁 Workers will continuously poll and process tasks")
    else:
        logger.info(f"🔄 Workers will wait for scheduler triggers")
    logger.info("=" * 60)
    
    # Start server
    server.run(port=port, generate_client_file=False)


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='VParse Heavy LitServe Worker Pool')
    parser.add_argument('--output-dir', type=str, default='/tmp/vparse_heavy_output',
                       help='Output directory for processed files')
    parser.add_argument('--accelerator', type=str, default='auto',
                       choices=['auto', 'cuda', 'cpu', 'mps'],
                       help='Accelerator type')
    parser.add_argument('--devices', type=str, default='auto',
                       help='Devices to use (auto or comma-separated list like 0,1,2)')
    parser.add_argument('--workers-per-device', type=int, default=1,
                       help='Number of workers per device')
    parser.add_argument('--port', type=int, default=9000,
                       help='Server port')
    parser.add_argument('--poll-interval', type=float, default=0.5,
                       help='Worker poll interval in seconds (default: 0.5)')
    parser.add_argument('--disable-worker-loop', action='store_true',
                       help='Disable worker auto-loop mode (use scheduler-driven mode)')
    
    args = parser.parse_args()
    
    # Process devices parameter
    devices = args.devices
    if devices != 'auto':
        try:
            devices = [int(d) for d in devices.split(',')]
        except:
            logger.warning(f"Invalid devices format: {devices}, using 'auto'")
            devices = 'auto'
    
    start_litserve_workers(
        output_dir=args.output_dir,
        accelerator=args.accelerator,
        devices=devices,
        workers_per_device=args.workers_per_device,
        port=args.port,
        poll_interval=args.poll_interval,
        enable_worker_loop=not args.disable_worker_loop
    )

