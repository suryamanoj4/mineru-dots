"""
VParse Heavy - Client Example
Heavy客户端示例

Demonstrates how to use the Python client to submit tasks and query status.
"""
import asyncio
import aiohttp
import os
import time
from pathlib import Path
from loguru import logger


class HeavyClient:
    """Heavy客户端"""
    
    def __init__(self, base_url='http://localhost:8000'):
        self.base_url = base_url
    
    async def submit_task(
        self, 
        file_path: str, 
        backend: str = 'pipeline', 
        lang: str = 'ch', 
        method: str = 'auto',
        formula_enable: bool = True,
        table_enable: bool = True,
        priority: int = 0
    ):
        """
        Submit a task
        
        Args:
            file_path: File path
            backend: Processing backend
            lang: Language
            method: Parsing method
            formula_enable: Whether to enable formula recognition
            table_enable: Whether to enable table recognition
            priority: Priority level
            
        Returns:
            Response dictionary containing task_id
        """
        url = f"{self.base_url}/api/v1/tasks/submit"
        
        # Check if file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Prepare form data
        data = aiohttp.FormData()
        data.add_field('file', open(file_path, 'rb'), filename=os.path.basename(file_path))
        data.add_field('backend', backend)
        data.add_field('lang', lang)
        data.add_field('method', method)
        data.add_field('formula_enable', str(formula_enable).lower())
        data.add_field('table_enable', str(table_enable).lower())
        data.add_field('priority', str(priority))
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Submit failed ({response.status}): {error_text}")
                return await response.json()
    
    async def get_status(self, task_id: str, upload_images: bool = False):
        """
        Query task status
        
        Args:
            task_id: Task ID
            upload_images: Whether to upload images to MinIO
            
        Returns:
            Task status dictionary
        """
        url = f"{self.base_url}/api/v1/tasks/{task_id}"
        params = {'upload_images': str(upload_images).lower()}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Query failed ({response.status}): {error_text}")
                return await response.json()
    
    async def wait_for_completion(
        self, 
        task_id: str, 
        timeout: int = 600, 
        poll_interval: int = 5
    ):
        """
        Wait for task completion
        
        Args:
            task_id: Task ID
            timeout: Timeout in seconds
            poll_interval: Polling interval in seconds
            
        Returns:
            Final task status
        """
        start_time = time.time()
        
        while True:
            status_res = await self.get_status(task_id)
            status = status_res.get('status')
            
            if status == 'completed':
                logger.info(f"✅ Task {task_id} completed!")
                return status_res
            
            if status == 'failed':
                error = status_res.get('error_message', 'Unknown error')
                logger.error(f"❌ Task {task_id} failed: {error}")
                return status_res
            
            if status == 'cancelled':
                logger.warning(f"🛑 Task {task_id} was cancelled")
                return status_res
            
            # Check timeout
            if time.time() - start_time > timeout:
                logger.error(f"⏰ Timeout waiting for task {task_id}")
                raise TimeoutError(f"Task {task_id} timed out after {timeout}s")
            
            # Wait before polling again
            logger.info(f"⏳ Task {task_id} is {status}, waiting...")
            await asyncio.sleep(poll_interval)
            
    async def get_queue_stats(self):
        """Get queue statistics"""
        url = f"{self.base_url}/api/v1/queue/stats"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.json()

    async def cancel_task(self, task_id: str):
        """Cancel a task"""
        url = f"{self.base_url}/api/v1/tasks/{task_id}"
        async with aiohttp.ClientSession() as session:
            async with session.delete(url) as response:
                return await response.json()


async def example_single_task(client: TianshuClient, file_path: str):
    """Example 1: Submit a single task and wait for completion"""
    logger.info("Example 1: Submitting a single task")
    
    client = HeavyClient()
    
    async with aiohttp.ClientSession() as session:
        # 提交任务
        result = await client.submit_task(
            session,
            file_path='../../demo/pdfs/demo1.pdf',
            backend='pipeline',
            lang='ch',
            formula_enable=True,
            table_enable=True
        )
        task_id = submit_res['task_id']
        logger.info(f"🚀 Task submitted, ID: {task_id}")
        
        # Wait for completion
        result = await client.wait_for_completion(task_id)
        
        if result['status'] == 'completed':
            md_content = result.get('data', {}).get('content', '')
            logger.info(f"📝 Markdown content length: {len(md_content)}")
            # logger.info(f"Content preview: {md_content[:200]}...")
            
    except Exception as e:
        logger.error(f"Error in Example 1: {e}")


async def example_batch_tasks(client: TianshuClient, file_paths: list):
    """Example 2: Batch submit multiple tasks and wait concurrently"""
    logger.info("Example 2: Submitting multiple tasks in batch")
    
    client = HeavyClient()
    
    try:
        # Submit all tasks concurrently
        submit_results = await asyncio.gather(*tasks)
        
        # Extract task_ids
        task_ids = [res['task_id'] for res in submit_results]
        logger.info(f"🚀 Submitted {len(task_ids)} tasks: {task_ids}")
        
        # Wait concurrently for all tasks to complete
        wait_tasks = [client.wait_for_completion(tid) for tid in task_ids]
        final_results = await asyncio.gather(*wait_tasks)
        
        # Statistics
        success = sum(1 for r in final_results if r['status'] == 'completed')
        failed = sum(1 for r in final_results if r['status'] == 'failed')
        logger.info(f"📊 Batch results: {success} successful, {failed} failed")
        
    except Exception as e:
        logger.error(f"Error in Example 2: {e}")


async def example_priority_queue(client: TianshuClient, file_path: str):
    """Example 3: Using priority queue"""
    logger.info("Example 3: Priority queue")
    
    client = HeavyClient()
    
    async with aiohttp.ClientSession() as session:
        # 提交低优先级任务
        low_priority = await client.submit_task(
            session,
            file_path='../../demo/pdfs/demo1.pdf',
            priority=0
        )
        logger.info(f"💤 Submitted low priority task: {low_p_task['task_id']}")
        
        # Submit high priority task
        high_p_task = await client.submit_task(
            file_path=file_path,
            priority=10
        )
        logger.info(f"⚡ Submitted high priority task: {high_p_task['task_id']}")
        
        # High priority task will be processed first
        logger.info("⏳ High priority task will be processed first...")
        
    except Exception as e:
        logger.error(f"Error in Example 3: {e}")


async def example_stats(client: TianshuClient):
    """Example 4: Monitoring queue status"""
    logger.info("Example 4: Monitoring queue status")
    
    client = HeavyClient()
    
    async with aiohttp.ClientSession() as session:
        # 获取队列统计
        stats = await client.get_queue_stats(session)
        
    except Exception as e:
        logger.error(f"Error in Example 4: {e}")


async def main():
    """Main function"""
    # Configure Tianshu server address
    base_url = os.getenv('TIANSHU_URL', 'http://localhost:8000')
    client = TianshuClient(base_url)
    
    # Path to test file
    test_pdf = "../../demo/pdfs/demo1.pdf"
    
    if not os.path.exists(test_pdf):
        logger.error(f"❌ Test file not found: {test_pdf}")
        return

    # Check server connectivity
    try:
        await client.get_queue_stats()
        logger.info("✅ Connected to Tianshu server")
    except Exception:
        logger.error(f"❌ Failed to connect to server at {base_url}")
        logger.info("   Make sure the server is running (python start_all.py)")
        return

    # Choose examples to run
    # Usage:
    # # Run all examples
    # await example_single_task(client, test_pdf)
    # await example_batch_tasks(client, [test_pdf, test_pdf])
    # await example_priority_queue(client, test_pdf)
    # await example_stats(client)
    
    # Run specific example
    await example_single_task(client, test_pdf)
    await example_stats(client)


if __name__ == "__main__":
    asyncio.run(main())
