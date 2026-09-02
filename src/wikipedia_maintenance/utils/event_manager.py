"""
Gestionnaire d'événements pour l'observabilité du système.

Fournit un système centralisé pour émettre et diffuser des événements structurés
vers l'interface React via Server-Sent Events (SSE).
"""

import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
import queue

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Types d'événements standardisés pour l'observabilité."""
    AUTOMATION_STARTED = "AUTOMATION_STARTED"
    ARTICLE_DISCOVERED = "ARTICLE_DISCOVERED"
    ARTICLE_QUEUED = "ARTICLE_QUEUED"
    ANALYSIS_STARTED = "ANALYSIS_STARTED"
    ANALYSIS_COMPLETED = "ANALYSIS_COMPLETED"
    REPAIR_STARTED = "REPAIR_STARTED"
    REPAIR_COMPLETED = "REPAIR_COMPLETED"
    VALIDATION_STARTED = "VALIDATION_STARTED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    PUBLISHING_STARTED = "PUBLISHING_STARTED"
    PUBLISHED = "PUBLISHED"
    ERROR = "ERROR"
    AUTOMATION_PAUSED = "AUTOMATION_PAUSED"
    AUTOMATION_STOPPED = "AUTOMATION_STOPPED"
    KILL_SWITCH_ACTIVATED = "KILL_SWITCH_ACTIVATED"
    KILL_SWITCH_DEACTIVATED = "KILL_SWITCH_DEACTIVATED"


@dataclass
class Event:
    """Événement structuré pour l'observabilité."""
    event_type: str
    timestamp: str
    data: Dict[str, Any]
    session_id: Optional[str] = None
    
    def to_sse(self) -> str:
        """Convertit l'événement au format SSE (Server-Sent Events)."""
        event_dict = {
            "type": self.event_type,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "data": self.data
        }
        return f"data: {json.dumps(event_dict)}\n\n"


class EventManager:
    """
    Gestionnaire centralisé d'événements.
    
    Maintient une file d'événements et permet aux clients de s'abonner
    pour recevoir les événements en temps réel via SSE.
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        Initialise le gestionnaire d'événements.
        
        Args:
            max_queue_size: Taille maximale de la file d'événements
        """
        self._event_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()
    
    async def emit(self, event_type: EventType, data: Dict[str, Any], session_id: Optional[str] = None) -> None:
        """
        Émet un événement vers tous les abonnés.
        
        Args:
            event_type: Type de l'événement
            data: Données de l'événement
            session_id: Identifiant de session (optionnel)
        """
        event = Event(
            event_type=event_type.value,
            timestamp=datetime.now().isoformat(),
            data=data,
            session_id=session_id
        )
        
        # Ajouter à la file principale
        try:
            self._event_queue.put_nowait(event)
        except queue.Full:
            logger.warning("Event queue full, dropping oldest event")
            try:
                self._event_queue.get_nowait()
                self._event_queue.put_nowait(event)
            except queue.Empty:
                pass
        
        # Diffuser aux abonnés
        async with self._lock:
            for subscriber_queue in self._subscribers:
                try:
                    await subscriber_queue.put(event)
                except asyncio.QueueFull:
                    logger.warning("Subscriber queue full, dropping event")
        
        logger.debug(f"Emitted event: {event_type.value} - {data}")
    
    async def subscribe(self) -> asyncio.Queue:
        """
        S'abonne pour recevoir les événements en temps réel.
        
        Returns:
            Queue asyncio pour recevoir les événements
        """
        subscriber_queue = asyncio.Queue(maxsize=100)
        
        async with self._lock:
            self._subscribers.append(subscriber_queue)
        
        logger.info(f"New event subscriber (total: {len(self._subscribers)})")
        return subscriber_queue
    
    async def unsubscribe(self, subscriber_queue: asyncio.Queue) -> None:
        """
        Désabonne un client.
        
        Args:
            subscriber_queue: Queue du client à désabonner
        """
        async with self._lock:
            if subscriber_queue in self._subscribers:
                self._subscribers.remove(subscriber_queue)
                logger.info(f"Event subscriber removed (total: {len(self._subscribers)})")
    
    def get_recent_events(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère les événements récents.
        
        Args:
            limit: Nombre maximum d'événements à retourner
            
        Returns:
            Liste des événements récents
        """
        events = []
        temp_queue = queue.Queue()
        
        # Récupérer tous les événements de la file
        while not self._event_queue.empty():
            try:
                event = self._event_queue.get_nowait()
                events.append(asdict(event))
                temp_queue.put_nowait(event)
            except queue.Empty:
                break
        
        # Remettre les événements dans la file
        while not temp_queue.empty():
            try:
                self._event_queue.put_nowait(temp_queue.get_nowait())
            except queue.Full:
                break
        
        # Retourner les plus récents
        return events[-limit:] if events else []
    
    def clear(self) -> None:
        """Efface tous les événements de la file."""
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break
        logger.info("Event queue cleared")


# Instance globale du gestionnaire d'événements
_global_event_manager: Optional[EventManager] = None


def get_event_manager() -> EventManager:
    """
    Récupère l'instance globale du gestionnaire d'événements.
    
    Returns:
        Instance du EventManager
    """
    global _global_event_manager
    if _global_event_manager is None:
        _global_event_manager = EventManager()
    return _global_event_manager


def reset_event_manager() -> None:
    """Réinitialise le gestionnaire d'événements (utile pour les tests)."""
    global _global_event_manager
    _global_event_manager = None
