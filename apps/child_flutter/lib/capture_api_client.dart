import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:image_picker/image_picker.dart';

const maxCaptureBytes = 8 * 1000 * 1000;

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
    required this.sessionId,
    this.authorizationToken,
  }) : _baseUri = Uri.parse(baseUrl);

  final Uri _baseUri;
  final String householdId;
  final String childId;
  final String sessionId;
  final String? authorizationToken;

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

    final pending = await _postJson(
      _path('/households/$householdId/sessions/$sessionId/capture-uploads'),
      headers: {'Idempotency-Key': uploadKey},
      body: {
        'media_type': mediaType,
        'byte_size': bytes.length,
        'content_sha256': contentSha256,
      },
      acceptedStatuses: const {200, 201},
    );
    final pendingCapture = _map(pending['capture']);
    final captureId = _string(pendingCapture['id']);
    final captureVersion = _int(pendingCapture['version']);
    final uploadUrl = _string(pending['upload_url']);

    await _putSignedImage(Uri.parse(uploadUrl), mediaType, bytes);

    final confirmed = await _postJson(
      _path(
        '/households/$householdId/captures/$captureId/upload-confirmations',
      ),
      headers: {'Idempotency-Key': 'capture-confirm-$captureId'},
      body: {'expected_capture_version': captureVersion},
      acceptedStatuses: const {200, 201},
    );
    final confirmedCapture = _map(confirmed);
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
    final pending = await _postJson(
      _path('/households/$householdId/sessions/$sessionId/capture-uploads'),
      headers: {'Idempotency-Key': uploadKey},
      body: {
        'media_type': mediaType,
        'byte_size': bytes.length,
        'content_sha256': contentSha256,
      },
      acceptedStatuses: const {200, 201},
    );
    final pendingCapture = _map(pending['capture']);
    final captureId = _string(pendingCapture['id']);
    final captureVersion = _int(pendingCapture['version']);
    await _putSignedImage(
      Uri.parse(_string(pending['upload_url'])),
      mediaType,
      bytes,
    );
    final confirmed = await _postJson(
      _path(
        '/households/$householdId/captures/$captureId/upload-confirmations',
      ),
      headers: {'Idempotency-Key': 'capture-confirm-$captureId'},
      body: {'expected_capture_version': captureVersion},
      acceptedStatuses: const {200, 201},
    );
    final confirmedCapture = _map(confirmed);
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

  Uri _path(String path) => _baseUri.replace(path: path, query: null);

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

  void _setPrincipalHeaders(HttpHeaders headers) {
    final token = authorizationToken;
    if (token != null && token.isNotEmpty) {
      headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      return;
    }
    headers
      ..set('X-Demo-Household-Id', householdId)
      ..set('X-Demo-Role', 'child')
      ..set('X-Demo-Child-Id', childId);
  }

  Future<void> _putSignedImage(
    Uri uri,
    String mediaType,
    List<int> bytes,
  ) async {
    final client = HttpClient();
    try {
      final request = await client.putUrl(uri);
      request.headers
        ..set(HttpHeaders.contentTypeHeader, mediaType)
        ..contentLength = bytes.length;
      request.add(bytes);
      final response = await request.close();
      await response.drain<void>();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw CaptureApiException(
          '题目照片上传失败，请重试。',
          statusCode: response.statusCode,
        );
      }
    } on CaptureApiException {
      rethrow;
    } on SocketException {
      throw const CaptureApiException('无法连接图片存储，请检查设备网络。');
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

  static OcrMode? _ocrMode(Object? value) {
    if (value == 'text') return OcrMode.text;
    if (value == 'formula') return OcrMode.formula;
    return null;
  }
}
