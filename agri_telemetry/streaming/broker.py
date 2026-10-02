"""
Event-Stream Broker Abstractions for Agri Telemetry & Forecasting Platform.
Provides both a zero-dependency deterministic InMemoryStreamBroker and an optional RedisStreamBroker.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Dict, List, Optional, Any, Callable
import json
import uuid


@dataclass
class StreamMessage:
    """Standardized envelope for stream messages."""
    message_id: str
    stream_name: str
    payload: Dict[str, Any]
    event_time: str
    ingestion_time: str
    correlation_id: str


class EventStreamBroker(ABC):
    """Abstract Base Class for event-stream message brokers."""

    @abstractmethod
    def publish(self, stream_name: str, payload: Dict[str, Any], event_time: Optional[str] = None, correlation_id: Optional[str] = None) -> str:
        """Publishes a payload to a named stream and returns message ID."""
        pass

    @abstractmethod
    def consume(self, stream_name: str, consumer_group: str = "default_group", batch_size: int = 10) -> List[StreamMessage]:
        """Consumes a batch of messages from a stream."""
        pass

    @abstractmethod
    def acknowledge(self, stream_name: str, consumer_group: str, message_id: str) -> bool:
        """Acknowledges successful processing of a message."""
        pass

    @abstractmethod
    def reset(self, stream_name: Optional[str] = None) -> None:
        """Resets stream buffers and consumer offsets."""
        pass


class InMemoryStreamBroker(EventStreamBroker):
    """
    Thread-safe in-memory stream broker with topic queues, consumer offsets, and replay support.
    Ideal for local testing, deterministic verification, and lightweight microservices.
    """

    def __init__(self):
        self._streams: Dict[str, List[StreamMessage]] = {}
        self._consumer_offsets: Dict[str, Dict[str, int]] = {}  # stream -> group -> offset
        self._lock = Lock()

    def publish(
        self,
        stream_name: str,
        payload: Dict[str, Any],
        event_time: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        with self._lock:
            if stream_name not in self._streams:
                self._streams[stream_name] = []

            now_iso = datetime.now(timezone.utc).isoformat()
            msg_id = f"{int(datetime.now(timezone.utc).timestamp() * 1000)}-{len(self._streams[stream_name])}"
            c_id = correlation_id or str(uuid.uuid4())
            e_time = event_time or now_iso

            msg = StreamMessage(
                message_id=msg_id,
                stream_name=stream_name,
                payload=payload,
                event_time=e_time,
                ingestion_time=now_iso,
                correlation_id=c_id,
            )
            self._streams[stream_name].append(msg)
            return msg_id

    def consume(
        self,
        stream_name: str,
        consumer_group: str = "default_group",
        batch_size: int = 10,
    ) -> List[StreamMessage]:
        with self._lock:
            if stream_name not in self._streams:
                return []

            if stream_name not in self._consumer_offsets:
                self._consumer_offsets[stream_name] = {}
            offset = self._consumer_offsets[stream_name].get(consumer_group, 0)

            all_msgs = self._streams[stream_name]
            batch = all_msgs[offset : offset + batch_size]
            self._consumer_offsets[stream_name][consumer_group] = offset + len(batch)
            return batch

    def acknowledge(self, stream_name: str, consumer_group: str, message_id: str) -> bool:
        # In-memory broker automatically advances offset upon consume
        return True

    def replay(self, stream_name: str, from_index: int = 0, count: Optional[int] = None) -> List[StreamMessage]:
        """Replays messages from a given index without modifying consumer group offsets."""
        with self._lock:
            if stream_name not in self._streams:
                return []
            msgs = self._streams[stream_name][from_index:]
            return msgs[:count] if count is not None else msgs

    def get_stream_length(self, stream_name: str) -> int:
        with self._lock:
            return len(self._streams.get(stream_name, []))

    def reset(self, stream_name: Optional[str] = None) -> None:
        with self._lock:
            if stream_name:
                self._streams.pop(stream_name, None)
                self._consumer_offsets.pop(stream_name, None)
            else:
                self._streams.clear()
                self._consumer_offsets.clear()


class RedisStreamBroker(EventStreamBroker):
    """
    Operational Redis Streams broker for distributed microservice deployments.
    Uses XADD, XREADGROUP, and XACK for reliable stream processing.
    """

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self._client = None

    def _get_client(self):
        if self._client is None:
            import redis
            self._client = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=True)
        return self._client

    def publish(
        self,
        stream_name: str,
        payload: Dict[str, Any],
        event_time: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> str:
        client = self._get_client()
        now_iso = datetime.now(timezone.utc).isoformat()
        c_id = correlation_id or str(uuid.uuid4())
        e_time = event_time or now_iso

        msg_data = {
            "payload_json": json.dumps(payload),
            "event_time": e_time,
            "ingestion_time": now_iso,
            "correlation_id": c_id,
        }
        msg_id = client.xadd(stream_name, msg_data)
        return str(msg_id)

    def consume(
        self,
        stream_name: str,
        consumer_group: str = "default_group",
        batch_size: int = 10,
    ) -> List[StreamMessage]:
        client = self._get_client()
        # Ensure group exists
        try:
            client.xgroup_create(stream_name, consumer_group, id="0", mkstream=True)
        except Exception:
            pass  # Group already exists

        entries = client.xreadgroup(
            groupname=consumer_group,
            consumername="worker_1",
            streams={stream_name: ">"},
            count=batch_size,
        )
        results: List[StreamMessage] = []
        if not entries:
            return results

        for s_name, msg_list in entries:
            for m_id, fields in msg_list:
                payload = json.loads(fields.get("payload_json", "{}"))
                results.append(
                    StreamMessage(
                        message_id=str(m_id),
                        stream_name=s_name,
                        payload=payload,
                        event_time=fields.get("event_time", ""),
                        ingestion_time=fields.get("ingestion_time", ""),
                        correlation_id=fields.get("correlation_id", ""),
                    )
                )
        return results

    def acknowledge(self, stream_name: str, consumer_group: str, message_id: str) -> bool:
        client = self._get_client()
        ack_count = client.xack(stream_name, consumer_group, message_id)
        return ack_count > 0

    def reset(self, stream_name: Optional[str] = None) -> None:
        client = self._get_client()
        if stream_name:
            client.delete(stream_name)
        else:
            client.flushdb()
