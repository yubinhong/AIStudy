import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_child/english_practice.dart';

class _FakeEnglishGateway implements EnglishPracticeGateway {
  _FakeEnglishGateway({required this.settings});

  final EnglishPracticeSettings settings;

  @override
  Future<EnglishPracticeSettings> loadSettings() async => settings;

  @override
  Future<List<EnglishScenario>> loadScenarios() async => const [
    EnglishScenario(
      id: 'greetings',
      title: '打招呼',
      description: '练习问候',
      targetMinutes: 5,
    ),
    EnglishScenario(
      id: 'school',
      title: '校园交流',
      description: '练习课堂表达',
      targetMinutes: 7,
    ),
    EnglishScenario(
      id: 'food_order',
      title: '点餐',
      description: '练习礼貌点餐',
      targetMinutes: 8,
    ),
  ];

  @override
  Future<List<EnglishSessionSummary>> loadRecentSessions() async => const [];

  @override
  Future<EnglishSessionSummary> startSession(String scenarioId) {
    throw UnimplementedError();
  }

  @override
  Future<WebSocket> connectSession(String sessionId) {
    throw UnimplementedError();
  }

  @override
  Future<void> completeSession(
    String sessionId, {
    required bool interrupted,
  }) async {}
}

void main() {
  testWidgets('always shows math and locked English subject cards', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SubjectSelectionScreen(
            displayName: '小禾',
            mathBuilder: (_) => const Text('数学学习桌'),
            englishGateway: _FakeEnglishGateway(
              settings: const EnglishPracticeSettings(
                enabled: false,
                level: 'pre_a1',
                providerAvailable: false,
                dailyLimitMinutes: 10,
              ),
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('数学'), findsOneWidget);
    expect(find.text('英语'), findsOneWidget);
    expect(find.text('口语服务尚未开放'), findsOneWidget);
    expect(find.byIcon(Icons.lock_outline), findsOneWidget);
  });

  testWidgets('math route remains independent and English lists three scenes', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(1024, 768);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final gateway = _FakeEnglishGateway(
      settings: const EnglishPracticeSettings(
        enabled: true,
        level: 'a1',
        providerAvailable: true,
        dailyLimitMinutes: 10,
      ),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SubjectSelectionScreen(
            displayName: '小禾',
            mathBuilder: (_) => const Scaffold(body: Text('数学学习桌')),
            englishGateway: gateway,
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('数学'));
    await tester.pumpAndSettle();
    expect(find.text('数学学习桌'), findsOneWidget);
    Navigator.of(tester.element(find.text('数学学习桌'))).pop();
    await tester.pumpAndSettle();

    await tester.tap(find.text('英语'));
    await tester.pumpAndSettle();
    expect(find.text('打招呼'), findsOneWidget);
    expect(find.text('校园交流'), findsOneWidget);
    expect(find.text('点餐'), findsOneWidget);
    expect(find.text('还没有练习记录'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
