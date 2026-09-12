"""
Performance optimization module for Wikipedia automation.

This module provides:
- Connection pooling for HTTP requests
- Controlled parallelism for independent operations
- Payload optimization
- Performance monitoring and metrics
"""

import logging
import time
import asyncio
from typing import Callable, Any, List, Optional, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from functools import wraps
import threading

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""
    operation_name: str
    total_time: float = 0.0
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    last_execution: Optional[float] = None
    
    def update(self, duration: float, success: bool) -> None:
        """Update metrics with a new execution."""
        self.call_count += 1
        self.total_time += duration
        
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        
        self.avg_time = self.total_time / self.call_count
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.last_execution = time.time()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of metrics."""
        return {
            'operation': self.operation_name,
            'total_calls': self.call_count,
            'success_rate': self.success_count / self.call_count if self.call_count > 0 else 0,
            'avg_time_ms': self.avg_time * 1000,
            'min_time_ms': self.min_time * 1000 if self.min_time != float('inf') else 0,
            'max_time_ms': self.max_time * 1000,
            'last_execution': self.last_execution
        }


class PerformanceMonitor:
    """Monitor and track performance metrics."""
    
    def __init__(self):
        """Initialize the performance monitor."""
        self._metrics: Dict[str, PerformanceMetrics] = {}
        self._lock = threading.Lock()
    
    def record_operation(self, operation_name: str, duration: float, success: bool) -> None:
        """Record an operation execution."""
        with self._lock:
            if operation_name not in self._metrics:
                self._metrics[operation_name] = PerformanceMetrics(operation_name=operation_name)
            self._metrics[operation_name].update(duration, success)
    
    def get_metrics(self, operation_name: str) -> Optional[PerformanceMetrics]:
        """Get metrics for a specific operation."""
        with self._lock:
            return self._metrics.get(operation_name)
    
    def get_all_metrics(self) -> Dict[str, PerformanceMetrics]:
        """Get all metrics."""
        with self._lock:
            return self._metrics.copy()
    
    def reset_metrics(self, operation_name: Optional[str] = None) -> None:
        """Reset metrics for a specific operation or all operations."""
        with self._lock:
            if operation_name:
                if operation_name in self._metrics:
                    del self._metrics[operation_name]
            else:
                self._metrics.clear()


class ControlledParallelism:
    """
    Manager for controlled parallel execution of independent operations.
    
    Provides:
- Thread pool execution with configurable limits
- Async support for I/O-bound operations
- Resource limits to prevent overload
- Progress tracking
    """
    
    def __init__(self, max_workers: int = 4, timeout: float = 300.0):
        """
        Initialize the parallelism manager.
        
        Args:
            max_workers: Maximum number of parallel workers
            timeout: Maximum timeout for operations in seconds
        """
        self.max_workers = max_workers
        self.timeout = timeout
        self._executor: Optional[ThreadPoolExecutor] = None
    
    def execute_parallel(
        self,
        functions: List[Callable],
        args_list: Optional[List[tuple]] = None,
        kwargs_list: Optional[List[dict]] = None
    ) -> List[Any]:
        """
        Execute functions in parallel with controlled concurrency.
        
        Args:
            functions: List of functions to execute
            args_list: List of argument tuples for each function
            kwargs_list: List of keyword argument dicts for each function
            
        Returns:
            List of results in the same order as input functions
        """
        if args_list is None:
            args_list = [() for _ in functions]
        if kwargs_list is None:
            kwargs_list = [{} for _ in functions]
        
        if len(functions) != len(args_list) or len(functions) != len(kwargs_list):
            raise ValueError("functions, args_list, and kwargs_list must have the same length")
        
        results = [None] * len(functions)
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_index = {}
            for i, (func, args, kwargs) in enumerate(zip(functions, args_list, kwargs_list)):
                future = executor.submit(func, *args, **kwargs)
                future_to_index[future] = i
            
            # Collect results as they complete
            for future in as_completed(future_to_index, timeout=self.timeout):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    logger.error(f"Parallel task {index} failed: {e}")
                    results[index] = e
        
        return results
    
    async def execute_parallel_async(
        self,
        coroutines: List[Callable]
    ) -> List[Any]:
        """
        Execute async coroutines in parallel with controlled concurrency.
        
        Args:
            coroutines: List of async functions to execute
            
        Returns:
            List of results
        """
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def limited_coro(coro):
            async with semaphore:
                return await coro()
        
        results = await asyncio.gather(
            *[limited_coro(coro()) for coro in coroutines],
            return_exceptions=True
        )
        
        return results


class PayloadOptimizer:
    """
    Optimizer for request payloads to reduce size and improve performance.
    
    Provides:
- Content compression
- Field filtering
- Size optimization
    """
    
    @staticmethod
    def optimize_json_payload(payload: Dict[str, Any], max_size_kb: int = 100) -> Dict[str, Any]:
        """
        Optimize JSON payload by removing unnecessary fields and reducing size.
        
        Args:
            payload: Original payload
            max_size_kb: Maximum size in kilobytes
            
        Returns:
            Optimized payload
        """
        import json
        
        # Remove None values
        optimized = {k: v for k, v in payload.items() if v is not None}
        
        # Check size
        payload_str = json.dumps(optimized)
        payload_size_kb = len(payload_str.encode('utf-8')) / 1024
        
        if payload_size_kb > max_size_kb:
            logger.warning(f"Payload size {payload_size_kb:.2f}KB exceeds limit {max_size_kb}KB")
            # Could implement field priority-based removal here
        
        return optimized
    
    @staticmethod
    def truncate_content(content: str, max_chars: int = 10000) -> str:
        """
        Truncate content to maximum character limit.
        
        Args:
            content: Original content
            max_chars: Maximum character limit
            
        Returns:
            Truncated content
        """
        if len(content) <= max_chars:
            return content
        
        logger.warning(f"Content truncated from {len(content)} to {max_chars} characters")
        return content[:max_chars] + "... [truncated]"
    
    @staticmethod
    def remove_empty_sections(wikitext: str) -> str:
        """
        Remove empty sections from wikitext to reduce payload size.
        
        Args:
            wikitext: Original wikitext
            
        Returns:
            Cleaned wikitext
        """
        lines = wikitext.split('\n')
        cleaned_lines = []
        current_section = []
        section_has_content = False
        
        for line in lines:
            stripped = line.strip()
            
            # Check if this is a section header
            if stripped.startswith('==') and stripped.endswith('=='):
                # Add previous section if it has content
                if section_has_content:
                    cleaned_lines.extend(current_section)
                
                # Start new section
                current_section = [line]
                section_has_content = False
            else:
                current_section.append(line)
                if stripped and not stripped.startswith('*') and not stripped.startswith('|'):
                    section_has_content = True
        
        # Add last section if it has content
        if section_has_content:
            cleaned_lines.extend(current_section)
        
        return '\n'.join(cleaned_lines)


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """
    Get the global performance monitor instance.
    
    Returns:
        PerformanceMonitor instance
    """
    global _performance_monitor
    
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    
    return _performance_monitor


def monitor_performance(operation_name: str):
    """
    Decorator to monitor performance of a function.
    
    Args:
        operation_name: Name of the operation for metrics
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            monitor = get_performance_monitor()
            start_time = time.time()
            success = False
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            except Exception as e:
                logger.error(f"Operation {operation_name} failed: {e}")
                raise
            finally:
                duration = time.time() - start_time
                monitor.record_operation(operation_name, duration, success)
        
        return wrapper
    return decorator


class BatchProcessor:
    """
    Process items in batches for better performance.
    
    Useful for:
- API calls with rate limits
- Database operations
- File processing
    """
    
    def __init__(self, batch_size: int = 10, delay_between_batches: float = 1.0):
        """
        Initialize the batch processor.
        
        Args:
            batch_size: Number of items per batch
            delay_between_batches: Delay in seconds between batches
        """
        self.batch_size = batch_size
        self.delay_between_batches = delay_between_batches
    
    def process_in_batches(
        self,
        items: List[Any],
        process_func: Callable[[List[Any]], Any],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """
        Process items in batches.
        
        Args:
            items: List of items to process
            process_func: Function to process each batch
            progress_callback: Optional callback (current, total)
            
        Returns:
            List of results from each batch
        """
        results = []
        total_items = len(items)
        
        for i in range(0, total_items, self.batch_size):
            batch = items[i:i + self.batch_size]
            
            try:
                batch_result = process_func(batch)
                results.append(batch_result)
                
                if progress_callback:
                    progress_callback(min(i + self.batch_size, total_items), total_items)
                
                # Add delay between batches (except for last batch)
                if i + self.batch_size < total_items:
                    time.sleep(self.delay_between_batches)
                    
            except Exception as e:
                logger.error(f"Batch processing failed at batch {i//self.batch_size}: {e}")
                results.append(None)
        
        return results