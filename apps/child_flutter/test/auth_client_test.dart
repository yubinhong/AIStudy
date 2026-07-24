import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:study_child/auth_client.dart';

void main() {
  test('normalizes a local HTTP server and rejects ambiguous URLs', () {
    expect(
      normalizeServerBaseUrl('  http://192.168.1.4:8000/  '),
      'http://192.168.1.4:8000',
    );
    expect(
      () => normalizeServerBaseUrl('https://user:pass@example.test'),
      throwsA(isA<ChildAuthException>()),
    );
    expect(
      () => normalizeServerBaseUrl('https://example.test/api'),
      throwsA(isA<ChildAuthException>()),
    );
    expect(
      () => normalizeServerBaseUrl('https://example.test?token=secret'),
      throwsA(isA<ChildAuthException>()),
    );
  });

  test('changing the configured server clears the previous session', () async {
    FlutterSecureStorage.setMockInitialValues({
      'study_server_base_url': 'http://192.168.1.4:8000',
      'study_session_token': 'old-server-session',
    });
    const store = SecureChildAuthStore();

    final saved = await store.saveServerBaseUrl('https://study.example.test/');

    expect(saved, 'https://study.example.test');
    expect(await store.readServerBaseUrl(), saved);
    expect(await store.readSessionToken(), isNull);
  });

  test('securely persists multiple child sessions without passwords', () async {
    FlutterSecureStorage.setMockInitialValues({});
    const store = SecureChildAuthStore();
    const first = ChildSavedAccount(
      username: 'child-a',
      serverBaseUrl: 'http://192.168.1.4:8000',
      sessionToken: 'session-a',
    );
    const second = ChildSavedAccount(
      username: 'child-b',
      serverBaseUrl: 'http://192.168.1.4:8000',
      sessionToken: 'session-b',
    );

    await store.saveAccount(first);
    await store.saveAccount(second);
    final accounts = await store.readSavedAccounts();

    expect(accounts.map((account) => account.username), ['child-a', 'child-b']);
    expect(
      accounts.every((account) => account.sessionToken.isNotEmpty),
      isTrue,
    );
    await store.removeAccount(first);
    expect((await store.readSavedAccounts()).single.username, 'child-b');
  });

  test('password login uses the configured server address', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final subscription = server.listen((request) async {
      expect(request.method, 'POST');
      expect(request.uri.path, '/auth/login');
      final body = jsonDecode(
        utf8.decode(await request.expand((chunk) => chunk).toList()),
      );
      expect(body['username'], 'child-a');
      expect(body['password'], 'child-password');
      expect(body['client'], 'flutter');
      request.response
        ..statusCode = HttpStatus.ok
        ..headers.contentType = ContentType.json
        ..write(
          jsonEncode({
            'access_token': 'configured-server-session',
            'account': {
              'role': 'child',
              'child_id': '00000000-0000-0000-0000-000000000101',
              'must_change_password': true,
            },
          }),
        );
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });

    final result = await ChildAuthClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
    ).login('child-a', 'child-password');

    expect(result.token, 'configured-server-session');
    expect(result.mustChangePassword, isTrue);
  });

  test('health check calls the configured server health endpoint', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final subscription = server.listen((request) async {
      expect(request.method, 'GET');
      expect(request.uri.path, '/healthz');
      request.response
        ..statusCode = HttpStatus.ok
        ..write('ok');
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });

    await ChildAuthClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
    ).checkHealth();
  });

  test(
    'reads pending password state and rotates the Flutter session',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      var requestCount = 0;
      final subscription = server.listen((request) async {
        requestCount += 1;
        expect(
          request.headers.value('authorization'),
          'Bearer pending-session',
        );
        request.response.headers.contentType = ContentType.json;
        if (request.uri.path == '/auth/me') {
          expect(request.method, 'GET');
          request.response
            ..statusCode = HttpStatus.ok
            ..write(
              jsonEncode({
                'role': 'child',
                'child_id': '00000000-0000-0000-0000-000000000101',
                'must_change_password': true,
              }),
            );
        } else {
          expect(request.uri.path, '/auth/change-password');
          expect(request.method, 'POST');
          final body = jsonDecode(
            utf8.decode(await request.expand((chunk) => chunk).toList()),
          );
          expect(body['current_password'], 'initial-password');
          expect(body['new_password'], 'new-child-password');
          request.response
            ..statusCode = HttpStatus.ok
            ..write(
              jsonEncode({
                'access_token': 'rotated-session',
                'account': {'must_change_password': false},
              }),
            );
        }
        await request.response.close();
      });
      addTearDown(() async {
        await subscription.cancel();
        await server.close(force: true);
      });
      final client = ChildAuthClient(
        baseUrl: 'http://${server.address.host}:${server.port}',
      );

      expect(await client.mustChangePassword('pending-session'), isTrue);
      final token = await client.changePassword(
        token: 'pending-session',
        currentPassword: 'initial-password',
        newPassword: 'new-child-password',
      );

      expect(token, 'rotated-session');
      expect(requestCount, 2);
    },
  );
}
