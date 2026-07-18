import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:image_picker/image_picker.dart';

const maxCaptureBytes = 8 * 1000 * 1000;

String _newSessionNonce() {
  final random = Random.secure();
  final bytes = List<int>.generate(16, (_) => random.nextInt(256));
  return bytes.map((value) => value.toRadixString(16).padLeft(2, '0')).join();
}

enum OcrMode { text, formula }

class CaptureApiException implements Exception {
  const CaptureApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class CaptureUploadReceipt {
  const CaptureUploadReceipt({
    required this.captureId,
    required this.captureVersion,
    required this.mediaType,
    required this.byteSize,
    required this.contentSha256,
    required this.ocrJobId,
    required this.ocrJobStatus,
    this.ocrMode = OcrMode.text,
    this.imageAnalysisJobId,
    this.imageAnalysisStatus,
  });

  final String captureId;
  final int captureVersion;
  final String mediaType;
  final int byteSize;
  final String contentSha256;
  final String ocrJobId;
  final String ocrJobStatus;
  final OcrMode ocrMode;
  final String? imageAnalysisJobId;
  final String? imageAnalysisStatus;

  bool get hasRemoteOcr => ocrJobId.isNotEmpty;
}

class OcrJobSnapshot {
  const OcrJobSnapshot({
    required this.jobId,
    required this.captureId,
    required this.status,
    required this.attempt,
    required this.resultId,
    this.mode = OcrMode.text,
  });

  final String jobId;
  final String captureId;
  final String status;
  final int attempt;
  final String? resultId;
  final OcrMode mode;
}

class CaptureApiClient {
  CaptureApiClient({
    required String baseUrl,
    required this.householdId,
    required this.childId,
    this.sessionId,
    required this.authorizationToken,
  }) : _baseUri = Uri.parse(baseUrl),
       _resolvedSessionId = sessionId {
    if (authorizationToken.isEmpty) {
      throw ArgumentError.value(
        authorizationToken,
        'authorizationToken',
        'a password-login session is required',
      );
    }
  }

  final Uri _baseUri;
  final String householdId;
  final String childId;
  final String? sessionId;
  final String authorizationToken;
  String? _resolvedSessionId;
  String _captureSessionNonce = _newSessionNonce();

  Future<List<Map<String, dynamic>>> listTasks() =>
      _getJsonList(_path('/households/$householdId/tasks'));

  Future<List<Map<String, dynamic>>> listDueMistakes() => _getJsonList(
    _path('/households/$householdId/children/$childId/mistakes?due_only=true'),
  );

  Future<Map<String, dynamic>> reviewMistake(
    String mistakeId,
    String outcome, {
    String? idempotencyKey,
  }) async {
    if (!const {'correct', 'needs_review', 'skipped'}.contains(outcome)) {
      throw const CaptureApiException('复习结果不合法。');
    }
    return _postJson(
      _path(
        '/households/$householdId/children/$childId/mistakes/$mistakeId/review',
      ),
      headers: {
        'Idempotency-Key': idempotencyKey ?? 'review-$mistakeId-$outcome',
      },
      body: {'outcome': outcome},
      acceptedStatuses: const {200},
    );
  }

  Future<void> prepareTaskSession(Map<String, dynamic> task) async {
    final taskId = _string(task['id']);
    final status = _string(task['status']);
    if (status == 'in_progress') {
      try {
        final active = await _getJson(
          _path('/households/$householdId/tasks/$taskId/active-session'),
        );
        _resolvedSessionId = _string(active['id']);
        return;
      } on CaptureApiException catch (error) {
        if (error.statusCode != HttpStatus.notFound) rethrow;
      }
    }
    if (status != 'assigned') {
      throw const CaptureApiException('这个任务已经结束，请选择其他任务。');
    }
    final version = _int(task['version']);
    final session = await _postJson(
      _path('/households/$householdId/tasks/$taskId/sessions'),
      headers: {'Idempotency-Key': 'start-task-$taskId-v$version'},
      body: {'expected_task_version': version},
      acceptedStatuses: const {200, 201},
    );
    _resolvedSessionId = _string(session['id']);
  }

  Future<CaptureUploadReceipt> uploadAndEnqueue(
    XFile image, {
    OcrMode ocrMode = OcrMode.text,
  }) async {
    return uploadAndEnqueueBytes(await image.readAsBytes(), ocrMode: ocrMode);
  }

  Future<CaptureUploadReceipt> uploadAndEnqueueBytes(
    Uint8List bytes, {
    OcrMode ocrMode = OcrMode.text,
  }) async {
    if (bytes.isEmpty || bytes.length > maxCaptureBytes) {
      throw const CaptureApiException('题目照片大小不符合要求。');
    }
    final mediaType = _mediaTypeFor(bytes);
    final contentSha256 = sha256.convert(bytes).toString();
    final uploadKey = 'capture-upload-${contentSha256.substring(0, 32)}';
    final activeSessionId = await _ensureCaptureSession();

    final confirmedCapture = await _uploadCapture(
      activeSessionId,
      bytes,
      mediaType: mediaType,
      contentSha256: contentSha256,
      idempotencyKey: uploadKey,
    );
    final captureId = _string(confirmedCapture['id']);
    final confirmedVersion = _int(confirmedCapture['version']);

    final job = await _postJson(
      _path('/households/$householdId/captures/$captureId/ocr-jobs'),
      headers: {'Idempotency-Key': 'capture-ocr-$captureId'},
      body: ocrMode == OcrMode.text ? null : {'mode': 'formula'},
      acceptedStatuses: const {200, 202},
    );
    return CaptureUploadReceipt(
      captureId: captureId,
      captureVersion: confirmedVersion,
      mediaType: mediaType,
      byteSize: bytes.length,
      contentSha256: contentSha256,
      ocrJobId: _string(job['id']),
      ocrJobStatus: _string(job['status']),
      ocrMode: _ocrMode(job['mode']) ?? ocrMode,
    );
  }

  Future<CaptureUploadReceipt> uploadAndStartImageAnalysisBytes(
    Uint8List bytes, {
    required Map<String, dynamic> sanitization,
  }) async {
    if (bytes.isEmpty || bytes.length > maxCaptureBytes) {
      throw const CaptureApiException('题目照片大小不符合要求。');
    }
    final mediaType = _mediaTypeFor(bytes);
    final contentSha256 = sha256.convert(bytes).toString();
    final uploadKey = 'capture-upload-$contentSha256'.substring(0, 47);
    final activeSessionId = await _ensureCaptureSession();
    final confirmedCapture = await _uploadCapture(
      activeSessionId,
      bytes,
      mediaType: mediaType,
      contentSha256: contentSha256,
      idempotencyKey: uploadKey,
    );
    final captureId = _string(confirmedCapture['id']);
    final confirmedVersion = _int(confirmedCapture['version']);
    final job = await _postJson(
      _path('/households/$householdId/captures/$captureId/image-analysis-jobs'),
      headers: {'Idempotency-Key': 'image-analysis-$captureId'},
      body: {
        'expected_capture_version': confirmedVersion,
        'sanitization': {
          ...sanitization,
          'sanitized_derivative_sha256': contentSha256,
        },
        'user_confirmed': true,
      },
      acceptedStatuses: const {200, 202},
    );
    return CaptureUploadReceipt(
      captureId: captureId,
      captureVersion: confirmedVersion,
      mediaType: mediaType,
      byteSize: bytes.length,
      contentSha256: contentSha256,
      ocrJobId: '',
      ocrJobStatus: 'not_started',
      imageAnalysisJobId: _string(job['id']),
      imageAnalysisStatus: _string(job['status']),
    );
  }

  Future<Map<String, dynamic>> getImageAnalysisJob(
    CaptureUploadReceipt receipt,
  ) async {
    final jobId = receipt.imageAnalysisJobId;
    if (jobId == null || jobId.isEmpty) {
      throw const CaptureApiException('视觉识别任务不存在，请重新拍题。');
    }
    return _getJson(
      _path(
        '/households/$householdId/captures/${receipt.captureId}/image-analysis-jobs/$jobId',
      ),
    );
  }

  Future<Map<String, dynamic>> getQuestionExtraction(
    CaptureUploadReceipt receipt,
  ) async {
    final jobId = receipt.imageAnalysisJobId;
    if (jobId == null || jobId.isEmpty) {
      throw const CaptureApiException('视觉识别任务不存在，请重新拍题。');
    }
    return _getJson(
      _path(
        '/households/$householdId/captures/${receipt.captureId}/image-analysis-jobs/$jobId/extraction',
      ),
    );
  }

  Future<Map<String, dynamic>?> waitForQuestionExtraction(
    CaptureUploadReceipt receipt, {
    Duration timeout = const Duration(seconds: 60),
    Duration pollInterval = const Duration(seconds: 2),
  }) async {
    final deadline = DateTime.now().add(timeout);
    while (DateTime.now().isBefore(deadline)) {
      final job = await getImageAnalysisJob(receipt);
      final status = _string(job['status']);
      if (status == 'blocked') {
        final errorCode = job['error_code']?.toString();
        if (errorCode == 'provider_not_enabled') {
          throw const CaptureApiException('视觉识别服务尚未启用，请联系家长检查服务配置。');
        }
        throw const CaptureApiException('照片未通过安全检查，请重新裁剪或遮挡敏感信息。');
      }
      if (status == 'failed') {
        if (job['error_code'] == 'provider_http_413') {
          throw const CaptureApiException('照片数据过大，已停止识别；请重新拍摄并只保留题目区域。');
        }
        if (job['error_code'] == 'provider_http_402') {
          throw const CaptureApiException(
            '视觉识别服务当前不可用，请家长检查 NewAPI 余额或模型额度后重试。',
          );
        }
        if (job['error_code'] == 'provider_timeout' ||
            job['error_code'] == 'provider_network_error') {
          throw const CaptureApiException('视觉识别服务连接超时，请检查服务端网络后重试。');
        }
        throw const CaptureApiException('题目识别失败，请换一张更清晰的照片重试。');
      }
      if (status == 'succeeded') {
        return getQuestionExtraction(receipt);
      }
      await Future<void>.delayed(pollInterval);
    }
    return null;
  }

  Future<Map<String, dynamic>> verifyQuestionExtraction({
    required CaptureUploadReceipt receipt,
    required String questionText,
    required Map<String, dynamic> extraction,
  }) {
    final jobId = receipt.imageAnalysisJobId;
    if (jobId == null || jobId.isEmpty) {
      throw const CaptureApiException('视觉识别任务不存在，请重新拍题。');
    }
    return _postJson(
      _path(
        '/households/$householdId/captures/${receipt.captureId}/image-analysis-jobs/$jobId/extraction/verify',
      ),
      headers: {'Idempotency-Key': 'verify-question-$jobId'},
      body: {
        'expected_capture_version': receipt.captureVersion,
        'question_text': questionText,
        'options': _stringList(extraction['options']),
        'formulas': _stringList(extraction['formulas']),
        'has_diagram': extraction['has_diagram'] == true,
        'has_handwriting': extraction['has_handwriting'] == true,
        'answer_text': extraction['detected_answer']?.toString(),
      },
      acceptedStatuses: const {200, 201},
    );
  }

  Future<Map<String, dynamic>> createTutorHint({
    required String verifiedQuestionId,
    required int level,
  }) {
    if (verifiedQuestionId.isEmpty) {
      throw const CaptureApiException('已确认题目不存在，请重新拍题。');
    }
    if (level < 1 || level > 3) {
      throw const CaptureApiException('提示级别不正确。');
    }
    return _postJson(
      _path('/households/$householdId/tutor/hints'),
      headers: {'Idempotency-Key': 'tutor-hint-$verifiedQuestionId-$level'},
      body: {'verified_question_id': verifiedQuestionId, 'level': level},
      acceptedStatuses: const {200},
    );
  }

  Future<Map<String, dynamic>> completeCurrentSession({
    required String outcome,
  }) async {
    if (!const {'learned', 'needs_review', 'skipped'}.contains(outcome)) {
      throw const CaptureApiException('学习结果不正确。');
    }
    final activeSessionId = await _ensureCaptureSession();
    final completed = await _postJson(
      _path('/households/$householdId/sessions/$activeSessionId/completion'),
      headers: {
        'Idempotency-Key': 'complete-session-$activeSessionId-$outcome',
      },
      body: {'outcome': outcome},
      acceptedStatuses: const {200},
    );
    _resolvedSessionId = null;
    _captureSessionNonce = _newSessionNonce();
    return completed;
  }

  Future<OcrJobSnapshot> getOcrJob(CaptureUploadReceipt receipt) async {
    final payload = await _getJson(
      _path(
        '/households/$householdId/captures/${receipt.captureId}/ocr-jobs/${receipt.ocrJobId}',
      ),
    );
    return OcrJobSnapshot(
      jobId: _string(payload['id']),
      captureId: _string(payload['capture_id']),
      status: _string(payload['status']),
      attempt: _int(payload['attempt']),
      resultId: payload['result_id'] as String?,
      mode: _ocrMode(payload['mode']) ?? OcrMode.text,
    );
  }

  Future<Map<String, dynamic>> getOcrResult(
    String captureId,
    String resultId,
  ) async {
    return _getJson(
      _path(
        '/households/$householdId/captures/$captureId/ocr-results/$resultId',
      ),
    );
  }

  Future<Map<String, dynamic>?> waitForOcrResult(
    CaptureUploadReceipt receipt, {
    Duration timeout = const Duration(seconds: 30),
    Duration pollInterval = const Duration(seconds: 2),
  }) async {
    final deadline = DateTime.now().add(timeout);
    while (DateTime.now().isBefore(deadline)) {
      final job = await getOcrJob(receipt);
      if (job.status == 'failed') {
        throw const CaptureApiException('本地 OCR 处理失败，请稍后重试。');
      }
      if (job.status == 'succeeded' && job.resultId != null) {
        return getOcrResult(receipt.captureId, job.resultId!);
      }
      await Future<void>.delayed(pollInterval);
    }
    return null;
  }

  Future<Map<String, dynamic>> confirmOcrCandidate({
    required CaptureUploadReceipt receipt,
    required String resultId,
    required String candidateId,
  }) {
    return _postJson(
      _path(
        '/households/$householdId/captures/${receipt.captureId}/ocr-results/$resultId/confirmations',
      ),
      headers: {'Idempotency-Key': 'capture-candidate-$candidateId'},
      body: {
        'expected_capture_version': receipt.captureVersion,
        'candidate_id': candidateId,
      },
      acceptedStatuses: const {200, 201},
    );
  }

  Future<Map<String, dynamic>> correctCapture({
    required CaptureUploadReceipt receipt,
    required String correctedText,
  }) {
    return _postJson(
      _path(
        '/households/$householdId/captures/${receipt.captureId}/corrections',
      ),
      headers: {'Idempotency-Key': 'capture-correction-${receipt.captureId}'},
      body: {
        'expected_capture_version': receipt.captureVersion,
        'corrected_text': correctedText,
      },
      acceptedStatuses: const {200, 201},
    );
  }

  Future<String> _ensureCaptureSession() async {
    final existing = _resolvedSessionId;
    if (existing != null && existing.isNotEmpty) return existing;
    final session = await _postJson(
      _path('/households/$householdId/capture-sessions'),
      headers: {
        'Idempotency-Key': 'capture-session-$childId-$_captureSessionNonce',
      },
      body: null,
      acceptedStatuses: const {200, 201},
    );
    final resolved = _string(session['id']);
    _resolvedSessionId = resolved;
    return resolved;
  }

  Uri _path(String path) {
    final parsed = Uri.parse(path);
    return _baseUri.replace(
      path: parsed.path,
      queryParameters: parsed.queryParameters.isEmpty
          ? null
          : parsed.queryParameters,
    );
  }

  Future<Map<String, dynamic>> _postJson(
    Uri uri, {
    Map<String, String> headers = const {},
    Map<String, dynamic>? body,
    required Set<int> acceptedStatuses,
  }) async {
    final client = HttpClient();
    try {
      final request = await client.postUrl(uri);
      request.headers.set(HttpHeaders.contentTypeHeader, 'application/json');
      _setPrincipalHeaders(request.headers);
      headers.forEach(request.headers.set);
      if (body != null) request.write(jsonEncode(body));
      final response = await request.close();
      final payload = await response.transform(utf8.decoder).join();
      if (!acceptedStatuses.contains(response.statusCode)) {
        throw CaptureApiException(
          '题目照片暂时无法提交，请稍后再试。',
          statusCode: response.statusCode,
        );
      }
      final decoded = jsonDecode(payload);
      if (decoded is! Map) {
        throw const CaptureApiException('服务端返回了无法识别的结果。');
      }
      return Map<String, dynamic>.from(decoded);
    } on CaptureApiException {
      rethrow;
    } on SocketException {
      throw const CaptureApiException('无法连接学习服务，请检查设备网络。');
    } on FormatException {
      throw const CaptureApiException('服务端返回了无法识别的结果。');
    } finally {
      client.close(force: true);
    }
  }

  Future<Map<String, dynamic>> _getJson(Uri uri) async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(uri);
      _setPrincipalHeaders(request.headers);
      final response = await request.close();
      final payload = await response.transform(utf8.decoder).join();
      if (response.statusCode != HttpStatus.ok) {
        throw CaptureApiException(
          '暂时无法读取本地 OCR 状态。',
          statusCode: response.statusCode,
        );
      }
      final decoded = jsonDecode(payload);
      if (decoded is! Map) {
        throw const CaptureApiException('服务端返回了无法识别的结果。');
      }
      return Map<String, dynamic>.from(decoded);
    } on CaptureApiException {
      rethrow;
    } on SocketException {
      throw const CaptureApiException('无法连接学习服务，请检查设备网络。');
    } on FormatException {
      throw const CaptureApiException('服务端返回了无法识别的结果。');
    } finally {
      client.close(force: true);
    }
  }

  Future<List<Map<String, dynamic>>> _getJsonList(Uri uri) async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(uri);
      _setPrincipalHeaders(request.headers);
      final response = await request.close();
      final payload = await response.transform(utf8.decoder).join();
      if (response.statusCode != HttpStatus.ok) {
        throw CaptureApiException(
          '暂时无法读取学习任务。',
          statusCode: response.statusCode,
        );
      }
      final decoded = jsonDecode(payload);
      if (decoded is! List) {
        throw const CaptureApiException('服务端返回了无法识别的结果。');
      }
      return decoded
          .whereType<Map>()
          .map(Map<String, dynamic>.from)
          .toList(growable: false);
    } on CaptureApiException {
      rethrow;
    } on SocketException {
      throw const CaptureApiException('无法连接学习服务，请检查设备网络。');
    } on FormatException {
      throw const CaptureApiException('服务端返回了无法识别的结果。');
    } finally {
      client.close(force: true);
    }
  }

  void _setPrincipalHeaders(HttpHeaders headers) {
    headers.set(HttpHeaders.authorizationHeader, 'Bearer $authorizationToken');
  }

  Future<Map<String, dynamic>> _uploadCapture(
    String activeSessionId,
    Uint8List bytes, {
    required String mediaType,
    required String contentSha256,
    required String idempotencyKey,
  }) async {
    final client = HttpClient();
    try {
      final request = await client.postUrl(
        _path(
          '/households/$householdId/sessions/$activeSessionId/captures/upload',
        ),
      );
      _setPrincipalHeaders(request.headers);
      request.headers
        ..set(HttpHeaders.contentTypeHeader, 'application/octet-stream')
        ..set('X-Capture-Media-Type', mediaType)
        ..set('X-Capture-Byte-Size', bytes.length.toString())
        ..set('X-Capture-Content-SHA256', contentSha256)
        ..set('Idempotency-Key', idempotencyKey)
        ..contentLength = bytes.length;
      request.add(bytes);
      final response = await request.close();
      final payload = await response.transform(utf8.decoder).join();
      if (response.statusCode != HttpStatus.ok &&
          response.statusCode != HttpStatus.created) {
        if (response.statusCode == HttpStatus.unprocessableEntity) {
          throw const CaptureApiException('题目照片未通过服务端图片校验，请重新拍摄。');
        }
        throw CaptureApiException(
          '题目照片上传失败，请重试。',
          statusCode: response.statusCode,
        );
      }
      final decoded = jsonDecode(payload);
      return _map(decoded);
    } on CaptureApiException {
      rethrow;
    } on SocketException {
      throw const CaptureApiException('无法连接学习服务，请检查设备网络。');
    } on FormatException {
      throw const CaptureApiException('服务端返回了无法识别的结果。');
    } finally {
      client.close(force: true);
    }
  }

  static String _mediaTypeFor(List<int> bytes) {
    final isJpeg =
        bytes.length >= 3 &&
        bytes[0] == 0xff &&
        bytes[1] == 0xd8 &&
        bytes[2] == 0xff;
    final isPng =
        bytes.length >= 8 &&
        bytes[0] == 0x89 &&
        bytes[1] == 0x50 &&
        bytes[2] == 0x4e &&
        bytes[3] == 0x47 &&
        bytes[4] == 0x0d &&
        bytes[5] == 0x0a &&
        bytes[6] == 0x1a &&
        bytes[7] == 0x0a;
    if (isJpeg) return 'image/jpeg';
    if (isPng) return 'image/png';
    throw const CaptureApiException('只支持 JPEG 或 PNG 题目照片。');
  }

  static Map<String, dynamic> _map(Object? value) {
    if (value is Map) return Map<String, dynamic>.from(value);
    throw const CaptureApiException('服务端返回了无法识别的结果。');
  }

  static String _string(Object? value) {
    if (value is String && value.isNotEmpty) return value;
    throw const CaptureApiException('服务端返回了无法识别的结果。');
  }

  static int _int(Object? value) {
    if (value is int) return value;
    throw const CaptureApiException('服务端返回了无法识别的结果。');
  }

  static List<String> _stringList(Object? value) {
    if (value == null) return const <String>[];
    if (value is! List) {
      throw const CaptureApiException('服务端返回了无法识别的结果。');
    }
    return value.map((item) => item.toString()).toList(growable: false);
  }

  static OcrMode? _ocrMode(Object? value) {
    if (value == 'text') return OcrMode.text;
    if (value == 'formula') return OcrMode.formula;
    return null;
  }
}
