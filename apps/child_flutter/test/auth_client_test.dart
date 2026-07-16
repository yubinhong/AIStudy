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
        ..write(jsonEncode({'access_token': 'configured-server-session'}));
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });

    final token = await ChildAuthClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
    ).login('child-a', 'child-password');

    expect(token, 'configured-server-session');
  });
}
