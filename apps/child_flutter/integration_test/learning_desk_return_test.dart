import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:study_child/english_practice.dart';
import 'package:study_child/main.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('returns to the learning desk on a physical iPad', (
    tester,
  ) async {
    await SystemChrome.setPreferredOrientations(const [
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    runApp(
      MaterialApp(
        home: Scaffold(
          body: SubjectSelectionScreen(
            displayName: '小禾',
            mathBuilder: (_) => const LearningDeskScreen(
              displayName: '小禾',
              curriculumVersion: '数学练习',
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('数学'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('错题讲解'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('使用示例题目'));
    await tester.pumpAndSettle();

    final confirmQuestion = find.widgetWithText(FilledButton, '确认题目');
    await tester.ensureVisible(confirmQuestion);
    await tester.tap(confirmQuestion);
    await tester.pump();
    final startLearning = find.widgetWithText(FilledButton, '开始学习');
    await tester.ensureVisible(startLearning);
    await tester.tap(startLearning);
    await tester.pumpAndSettle();

    final understood = find.text('我想到了');
    await tester.ensureVisible(understood);
    await tester.tap(understood);
    await tester.pump();
    final complete = find.text('我会了，完成本题');
    await tester.ensureVisible(complete);
    await tester.tap(complete);
    await tester.pumpAndSettle();
    final returnDesk = find.text('返回学习桌');
    await tester.ensureVisible(returnDesk);
    await tester.tap(returnDesk);
    await tester.pumpAndSettle();

    expect(find.text('小禾的学习桌'), findsOneWidget);
    expect(find.text('错题讲解'), findsOneWidget);
  });
}
