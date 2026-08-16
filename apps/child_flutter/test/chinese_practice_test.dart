import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_child/english_practice.dart';
import 'package:study_child/features/chinese/chinese_home_page.dart';
import 'package:study_child/features/chinese/data/chinese_api_client.dart';
import 'package:study_child/features/chinese/domain/chinese_models.dart';

class _FakeChineseGateway implements ChinesePracticeGateway {
  int submissions = 0;
  List<ChineseReviewItem> dueReviews = const [];

  @override
  Future<List<ChineseContentItem>> loadContent() async => const [
    ChineseContentItem(
      id: '10000000-0000-0000-0000-000000000002',
      revision: 1,
      skill: 'sentence',
      title: '句子排排队',
      prompt: '把词语排成一句通顺的话。',
      options: ['小树', '的', '的'],
      sourceLabel: '原创练习',
    ),
  ];

  @override
  Future<List<ChineseReviewItem>> loadDueReviews() async => dueReviews;

  @override
  Future<ChineseAttemptResult> submitAttempt(
    ChineseContentItem item,
    Map<String, dynamic> response,
    int elapsedMs,
  ) async {
    submissions += 1;
    expect(response, {
      'tokens': ['小树', '的', '的'],
    });
    return const ChineseAttemptResult(
      correct: true,
      score: 1,
      maxScore: 1,
      feedbackTags: ['correct'],
    );
  }
}

void main() {
  testWidgets('subject home shows Chinese only when enabled', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SubjectSelectionScreen(
            displayName: '小禾',
            enabledSubjects: const {'math', 'chinese'},
            mathBuilder: (_) => const Text('数学'),
            chineseBuilder: (_) => const Text('语文练习页'),
          ),
        ),
      ),
    );

    expect(find.text('语文'), findsOneWidget);
    await tester.tap(find.text('语文'));
    await tester.pumpAndSettle();
    expect(find.text('语文练习页'), findsOneWidget);
  });

  testWidgets('Chinese sentence practice submits ordered tokens', (
    tester,
  ) async {
    final gateway = _FakeChineseGateway();
    await tester.pumpWidget(
      MaterialApp(home: ChineseHomePage(gateway: gateway)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('句子排排队'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('小树'));
    await tester.pump();
    await tester.tap(find.text('的').first);
    await tester.pump();
    await tester.tap(find.text('的').first);
    await tester.tap(find.text('提交回答'));
    await tester.pumpAndSettle();

    expect(gateway.submissions, 1);
    expect(find.text('回答正确，已加入后续复习。'), findsOneWidget);
  });

  testWidgets('due Chinese review opens the same content before submitting', (
    tester,
  ) async {
    final gateway = _FakeChineseGateway()
      ..dueReviews = [
        ChineseReviewItem(
          contentId: '10000000-0000-0000-0000-000000000002',
          contentRevision: 1,
          dueAt: DateTime.utc(2026, 8, 16),
          skill: 'sentence',
        ),
      ];
    await tester.pumpWidget(
      MaterialApp(home: ChineseHomePage(gateway: gateway)),
    );
    await tester.pumpAndSettle();

    expect(find.text('到期复习'), findsOneWidget);
    await tester.tap(find.text('句子排排队').first);
    await tester.pumpAndSettle();

    expect(find.text('提交回答'), findsOneWidget);
    expect(gateway.submissions, 0);
  });
}
