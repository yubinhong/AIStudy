/// In-memory boundary for the device's future SQLite-backed offline queue.
///
/// The queue keeps transport-neutral JSON instead of duplicating public Task,
/// Session or Attempt models. A later persistence adapter can store the same
/// envelope in SQLite without changing retry or acknowledgement semantics.
class PendingSyncEvent {
  PendingSyncEvent({
    required this.eventId,
    required this.idempotencyKey,
    required Map<String, Object?> payload,
  }) : payload = Map.unmodifiable(payload);

  final String eventId;
  final String idempotencyKey;
  final Map<String, Object?> payload;
}

class OfflineSyncQueue {
  final List<PendingSyncEvent> _events = [];

  List<PendingSyncEvent> get pending => List.unmodifiable(_events);

  void enqueue(PendingSyncEvent event) {
    if (_events.any((pending) => pending.eventId == event.eventId)) {
      throw ArgumentError.value(
        event.eventId,
        'eventId',
        'must be unique in the queue',
      );
    }
    _events.add(event);
  }

  List<PendingSyncEvent> nextBatch({int maxEvents = 50}) {
    if (maxEvents < 1 || maxEvents > 50) {
      throw ArgumentError.value(
        maxEvents,
        'maxEvents',
        'must be between 1 and 50',
      );
    }
    return List.unmodifiable(_events.take(maxEvents));
  }

  void acknowledge(Iterable<String> appliedOrReplayedEventIds) {
    final acknowledged = appliedOrReplayedEventIds.toSet();
    _events.removeWhere((event) => acknowledged.contains(event.eventId));
  }
}
