import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
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

  test(
    'SQLite queue survives reopen and keeps failed events retryable',
    () async {
      sqfliteFfiInit();
      final directory = await Directory.systemTemp.createTemp(
        'study-offline-sync-',
      );
      addTearDown(() => directory.delete(recursive: true));
      final path = '${directory.path}/queue.db';
      var queue = await SqliteOfflineSyncQueue.open(
        scopeKey: 'server-a:household-a:child-a',
        factory: databaseFactoryFfi,
        databasePath: path,
      );
      await queue.enqueue(event('event-1'));
      await queue.recordRetry('event-1', 'network_unavailable');
      await queue.close();

      queue = await SqliteOfflineSyncQueue.open(
        scopeKey: 'server-a:household-a:child-a',
        factory: databaseFactoryFfi,
        databasePath: path,
      );
      final restored = await queue.nextBatch();
      expect(restored.single.eventId, 'event-1');
      expect(restored.single.attemptCount, 1);
      expect(restored.single.lastErrorCode, 'network_unavailable');

      await queue.acknowledge(['event-1']);
      expect(await queue.pending, isEmpty);
      await queue.close();
    },
  );

  test('SQLite queue isolates account scopes in the same database', () async {
    sqfliteFfiInit();
    final directory = await Directory.systemTemp.createTemp(
      'study-offline-scope-',
    );
    addTearDown(() => directory.delete(recursive: true));
    final path = '${directory.path}/queue.db';
    final first = await SqliteOfflineSyncQueue.open(
      scopeKey: 'server-a:household-a:child-a',
      factory: databaseFactoryFfi,
      databasePath: path,
    );
    await first.enqueue(event('same-event'));
    await first.close();
    final second = await SqliteOfflineSyncQueue.open(
      scopeKey: 'server-a:household-a:child-b',
      factory: databaseFactoryFfi,
      databasePath: path,
    );
    expect(await second.pending, isEmpty);
    await second.enqueue(event('same-event'));
    expect((await second.pending).single.eventId, 'same-event');
    await second.close();
  });
}
