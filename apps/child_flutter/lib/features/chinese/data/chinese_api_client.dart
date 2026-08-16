import 'dart:convert';
import 'dart:io';

import '../domain/chinese_models.dart';

abstract interface class ChinesePracticeGateway {
  Future<List<ChineseContentItem>> loadContent();

  Future<List<ChineseReviewItem>> loadDueReviews();

  Future<ChineseAttemptResult> submitAttempt(
    ChineseContentItem item,
    Map<String, dynamic> response,
    int elapsedMs,
  );
}

class ChinesePracticeException implements Exception {
  const ChinesePracticeException(this.message);

  final String message;
}

class HttpChinesePracticeGateway implements ChinesePracticeGateway {
  HttpChinesePracticeGateway({
    required Uri baseUri,
    required this.householdId,
    required this.childId,
    required this.authorizationToken,
  }) : _baseUri = baseUri;

  final Uri _baseUri;
  final String householdId;
  final String childId;
  final String authorizationToken;
  int _nonce = 0;

  String get _root => '/households/$householdId/children/$childId/chinese';

  @override
  Future<List<ChineseContentItem>> loadContent() async {
    final payload = await _request('GET', '$_root/content');
    if (payload is! List) {
      throw const ChinesePracticeException('语文练习数据暂时不可用。');
    }
    return payload
        .whereType<Map>()
        .map(
          (item) =>
              ChineseContentItem.fromJson(Map<String, dynamic>.from(item)),
        )
        .toList(growable: false);
  }

  @override
  Future<List<ChineseReviewItem>> loadDueReviews() async {
    try {
      final payload = await _request('GET', '$_root/reviews?due_only=true');
      if (payload is! List) return const <ChineseReviewItem>[];
      return payload
          .whereType<Map>()
          .map(
            (item) =>
                ChineseReviewItem.fromJson(Map<String, dynamic>.from(item)),
          )
          .toList(growable: false);
    } on ChinesePracticeException {
      // Older servers do not expose the additive review route. Practice stays
      // available until API and app are released as a pair.
      return const <ChineseReviewItem>[];
    }
  }

  @override
  Future<ChineseAttemptResult> submitAttempt(
    ChineseContentItem item,
    Map<String, dynamic> response,
    int elapsedMs,
  ) async {
    final payload = await _request(
      'POST',
      '$_root/attempts',
      body: {
        'content_id': item.id,
        'content_revision': item.revision,
        'response': response,
        'elapsed_ms': elapsedMs,
      },
      idempotencyKey: _key(),
    );
    if (payload is! Map) {
      throw const ChinesePracticeException('语文评分结果暂时不可用。');
    }
    return ChineseAttemptResult.fromJson(Map<String, dynamic>.from(payload));
  }

  Future<dynamic> _request(
    String method,
    String path, {
    Map<String, dynamic>? body,
    String? idempotencyKey,
  }) async {
    final client = HttpClient();
    try {
      final request = method == 'POST'
          ? await client.postUrl(_baseUri.resolve(path))
          : await client.getUrl(_baseUri.resolve(path));
      request.headers.set('Authorization', 'Bearer $authorizationToken');
      if (idempotencyKey != null) {
        request.headers.set('Idempotency-Key', idempotencyKey);
      }
      if (body != null) {
        request.headers.contentType = ContentType.json;
        request.write(jsonEncode(body));
      }
      final response = await request.close();
      final text = await response.transform(utf8.decoder).join();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw const ChinesePracticeException('语文练习暂时不可用，请稍后重试。');
      }
      return jsonDecode(text);
    } on ChinesePracticeException {
      rethrow;
    } on Object {
      throw const ChinesePracticeException('无法连接学习服务，请检查网络。');
    } finally {
      client.close(force: true);
    }
  }

  String _key() {
    _nonce += 1;
    return 'chinese-attempt-$childId-${DateTime.now().microsecondsSinceEpoch}-$_nonce';
  }
}
