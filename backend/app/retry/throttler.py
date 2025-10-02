"""Throttling adaptativo de chamadas por provedor."""
import asyncio
import time
from typing import Dict, Callable, Any
from collections import defaultdict, deque

from app.utils.logger import get_logger

logger = get_logger()


class AdaptiveThrottler:
    """
    Throttler adaptativo que limita chamadas simultâneas por provedor
    e ajusta automaticamente baseado em taxa de falhas.
    """
    
    def __init__(self, limits: Dict[str, int]):
        """
        Args:
            limits: Dicionário {provider: max_concurrent_calls}
        """
        self.semaphores = {
            provider: asyncio.Semaphore(limit)
            for provider, limit in limits.items()
        }
        
        # Estatísticas
        self.call_counts = defaultdict(int)
        self.failure_counts = defaultdict(int)
        self.success_counts = defaultdict(int)
        self.recent_calls = defaultdict(lambda: deque(maxlen=20))
        
        # Limites originais (para reset)
        self.original_limits = limits.copy()
        self.current_limits = limits.copy()
        
        # Lock para ajustes
        self._adjustment_lock = asyncio.Lock()
    
    async def call(
        self,
        provider: str,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Executa função com throttling.
        
        Args:
            provider: Nome do provedor
            func: Função async a executar
            *args, **kwargs: Argumentos para função
            
        Returns:
            Resultado da função
        """
        if provider not in self.semaphores:
            logger.warning(
                "provider_unknown",
                provider=provider,
                msg="Provedor não configurado, sem throttling"
            )
            return await func(*args, **kwargs)
        
        start = time.time()
        
        # Aguardar slot disponível
        available_slots = self.semaphores[provider]._value
        if available_slots == 0:
            logger.debug(
                "waiting_for_slot",
                provider=provider,
                current_limit=self.current_limits[provider]
            )
        
        async with self.semaphores[provider]:
            try:
                result = await func(*args, **kwargs)
                await self._record_success(provider, time.time() - start)
                return result
            
            except Exception as e:
                await self._record_failure(provider, e)
                raise
    
    async def _record_success(self, provider: str, latency: float):
        """Registra chamada bem-sucedida."""
        self.call_counts[provider] += 1
        self.success_counts[provider] += 1
        self.recent_calls[provider].append({
            "success": True,
            "timestamp": time.time(),
            "latency": latency
        })
        
        # Verificar se pode aumentar limite
        await self._maybe_increase_limit(provider)
    
    async def _record_failure(self, provider: str, error: Exception):
        """Registra falha."""
        self.call_counts[provider] += 1
        self.failure_counts[provider] += 1
        self.recent_calls[provider].append({
            "success": False,
            "timestamp": time.time(),
            "error": type(error).__name__
        })
        
        # Verificar se deve reduzir limite
        await self._maybe_decrease_limit(provider)
    
    async def _maybe_decrease_limit(self, provider: str):
        """Reduz limite se taxa de falha alta."""
        async with self._adjustment_lock:
            recent = list(self.recent_calls[provider])
            if len(recent) < 10:
                return
            
            # Taxa de falha nas últimas 20 chamadas
            failures = sum(1 for c in recent if not c["success"])
            failure_rate = failures / len(recent)
            
            if failure_rate > 0.3:  # >30% de falhas
                current = self.current_limits[provider]
                if current > 2:
                    new_limit = max(2, current - 1)
                    await self._adjust_limit(provider, new_limit)
                    logger.warning(
                        "throttle_decreased",
                        provider=provider,
                        old_limit=current,
                        new_limit=new_limit,
                        failure_rate=f"{failure_rate:.1%}"
                    )
    
    async def _maybe_increase_limit(self, provider: str):
        """Aumenta limite se taxa de sucesso alta e estável."""
        async with self._adjustment_lock:
            recent = list(self.recent_calls[provider])
            if len(recent) < 20:
                return
            
            # Taxa de sucesso nas últimas 20
            successes = sum(1 for c in recent if c["success"])
            success_rate = successes / len(recent)
            
            # Aumentar apenas se estável (95%+ sucesso)
            if success_rate > 0.95:
                current = self.current_limits[provider]
                original = self.original_limits[provider]
                
                if current < original:
                    new_limit = min(original, current + 1)
                    await self._adjust_limit(provider, new_limit)
                    logger.info(
                        "throttle_increased",
                        provider=provider,
                        old_limit=current,
                        new_limit=new_limit,
                        success_rate=f"{success_rate:.1%}"
                    )
    
    async def _adjust_limit(self, provider: str, new_limit: int):
        """Ajusta limite de um provedor."""
        # Criar novo semáforo com novo limite
        self.semaphores[provider] = asyncio.Semaphore(new_limit)
        self.current_limits[provider] = new_limit
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso."""
        stats = {}
        
        for provider in self.semaphores.keys():
            total = self.call_counts[provider]
            success = self.success_counts[provider]
            failure = self.failure_counts[provider]
            
            stats[provider] = {
                "total_calls": total,
                "successes": success,
                "failures": failure,
                "success_rate": success / total if total > 0 else 0,
                "current_limit": self.current_limits[provider],
                "original_limit": self.original_limits[provider],
                "available_slots": self.semaphores[provider]._value,
            }
        
        return stats
    
    def reset_stats(self):
        """Reseta estatísticas."""
        self.call_counts.clear()
        self.failure_counts.clear()
        self.success_counts.clear()
        self.recent_calls.clear()
        
        # Restaurar limites originais
        for provider, limit in self.original_limits.items():
            self.semaphores[provider] = asyncio.Semaphore(limit)
            self.current_limits[provider] = limit
        
        logger.info("throttler_reset", msg="Estatísticas e limites resetados")


# Instância global
_global_throttler: AdaptiveThrottler | None = None


def init_throttler(limits: Dict[str, int]):
    """Inicializa throttler global."""
    global _global_throttler
    _global_throttler = AdaptiveThrottler(limits)
    logger.info("throttler_initialized", limits=limits)


def get_throttler() -> AdaptiveThrottler:
    """Retorna throttler global."""
    if _global_throttler is None:
        raise RuntimeError("Throttler não inicializado. Chame init_throttler() primeiro.")
    return _global_throttler