import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';
import 'package:study_child/task_progress_store.dart';

void main() {
  test('memory progress store replaces and clears a task position', () async {
    final store = MemoryTaskProgressStore();

    await store.save(
      taskId: 'task-a',
      sessionId: 'session-a',
      nextExerciseIndex: 1,
    );
    expect((await store.load('task-a'))?.nextExerciseIndex, 1);

    await store.save(
      taskId: 'task-a',
      sessionId: 'session-a',
      nextExerciseIndex: 2,
    );
    expect((await store.load('task-a'))?.nextExerciseIndex, 2);

    await store.clear('task-a');
    expect(await store.load('task-a'), isNull);
  });

  test('SQLite progress survives reopen and isolates account scopes', () async {
    sqfliteFfiInit();
    final directory = await Directory.systemTemp.createTemp(
      'study-task-progress-',
    );
    addTearDown(() => directory.delete(recursive: true));
    final path = '${directory.path}/progress.db';

    var first = await SqliteTaskProgressStore.open(
      scopeKey: 'server-a:household-a:child-a',
      factory: databaseFactoryFfi,
      databasePath: path,
    );
    await first.save(
      taskId: 'task-a',
      sessionId: 'session-a',
      nextExerciseIndex: 2,
    );
    await first.close();

    first = await SqliteTaskProgressStore.open(
      scopeKey: 'server-a:household-a:child-a',
      factory: databaseFactoryFfi,
      databasePath: path,
    );
    expect((await first.load('task-a'))?.sessionId, 'session-a');
    expect((await first.load('task-a'))?.nextExerciseIndex, 2);
    await first.close();

    final other = await SqliteTaskProgressStore.open(
      scopeKey: 'server-a:household-a:child-b',
      factory: databaseFactoryFfi,
      databasePath: path,
    );
    expect(await other.load('task-a'), isNull);
    await other.close();
  });
}
