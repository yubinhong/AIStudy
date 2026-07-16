import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:study_child/capture_api_client.dart';

void main() {
  test('uploads, confirms, and enqueues an optional formula OCR job', () async {
    final requests = <String>[];
    final uploadedBytes = <int>[];
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final captureId = '00000000-0000-0000-0000-000000000301';
    final jobId = '00000000-0000-0000-0000-000000000302';
    final serverSubscription = server.listen((request) async {
      requests.add('${request.method} ${request.uri.path}');
      if (request.method == 'POST' &&
          request.uri.path.endsWith('/capture-uploads')) {
        final body = jsonDecode(
          utf8.decode(await request.expand((chunk) => chunk).toList()),
        );
        expect(body['media_type'], 'image/jpeg');
        expect(body['byte_size'], 3);
        expect(
          request.headers.value(HttpHeaders.authorizationHeader),
          'Bearer test-session-token',
        );
        final response = {
          'capture': _capture(captureId, version: 1),
          'upload_url':
              'http://${server.address.host}:${server.port}/signed/$captureId',
          'upload_expires_at': '2026-07-14T16:00:00Z',
        };
        request.response
          ..statusCode = HttpStatus.created
          ..headers.contentType = ContentType.json
          ..write(jsonEncode(response));
        await request.response.close();
        return;
      }
      if (request.method == 'PUT' && request.uri.path == '/signed/$captureId') {
        uploadedBytes.addAll(await request.expand((chunk) => chunk).toList());
        request.response.statusCode = HttpStatus.noContent;
        await request.response.close();
        return;
      }
      if (request.method == 'POST' &&
          request.uri.path.endsWith('/upload-confirmations')) {
        final body = jsonDecode(
          utf8.decode(await request.expand((chunk) => chunk).toList()),
        );
        expect(body['expected_capture_version'], 1);
        request.response
          ..statusCode = HttpStatus.created
          ..headers.contentType = ContentType.json
          ..write(jsonEncode(_capture(captureId, version: 2)));
        await request.response.close();
        return;
      }
      if (request.method == 'POST' && request.uri.path.endsWith('/ocr-jobs')) {
        final body = jsonDecode(
          utf8.decode(await request.expand((chunk) => chunk).toList()),
        );
        expect(body['mode'], 'formula');
        request.response
          ..statusCode = HttpStatus.accepted
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'id': jobId,
              'capture_id': captureId,
              'status': 'queued',
              'mode': 'formula',
              'attempt': 0,
              'enqueued_at': '2026-07-14T16:00:00Z',
            }),
          );
        await request.response.close();
        return;
      }
      if (request.method == 'GET' &&
          request.uri.path.endsWith('/ocr-jobs/$jobId')) {
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'id': jobId,
              'capture_id': captureId,
              'status': 'queued',
              'mode': 'formula',
              'attempt': 0,
              'enqueued_at': '2026-07-14T16:00:00Z',
              'result_id': null,
            }),
          );
        await request.response.close();
        return;
      }
      request.response.statusCode = HttpStatus.notFound;
      await request.response.close();
    });
    addTearDown(() async {
      await serverSubscription.cancel();
      await server.close(force: true);
    });

    final directory = await Directory.systemTemp.createTemp(
      'study-capture-client',
    );
    final file = File('${directory.path}/question.jpg');
    await file.writeAsBytes(const [0xff, 0xd8, 0xff]);
    addTearDown(() => directory.delete(recursive: true));

    final receipt = await CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: '00000000-0000-0000-0000-000000000001',
      childId: '00000000-0000-0000-0000-000000000101',
      sessionId: '00000000-0000-0000-0000-000000000201',
      authorizationToken: 'test-session-token',
    ).uploadAndEnqueue(XFile(file.path), ocrMode: OcrMode.formula);

    expect(receipt.captureId, captureId);
    expect(receipt.captureVersion, 2);
    expect(receipt.ocrJobId, jobId);
    expect(receipt.ocrJobStatus, 'queued');
    expect(receipt.ocrMode, OcrMode.formula);
    expect(receipt.contentSha256.length, 64);
    final job = await CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: '00000000-0000-0000-0000-000000000001',
      childId: '00000000-0000-0000-0000-000000000101',
      sessionId: '00000000-0000-0000-0000-000000000201',
      authorizationToken: 'test-session-token',
    ).getOcrJob(receipt);
    expect(job.status, 'queued');
    expect(job.mode, OcrMode.formula);
    expect(job.resultId, isNull);
    expect(uploadedBytes, const [0xff, 0xd8, 0xff]);
    expect(requests, [
      'POST /households/00000000-0000-0000-0000-000000000001/sessions/00000000-0000-0000-0000-000000000201/capture-uploads',
      'PUT /signed/00000000-0000-0000-0000-000000000301',
      'POST /households/00000000-0000-0000-0000-000000000001/captures/00000000-0000-0000-0000-000000000301/upload-confirmations',
      'POST /households/00000000-0000-0000-0000-000000000001/captures/00000000-0000-0000-0000-000000000301/ocr-jobs',
      'GET /households/00000000-0000-0000-0000-000000000001/captures/00000000-0000-0000-0000-000000000301/ocr-jobs/00000000-0000-0000-0000-000000000302',
    ]);
  });

  test('rejects a non-JPEG/PNG input before any network request', () async {
    final directory = await Directory.systemTemp.createTemp(
      'study-capture-client',
    );
    final file = File('${directory.path}/question.heic');
    await file.writeAsBytes(const [0, 1, 2]);
    addTearDown(() => directory.delete(recursive: true));

    await expectLater(
      CaptureApiClient(
        baseUrl: 'http://127.0.0.1:1',
        householdId: 'household',
        childId: 'child',
        sessionId: 'session',
        authorizationToken: 'test-session-token',
      ).uploadAndEnqueue(XFile(file.path)),
      throwsA(isA<CaptureApiException>()),
    );
  });

  test(
    'uploads only the confirmed derivative and records blocked image analysis',
    () async {
      final requests = <String>[];
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      const captureId = '00000000-0000-0000-0000-000000000501';
      const analysisJobId = '00000000-0000-0000-0000-000000000502';
      final subscription = server.listen((request) async {
        requests.add('${request.method} ${request.uri.path}');
        if (request.method == 'POST' &&
            request.uri.path.endsWith('/capture-uploads')) {
          request.response
            ..statusCode = HttpStatus.created
            ..headers.contentType = ContentType.json
            ..write(
              jsonEncode({
                'capture': _capture(captureId, version: 1),
                'upload_url':
                    'http://${server.address.host}:${server.port}/signed/$captureId',
                'upload_expires_at': '2026-07-14T16:00:00Z',
              }),
            );
          await request.response.close();
          return;
        }
        if (request.method == 'PUT' &&
            request.uri.path == '/signed/$captureId') {
          request.response.statusCode = HttpStatus.noContent;
          await request.response.close();
          return;
        }
        if (request.method == 'POST' &&
            request.uri.path.endsWith('/upload-confirmations')) {
          request.response
            ..statusCode = HttpStatus.created
            ..headers.contentType = ContentType.json
            ..write(jsonEncode(_capture(captureId, version: 2)));
          await request.response.close();
          return;
        }
        if (request.method == 'POST' &&
            request.uri.path.endsWith('/image-analysis-jobs')) {
          final body = jsonDecode(
            utf8.decode(await request.expand((chunk) => chunk).toList()),
          );
          expect(body['user_confirmed'], true);
          expect(
            body['sanitization']['schema_version'],
            'privacy-sanitization.v1',
          );
          expect(
            body['sanitization']['sanitized_derivative_sha256'],
            isA<String>(),
          );
          request.response
            ..statusCode = HttpStatus.accepted
            ..headers.contentType = ContentType.json
            ..write(
              jsonEncode({
                'id': analysisJobId,
                'capture_id': captureId,
                'household_id': '00000000-0000-0000-0000-000000000001',
                'child_id': '00000000-0000-0000-0000-000000000101',
                'status': 'blocked',
                'attempt': 0,
                'sanitization_schema_version': 'privacy-sanitization.v1',
                'sanitized_derivative_sha256':
                    body['sanitization']['sanitized_derivative_sha256'],
                'created_at': '2026-07-14T16:00:00Z',
                'updated_at': '2026-07-14T16:00:00Z',
                'error_code': 'provider_not_enabled',
              }),
            );
          await request.response.close();
          return;
        }
        request.response.statusCode = HttpStatus.notFound;
        await request.response.close();
      });
      addTearDown(() async {
        await subscription.cancel();
        await server.close(force: true);
      });

      final receipt =
          await CaptureApiClient(
            baseUrl: 'http://${server.address.host}:${server.port}',
            householdId: '00000000-0000-0000-0000-000000000001',
            childId: '00000000-0000-0000-0000-000000000101',
            sessionId: '00000000-0000-0000-0000-000000000201',
            authorizationToken: 'test-session-token',
          ).uploadAndStartImageAnalysisBytes(
            Uint8List.fromList(const [0xff, 0xd8, 0xff]),
            sanitization: {
              'schema_version': 'privacy-sanitization.v1',
              'sanitizer_version': 'flutter-local-manual-v1',
              'safe_to_upload': true,
              'requires_confirmation': true,
              'sensitive_types': const <String>[],
              'region_count': 0,
              'face_detected': false,
              'qr_detected': false,
              'barcode_detected': false,
              'blocked_reasons': const <String>[],
            },
          );

      expect(receipt.imageAnalysisJobId, analysisJobId);
      expect(receipt.imageAnalysisStatus, 'blocked');
      expect(receipt.hasRemoteOcr, isFalse);
      expect(requests, [
        'POST /households/00000000-0000-0000-0000-000000000001/sessions/00000000-0000-0000-0000-000000000201/capture-uploads',
        'PUT /signed/$captureId',
        'POST /households/00000000-0000-0000-0000-000000000001/captures/$captureId/upload-confirmations',
        'POST /households/00000000-0000-0000-0000-000000000001/captures/$captureId/image-analysis-jobs',
      ]);
    },
  );

  test('polls a completed OCR result and confirms or corrects it', () async {
    final requests = <String>[];
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    const captureId = '00000000-0000-0000-0000-000000000401';
    const jobId = '00000000-0000-0000-0000-000000000402';
    const resultId = '00000000-0000-0000-0000-000000000403';
    const candidateId = '00000000-0000-0000-0000-000000000404';
    final subscription = server.listen((request) async {
      requests.add('${request.method} ${request.uri.path}');
      if (request.method == 'GET' &&
          request.uri.path.endsWith('/ocr-jobs/$jobId')) {
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'id': jobId,
              'capture_id': captureId,
              'status': 'succeeded',
              'attempt': 1,
              'result_id': resultId,
            }),
          );
        await request.response.close();
        return;
      }
      if (request.method == 'GET' &&
          request.uri.path.endsWith('/ocr-results/$resultId')) {
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'result': {'id': resultId, 'status': 'candidate'},
              'candidates': [
                {
                  'id': candidateId,
                  'result_id': resultId,
                  'sequence': 1,
                  'text': '3 + 4 = ?',
                  'confidence': 0.98,
                },
              ],
            }),
          );
        await request.response.close();
        return;
      }
      if (request.method == 'POST' &&
          request.uri.path.endsWith('/confirmations')) {
        expect(
          request.headers.value('Idempotency-Key'),
          'capture-candidate-$candidateId',
        );
        final body = jsonDecode(
          utf8.decode(await request.expand((chunk) => chunk).toList()),
        );
        expect(body['candidate_id'], candidateId);
        request.response
          ..statusCode = HttpStatus.created
          ..headers.contentType = ContentType.json
          ..write(jsonEncode({'id': captureId, 'corrected_text': '3 + 4 = ?'}));
        await request.response.close();
        return;
      }
      if (request.method == 'POST' &&
          request.uri.path.endsWith('/corrections')) {
        expect(
          request.headers.value('Idempotency-Key'),
          'capture-correction-$captureId',
        );
        final body = jsonDecode(
          utf8.decode(await request.expand((chunk) => chunk).toList()),
        );
        expect(body['corrected_text'], '3 + 4 = 7');
        request.response
          ..statusCode = HttpStatus.created
          ..headers.contentType = ContentType.json
          ..write(jsonEncode({'id': captureId, 'corrected_text': '3 + 4 = 7'}));
        await request.response.close();
        return;
      }
      request.response.statusCode = HttpStatus.notFound;
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });

    const receipt = CaptureUploadReceipt(
      captureId: captureId,
      captureVersion: 2,
      mediaType: 'image/jpeg',
      byteSize: 3,
      contentSha256:
          '0000000000000000000000000000000000000000000000000000000000000000',
      ocrJobId: jobId,
      ocrJobStatus: 'queued',
    );
    final client = CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: 'household',
      childId: 'child',
      sessionId: 'session',
      authorizationToken: 'test-session-token',
    );

    final result = await client.waitForOcrResult(
      receipt,
      timeout: const Duration(seconds: 1),
      pollInterval: const Duration(milliseconds: 1),
    );
    expect(result?['result'], {'id': resultId, 'status': 'candidate'});
    expect((result?['candidates'] as List).single['id'], candidateId);
    await client.confirmOcrCandidate(
      receipt: receipt,
      resultId: resultId,
      candidateId: candidateId,
    );
    await client.correctCapture(receipt: receipt, correctedText: '3 + 4 = 7');
    expect(requests, [
      'GET /households/household/captures/$captureId/ocr-jobs/$jobId',
      'GET /households/household/captures/$captureId/ocr-results/$resultId',
      'POST /households/household/captures/$captureId/ocr-results/$resultId/confirmations',
      'POST /households/household/captures/$captureId/corrections',
    ]);
  });
}

Map<String, Object> _capture(String id, {required int version}) => {
  'id': id,
  'household_id': '00000000-0000-0000-0000-000000000001',
  'child_id': '00000000-0000-0000-0000-000000000101',
  'session_id': '00000000-0000-0000-0000-000000000201',
  'media_type': 'image/jpeg',
  'byte_size': 3,
  'content_sha256': '0' * 64,
  'status': version == 1 ? 'upload_pending' : 'needs_correction',
  'version': version,
  'created_at': '2026-07-14T16:00:00Z',
};
