#!/usr/bin/env python3
"""
Health Check System
Monitor models, resources, and system health
"""

import psutil
import time
import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Handle torch import gracefully
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class HealthStatus(Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class HealthCheck:
    """Base health check class"""
    
    def __init__(self, name: str):
        self.name = name
        self.last_check_time: Optional[datetime] = None
        self.last_status = HealthStatus.HEALTHY
        self.last_details = {}
    
    def check(self) -> Dict:
        """
        Perform health check
        
        Returns:
            {
                'name': str,
                'status': HealthStatus,
                'details': dict,
                'timestamp': str
            }
        """
        raise NotImplementedError


class ModelHealthCheck(HealthCheck):
    """Check if models are loaded and functional"""
    
    def __init__(self, translator):
        super().__init__("model_health")
        self.translator = translator
    
    def check(self) -> Dict:
        """Check model health"""
        self.last_check_time = datetime.now()
        
        try:
            # Check if models are loaded
            has_whisper = hasattr(self.translator, 'whisper_model') and self.translator.whisper_model is not None
            has_translator = hasattr(self.translator, 'translator_model') and self.translator.translator_model is not None
            
            if not has_whisper or not has_translator:
                self.last_status = HealthStatus.UNHEALTHY
                self.last_details = {
                    'whisper_loaded': has_whisper,
                    'translator_loaded': has_translator,
                    'error': 'Models not loaded'
                }
            else:
                # Try a simple inference test
                import numpy as np
                test_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
                
                try:
                    # Quick transcription test (should be fast for silence)
                    result = self.translator.whisper_model.transcribe(
                        test_audio,
                        language=self.translator.source_language,
                        task="transcribe"
                    )
                    
                    self.last_status = HealthStatus.HEALTHY
                    self.last_details = {
                        'whisper_loaded': True,
                        'translator_loaded': True,
                        'test_passed': True
                    }
                
                except Exception as e:
                    self.last_status = HealthStatus.DEGRADED
                    self.last_details = {
                        'whisper_loaded': True,
                        'translator_loaded': True,
                        'test_passed': False,
                        'error': str(e)
                    }
        
        except Exception as e:
            self.last_status = HealthStatus.UNHEALTHY
            self.last_details = {'error': str(e)}
        
        return {
            'name': self.name,
            'status': self.last_status.value,
            'details': self.last_details,
            'timestamp': self.last_check_time.isoformat()
        }


class SystemResourceCheck(HealthCheck):
    """Check system resources (CPU, Memory, Disk)"""
    
    def __init__(self):
        super().__init__("system_resources")
        
        # Thresholds
        self.cpu_warning_threshold = 80.0  # %
        self.cpu_critical_threshold = 95.0  # %
        self.memory_warning_threshold = 80.0  # %
        self.memory_critical_threshold = 95.0  # %
        self.disk_warning_threshold = 85.0  # %
        self.disk_critical_threshold = 95.0  # %
    
    def check(self) -> Dict:
        """Check system resources"""
        self.last_check_time = datetime.now()
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Disk usage (use appropriate path for OS)
            try:
                disk = psutil.disk_usage('/')
            except:
                disk = psutil.disk_usage('C:\\')
            disk_percent = disk.percent
            
            # Determine overall status
            if (cpu_percent >= self.cpu_critical_threshold or
                memory_percent >= self.memory_critical_threshold or
                disk_percent >= self.disk_critical_threshold):
                self.last_status = HealthStatus.UNHEALTHY
            elif (cpu_percent >= self.cpu_warning_threshold or
                  memory_percent >= self.memory_warning_threshold or
                  disk_percent >= self.disk_warning_threshold):
                self.last_status = HealthStatus.DEGRADED
            else:
                self.last_status = HealthStatus.HEALTHY
            
            self.last_details = {
                'cpu_percent': round(cpu_percent, 2),
                'memory_percent': round(memory_percent, 2),
                'memory_available_gb': round(memory.available / (1024**3), 2),
                'disk_percent': round(disk_percent, 2),
                'disk_free_gb': round(disk.free / (1024**3), 2)
            }
        
        except Exception as e:
            self.last_status = HealthStatus.UNHEALTHY
            self.last_details = {'error': str(e)}
        
        return {
            'name': self.name,
            'status': self.last_status.value,
            'details': self.last_details,
            'timestamp': self.last_check_time.isoformat()
        }


class GPUHealthCheck(HealthCheck):
    """Check GPU status and utilization"""
    
    def __init__(self):
        super().__init__("gpu_health")
        self.has_cuda = TORCH_AVAILABLE and torch.cuda.is_available()
    
    def check(self) -> Dict:
        """Check GPU health"""
        self.last_check_time = datetime.now()
        
        if not self.has_cuda:
            self.last_status = HealthStatus.HEALTHY  # CPU-only is fine
            self.last_details = {
                'cuda_available': False,
                'device': 'cpu'
            }
        else:
            try:
                device_count = torch.cuda.device_count()
                
                gpu_details = []
                for i in range(device_count):
                    # Get GPU memory
                    memory_allocated = torch.cuda.memory_allocated(i) / (1024**3)  # GB
                    memory_reserved = torch.cuda.memory_reserved(i) / (1024**3)  # GB
                    
                    # Get total memory
                    props = torch.cuda.get_device_properties(i)
                    total_memory = props.total_memory / (1024**3)  # GB
                    
                    utilization = (memory_allocated / total_memory) * 100 if total_memory > 0 else 0
                    
                    gpu_details.append({
                        'device_id': i,
                        'name': props.name,
                        'memory_allocated_gb': round(memory_allocated, 2),
                        'memory_reserved_gb': round(memory_reserved, 2),
                        'total_memory_gb': round(total_memory, 2),
                        'utilization_percent': round(utilization, 2)
                    })
                
                # Determine status based on utilization
                max_utilization = max(gpu['utilization_percent'] for gpu in gpu_details) if gpu_details else 0
                
                if max_utilization >= 95:
                    self.last_status = HealthStatus.UNHEALTHY
                elif max_utilization >= 85:
                    self.last_status = HealthStatus.DEGRADED
                else:
                    self.last_status = HealthStatus.HEALTHY
                
                self.last_details = {
                    'cuda_available': True,
                    'device_count': device_count,
                    'gpus': gpu_details
                }
            
            except Exception as e:
                self.last_status = HealthStatus.UNHEALTHY
                self.last_details = {
                    'cuda_available': True,
                    'error': str(e)
                }
        
        return {
            'name': self.name,
            'status': self.last_status.value,
            'details': self.last_details,
            'timestamp': self.last_check_time.isoformat()
        }


class APIHealthCheck(HealthCheck):
    """Check API responsiveness"""
    
    def __init__(self):
        super().__init__("api_health")
        self.response_time_threshold = 5.0  # seconds
    
    def check(self) -> Dict:
        """Check API health"""
        self.last_check_time = datetime.now()
        
        try:
            # Simple ping test
            start_time = time.time()
            
            # Simulate a lightweight operation
            time.sleep(0.01)
            
            response_time = time.time() - start_time
            
            if response_time > self.response_time_threshold:
                self.last_status = HealthStatus.DEGRADED
            else:
                self.last_status = HealthStatus.HEALTHY
            
            self.last_details = {
                'response_time_ms': round(response_time * 1000, 2),
                'threshold_ms': self.response_time_threshold * 1000
            }
        
        except Exception as e:
            self.last_status = HealthStatus.UNHEALTHY
            self.last_details = {'error': str(e)}
        
        return {
            'name': self.name,
            'status': self.last_status.value,
            'details': self.last_details,
            'timestamp': self.last_check_time.isoformat()
        }


class DependencyHealthCheck(HealthCheck):
    """Check external dependencies (Redis, etc.)"""
    
    def __init__(self, redis_client=None):
        super().__init__("dependencies")
        self.redis_client = redis_client
    
    def check(self) -> Dict:
        """Check dependencies"""
        self.last_check_time = datetime.now()
        
        dependencies = {}
        all_healthy = True
        
        # Check Redis
        if self.redis_client:
            try:
                self.redis_client.ping()
                dependencies['redis'] = {
                    'status': 'healthy',
                    'connected': True
                }
            except Exception as e:
                dependencies['redis'] = {
                    'status': 'unhealthy',
                    'connected': False,
                    'error': str(e)
                }
                all_healthy = False
        
        self.last_status = HealthStatus.HEALTHY if all_healthy else HealthStatus.UNHEALTHY
        self.last_details = dependencies
        
        return {
            'name': self.name,
            'status': self.last_status.value,
            'details': self.last_details,
            'timestamp': self.last_check_time.isoformat()
        }


class HealthMonitor:
    """Aggregate health monitor"""
    
    def __init__(self):
        self.checks: List[HealthCheck] = []
    
    def add_check(self, check: HealthCheck):
        """Add a health check"""
        self.checks.append(check)
    
    def run_all_checks(self) -> Dict:
        """Run all health checks"""
        results = []
        
        for check in self.checks:
            try:
                result = check.check()
                results.append(result)
            except Exception as e:
                logger.error(f"Health check '{check.name}' failed: {e}")
                results.append({
                    'name': check.name,
                    'status': HealthStatus.UNHEALTHY.value,
                    'details': {'error': str(e)},
                    'timestamp': datetime.now().isoformat()
                })
        
        # Determine overall status
        statuses = [r['status'] for r in results]
        
        if 'unhealthy' in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif 'degraded' in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        return {
            'overall_status': overall_status.value,
            'checks': results,
            'timestamp': datetime.now().isoformat()
        }
    
    async def run_all_checks_async(self) -> Dict:
        """Run all health checks asynchronously"""
        tasks = []
        
        for check in self.checks:
            # Wrap sync check in async
            task = asyncio.create_task(
                asyncio.to_thread(check.check)
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'name': self.checks[i].name,
                    'status': HealthStatus.UNHEALTHY.value,
                    'details': {'error': str(result)},
                    'timestamp': datetime.now().isoformat()
                })
            else:
                processed_results.append(result)
        
        # Determine overall status
        statuses = [r['status'] for r in processed_results]
        
        if 'unhealthy' in statuses:
            overall_status = HealthStatus.UNHEALTHY
        elif 'degraded' in statuses:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        return {
            'overall_status': overall_status.value,
            'checks': processed_results,
            'timestamp': datetime.now().isoformat()
        }


# Global health monitor instance
health_monitor = HealthMonitor()


def initialize_health_checks(translator=None, redis_client=None):
    """Initialize all health checks"""
    health_monitor.checks.clear()
    
    # Add checks
    health_monitor.add_check(SystemResourceCheck())
    health_monitor.add_check(GPUHealthCheck())
    health_monitor.add_check(APIHealthCheck())
    
    if translator:
        health_monitor.add_check(ModelHealthCheck(translator))
    
    if redis_client:
        health_monitor.add_check(DependencyHealthCheck(redis_client))
    
    logger.info(f"Initialized {len(health_monitor.checks)} health checks")
