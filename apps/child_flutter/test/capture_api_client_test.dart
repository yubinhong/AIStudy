import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:image_picker/image_picker.dart';
import 'package:study_child/capture_api_client.dart';

void main() {
  test(
    'loads a private curriculum page image with the child session',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final subscription = server.listen((request) async {
        expect(
          request.headers.value(HttpHeaders.authorizationHeader),
          'Bearer test-session-token',
        );
        expect(
          request.uri.path,
          '/households/00000000-0000-0000-0000-000000000001/'
          'children/00000000-0000-0000-0000-000000000101/curriculum/'
          'snapshots/00000000-0000-0000-0000-000000000201/pages/14/image',
        );
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType('image', 'jpeg')
          ..add(const [0xff, 0xd8, 0xff, 0xd9]);
        await request.response.close();
      });
      addTearDown(() async {
        await subscription.cancel();
        await server.close(force: true);
      });
      final client = CaptureApiClient(
        baseUrl: 'http://${server.address.host}:${server.port}',
        householdId: '00000000-0000-0000-0000-000000000001',
        childId: '00000000-0000-0000-0000-000000000101',
        authorizationToken: 'test-session-token',
      );

      final bytes = await client.loadCurriculumPageImage(
        '00000000-0000-0000-0000-000000000201',
        14,
      );

      expect(bytes, Uint8List.fromList(const [0xff, 0xd8, 0xff, 0xd9]));
    },
  );

  test('loads real tasks and resumes an existing active session', () async {
    final requests = <String>[];
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    const taskId = '00000000-0000-0000-0000-000000000211';
    const sessionId = '00000000-0000-0000-0000-000000000212';
    final subscription = server.listen((request) async {
      requests.add('${request.method} ${request.uri.path}');
      expect(
        request.headers.value(HttpHeaders.authorizationHeader),
        'Bearer test-session-token',
      );
      request.response.headers.contentType = ContentType.json;
      if (request.method == 'GET' && request.uri.path.endsWith('/tasks')) {
        request.response
          ..statusCode = HttpStatus.ok
          ..write(
            jsonEncode([
              {
                'id': taskId,
                'status': 'in_progress',
                'version': 2,
                'scheduled_for': '2026-07-17',
              },
            ]),
          );
      } else if (request.method == 'GET' &&
          request.uri.path.endsWith('/tasks/$taskId/active-session')) {
        request.response
          ..statusCode = HttpStatus.ok
          ..write(jsonEncode({'id': sessionId}));
      } else {
        request.response.statusCode = HttpStatus.notFound;
      }
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });
    final client = CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: '00000000-0000-0000-0000-000000000001',
      childId: '00000000-0000-0000-0000-000000000101',
      authorizationToken: 'test-session-token',
    );

    final tasks = await client.listTasks();
    await client.prepareTaskSession(tasks.single);

    expect(tasks.single['id'], taskId);
    expect(requests, [
      'GET /households/00000000-0000-0000-0000-000000000001/tasks',
      'GET /households/00000000-0000-0000-0000-000000000001/tasks/$taskId/active-session',
    ]);
  });

  test('uploads, confirms, and enqueues an optional formula OCR job', () async {
    final requests = <String>[];
    final uploadedBytes = <int>[];
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final captureId = '00000000-0000-0000-0000-000000000301';
    final jobId = '00000000-0000-0000-0000-000000000302';
    final serverSubscription = server.listen((request) async {
      requests.add('${request.method} ${request.uri.path}');
      if (request.method == 'POST' &&
          request.uri.path.endsWith('/captures/upload')) {
        final body = await request.expand((chunk) => chunk).toList();
        expect(body, const [0xff, 0xd8, 0xff]);
        expect(request.headers.value('X-Capture-Media-Type'), 'image/jpeg');
        expect(request.headers.value('X-Capture-Byte-Size'), '3');
        expect(
          request.headers.value(HttpHeaders.authorizationHeader),
          'Bearer test-session-token',
        );
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
    expect(uploadedBytes, isEmpty);
    expect(requests, [
      'POST /households/00000000-0000-0000-0000-000000000001/sessions/00000000-0000-0000-0000-000000000201/captures/upload',
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
      final analysisKeys = <String>[];
      final uploadKeys = <String>[];
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      const captureId = '00000000-0000-0000-0000-000000000501';
      const analysisJobId = '00000000-0000-0000-0000-000000000502';
      const sessionId = '00000000-0000-0000-0000-000000000201';
      final subscription = server.listen((request) async {
        requests.add('${request.method} ${request.uri.path}');
        if (request.method == 'POST' &&
            request.uri.path.endsWith('/capture-sessions')) {
          expect(
            request.headers.value(HttpHeaders.authorizationHeader),
            'Bearer test-session-token',
          );
          request.response
            ..statusCode = HttpStatus.created
            ..headers.contentType = ContentType.json
            ..write(
              jsonEncode({
                'id': sessionId,
                'household_id': '00000000-0000-0000-0000-000000000001',
                'child_id': '00000000-0000-0000-0000-000000000101',
                'task_id': '00000000-0000-0000-0000-000000000202',
                'task_version': 2,
                'status': 'active',
                'started_at': '2026-07-17T16:00:00Z',
              }),
            );
          await request.response.close();
          return;
        }
        if (request.method == 'POST' &&
            request.uri.path.endsWith('/captures/upload')) {
          uploadKeys.add(request.headers.value('Idempotency-Key')!);
          await request.drain<void>();
          request.response
            ..statusCode = HttpStatus.created
            ..headers.contentType = ContentType.json
            ..write(jsonEncode(_capture(captureId, version: 2)));
          await request.response.close();
          return;
        }
        if (request.method == 'POST' &&
            request.uri.path.endsWith('/image-analysis-jobs')) {
          analysisKeys.add(request.headers.value('Idempotency-Key')!);
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

      final client = CaptureApiClient(
        baseUrl: 'http://${server.address.host}:${server.port}',
        householdId: '00000000-0000-0000-0000-000000000001',
        childId: '00000000-0000-0000-0000-000000000101',
        authorizationToken: 'test-session-token',
      );
      final receipt = await client.uploadAndStartImageAnalysisBytes(
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
      final retryReceipt = await client.uploadAndStartImageAnalysisBytes(
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
        retryNonce: 'retry-12345678',
      );

      expect(receipt.imageAnalysisJobId, analysisJobId);
      expect(retryReceipt.imageAnalysisJobId, analysisJobId);
      expect(receipt.imageAnalysisStatus, 'blocked');
      expect(receipt.hasRemoteOcr, isFalse);
      expect(analysisKeys, [
        'image-analysis-$captureId',
        'image-analysis-$captureId-retry-retry-12345678',
      ]);
      expect(uploadKeys, [
        startsWith('capture-upload-'),
        startsWith('capture-upload-'),
      ]);
      expect(uploadKeys[0], isNot(uploadKeys[1]));
      expect(requests, [
        'POST /households/00000000-0000-0000-0000-000000000001/capture-sessions',
        'POST /households/00000000-0000-0000-0000-000000000001/sessions/00000000-0000-0000-0000-000000000201/captures/upload',
        'POST /households/00000000-0000-0000-0000-000000000001/captures/$captureId/image-analysis-jobs',
        'POST /households/00000000-0000-0000-0000-000000000001/sessions/00000000-0000-0000-0000-000000000201/captures/upload',
        'POST /households/00000000-0000-0000-0000-000000000001/captures/$captureId/image-analysis-jobs',
      ]);
    },
  );

  test('polls visual extraction and persists human verification', () async {
    final requests = <String>[];
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    const captureId = '00000000-0000-0000-0000-000000000601';
    const analysisJobId = '00000000-0000-0000-0000-000000000602';
    const extractionId = '00000000-0000-0000-0000-000000000603';
    final subscription = server.listen((request) async {
      requests.add('${request.method} ${request.uri.path}');
      if (request.method == 'GET' &&
          request.uri.path.endsWith('/image-analysis-jobs/$analysisJobId')) {
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'id': analysisJobId,
              'capture_id': captureId,
              'status': 'succeeded',
              'attempt': 1,
              'extraction_id': extractionId,
            }),
          );
        await request.response.close();
        return;
      }
      if (request.method == 'GET' && request.uri.path.endsWith('/extraction')) {
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'id': extractionId,
              'capture_id': captureId,
              'extraction': {
                'schema_version': 'question-extraction.v1',
                'subject': 'math',
                'question_text': 'synthetic question',
                'options': ['A', 'B'],
                'formulas': ['1+1'],
                'has_diagram': false,
                'has_handwriting': false,
                'detected_answer': null,
                'question_region_count': 1,
                'confidence': 0.9,
                'needs_confirmation': true,
              },
              'created_at': '2026-07-17T16:00:00Z',
            }),
          );
        await request.response.close();
        return;
      }
      if (request.method == 'POST' &&
          request.uri.path.endsWith('/extraction/verify')) {
        final body = jsonDecode(
          utf8.decode(await request.expand((chunk) => chunk).toList()),
        );
        expect(body['question_text'], '花丛中有蜻蜓和蝴蝶共35只');
        expect(body['options'], ['A', 'B']);
        expect(body['formulas'], ['1+1']);
        expect(body['expected_capture_version'], 2);
        request.response
          ..statusCode = HttpStatus.created
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'id': '00000000-0000-0000-0000-000000000604',
              'capture_id': captureId,
              'extraction_id': extractionId,
              'question_text': body['question_text'],
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

    const receipt = CaptureUploadReceipt(
      captureId: captureId,
      captureVersion: 2,
      mediaType: 'image/jpeg',
      byteSize: 3,
      contentSha256:
          '0000000000000000000000000000000000000000000000000000000000000000',
      ocrJobId: '',
      ocrJobStatus: 'not_started',
      imageAnalysisJobId: analysisJobId,
      imageAnalysisStatus: 'queued',
    );
    final client = CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: 'household',
      childId: 'child',
      sessionId: 'session',
      authorizationToken: 'test-session-token',
    );

    final record = await client.waitForQuestionExtraction(
      receipt,
      timeout: const Duration(seconds: 1),
      pollInterval: const Duration(milliseconds: 1),
    );
    final extraction = Map<String, dynamic>.from(record!['extraction'] as Map);
    expect(extraction['question_text'], 'synthetic question');
    await client.verifyQuestionExtraction(
      receipt: receipt,
      questionText: '花丛中有蜻蜓和蝴蝶共35只',
      extraction: extraction,
    );
    expect(requests, [
      'GET /households/household/captures/$captureId/image-analysis-jobs/$analysisJobId',
      'GET /households/household/captures/$captureId/image-analysis-jobs/$analysisJobId/extraction',
      'POST /households/household/captures/$captureId/image-analysis-jobs/$analysisJobId/extraction/verify',
    ]);
  });

  test(
    'maps provider billing failures to an actionable capture message',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      const jobId = '00000000-0000-0000-0000-000000000701';
      final subscription = server.listen((request) async {
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'id': jobId,
              'capture_id': '00000000-0000-0000-0000-000000000702',
              'status': 'failed',
              'attempt': 1,
              'error_code': 'provider_http_402',
            }),
          );
        await request.response.close();
      });
      addTearDown(() async {
        await subscription.cancel();
        await server.close(force: true);
      });
      final client = CaptureApiClient(
        baseUrl: 'http://${server.address.host}:${server.port}',
        householdId: 'household',
        childId: 'child',
        authorizationToken: 'test-session-token',
      );
      const receipt = CaptureUploadReceipt(
        captureId: '00000000-0000-0000-0000-000000000702',
        captureVersion: 2,
        mediaType: 'image/jpeg',
        byteSize: 3,
        contentSha256:
            'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
        ocrJobId: '',
        ocrJobStatus: 'not_started',
        imageAnalysisJobId: jobId,
      );

      await expectLater(
        client.waitForQuestionExtraction(receipt),
        throwsA(
          predicate<CaptureApiException>(
            (error) => error.message.contains('NewAPI 余额或模型额度'),
          ),
        ),
      );
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

  test(
    'requests a persisted Tutor hint by server-issued question id',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      const verifiedQuestionId = '00000000-0000-0000-0000-000000000701';
      final subscription = server.listen((request) async {
        expect(request.method, 'POST');
        expect(request.uri.path, '/households/household/tutor/hints');
        expect(
          request.headers.value('Idempotency-Key'),
          'tutor-hint-$verifiedQuestionId-2',
        );
        final body = jsonDecode(
          utf8.decode(await request.expand((chunk) => chunk).toList()),
        );
        expect(body, {'verified_question_id': verifiedQuestionId, 'level': 2});
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'id': '00000000-0000-0000-0000-000000000702',
              'verified_question_id': verifiedQuestionId,
              'level': 2,
              'prompt': '先说说第一步。',
              'next_step': '只写第一步算式。',
            }),
          );
        await request.response.close();
      });
      addTearDown(() async {
        await subscription.cancel();
        await server.close(force: true);
      });
      final client = CaptureApiClient(
        baseUrl: 'http://${server.address.host}:${server.port}',
        householdId: 'household',
        childId: 'child',
        authorizationToken: 'test-session-token',
      );

      final response = await client.createTutorHint(
        verifiedQuestionId: verifiedQuestionId,
        level: 2,
      );
      expect(response['prompt'], '先说说第一步。');
    },
  );

  test('uses a Tutor-specific error when a hint request is rejected', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    const verifiedQuestionId = '00000000-0000-0000-0000-000000000703';
    final subscription = server.listen((request) async {
      await request.drain<void>();
      request.response
        ..statusCode = HttpStatus.conflict
        ..headers.contentType = ContentType.json
        ..write(jsonEncode({'detail': 'capture state conflict'}));
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });
    final client = CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: 'household',
      childId: 'child',
      authorizationToken: 'test-session-token',
    );

    await expectLater(
      client.createTutorHint(verifiedQuestionId: verifiedQuestionId, level: 1),
      throwsA(
        isA<CaptureApiException>()
            .having((error) => error.statusCode, 'statusCode', 409)
            .having((error) => error.message, 'message', '暂时无法获取这道题的提示，请稍后重试。'),
      ),
    );
  });

  test('completes the current session with an explicit outcome', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    const sessionId = '00000000-0000-0000-0000-000000000801';
    final subscription = server.listen((request) async {
      expect(
        request.uri.path,
        '/households/household/sessions/$sessionId/completion',
      );
      expect(
        request.headers.value('Idempotency-Key'),
        'complete-session-$sessionId-needs_review',
      );
      final body = jsonDecode(
        utf8.decode(await request.expand((chunk) => chunk).toList()),
      );
      expect(body, {'outcome': 'needs_review'});
      request.response
        ..statusCode = HttpStatus.ok
        ..headers.contentType = ContentType.json
        ..write(
          jsonEncode({
            'id': sessionId,
            'status': 'completed',
            'outcome': 'needs_review',
          }),
        );
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });
    final client = CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: 'household',
      childId: 'child',
      sessionId: sessionId,
      authorizationToken: 'test-session-token',
    );

    final response = await client.completeCurrentSession(
      outcome: 'needs_review',
    );
    expect(response['status'], 'completed');
  });

  test('loads due mistakes and submits a review result', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    const mistakeId = '00000000-0000-0000-0000-000000000901';
    final subscription = server.listen((request) async {
      if (request.method == 'GET') {
        expect(
          request.uri.path,
          '/households/household/children/child/mistakes',
        );
        expect(request.uri.queryParameters['due_only'], 'true');
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode([
              {
                'mistake': {'id': mistakeId},
              },
            ]),
          );
      } else {
        expect(request.method, 'POST');
        expect(
          request.uri.path,
          '/households/household/children/child/mistakes/$mistakeId/review',
        );
        expect(
          request.headers.value('Idempotency-Key'),
          'review-$mistakeId-correct',
        );
        final body = jsonDecode(
          utf8.decode(await request.expand((chunk) => chunk).toList()),
        );
        expect(body, {
          'outcome': 'correct',
          'answer_summary': '旧客户端未提交作答文本',
          'submitted_answer': null,
          'evidence_confirmed': false,
        });
        request.response
          ..statusCode = HttpStatus.ok
          ..headers.contentType = ContentType.json
          ..write(
            jsonEncode({
              'mistake': {'id': mistakeId},
            }),
          );
      }
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });
    final client = CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: 'household',
      childId: 'child',
      sessionId: 'session',
      authorizationToken: 'test-session-token',
    );

    final due = await client.listDueMistakes();
    final reviewed = await client.reviewMistake(mistakeId, 'correct');
    expect(due.single['mistake'], {'id': mistakeId});
    expect(reviewed['mistake'], {'id': mistakeId});
  });

  test('falls back to all mistakes when none are due yet', () async {
    final requestedDueValues = <String?>[];
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    const mistakeId = '00000000-0000-0000-0000-000000000902';
    final subscription = server.listen((request) async {
      final dueOnly = request.uri.queryParameters['due_only'];
      requestedDueValues.add(dueOnly);
      request.response
        ..statusCode = HttpStatus.ok
        ..headers.contentType = ContentType.json
        ..write(
          jsonEncode(
            dueOnly == 'true'
                ? []
                : [
                    {
                      'mistake': {'id': mistakeId},
                      'schedule': {'due_at': '2026-07-24T08:00:00Z'},
                    },
                  ],
          ),
        );
      await request.response.close();
    });
    addTearDown(() async {
      await subscription.cancel();
      await server.close(force: true);
    });
    final client = CaptureApiClient(
      baseUrl: 'http://${server.address.host}:${server.port}',
      householdId: 'household',
      childId: 'child',
      sessionId: 'session',
      authorizationToken: 'test-session-token',
    );

    final reviewQueue = await client.listReviewMistakes();

    expect(requestedDueValues, ['true', 'false']);
    expect(reviewQueue.single['mistake'], {'id': mistakeId});
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
