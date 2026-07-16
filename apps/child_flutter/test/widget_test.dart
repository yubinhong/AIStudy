import 'dart:convert';
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';

import 'package:study_child/auth_client.dart';
import 'package:study_child/main.dart';
import 'package:study_child/privacy_sanitization_preview.dart';
import 'package:study_child/startup_transition.dart';

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
            return 'configured-session';
          },
          onLoggedIn: (baseUrl, token) {
            expect(baseUrl, 'http://192.168.1.4:8000');
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

  testWidgets('opens OCR confirmation from the learning desk', (tester) async {
    await tester.pumpWidget(
      StudyChildApp(
        loadChildren: () async => [
          {'display_name': '小禾', 'curriculum_version': 'math-demo-2026'},
        ],
      ),
    );
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('拍题'));
    await tester.tap(find.text('拍题'));
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

  testWidgets('opens the thinking practice from the learning desk', (
    tester,
  ) async {
    await tester.pumpWidget(
      StudyChildApp(
        loadChildren: () async => [
          {'display_name': '小禾', 'curriculum_version': 'math-demo-2026'},
        ],
      ),
    );
    await tester.pumpAndSettle();

    await tester.ensureVisible(find.text('继续学习'));
    await tester.tap(find.text('继续学习'));
    await tester.pumpAndSettle();

    expect(find.text('小禾的数学练习'), findsOneWidget);
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
}

class _MemoryChildAuthStore implements ChildAuthStore {
  String? serverBaseUrl;
  String? sessionToken = 'old-server-session';

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
}
