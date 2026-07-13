import 'package:flutter_test/flutter_test.dart';

import 'package:study_child/main.dart';

void main() {
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
}
