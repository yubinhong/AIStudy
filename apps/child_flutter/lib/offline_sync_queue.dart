import 'dart:convert';

import 'package:sqflite/sqflite.dart';

/// Transport-neutral event persisted without images, credentials or tokens.
class PendingSyncEvent {
  PendingSyncEvent({
    required this.eventId,
    required this.idempotencyKey,
    required Map<String, Object?> payload,
    this.attemptCount = 0,
    this.lastErrorCode,
  }) : payload = Map.unmodifiable(payload);

  final String eventId;
  final String idempotencyKey;
  final Map<String, Object?> payload;
  final int attemptCount;
  final String? lastErrorCode;
}

/// Fast in-memory reference implementation used by pure unit tests.
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

/// SQLite-backed queue that survives process termination and scopes rows to
/// one server/household/child identity without storing the login session.
class SqliteOfflineSyncQueue {
  SqliteOfflineSyncQueue._(this._database, this.scopeKey);

  static const _table = 'pending_sync_events';

  final Database _database;
  final String scopeKey;

  static Future<SqliteOfflineSyncQueue> open({
    required String scopeKey,
    DatabaseFactory? factory,
    String? databasePath,
  }) async {
    if (scopeKey.trim().isEmpty) {
      throw ArgumentError.value(scopeKey, 'scopeKey', 'must not be empty');
    }
    final selectedFactory = factory ?? databaseFactory;
    final path =
        databasePath ??
        '${await getDatabasesPath()}/study_child_offline_sync.db';
    final database = await selectedFactory.openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (database, _) async {
          await database.execute('''
            CREATE TABLE $_table (
              scope_key TEXT NOT NULL,
              event_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              payload_json TEXT NOT NULL,
              created_at_ms INTEGER NOT NULL,
              attempt_count INTEGER NOT NULL DEFAULT 0,
              last_error_code TEXT,
              PRIMARY KEY (scope_key, event_id)
            )
          ''');
          await database.execute('''
            CREATE INDEX ix_pending_sync_scope_created
            ON $_table (scope_key, created_at_ms, event_id)
          ''');
        },
      ),
    );
    return SqliteOfflineSyncQueue._(database, scopeKey.trim());
  }

  Future<List<PendingSyncEvent>> get pending => nextBatch(maxEvents: 50);

  Future<void> enqueue(PendingSyncEvent event) async {
    _validateEvent(event);
    try {
      await _database.insert(_table, {
        'scope_key': scopeKey,
        'event_id': event.eventId,
        'idempotency_key': event.idempotencyKey,
        'payload_json': jsonEncode(event.payload),
        'created_at_ms': DateTime.now().toUtc().millisecondsSinceEpoch,
        'attempt_count': event.attemptCount,
        'last_error_code': event.lastErrorCode,
      });
    } on DatabaseException catch (error) {
      if (error.isUniqueConstraintError()) {
        throw ArgumentError.value(
          event.eventId,
          'eventId',
          'must be unique within this account scope',
        );
      }
      rethrow;
    }
  }

  Future<List<PendingSyncEvent>> nextBatch({int maxEvents = 50}) async {
    _validateBatchSize(maxEvents);
    final rows = await _database.query(
      _table,
      where: 'scope_key = ?',
      whereArgs: [scopeKey],
      orderBy: 'created_at_ms ASC, event_id ASC',
      limit: maxEvents,
    );
    return List.unmodifiable(rows.map(_eventFromRow));
  }

  Future<void> acknowledge(Iterable<String> eventIds) async {
    final ids = eventIds.toSet();
    if (ids.isEmpty) return;
    await _database.transaction((transaction) async {
      for (final eventId in ids) {
        await transaction.delete(
          _table,
          where: 'scope_key = ? AND event_id = ?',
          whereArgs: [scopeKey, eventId],
        );
      }
    });
  }

  Future<void> recordRetry(String eventId, String errorCode) async {
    if (errorCode.isEmpty || errorCode.length > 80) {
      throw ArgumentError.value(
        errorCode,
        'errorCode',
        'must be 1-80 characters',
      );
    }
    await _database.rawUpdate(
      '''
      UPDATE $_table
      SET attempt_count = attempt_count + 1, last_error_code = ?
      WHERE scope_key = ? AND event_id = ?
      ''',
      [errorCode, scopeKey, eventId],
    );
  }

  Future<void> close() => _database.close();

  static PendingSyncEvent _eventFromRow(Map<String, Object?> row) {
    final decoded = jsonDecode(row['payload_json']! as String);
    if (decoded is! Map) {
      throw const FormatException(
        'offline event payload must be a JSON object',
      );
    }
    return PendingSyncEvent(
      eventId: row['event_id']! as String,
      idempotencyKey: row['idempotency_key']! as String,
      payload: Map<String, Object?>.from(decoded),
      attemptCount: row['attempt_count']! as int,
      lastErrorCode: row['last_error_code'] as String?,
    );
  }

  static void _validateEvent(PendingSyncEvent event) {
    if (event.eventId.isEmpty || event.idempotencyKey.length < 8) {
      throw ArgumentError('offline event identifiers are invalid');
    }
    try {
      jsonEncode(event.payload);
    } on JsonUnsupportedObjectError catch (error) {
      throw ArgumentError.value(event.payload, 'payload', error.toString());
    }
  }

  static void _validateBatchSize(int maxEvents) {
    if (maxEvents < 1 || maxEvents > 50) {
      throw ArgumentError.value(
        maxEvents,
        'maxEvents',
        'must be between 1 and 50',
      );
    }
  }
}
