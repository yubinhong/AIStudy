import 'package:sqflite/sqflite.dart';

/// The durable position of one task session on one child device.
///
/// This contains only task/session identifiers and a bounded exercise index;
/// it never stores question text, images, credentials, or session tokens.
class TaskExerciseProgress {
  const TaskExerciseProgress({
    required this.taskId,
    required this.sessionId,
    required this.nextExerciseIndex,
  });

  final String taskId;
  final String sessionId;
  final int nextExerciseIndex;
}

abstract interface class TaskProgressStore {
  Future<TaskExerciseProgress?> load(String taskId);

  Future<void> save({
    required String taskId,
    required String sessionId,
    required int nextExerciseIndex,
  });

  Future<void> clear(String taskId);

  Future<void> close();
}

/// Small in-memory implementation used by widget tests and previews.
class MemoryTaskProgressStore implements TaskProgressStore {
  final Map<String, TaskExerciseProgress> _progress = {};

  @override
  Future<TaskExerciseProgress?> load(String taskId) async => _progress[taskId];

  @override
  Future<void> save({
    required String taskId,
    required String sessionId,
    required int nextExerciseIndex,
  }) async {
    _validateProgress(taskId, sessionId, nextExerciseIndex);
    _progress[taskId] = TaskExerciseProgress(
      taskId: taskId,
      sessionId: sessionId,
      nextExerciseIndex: nextExerciseIndex,
    );
  }

  @override
  Future<void> clear(String taskId) async => _progress.remove(taskId);

  @override
  Future<void> close() async {}
}

/// SQLite-backed task position store. Rows are isolated by server/household/
/// child scope so switching accounts cannot resume another child's task.
class SqliteTaskProgressStore implements TaskProgressStore {
  SqliteTaskProgressStore._(this._database, this.scopeKey);

  static const _table = 'task_exercise_progress';

  final Database _database;
  final String scopeKey;

  static Future<SqliteTaskProgressStore> open({
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
        '${await getDatabasesPath()}/study_child_task_progress.db';
    final database = await selectedFactory.openDatabase(
      path,
      options: OpenDatabaseOptions(
        version: 1,
        onCreate: (database, _) async {
          await database.execute('''
            CREATE TABLE $_table (
              scope_key TEXT NOT NULL,
              task_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              next_exercise_index INTEGER NOT NULL,
              updated_at_ms INTEGER NOT NULL,
              PRIMARY KEY (scope_key, task_id)
            )
          ''');
          await database.execute('''
            CREATE INDEX ix_task_progress_scope_updated
            ON $_table (scope_key, updated_at_ms, task_id)
          ''');
        },
      ),
    );
    return SqliteTaskProgressStore._(database, scopeKey.trim());
  }

  @override
  Future<TaskExerciseProgress?> load(String taskId) async {
    if (taskId.trim().isEmpty) {
      throw ArgumentError.value(taskId, 'taskId', 'must not be empty');
    }
    final rows = await _database.query(
      _table,
      columns: const ['task_id', 'session_id', 'next_exercise_index'],
      where: 'scope_key = ? AND task_id = ?',
      whereArgs: [scopeKey, taskId],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    final row = rows.single;
    return TaskExerciseProgress(
      taskId: row['task_id']! as String,
      sessionId: row['session_id']! as String,
      nextExerciseIndex: row['next_exercise_index']! as int,
    );
  }

  @override
  Future<void> save({
    required String taskId,
    required String sessionId,
    required int nextExerciseIndex,
  }) async {
    _validateProgress(taskId, sessionId, nextExerciseIndex);
    await _database.insert(_table, {
      'scope_key': scopeKey,
      'task_id': taskId,
      'session_id': sessionId,
      'next_exercise_index': nextExerciseIndex,
      'updated_at_ms': DateTime.now().toUtc().millisecondsSinceEpoch,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  @override
  Future<void> clear(String taskId) async {
    if (taskId.trim().isEmpty) {
      throw ArgumentError.value(taskId, 'taskId', 'must not be empty');
    }
    await _database.delete(
      _table,
      where: 'scope_key = ? AND task_id = ?',
      whereArgs: [scopeKey, taskId],
    );
  }

  @override
  Future<void> close() => _database.close();
}

void _validateProgress(String taskId, String sessionId, int nextIndex) {
  if (taskId.trim().isEmpty || sessionId.trim().isEmpty) {
    throw ArgumentError('task and session identifiers are required');
  }
  if (nextIndex < 0 || nextIndex > 5) {
    throw ArgumentError.value(
      nextIndex,
      'nextExerciseIndex',
      'must be between 0 and 5',
    );
  }
}
