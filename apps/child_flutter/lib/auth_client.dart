import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';

import 'package:flutter/foundation.dart';
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
    this.username,
  });

  final String token;
  final bool mustChangePassword;
  final String? username;
}

class ChildSavedAccount {
  const ChildSavedAccount({
    required this.username,
    required this.serverBaseUrl,
    required this.sessionToken,
  });

  final String username;
  final String serverBaseUrl;
  final String sessionToken;

  String get key => '$serverBaseUrl\n$username';

  Map<String, String> toJson() => {
    'username': username,
    'server_base_url': serverBaseUrl,
    'session_token': sessionToken,
  };

  static ChildSavedAccount? fromJson(Object? value) {
    if (value is! Map) return null;
    final username = value['username'];
    final serverBaseUrl = value['server_base_url'];
    final sessionToken = value['session_token'];
    if (username is! String ||
        username.trim().isEmpty ||
        serverBaseUrl is! String ||
        sessionToken is! String ||
        sessionToken.isEmpty) {
      return null;
    }
    try {
      return ChildSavedAccount(
        username: username.trim(),
        serverBaseUrl: normalizeServerBaseUrl(serverBaseUrl),
        sessionToken: sessionToken,
      );
    } on ChildAuthException {
      return null;
    }
  }
}

void logChildNetworkFailure({
  required String operation,
  required String baseUrl,
  required Object error,
  required StackTrace stackTrace,
}) {
  debugPrint(
    'study.child.network_failed operation=$operation base_url=$baseUrl '
    'error_type=${error.runtimeType} error=$error',
  );
  developer.log(
    'operation=$operation base_url=$baseUrl error_type=${error.runtimeType}',
    name: 'study.child.network_failed',
    error: error,
    stackTrace: stackTrace,
  );
}

String childNetworkFailureMessage(String baseUrl, Object error) {
  if (error is SocketException) {
    final code = error.osError?.errorCode;
    final reason = error.osError?.message ?? '网络不可达';
    return '无法连接 $baseUrl（网络错误${code == null ? '' : ' $code'}：$reason）。';
  }
  return '无法连接 $baseUrl（${error.runtimeType}）。';
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

  Future<List<ChildSavedAccount>> readSavedAccounts();

  Future<void> saveAccount(ChildSavedAccount account);

  Future<void> removeAccount(ChildSavedAccount account);
}

class SecureChildAuthStore implements ChildAuthStore {
  const SecureChildAuthStore({FlutterSecureStorage? storage})
    : _storage = storage ?? const FlutterSecureStorage();

  static const _sessionKey = 'study_session_token';
  static const _serverKey = 'study_server_base_url';
  static const _accountsKey = 'study_saved_child_accounts';
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

  @override
  Future<List<ChildSavedAccount>> readSavedAccounts() async {
    final raw = await _storage.read(key: _accountsKey);
    if (raw == null || raw.isEmpty) return [];
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! List) return [];
      return decoded
          .map(ChildSavedAccount.fromJson)
          .whereType<ChildSavedAccount>()
          .toList(growable: false);
    } on Object {
      return [];
    }
  }

  @override
  Future<void> saveAccount(ChildSavedAccount account) async {
    final accounts = [...await readSavedAccounts()];
    final index = accounts.indexWhere((item) => item.key == account.key);
    if (index == -1) {
      accounts.add(account);
    } else {
      accounts[index] = account;
    }
    await _storage.write(
      key: _accountsKey,
      value: jsonEncode(accounts.map((item) => item.toJson()).toList()),
    );
  }

  @override
  Future<void> removeAccount(ChildSavedAccount account) async {
    final accounts = (await readSavedAccounts())
        .where((item) => item.key != account.key)
        .toList(growable: false);
    await _storage.write(
      key: _accountsKey,
      value: jsonEncode(accounts.map((item) => item.toJson()).toList()),
    );
  }
}

class ChildAuthClient {
  ChildAuthClient({required String baseUrl})
    : baseUrl = normalizeServerBaseUrl(baseUrl);

  final String baseUrl;

  Future<void> checkHealth() async {
    final client = HttpClient()..connectionTimeout = const Duration(seconds: 8);
    try {
      final request = await client.getUrl(Uri.parse('$baseUrl/healthz'));
      final response = await request.close();
      await response.drain<void>();
      if (response.statusCode != HttpStatus.ok) {
        throw ChildAuthException('学习服务健康检查返回 HTTP ${response.statusCode}。');
      }
    } on ChildAuthException {
      rethrow;
    } on Object catch (error, stackTrace) {
      logChildNetworkFailure(
        operation: 'health_check',
        baseUrl: baseUrl,
        error: error,
        stackTrace: stackTrace,
      );
      throw ChildAuthException(childNetworkFailureMessage(baseUrl, error));
    } finally {
      client.close(force: true);
    }
  }

  Future<ChildLoginResult> login(String username, String password) async {
    final client = HttpClient();
    try {
      final request = await client.postUrl(Uri.parse('$baseUrl/auth/login'));
      request.headers.contentType = ContentType.json;
      request.add(
        utf8.encode(
          jsonEncode({
            'username': username,
            'password': password,
            'client': 'flutter',
          }),
        ),
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
        username: account['username'] is String
            ? (account['username'] as String).trim()
            : null,
      );
    } on ChildAuthException {
      rethrow;
    } on Object catch (error, stackTrace) {
      logChildNetworkFailure(
        operation: 'login',
        baseUrl: baseUrl,
        error: error,
        stackTrace: stackTrace,
      );
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
    } on Object catch (error, stackTrace) {
      logChildNetworkFailure(
        operation: 'session_status',
        baseUrl: baseUrl,
        error: error,
        stackTrace: stackTrace,
      );
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
      request.add(
        utf8.encode(
          jsonEncode({
            'current_password': currentPassword,
            'new_password': newPassword,
          }),
        ),
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
    } on Object catch (error, stackTrace) {
      logChildNetworkFailure(
        operation: 'change_password',
        baseUrl: baseUrl,
        error: error,
        stackTrace: stackTrace,
      );
      throw const ChildAuthException('暂时无法连接学习服务。');
    } finally {
      client.close(force: true);
    }
  }
}
