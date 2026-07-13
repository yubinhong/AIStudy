import 'package:flutter_test/flutter_test.dart';
import 'package:study_child/offline_sync_queue.dart';

PendingSyncEvent event(String id) => PendingSyncEvent(
  eventId: id,
  idempotencyKey: 'offline-key-$id',
  payload: {'schema_version': 1, 'kind': 'record_attempt', 'event_id': id},
);

void main() {
  test('keeps unacknowledged events in FIFO order', () {
    final queue = OfflineSyncQueue()
      ..enqueue(event('event-1'))
      ..enqueue(event('event-2'));

    expect(queue.nextBatch().map((item) => item.eventId), [
      'event-1',
      'event-2',
    ]);

    queue.acknowledge(['event-1']);

    expect(queue.pending.map((item) => item.eventId), ['event-2']);
  });

  test('rejects duplicate event ids and keeps the pending queue intact', () {
    final queue = OfflineSyncQueue()..enqueue(event('event-1'));

    expect(() => queue.enqueue(event('event-1')), throwsArgumentError);
    expect(queue.pending.single.eventId, 'event-1');
  });

  test('limits batches to the contract maximum', () {
    final queue = OfflineSyncQueue()..enqueue(event('event-1'));

    expect(() => queue.nextBatch(maxEvents: 0), throwsArgumentError);
    expect(() => queue.nextBatch(maxEvents: 51), throwsArgumentError);
  });
}
