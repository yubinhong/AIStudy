import 'dart:convert';
import 'dart:async';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

import 'package:study_child/auth_client.dart';
import 'package:study_child/capture_api_client.dart';
import 'package:study_child/main.dart';
import 'package:study_child/privacy_sanitization_preview.dart';
import 'package:study_child/startup_transition.dart';
import 'package:study_child/task_progress_store.dart';

class _FullSolutionCaptureClient extends CaptureApiClient {
  _FullSolutionCaptureClient()
    : super(
        baseUrl: 'http://localhost:8000',
        householdId: '00000000-0000-0000-0000-000000000001',
        childId: '00000000-0000-0000-0000-000000000101',
        authorizationToken: 'test-session',
      );

  @override
  Future<Map<String, dynamic>> createTutorHint({
    required String verifiedQuestionId,
    required int level,
    String mode = 'guided_practice',
    String? answerState,
    bool evidenceConfirmed = false,
  }) async {
    return <String, dynamic>{
      'prompt': '先找出题目给出的条件。',
      'solution_steps': <String>['列出算式', '完成计算'],
      'direct_answer': '42',
      'verification': '把答案代回题意检查。',
    };
  }
}

class _ReviewCloseoutCaptureClient extends CaptureApiClient {
  _ReviewCloseoutCaptureClient()
    : super(
        baseUrl: 'http://localhost:8000',
        householdId: '00000000-0000-0000-0000-000000000001',
        childId: '00000000-0000-0000-0000-000000000101',
        authorizationToken: 'test-session',
      );

  String? completionOutcome;

  @override
  Future<Map<String, dynamic>> recordAttempt({
    required String answerSummary,
    required String answerState,
    required bool evidenceConfirmed,
    int? nextExerciseIndex,
  }) async => <String, dynamic>{};

  @override
  Future<Map<String, dynamic>> completeCurrentSession({
    required String outcome,
  }) async {
    completionOutcome = outcome;
    return {'outcome': outcome, 'mistake': <String, dynamic>{}};
  }
}

class _IntermediateTaskCaptureClient extends CaptureApiClient {
  _IntermediateTaskCaptureClient()
    : super(
        baseUrl: 'http://localhost:8000',
        householdId: '00000000-0000-0000-0000-000000000001',
        childId: '00000000-0000-0000-0000-000000000101',
        authorizationToken: 'test-session',
      );

  var attempts = 0;
  var completions = 0;
  var preparedNextExercise = false;

  @override
  Future<Map<String, dynamic>> recordAttempt({
    required String answerSummary,
    required String answerState,
    required bool evidenceConfirmed,
    int? nextExerciseIndex,
  }) async {
    attempts += 1;
    return <String, dynamic>{};
  }

  @override
  void prepareNextTaskExercise() {
    preparedNextExercise = true;
  }

  @override
  Future<Map<String, dynamic>> completeCurrentSession({
    required String outcome,
  }) async {
    completions += 1;
    return <String, dynamic>{'outcome': outcome};
  }
}

class _CurriculumTaskClient extends CaptureApiClient {
  _CurriculumTaskClient({
    this.multiExercise = false,
    this.serverNextExerciseIndex,
  }) : super(
         baseUrl: 'http://localhost:8000',
         householdId: '00000000-0000-0000-0000-000000000001',
         childId: '00000000-0000-0000-0000-000000000101',
         authorizationToken: 'test-session',
       );

  final bool multiExercise;
  final int? serverNextExerciseIndex;

  int taskListCalls = 0;
  bool taskSessionPrepared = false;
  bool taskSkipped = false;

  @override
  String? get activeSessionId => 'task-session';

  @override
  int? get activeNextExerciseIndex => serverNextExerciseIndex;

  @override
  Future<void> prepareTaskSession(Map<String, dynamic> task) async {
    taskSessionPrepared = true;
  }

  @override
  Future<void> skipTask(Map<String, dynamic> task) async {
    taskSkipped = true;
  }

  @override
  Future<List<Map<String, dynamic>>> listTasks() async {
    taskListCalls += 1;
    final today = DateTime.now().toIso8601String().substring(0, 10);
    return [
      {
        'id': '00000000-0000-0000-0000-000000000501',
        'title': '位置关系练习',
        'status': 'assigned',
        'scheduled_for': today,
        'exercises': [
          {
            'source_type': 'curriculum',
            'source_title': '位置',
            'source_page': 14,
            'snapshot_id': '00000000-0000-0000-0000-000000000201',
            'question_text': '把铅笔放在书本的下面。',
            'visual_description': '原页展示一本书和一支铅笔。',
            'requires_visual_context': true,
          },
          if (multiExercise)
            {
              'source_type': 'curriculum',
              'source_title': '位置',
              'source_page': 15,
              'snapshot_id': '00000000-0000-0000-0000-000000000201',
              'question_text': '把橡皮放在铅笔的右边。',
              'visual_description': '原页展示一块橡皮和一支铅笔。',
              'requires_visual_context': true,
            },
        ],
      },
    ];
  }
}

void main() {
  testWidgets('configures and persists the server before password login', (
    tester,
  ) async {
    final store = _MemoryChildAuthStore();
    String? usedBaseUrl;
    String? savedToken;
    await tester.pumpWidget(
      MaterialApp(
        home: ChildLoginScreen(
          initialServerBaseUrl: defaultServerBaseUrl,
          store: store,
          loginAction: (baseUrl, username, password) async {
            usedBaseUrl = baseUrl;
            expect(username, 'child-a');
            expect(password, 'child-password');
            return const ChildLoginResult(
              token: 'configured-session',
              mustChangePassword: false,
              householdId: '00000000-0000-0000-0000-000000000001',
            );
          },
          healthAction: (_) async {},
          onLoggedIn:
              (baseUrl, token, mustChangePassword, username, householdId) {
                expect(baseUrl, 'http://192.168.1.4:8000');
                expect(mustChangePassword, isFalse);
                expect(username, 'child-a');
                savedToken = token;
              },
        ),
      ),
    );

    await tester.enterText(
      find.byKey(const ValueKey('server-base-url')),
      'http://192.168.1.4:8000/',
    );
    await tester.enterText(find.bySemanticsLabel('用户名'), 'child-a');
    await tester.enterText(find.bySemanticsLabel('密码'), 'child-password');
    await tester.tap(find.widgetWithText(FilledButton, '登录'));
    await tester.pumpAndSettle();

    expect(usedBaseUrl, 'http://192.168.1.4:8000');
    expect(store.serverBaseUrl, usedBaseUrl);
    expect(store.sessionToken, 'configured-session');
    expect(savedToken, 'configured-session');
  });

  testWidgets('login form remains scrollable on a compact viewport', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 320);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        home: ChildLoginScreen(
          initialServerBaseUrl: defaultServerBaseUrl,
          store: _MemoryChildAuthStore(),
          onLoggedIn: (_, _, _, _, _) {},
          healthAction: (_) async {},
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('登录学习桌'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('shows the configured service health on the login form', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ChildLoginScreen(
          initialServerBaseUrl: 'http://192.168.1.4:8000',
          store: _MemoryChildAuthStore(),
          onLoggedIn: (_, _, _, _, _) {},
          healthAction: (baseUrl) async {
            expect(baseUrl, 'http://192.168.1.4:8000');
          },
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('学习服务已连接'), findsOneWidget);
    expect(find.text('重新检测'), findsOneWidget);
  });

  testWidgets('restores a pending session into the first password screen', (
    tester,
  ) async {
    final store = _MemoryChildAuthStore(
      serverBaseUrl: 'http://192.168.1.4:8000',
      sessionToken: 'pending-session',
    );
    await tester.pumpWidget(
      StudyChildApp(
        authStore: store,
        sessionStatusAction: (baseUrl, token) async {
          expect(baseUrl, 'http://192.168.1.4:8000');
          expect(token, 'pending-session');
          return const ChildSessionInfo(
            username: 'child-a',
            mustChangePassword: true,
            householdId: '00000000-0000-0000-0000-000000000001',
          );
        },
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('先设置自己的密码'), findsOneWidget);
    expect(find.text('API 尚未连接'), findsNothing);
  });

  testWidgets('changes the initial password and stores the rotated session', (
    tester,
  ) async {
    final store = _MemoryChildAuthStore(sessionToken: 'pending-session');
    String? rotatedToken;
    await tester.pumpWidget(
      MaterialApp(
        home: ChildPasswordChangeScreen(
          baseUrl: 'http://192.168.1.4:8000',
          token: 'pending-session',
          store: store,
          changeAction: (baseUrl, token, currentPassword, newPassword) async {
            expect(baseUrl, 'http://192.168.1.4:8000');
            expect(token, 'pending-session');
            expect(currentPassword, 'initial-password');
            expect(newPassword, 'new-child-password');
            return 'rotated-session';
          },
          onChanged: (token) => rotatedToken = token,
          onCancel: () {},
        ),
      ),
    );

    await tester.enterText(find.bySemanticsLabel('当前初始密码'), 'initial-password');
    await tester.enterText(find.bySemanticsLabel('新密码'), 'new-child-password');
    await tester.enterText(
      find.bySemanticsLabel('再次输入新密码'),
      'new-child-password',
    );
    await tester.tap(find.text('保存并进入学习桌'));
    await tester.pumpAndSettle();

    expect(rotatedToken, 'rotated-session');
    expect(store.sessionToken, 'rotated-session');
  });

  testWidgets('shows a finite startup transition while the profile loads', (
    tester,
  ) async {
    final children = Completer<List<Map<String, dynamic>>>();

    await tester.pumpWidget(StudyChildApp(loadChildren: () => children.future));
    await tester.pump();

    expect(find.byKey(const ValueKey('startup-transition')), findsOneWidget);
    expect(find.text('正在准备今天的学习桌…'), findsOneWidget);

    children.complete([
      {'display_name': 'Synthetic Child A', 'curriculum_version': 'math-demo'},
    ]);
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('startup-transition')), findsNothing);
    expect(find.textContaining('Synthetic Child A'), findsOneWidget);
  });

  testWidgets('skips the startup transition when reduced motion is enabled', (
    tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: MediaQuery(
          data: MediaQueryData(disableAnimations: true),
          child: StartupTransition(child: Text('学习桌已准备好')),
        ),
      ),
    );
    await tester.pump();

    expect(find.byKey(const ValueKey('startup-transition')), findsNothing);
    expect(find.text('学习桌已准备好'), findsOneWidget);
  });

  testWidgets('renders a shared child profile', (tester) async {
    await tester.pumpWidget(
      StudyChildApp(
        loadChildren: () async => [
          {
            'display_name': 'Synthetic Child A',
            'curriculum_version': 'math-demo-2026',
          },
        ],
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('Synthetic Child A'), findsOneWidget);
  });

  testWidgets('reloads the subject home when switching back to an account', (
    tester,
  ) async {
    var activeUsername = 'child-a';
    late StateSetter updateHost;

    await tester.pumpWidget(
      MaterialApp(
        home: StatefulBuilder(
          builder: (context, setState) {
            updateHost = setState;
            return ChildProfileScreen(
              authorizationToken: 'session-$activeUsername',
              username: activeUsername,
              loadChildren: () async => [
                {
                  'id': '00000000-0000-0000-0000-000000000101',
                  'display_name': activeUsername,
                  'curriculum_version': 'math-demo-2026',
                },
              ],
            );
          },
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('child-a，今天想学什么？'), findsOneWidget);

    updateHost(() => activeUsername = 'child-b');
    await tester.pumpAndSettle();
    expect(find.text('child-b，今天想学什么？'), findsOneWidget);

    updateHost(() => activeUsername = 'child-a');
    await tester.pumpAndSettle();
    expect(find.text('child-a，今天想学什么？'), findsOneWidget);
  });

  testWidgets('compact subject home and math desk fit a portrait phone width', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      StudyChildApp(
        loadChildren: () async => [
          {'display_name': '小汤圆', 'curriculum_version': 'math-demo-2026'},
        ],
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('数学'), findsOneWidget);
    expect(find.text('英语'), findsOneWidget);
    await tester.tap(find.text('数学'));
    await tester.pumpAndSettle();
    expect(find.text('错题讲解'), findsOneWidget);
    expect(find.text('今日任务'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('shows today task context and starts its specified exercise', (
    tester,
  ) async {
    final client = _CurriculumTaskClient();
    await tester.pumpWidget(
      MaterialApp(
        home: LearningDeskScreen(
          displayName: '小禾',
          curriculumVersion: 'math-demo-2026',
          captureClient: client,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('今日任务'), findsOneWidget);
    expect(find.text('位置关系练习'), findsOneWidget);
    expect(find.text('把铅笔放在书本的下面。'), findsOneWidget);
    expect(client.taskListCalls, 1);

    final startButton = find.widgetWithText(FilledButton, '开始任务');
    await tester.ensureVisible(startButton);
    await tester.tap(startButton);
    await tester.pumpAndSettle();

    expect(client.taskSessionPrepared, isTrue);
    expect(find.text('拍题'), findsOneWidget);
    expect(find.text('本次任务题目 · 位置 · 第 14 页'), findsOneWidget);
    expect(find.text('把铅笔放在书本的下面。'), findsOneWidget);
  });

  testWidgets('starts a multi-exercise task at the first exercise', (
    tester,
  ) async {
    final client = _CurriculumTaskClient(multiExercise: true);
    await tester.pumpWidget(
      MaterialApp(
        home: LearningDeskScreen(
          displayName: '小禾',
          curriculumVersion: 'math-demo-2026',
          captureClient: client,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('共 2 题'), findsOneWidget);
    final startButton = find.widgetWithText(FilledButton, '开始任务');
    await tester.ensureVisible(startButton);
    await tester.tap(startButton);
    await tester.pumpAndSettle();

    expect(find.textContaining('第 1 题，共 2 题'), findsOneWidget);
    expect(find.text('把铅笔放在书本的下面。'), findsOneWidget);
    expect(find.text('当前任务包含多道题，请让家长拆成单题后再开始。'), findsNothing);
  });

  testWidgets(
    'resumes a task at the persisted exercise after process restart',
    (tester) async {
      final client = _CurriculumTaskClient(multiExercise: true);
      final progress = MemoryTaskProgressStore();
      await progress.save(
        taskId: '00000000-0000-0000-0000-000000000501',
        sessionId: 'task-session',
        nextExerciseIndex: 1,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: LearningDeskScreen(
            displayName: '小禾',
            curriculumVersion: 'math-demo-2026',
            captureClient: client,
            taskProgressStore: progress,
          ),
        ),
      );
      await tester.pumpAndSettle();

      final startButton = find.widgetWithText(FilledButton, '开始任务');
      await tester.ensureVisible(startButton);
      await tester.tap(startButton);
      await tester.pumpAndSettle();

      expect(find.textContaining('第 2 题，共 2 题'), findsOneWidget);
      expect(find.text('把橡皮放在铅笔的右边。'), findsOneWidget);
    },
  );

  testWidgets('prefers server task progress when another device advanced it', (
    tester,
  ) async {
    final client = _CurriculumTaskClient(
      multiExercise: true,
      serverNextExerciseIndex: 1,
    );
    await tester.pumpWidget(
      MaterialApp(
        home: LearningDeskScreen(
          displayName: '小禾',
          curriculumVersion: 'math-demo-2026',
          captureClient: client,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final startButton = find.widgetWithText(FilledButton, '开始任务');
    await tester.ensureVisible(startButton);
    await tester.tap(startButton);
    await tester.pumpAndSettle();

    expect(find.textContaining('第 2 题，共 2 题'), findsOneWidget);
    expect(find.text('把橡皮放在铅笔的右边。'), findsOneWidget);
  });

  testWidgets('records skipping the current task', (tester) async {
    final client = _CurriculumTaskClient();
    await tester.pumpWidget(
      MaterialApp(
        home: LearningDeskScreen(
          displayName: '小禾',
          curriculumVersion: 'math-demo-2026',
          captureClient: client,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final skipButton = find.widgetWithText(TextButton, '稍后再做');
    await tester.ensureVisible(skipButton);
    await tester.tap(skipButton);
    await tester.pumpAndSettle();

    expect(client.taskSkipped, isTrue);
    expect(find.text('已跳过今天的任务，之后可以从家长安排中重新开始。'), findsOneWidget);
  });

  testWidgets('opens OCR confirmation from the learning desk', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: LearningDeskScreen(
          displayName: '小禾',
          username: 'xiaotangyuan',
          curriculumVersion: 'math-demo-2026',
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('错题讲解'));
    await tester.tap(find.text('错题讲解'));
    await tester.pumpAndSettle();

    expect(find.text('拍题'), findsOneWidget);
    await tester.tap(find.text('使用示例题目'));
    await tester.pumpAndSettle();

    expect(find.text('先确认题目'), findsOneWidget);
    expect(find.text('3 + 4 = ?'), findsOneWidget);

    final confirmButton = find.widgetWithText(FilledButton, '确认题目');
    await tester.ensureVisible(confirmButton);
    await tester.tap(confirmButton);
    await tester.pump();

    expect(find.text('题目已确认，可以开始学习。'), findsOneWidget);
  });

  testWidgets('renders the thinking practice', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: TutorHintScreen(displayName: 'xiaotangyuan')),
    );
    await tester.pumpAndSettle();

    expect(find.text('xiaotangyuan的数学练习'), findsOneWidget);
    expect(find.text('先想一想'), findsOneWidget);
    expect(find.text('我想到了'), findsOneWidget);

    await tester.ensureVisible(find.text('再给一点提示'));
    await tester.tap(find.text('再给一点提示'));
    await tester.pump();
    expect(find.textContaining('题目告诉了我们'), findsOneWidget);

    await tester.ensureVisible(find.text('我想到了'));
    await tester.tap(find.text('我想到了'));
    await tester.pump();
    expect(find.text('继续说下去'), findsOneWidget);
  });

  testWidgets('returns to the learning desk after the full solution is shown', (
    tester,
  ) async {
    final client = _FullSolutionCaptureClient();
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => TutorHintScreen(
                    verifiedQuestionId: 'verified-question',
                    captureClient: client,
                    answerState: 'blank',
                    evidenceConfirmed: true,
                  ),
                ),
              ),
              child: const Text('打开讲解'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('打开讲解'));
    await tester.pumpAndSettle();

    expect(find.text('完整解答'), findsOneWidget);
    expect(find.text('返回学习桌'), findsOneWidget);
    expect(find.text('查看完整解答'), findsNothing);

    final returnHome = find.text('返回学习桌');
    await tester.ensureVisible(returnHome);
    await tester.tap(returnHome);
    await tester.pumpAndSettle();
    expect(find.text('打开讲解'), findsOneWidget);
  });

  testWidgets('returns to the learning desk after completing a question', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const TutorHintScreen(),
                ),
              ),
              child: const Text('打开练习'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('打开练习'));
    await tester.pumpAndSettle();
    final understood = find.text('我想到了');
    await tester.ensureVisible(understood);
    await tester.tap(understood);
    await tester.pump();
    final complete = find.text('我会了，完成本题');
    await tester.ensureVisible(complete);
    await tester.tap(complete);
    await tester.pumpAndSettle();

    expect(find.text('本题已完成。'), findsOneWidget);
    final returnDesk = find.text('返回学习桌');
    await tester.ensureVisible(returnDesk);
    await tester.tap(returnDesk);
    await tester.pumpAndSettle();
    expect(find.text('打开练习'), findsOneWidget);
  });

  testWidgets(
    'adds a confirmed question to review and returns to the learning desk',
    (tester) async {
      final client = _ReviewCloseoutCaptureClient();
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: FilledButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => TutorHintScreen(
                      captureClient: client,
                      answerState: 'blank',
                      evidenceConfirmed: true,
                    ),
                  ),
                ),
                child: const Text('打开练习'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('打开练习'));
      await tester.pumpAndSettle();
      final understood = find.text('我想到了');
      await tester.ensureVisible(understood);
      await tester.tap(understood);
      await tester.pump();
      final needsReview = find.text('还没完全会，加入复习');
      await tester.ensureVisible(needsReview);
      await tester.tap(needsReview);
      await tester.pumpAndSettle();

      expect(client.completionOutcome, 'needs_review');
      expect(find.text('打开练习'), findsOneWidget);
      expect(find.text('已完成本题，并加入复习清单。'), findsNothing);
    },
  );

  testWidgets('keeps a task session open between exercises', (tester) async {
    final client = _IntermediateTaskCaptureClient();
    await tester.pumpWidget(
      MaterialApp(
        home: Builder(
          builder: (context) => Scaffold(
            body: FilledButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => TutorHintScreen(
                    captureClient: client,
                    verifiedQuestionId: 'verified-question',
                    answerState: 'worked',
                    evidenceConfirmed: true,
                    taskExerciseIndex: 0,
                    taskExerciseCount: 2,
                  ),
                ),
              ),
              child: const Text('打开任务题目'),
            ),
          ),
        ),
      ),
    );

    await tester.tap(find.text('打开任务题目'));
    await tester.pumpAndSettle();
    final understood = find.text('我想到了');
    await tester.ensureVisible(understood);
    await tester.tap(understood);
    await tester.pump();
    final complete = find.text('我会了，完成本题');
    await tester.ensureVisible(complete);
    await tester.tap(complete);
    await tester.pumpAndSettle();

    expect(client.attempts, 1);
    expect(client.preparedNextExercise, isTrue);
    expect(client.completions, 0);
    expect(find.text('打开任务题目'), findsOneWidget);
  });

  testWidgets(
    'shows local sanitization preview and returns only sanitized copy',
    (tester) async {
      SanitizedImageSelection? selection;
      final image = XFile.fromData(
        base64Decode(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
        ),
        name: 'synthetic.png',
        mimeType: 'image/png',
      );

      await tester.pumpWidget(
        MaterialApp(
          home: SanitizationPreviewScreen(
            image: image,
            onConfirmed: (value) => selection = value,
            renderer: (source, masks) async =>
                SanitizedImageSelection(bytes: source, sha256: '0' * 64),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      expect(find.text('先保护隐私，再识别题目'), findsOneWidget);
      expect(
        find.text('原图只留在本机。请检查脱敏区域；可在照片上拖动涂抹姓名、学校、电话和背景信息。'),
        findsOneWidget,
      );

      final confirmSanitization = find.text('确认脱敏并继续');
      await tester.ensureVisible(confirmSanitization);
      await tester.tap(confirmSanitization);
      await tester.pump();
      await tester.pump();
      expect(selection, isNotNull);
      expect(selection!.bytes, isNotEmpty);
      expect(selection!.sha256, hasLength(64));
    },
  );

  testWidgets('bounds the sanitized PNG before upload', (tester) async {
    final selection = await tester.runAsync(() async {
      final recorder = ui.PictureRecorder();
      final canvas = Canvas(recorder);
      canvas.drawRect(
        const Rect.fromLTWH(0, 0, 400, 300),
        Paint()..color = const Color(0xFFE5E1D8),
      );
      final picture = recorder.endRecording();
      final image = await picture.toImage(400, 300);
      final encoded = await image.toByteData(format: ui.ImageByteFormat.png);
      final result = await renderSanitizedImage(
        encoded!.buffer.asUint8List(),
        const [Rect.fromLTWH(0.1, 0.1, 0.2, 0.1)],
        maxDimensions: const [180, 150, 120],
      );
      image.dispose();
      picture.dispose();
      return result;
    });

    expect(selection!.bytes.length, lessThanOrEqualTo(maxSanitizedUploadBytes));
    expect(selection.pixelWidth, 180);
    expect(selection.pixelHeight, 135);
    expect(selection.maskCount, 1);
  });

  testWidgets('shows retry and retake actions after recognition failure', (
    tester,
  ) async {
    const receipt = CaptureUploadReceipt(
      captureId: '00000000-0000-0000-0000-000000000801',
      captureVersion: 2,
      mediaType: 'image/png',
      byteSize: 68,
      contentSha256:
          '0000000000000000000000000000000000000000000000000000000000000000',
      ocrJobId: '',
      ocrJobStatus: 'not_started',
      imageAnalysisJobId: '00000000-0000-0000-0000-000000000802',
      imageAnalysisStatus: 'queued',
    );
    await tester.pumpWidget(
      MaterialApp(
        home: OcrConfirmationScreen(
          imageBytes: Uint8List.fromList(
            base64Decode(
              'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
            ),
          ),
          uploadReceipt: receipt,
          captureClient: CaptureApiClient(
            baseUrl: 'http://127.0.0.1:1',
            householdId: 'household',
            childId: 'child',
            authorizationToken: 'test-session-token',
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('重新识别当前照片'), findsOneWidget);
    expect(find.text('重新拍题'), findsOneWidget);
  });

  testWidgets('uses a large scrollable multiline question editor', (
    tester,
  ) async {
    await tester.pumpWidget(const MaterialApp(home: OcrConfirmationScreen()));
    await tester.pumpAndSettle();

    final field = tester.widget<TextField>(find.byType(TextField));
    expect(field.expands, isTrue);
    expect(field.maxLines, isNull);
    expect(find.text('题目较长时可在框内上下拖动查看，确认前请逐字核对。'), findsOneWidget);
  });

  testWidgets('keeps upload progress visible until the upload finishes', (
    tester,
  ) async {
    final upload = Completer<CaptureUploadReceipt>();
    const receipt = CaptureUploadReceipt(
      captureId: '00000000-0000-0000-0000-000000000901',
      captureVersion: 1,
      mediaType: 'image/png',
      byteSize: 68,
      contentSha256:
          '0000000000000000000000000000000000000000000000000000000000000000',
      ocrJobId: '',
      ocrJobStatus: 'not_started',
      imageAnalysisJobId: '00000000-0000-0000-0000-000000000902',
      imageAnalysisStatus: 'queued',
    );
    await tester.pumpWidget(
      MaterialApp(
        home: CaptureUploadProgressScreen(
          imageBytes: Uint8List.fromList(
            base64Decode(
              'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
            ),
          ),
          sanitization: const {'safe_to_upload': true},
          captureClient: CaptureApiClient(
            baseUrl: 'http://127.0.0.1:1',
            householdId: 'household',
            childId: 'child',
            authorizationToken: 'test-session-token',
          ),
          uploadAction: () => upload.future,
        ),
      ),
    );
    await tester.pump();
    expect(find.text('正在处理题目照片'), findsOneWidget);
    expect(find.text('照片已完成脱敏，正在安全上传并启动识别……'), findsOneWidget);

    upload.complete(receipt);
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('ocr-confirmation')), findsOneWidget);
  });

  testWidgets('requires a first sentence before the detail step', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: PictureWritingGuideScreen(
          guideRecord: <String, dynamic>{
            'guide': <String, dynamic>{
              'scene_observations': <String>['画面里有一棵树。'],
              'focus_questions': <String>['谁在做什么？', '在哪里？'],
              'sentence_starters': <String>['早上，'],
              'detail_prompts': <String>['补充一个动作。'],
            },
          },
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('下一步'));
    await tester.pump();
    expect(find.text('先写一句，再进入下一步。'), findsOneWidget);
    expect(find.text('第 2 步，共 3 步'), findsOneWidget);

    await tester.enterText(find.byType(TextField), '小明在浇花。');
    await tester.tap(find.text('下一步'));
    await tester.pumpAndSettle();
    expect(find.text('补上细节'), findsOneWidget);
    expect(find.text('第 3 步，共 3 步'), findsOneWidget);
  });

  test('provides a generic safe fallback guide without image claims', () {
    final record = pictureWritingFallbackGuideRecord();
    final guide = record['guide']! as Map<String, dynamic>;
    expect(record['source'], 'local-observation-prompts');
    expect(record['needs_confirmation'], true);
    expect(guide['scene_observations'], isA<List<String>>());
    expect(guide['focus_questions'], isA<List<String>>());
    expect(guide.containsKey('detected_subject'), isFalse);
  });

  testWidgets('shows account switching and logout actions', (tester) async {
    final first = const ChildSavedAccount(
      username: 'child-a',
      serverBaseUrl: 'http://192.168.1.4:8000',
      sessionToken: 'session-a',
    );
    final second = const ChildSavedAccount(
      username: 'child-b',
      serverBaseUrl: 'http://192.168.1.4:8000',
      sessionToken: 'session-b',
    );
    final store = _MemoryChildAuthStore(savedAccounts: [first, second]);
    ChildSavedAccount? switched;
    var added = false;
    var loggedOut = false;
    Widget accountHost() => Builder(
      builder: (context) => Scaffold(
        body: Center(
          child: FilledButton(
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(
                builder: (_) => ChildAccountScreen(
                  store: store,
                  currentToken: first.sessionToken,
                  currentUsername: first.username,
                  onAddAccount: () async => added = true,
                  onLogout: () async => loggedOut = true,
                  onSwitchAccount: (account) async => switched = account,
                ),
              ),
            ),
            child: const Text('打开账号页'),
          ),
        ),
      ),
    );

    await tester.pumpWidget(MaterialApp(home: accountHost()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('打开账号页'));
    await tester.pumpAndSettle();
    expect(find.text('切换账号'), findsOneWidget);
    expect(find.text('child-a'), findsWidgets);
    await tester.tap(find.text('切换').first);
    await tester.pumpAndSettle();
    expect(switched?.username, 'child-b');

    await tester.tap(find.text('打开账号页'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('添加账号'));
    await tester.pumpAndSettle();
    expect(added, isTrue);

    await tester.tap(find.text('打开账号页'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('注销当前账号'));
    await tester.pumpAndSettle();
    expect(loggedOut, isTrue);
  });
}

class _MemoryChildAuthStore implements ChildAuthStore {
  _MemoryChildAuthStore({
    this.serverBaseUrl,
    this.sessionToken = 'old-server-session',
    List<ChildSavedAccount>? savedAccounts,
  }) : savedAccounts = savedAccounts ?? [];

  String? serverBaseUrl;
  String? sessionToken;
  List<ChildSavedAccount> savedAccounts;

  @override
  Future<void> clearSessionToken() async => sessionToken = null;

  @override
  Future<String?> readServerBaseUrl() async => serverBaseUrl;

  @override
  Future<String?> readSessionToken() async => sessionToken;

  @override
  Future<String> saveServerBaseUrl(String value) async {
    final normalized = normalizeServerBaseUrl(value);
    if (serverBaseUrl != normalized) await clearSessionToken();
    serverBaseUrl = normalized;
    return normalized;
  }

  @override
  Future<void> writeSessionToken(String token) async => sessionToken = token;

  @override
  Future<List<ChildSavedAccount>> readSavedAccounts() async => savedAccounts;

  @override
  Future<void> saveAccount(ChildSavedAccount account) async {
    final index = savedAccounts.indexWhere((item) => item.key == account.key);
    if (index == -1) {
      savedAccounts.add(account);
    } else {
      savedAccounts[index] = account;
    }
  }

  @override
  Future<void> removeAccount(ChildSavedAccount account) async {
    savedAccounts.removeWhere((item) => item.key == account.key);
  }
}
