import 'dart:math';

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
      skill: 'poem',
      title: '春晓',
      prompt: '春眠不觉晓，下一句是？',
      options: ['处处闻啼鸟', '月落乌啼霜满天'],
      sourceLabel: '家庭教材',
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
    expect(response, {'choice': '处处闻啼鸟'});
    return const ChineseAttemptResult(
      correct: true,
      score: 1,
      maxScore: 1,
      feedbackTags: ['correct'],
    );
  }
}

class _GroupedPoemGateway extends _FakeChineseGateway {
  @override
  Future<List<ChineseContentItem>> loadContent() async => const [
    ChineseContentItem(
      id: 'poem-a-1',
      revision: 1,
      skill: 'poem',
      title: '春晓',
      prompt: '春眠不觉晓，下一句是？',
      options: ['处处闻啼鸟'],
      sourceLabel: '家庭教材',
    ),
    ChineseContentItem(
      id: 'poem-a-2',
      revision: 1,
      skill: 'poem',
      title: '春晓',
      prompt: '处处闻啼鸟，下一句是？',
      options: ['夜来风雨声'],
      sourceLabel: '家庭教材',
    ),
    ChineseContentItem(
      id: 'poem-a-3',
      revision: 1,
      skill: 'poem',
      title: '春晓',
      prompt: '夜来风雨声，下一句是？',
      options: ['花落知多少'],
      sourceLabel: '家庭教材',
    ),
    ChineseContentItem(
      id: 'poem-b-1',
      revision: 1,
      skill: 'poem',
      title: '静夜思',
      prompt: '床前明月光，下一句是？',
      options: ['疑是地上霜'],
      sourceLabel: '家庭教材',
    ),
    ChineseContentItem(
      id: 'poem-b-2',
      revision: 1,
      skill: 'poem',
      title: '静夜思',
      prompt: '疑是地上霜，下一句是？',
      options: ['举头望明月'],
      sourceLabel: '家庭教材',
    ),
  ];
}

class _EmptyPoemGateway extends _FakeChineseGateway {
  @override
  Future<List<ChineseContentItem>> loadContent() async => const [];
}

class _RefreshingPoemGateway extends _FakeChineseGateway {
  int loads = 0;

  @override
  Future<List<ChineseContentItem>> loadContent() async {
    loads += 1;
    if (loads == 1) {
      return const [
        ChineseContentItem(
          id: 'stale-rhyme',
          revision: 1,
          skill: 'poem',
          title: '剪窗花',
          prompt: '剪条鲤鱼摇尾巴，下一句是？',
          options: ['剪只小鸡叫喳喳'],
          sourceLabel: '家庭教材',
        ),
      ];
    }
    return const [
      ChineseContentItem(
        id: 'current-poem',
        revision: 1,
        skill: 'poem',
        title: '咏鹅',
        prompt: '鹅，鹅，鹅，下一句是？',
        options: ['曲项向天歌'],
        sourceLabel: '家庭教材',
      ),
    ];
  }
}

class _RevokedPoemGateway extends _RefreshingPoemGateway {
  @override
  Future<List<ChineseContentItem>> loadContent() async {
    loads += 1;
    if (loads == 1) {
      return const [
        ChineseContentItem(
          id: 'stale-rhyme',
          revision: 1,
          skill: 'poem',
          title: '剪窗花',
          prompt: '剪条鲤鱼摇尾巴，下一句是？',
          options: ['剪只小鸡叫喳喳'],
          sourceLabel: '家庭教材',
        ),
      ];
    }
    return const [];
  }
}

class _FixedRandom implements Random {
  const _FixedRandom();

  @override
  bool nextBool() => true;

  @override
  double nextDouble() => 0;

  @override
  int nextInt(int max) => max > 1 ? 1 : 0;
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

  testWidgets('Chinese poem spot check submits the selected next line', (
    tester,
  ) async {
    final gateway = _FakeChineseGateway();
    await tester.pumpWidget(
      MaterialApp(home: ChineseHomePage(gateway: gateway)),
    );
    await tester.pumpAndSettle();

    expect(find.text('看图写话'), findsOneWidget);
    await tester.tap(find.text('古诗抽查'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('处处闻啼鸟'));
    await tester.tap(find.text('提交回答'));
    await tester.pumpAndSettle();

    expect(gateway.submissions, 1);
    expect(find.text('回答正确，已加入后续复习。'), findsOneWidget);
  });

  testWidgets('poem spot check chooses a poem before choosing its question', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: ChineseHomePage(
          gateway: _GroupedPoemGateway(),
          poemRandom: const _FixedRandom(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('古诗抽查'));
    await tester.pumpAndSettle();

    expect(find.text('静夜思'), findsOneWidget);
    expect(find.text('疑是地上霜，下一句是？'), findsOneWidget);
    expect(find.text('春眠不觉晓，下一句是？'), findsNothing);
  });

  testWidgets('poem spot check refreshes stale content before opening', (
    tester,
  ) async {
    final gateway = _RefreshingPoemGateway();
    await tester.pumpWidget(
      MaterialApp(home: ChineseHomePage(gateway: gateway)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('古诗抽查'));
    await tester.pumpAndSettle();

    expect(gateway.loads, 2);
    expect(find.text('咏鹅'), findsOneWidget);
    expect(find.text('鹅，鹅，鹅，下一句是？'), findsOneWidget);
    expect(find.text('剪窗花'), findsNothing);
  });

  testWidgets('poem spot check does not open content revoked after page load', (
    tester,
  ) async {
    final gateway = _RevokedPoemGateway();
    await tester.pumpWidget(
      MaterialApp(home: ChineseHomePage(gateway: gateway)),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('古诗抽查'));
    await tester.pumpAndSettle();

    expect(gateway.loads, 2);
    expect(find.text('语文学习'), findsOneWidget);
    expect(find.text('当前没有可抽查的古诗，请稍后重试。'), findsOneWidget);
    expect(find.text('剪窗花'), findsNothing);
  });

  testWidgets(
    'Chinese home keeps poem entry visible before curriculum review',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(home: ChineseHomePage(gateway: _EmptyPoemGateway())),
      );
      await tester.pumpAndSettle();

      expect(find.text('看图写话'), findsOneWidget);
      expect(find.text('古诗抽查'), findsOneWidget);
      expect(find.text('家长上传并审核教材后开放'), findsOneWidget);
      expect(
        tester.widget<ListTile>(find.widgetWithText(ListTile, '古诗抽查')).enabled,
        isFalse,
      );
    },
  );

  testWidgets('due Chinese review opens the same content before submitting', (
    tester,
  ) async {
    final gateway = _FakeChineseGateway()
      ..dueReviews = [
        ChineseReviewItem(
          contentId: '10000000-0000-0000-0000-000000000002',
          contentRevision: 1,
          dueAt: DateTime.utc(2026, 8, 16),
          skill: 'poem',
        ),
      ];
    await tester.pumpWidget(
      MaterialApp(home: ChineseHomePage(gateway: gateway)),
    );
    await tester.pumpAndSettle();

    expect(find.text('到期复习'), findsOneWidget);
    await tester.tap(find.text('春晓').first);
    await tester.pumpAndSettle();

    expect(find.text('提交回答'), findsOneWidget);
    expect(gateway.submissions, 0);
  });
}
