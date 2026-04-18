"""
VParse Heavy - Unified Startup Script
Heavy统一启动脚本

Start all services with one click: API Server + LitServe Workers + Task Scheduler
"""
import subprocess
import signal
import sys
import time
import os
from loguru import logger
from pathlib import Path
import argparse


class HeavyLauncher:
    """Heavy服务启动器"""
    
    def __init__(
        self,
        output_dir='/tmp/vparse_heavy_output',
        api_port=8000,
        worker_port=9000,
        workers_per_device=1,
        devices='auto',
        accelerator='auto'
    ):
        self.output_dir = output_dir
        self.api_port = api_port
        self.worker_port = worker_port
        self.workers_per_device = workers_per_device
        self.devices = devices
        self.accelerator = accelerator
        self.processes = []
    
    def start_services(self):
        """Start all services"""
        logger.info("=" * 70)
        logger.info("🚀 VParse Heavy - Starting All Services")
        logger.info("=" * 70)
        logger.info("Heavy - 企业级多GPU文档解析服务")
        logger.info("")
        
        try:
            # 1. Start API Server
            logger.info("📡 [1/3] Starting API Server...")
            env = os.environ.copy()
            env['API_PORT'] = str(self.api_port)
            api_proc = subprocess.Popen(
                [sys.executable, 'api_server.py'],
                cwd=Path(__file__).parent,
                env=env
            )
            self.processes.append(('API Server', api_proc))
            time.sleep(3)
            
            if api_proc.poll() is not None:
                logger.error("❌ API Server failed to start!")
                return False
            
            logger.info(f"   ✅ API Server started (PID: {api_proc.pid})")
            logger.info(f"   📖 API Docs: http://localhost:{self.api_port}/docs")
            logger.info("")
            
            # 2. Start LitServe Worker Pool
            logger.info("⚙️  [2/3] Starting LitServe Worker Pool...")
            worker_cmd = [
                sys.executable, 'litserve_worker.py',
                '--output-dir', self.output_dir,
                '--accelerator', self.accelerator,
                '--workers-per-device', str(self.workers_per_device),
                '--port', str(self.worker_port),
                '--devices', str(self.devices) if isinstance(self.devices, str) else ','.join(map(str, self.devices))
            ]
            
            worker_proc = subprocess.Popen(
                worker_cmd,
                cwd=Path(__file__).parent
            )
            self.processes.append(('LitServe Workers', worker_proc))
            time.sleep(5)
            
            if worker_proc.poll() is not None:
                logger.error("❌ LitServe Workers failed to start!")
                return False
            
            logger.info(f"   ✅ LitServe Workers started (PID: {worker_proc.pid})")
            logger.info(f"   🔌 Worker Port: {self.worker_port}")
            logger.info(f"   👷 Workers per Device: {self.workers_per_device}")
            logger.info("")
            
            # 3. Start Task Scheduler
            logger.info("🔄 [3/3] Starting Task Scheduler...")
            scheduler_cmd = [
                sys.executable, 'task_scheduler.py',
                '--litserve-url', f'http://localhost:{self.worker_port}/predict',
                '--wait-for-workers'
            ]
            
            scheduler_proc = subprocess.Popen(
                scheduler_cmd,
                cwd=Path(__file__).parent
            )
            self.processes.append(('Task Scheduler', scheduler_proc))
            time.sleep(3)
            
            if scheduler_proc.poll() is not None:
                logger.error("❌ Task Scheduler failed to start!")
                return False
            
            logger.info(f"   ✅ Task Scheduler started (PID: {scheduler_proc.pid})")
            logger.info("")
            
            # Startup successful
            logger.info("=" * 70)
            logger.info("✅ All Services Started Successfully!")
            logger.info("=" * 70)
            logger.info("")
            logger.info("📚 Quick Start:")
            logger.info(f"   • API Documentation: http://localhost:{self.api_port}/docs")
            logger.info(f"   • Submit Task:       POST http://localhost:{self.api_port}/api/v1/tasks/submit")
            logger.info(f"   • Query Status:      GET  http://localhost:{self.api_port}/api/v1/tasks/{{task_id}}")
            logger.info(f"   • Queue Stats:       GET  http://localhost:{self.api_port}/api/v1/queue/stats")
            logger.info("")
            logger.info("🔧 Service Details:")
            for name, proc in self.processes:
                logger.info(f"   • {name:20s} PID: {proc.pid}")
            logger.info("")
            logger.info("⚠️  Press Ctrl+C to stop all services")
            logger.info("=" * 70)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start services: {e}")
            self.stop_services()
            return False
    
    def stop_services(self, signum=None, frame=None):
        """Stop all services"""
        logger.info("")
        logger.info("=" * 70)
        logger.info("⏹️  Stopping All Services...")
        logger.info("=" * 70)
        
        for name, proc in self.processes:
            if proc.poll() is None:  # Process is still running
                logger.info(f"   Stopping {name} (PID: {proc.pid})...")
                proc.terminate()
        
        # Wait for all processes to terminate
        for name, proc in self.processes:
            try:
                proc.wait(timeout=10)
                logger.info(f"   ✅ {name} stopped")
            except subprocess.TimeoutExpired:
                logger.warning(f"   ⚠️  {name} did not stop gracefully, forcing...")
                proc.kill()
                proc.wait()
        
        logger.info("=" * 70)
        logger.info("✅ All Services Stopped")
        logger.info("=" * 70)
        sys.exit(0)
    
    def wait(self):
        """Wait for all services"""
        try:
            while True:
                time.sleep(1)
                
                # Check process status
                for name, proc in self.processes:
                    if proc.poll() is not None:
                        logger.error(f"❌ {name} unexpectedly stopped!")
                        self.stop_services()
                        return
                        
        except KeyboardInterrupt:
            self.stop_services()


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='VParse Heavy - 统一启动脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  # Start with default config (auto-detect GPU)
  python start_all.py
  
  # Use CPU mode
  python start_all.py --accelerator cpu
  
  # Specify output directory and port
  python start_all.py --output-dir /data/output --api-port 8080
  
  # Start 2 workers per GPU
  python start_all.py --accelerator cuda --workers-per-device 2
  
  # Use specific GPUs only
  python start_all.py --accelerator cuda --devices 0,1
        """
    )
    
    parser.add_argument('--output-dir', type=str, default='/tmp/vparse_heavy_output',
                       help='输出目录 (默认: /tmp/vparse_heavy_output)')
    parser.add_argument('--api-port', type=int, default=8000,
                       help='API server port (default: 8000)')
    parser.add_argument('--worker-port', type=int, default=9000,
                       help='Worker server port (default: 9000)')
    parser.add_argument('--accelerator', type=str, default='auto',
                       choices=['auto', 'cuda', 'cpu', 'mps'],
                       help='Accelerator type (default: auto, auto-detected)')
    parser.add_argument('--workers-per-device', type=int, default=1,
                       help='Number of workers per GPU (default: 1)')
    parser.add_argument('--devices', type=str, default='auto',
                       help='GPU devices to use, comma-separated (default: auto, use all GPUs)')
    
    args = parser.parse_args()
    
    # Process devices parameter
    devices = args.devices
    if devices != 'auto':
        try:
            devices = [int(d) for d in devices.split(',')]
        except:
            logger.warning(f"Invalid devices format: {devices}, using 'auto'")
            devices = 'auto'
    
    # 创建启动器
    launcher = HeavyLauncher(
        output_dir=args.output_dir,
        api_port=args.api_port,
        worker_port=args.worker_port,
        workers_per_device=args.workers_per_device,
        devices=devices,
        accelerator=args.accelerator
    )
    
    # Set up signal handling
    signal.signal(signal.SIGINT, launcher.stop_services)
    signal.signal(signal.SIGTERM, launcher.stop_services)
    
    # Start services
    if launcher.start_services():
        launcher.wait()
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
