import 'dart:convert';
import 'dart:io';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

const defaultServerBaseUrl = String.fromEnvironment(
  'STUDY_API_URL',
  defaultValue: 'http://127.0.0.1:8000',
);

class ChildAuthException implements Exception {
  const ChildAuthException(this.message);

  final String message;

  @override
  String toString() => message;
}

String normalizeServerBaseUrl(String value) {
  final text = value.trim();
  final uri = Uri.tryParse(text);
  final scheme = uri?.scheme.toLowerCase();
  if (uri == null ||
      (scheme != 'http' && scheme != 'https') ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty ||
      uri.hasQuery ||
      uri.hasFragment ||
      (uri.path.isNotEmpty && uri.path != '/')) {
    throw const ChildAuthException('请输入完整的 HTTP 或 HTTPS 服务端地址。');
  }
  return text.endsWith('/') ? text.substring(0, text.length - 1) : text;
}

abstract interface class ChildAuthStore {
  Future<String?> readSessionToken();

  Future<String?> readServerBaseUrl();

  Future<String> saveServerBaseUrl(String value);

  Future<void> writeSessionToken(String token);

  Future<void> clearSessionToken();
}

class SecureChildAuthStore implements ChildAuthStore {
  const SecureChildAuthStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _sessionKey = 'study_session_token';
  static const _serverKey = 'study_server_base_url';
  final FlutterSecureStorage _storage;

  @override
  Future<String?> readSessionToken() => _storage.read(key: _sessionKey);

  @override
  Future<String?> readServerBaseUrl() => _storage.read(key: _serverKey);

  @override
  Future<String> saveServerBaseUrl(String value) async {
    final normalized = normalizeServerBaseUrl(value);
    final current = await readServerBaseUrl();
    if (current != normalized) {
      await clearSessionToken();
    }
    await _storage.write(key: _serverKey, value: normalized);
    return normalized;
  }

  @override
  Future<void> writeSessionToken(String token) =>
      _storage.write(key: _sessionKey, value: token);

  @override
  Future<void> clearSessionToken() => _storage.delete(key: _sessionKey);
}

class ChildAuthClient {
  ChildAuthClient({required String baseUrl})
    : baseUrl = normalizeServerBaseUrl(baseUrl);

  final String baseUrl;

  Future<String> login(String username, String password) async {
    final client = HttpClient();
    try {
      final request = await client.postUrl(Uri.parse('$baseUrl/auth/login'));
      request.headers.contentType = ContentType.json;
      request.write(
        jsonEncode({
          'username': username,
          'password': password,
          'client': 'flutter',
        }),
      );
      final response = await request.close();
      final body = jsonDecode(await response.transform(utf8.decoder).join());
      if (response.statusCode != HttpStatus.ok ||
          body is! Map ||
          body['access_token'] is! String) {
        throw const ChildAuthException('用户名或密码不正确。');
      }
      return body['access_token'] as String;
    } on ChildAuthException {
      rethrow;
    } on Object {
      throw const ChildAuthException('暂时无法连接学习服务。');
    } finally {
      client.close(force: true);
    }
  }
}
