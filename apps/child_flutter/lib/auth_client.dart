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

class ChildSessionExpiredException extends ChildAuthException {
  const ChildSessionExpiredException() : super('登录已失效，请重新登录。');
}

class ChildLoginResult {
  const ChildLoginResult({
    required this.token,
    required this.mustChangePassword,
  });

  final String token;
  final bool mustChangePassword;
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

  Future<ChildLoginResult> login(String username, String password) async {
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
          body['access_token'] is! String ||
          body['account'] is! Map) {
        throw const ChildAuthException('用户名或密码不正确。');
      }
      final account = body['account'] as Map;
      if (account['role'] != 'child' || account['child_id'] is! String) {
        throw const ChildAuthException('请使用孩子账号登录。');
      }
      final mustChangePassword = account['must_change_password'];
      if (mustChangePassword is! bool) {
        throw const ChildAuthException('登录响应不完整，请联系家长。');
      }
      return ChildLoginResult(
        token: body['access_token'] as String,
        mustChangePassword: mustChangePassword,
      );
    } on ChildAuthException {
      rethrow;
    } on Object {
      throw const ChildAuthException('暂时无法连接学习服务。');
    } finally {
      client.close(force: true);
    }
  }

  Future<bool> mustChangePassword(String token) async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(Uri.parse('$baseUrl/auth/me'));
      request.headers.set('Authorization', 'Bearer $token');
      final response = await request.close();
      final body = jsonDecode(await response.transform(utf8.decoder).join());
      if (response.statusCode == HttpStatus.unauthorized) {
        throw const ChildSessionExpiredException();
      }
      if (response.statusCode != HttpStatus.ok || body is! Map) {
        throw const ChildAuthException('暂时无法读取登录状态。');
      }
      if (body['role'] != 'child' || body['child_id'] is! String) {
        throw const ChildSessionExpiredException();
      }
      final required = body['must_change_password'];
      if (required is! bool) {
        throw const ChildAuthException('登录状态响应不完整。');
      }
      return required;
    } on ChildAuthException {
      rethrow;
    } on Object {
      throw const ChildAuthException('暂时无法连接学习服务。');
    } finally {
      client.close(force: true);
    }
  }

  Future<String> changePassword({
    required String token,
    required String currentPassword,
    required String newPassword,
  }) async {
    final client = HttpClient();
    try {
      final request = await client.postUrl(
        Uri.parse('$baseUrl/auth/change-password'),
      );
      request.headers
        ..contentType = ContentType.json
        ..set('Authorization', 'Bearer $token');
      request.write(
        jsonEncode({
          'current_password': currentPassword,
          'new_password': newPassword,
        }),
      );
      final response = await request.close();
      final body = jsonDecode(await response.transform(utf8.decoder).join());
      if (response.statusCode != HttpStatus.ok ||
          body is! Map ||
          body['access_token'] is! String ||
          body['account'] is! Map ||
          (body['account'] as Map)['must_change_password'] != false) {
        throw const ChildAuthException('当前密码不正确，或新密码不符合要求。');
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
