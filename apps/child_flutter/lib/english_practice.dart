import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_soloud/flutter_soloud.dart';
import 'package:record/record.dart';

class EnglishPracticeException implements Exception {
  const EnglishPracticeException(this.message);

  final String message;

  @override
  String toString() => message;
}

class EnglishPracticeSettings {
  const EnglishPracticeSettings({
    required this.enabled,
    required this.level,
    required this.providerAvailable,
    required this.dailyLimitMinutes,
  });

  final bool enabled;
  final String level;
  final bool providerAvailable;
  final int dailyLimitMinutes;

  bool get canStart => enabled && providerAvailable;

  factory EnglishPracticeSettings.fromJson(Map<String, dynamic> value) {
    return EnglishPracticeSettings(
      enabled: value['enabled'] == true,
      level: value['level']?.toString() ?? 'pre_a1',
      providerAvailable: value['provider_available'] == true,
      dailyLimitMinutes: value['daily_limit_minutes'] as int? ?? 10,
    );
  }
}

class EnglishScenario {
  const EnglishScenario({
    required this.id,
    required this.title,
    required this.description,
    required this.targetMinutes,
  });

  final String id;
  final String title;
  final String description;
  final int targetMinutes;

  factory EnglishScenario.fromJson(Map<String, dynamic> value) {
    return EnglishScenario(
      id: value['id']?.toString() ?? '',
      title: value['title']?.toString() ?? '',
      description: value['description']?.toString() ?? '',
      targetMinutes: value['target_minutes'] as int? ?? 5,
    );
  }
}

class EnglishSessionSummary {
  const EnglishSessionSummary({
    required this.id,
    required this.scenarioId,
    required this.level,
    required this.status,
    required this.durationSeconds,
    required this.turnCount,
    required this.startedAt,
  });

  final String id;
  final String scenarioId;
  final String level;
  final String status;
  final int durationSeconds;
  final int turnCount;
  final DateTime startedAt;

  factory EnglishSessionSummary.fromJson(Map<String, dynamic> value) {
    return EnglishSessionSummary(
      id: value['id']?.toString() ?? '',
      scenarioId: value['scenario_id']?.toString() ?? '',
      level: value['level']?.toString() ?? 'pre_a1',
      status: value['status']?.toString() ?? 'interrupted',
      durationSeconds: value['duration_seconds'] as int? ?? 0,
      turnCount: value['turn_count'] as int? ?? 0,
      startedAt:
          DateTime.tryParse(value['started_at']?.toString() ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0),
    );
  }
}

abstract interface class EnglishPracticeGateway {
  Future<EnglishPracticeSettings> loadSettings();
  Future<List<EnglishScenario>> loadScenarios();
  Future<List<EnglishSessionSummary>> loadRecentSessions();
  Future<EnglishSessionSummary> startSession(String scenarioId);
  Future<WebSocket> connectSession(String sessionId);
  Future<void> completeSession(String sessionId, {required bool interrupted});
}

class EnglishPracticeApiClient implements EnglishPracticeGateway {
  EnglishPracticeApiClient({
    required String baseUrl,
    required this.householdId,
    required this.childId,
    required this.authorizationToken,
  }) : _baseUri = Uri.parse(baseUrl);

  final Uri _baseUri;
  final String householdId;
  final String childId;
  final String authorizationToken;
  int _nonce = 0;

  String get _root =>
      '/households/$householdId/children/$childId/english-practice';

  @override
  Future<EnglishPracticeSettings> loadSettings() async {
    return EnglishPracticeSettings.fromJson(
      await _json('GET', '$_root/settings'),
    );
  }

  @override
  Future<List<EnglishScenario>> loadScenarios() async {
    final values = await _jsonList('$_root/scenarios');
    return values.map(EnglishScenario.fromJson).toList(growable: false);
  }

  @override
  Future<List<EnglishSessionSummary>> loadRecentSessions() async {
    final values = await _jsonList('$_root/sessions?limit=10');
    return values.map(EnglishSessionSummary.fromJson).toList(growable: false);
  }

  @override
  Future<EnglishSessionSummary> startSession(String scenarioId) async {
    final value = await _json(
      'POST',
      '$_root/sessions',
      body: {'scenario_id': scenarioId},
      idempotencyKey: _key('start'),
    );
    return EnglishSessionSummary.fromJson(value);
  }

  @override
  Future<WebSocket> connectSession(String sessionId) {
    final uri = _baseUri.replace(
      scheme: _baseUri.scheme == 'https' ? 'wss' : 'ws',
      path: '${_baseUri.path}$_root/sessions/$sessionId/stream'.replaceAll(
        '//',
        '/',
      ),
      query: null,
    );
    return WebSocket.connect(
      uri.toString(),
      headers: {'Authorization': 'Bearer $authorizationToken'},
    );
  }

  @override
  Future<void> completeSession(
    String sessionId, {
    required bool interrupted,
  }) async {
    await _json(
      'POST',
      '$_root/sessions/$sessionId/complete',
      body: {'status': interrupted ? 'interrupted' : 'completed'},
      idempotencyKey: _key('complete'),
    );
  }

  Future<Map<String, dynamic>> _json(
    String method,
    String path, {
    Map<String, dynamic>? body,
    String? idempotencyKey,
  }) async {
    final client = HttpClient();
    try {
      final uri = _baseUri.resolve(path);
      final request = method == 'POST'
          ? await client.postUrl(uri)
          : await client.getUrl(uri);
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
        throw const EnglishPracticeException('英语口语服务暂时不可用。');
      }
      final decoded = jsonDecode(text);
      if (decoded is! Map) {
        throw const EnglishPracticeException('英语口语服务返回了无法识别的数据。');
      }
      return Map<String, dynamic>.from(decoded);
    } on EnglishPracticeException {
      rethrow;
    } on Object {
      throw const EnglishPracticeException('无法连接英语口语服务，请检查网络。');
    } finally {
      client.close(force: true);
    }
  }

  Future<List<Map<String, dynamic>>> _jsonList(String path) async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(_baseUri.resolve(path));
      request.headers.set('Authorization', 'Bearer $authorizationToken');
      final response = await request.close();
      final text = await response.transform(utf8.decoder).join();
      if (response.statusCode != HttpStatus.ok) {
        throw const EnglishPracticeException('英语口语服务暂时不可用。');
      }
      final decoded = jsonDecode(text);
      if (decoded is! List) {
        throw const EnglishPracticeException('英语口语服务返回了无法识别的数据。');
      }
      return decoded.whereType<Map>().map(Map<String, dynamic>.from).toList();
    } on EnglishPracticeException {
      rethrow;
    } on Object {
      throw const EnglishPracticeException('无法连接英语口语服务，请检查网络。');
    } finally {
      client.close(force: true);
    }
  }

  String _key(String operation) {
    _nonce += 1;
    return 'english-$operation-$childId-${DateTime.now().microsecondsSinceEpoch}-$_nonce';
  }
}

class SubjectSelectionScreen extends StatefulWidget {
  const SubjectSelectionScreen({
    super.key,
    required this.displayName,
    required this.mathBuilder,
    this.chineseBuilder,
    this.enabledSubjects = const {'math'},
    this.englishGateway,
  });

  final String displayName;
  final WidgetBuilder mathBuilder;
  final WidgetBuilder? chineseBuilder;
  final Set<String> enabledSubjects;
  final EnglishPracticeGateway? englishGateway;

  @override
  State<SubjectSelectionScreen> createState() => _SubjectSelectionScreenState();
}

class _SubjectSelectionScreenState extends State<SubjectSelectionScreen> {
  late Future<EnglishPracticeSettings>? _settings;

  @override
  void initState() {
    super.initState();
    _settings = widget.englishGateway?.loadSettings();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${widget.displayName}，今天想学什么？',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 20),
          Expanded(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final columns = constraints.maxWidth >= 700 ? 2 : 1;
                return GridView.count(
                  crossAxisCount: columns,
                  mainAxisSpacing: 16,
                  crossAxisSpacing: 16,
                  childAspectRatio: columns == 2 ? 1.7 : 2.2,
                  children: [
                    _SubjectCard(
                      icon: Icons.calculate_outlined,
                      title: '数学',
                      subtitle: '错题讲解、复习错题、今日任务',
                      onTap: () => Navigator.of(context).push(
                        MaterialPageRoute<void>(builder: widget.mathBuilder),
                      ),
                    ),
                    if (widget.enabledSubjects.contains('chinese') &&
                        widget.chineseBuilder != null)
                      _SubjectCard(
                        icon: Icons.menu_book_outlined,
                        title: '语文',
                        subtitle: '字词、句子、阅读与古诗文',
                        onTap: () => Navigator.of(context).push(
                          MaterialPageRoute<void>(
                            builder: widget.chineseBuilder!,
                          ),
                        ),
                      ),
                    FutureBuilder<EnglishPracticeSettings>(
                      future: _settings,
                      builder: (context, snapshot) {
                        final settings = snapshot.data;
                        final unlocked = settings?.canStart == true;
                        final reason =
                            settings == null || !settings.providerAvailable
                            ? '口语服务尚未开放'
                            : !settings.enabled
                            ? '需要家长先启用'
                            : '5–8 分钟情景对话';
                        return _SubjectCard(
                          icon: Icons.record_voice_over_outlined,
                          title: '英语',
                          subtitle: reason,
                          locked: !unlocked,
                          onTap: unlocked && widget.englishGateway != null
                              ? () => Navigator.of(context).push(
                                  MaterialPageRoute<void>(
                                    builder: (_) => EnglishPracticeHomeScreen(
                                      gateway: widget.englishGateway!,
                                      initialSettings: settings!,
                                    ),
                                  ),
                                )
                              : null,
                        );
                      },
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _SubjectCard extends StatelessWidget {
  const _SubjectCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.locked = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback? onTap;
  final bool locked;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              Icon(icon, size: 44),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: Theme.of(context).textTheme.headlineSmall,
                    ),
                    const SizedBox(height: 6),
                    Text(subtitle),
                  ],
                ),
              ),
              Icon(locked ? Icons.lock_outline : Icons.chevron_right),
            ],
          ),
        ),
      ),
    );
  }
}

class EnglishPracticeHomeScreen extends StatefulWidget {
  const EnglishPracticeHomeScreen({
    super.key,
    required this.gateway,
    required this.initialSettings,
  });

  final EnglishPracticeGateway gateway;
  final EnglishPracticeSettings initialSettings;

  @override
  State<EnglishPracticeHomeScreen> createState() =>
      _EnglishPracticeHomeScreenState();
}

class _EnglishPracticeHomeScreenState extends State<EnglishPracticeHomeScreen> {
  late Future<(List<EnglishScenario>, List<EnglishSessionSummary>)> _content;

  @override
  void initState() {
    super.initState();
    _reload();
  }

  void _reload() {
    _content =
        Future.wait([
          widget.gateway.loadScenarios(),
          widget.gateway.loadRecentSessions(),
        ]).then(
          (items) => (
            items[0] as List<EnglishScenario>,
            items[1] as List<EnglishSessionSummary>,
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('英语口语')),
      body: FutureBuilder<(List<EnglishScenario>, List<EnglishSessionSummary>)>(
        future: _content,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: FilledButton.icon(
                onPressed: () => setState(_reload),
                icon: const Icon(Icons.refresh),
                label: const Text('重试'),
              ),
            );
          }
          final (scenarios, recent) = snapshot.data!;
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text('选择情景', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 12),
              ...scenarios.map(
                (scenario) => Card(
                  child: ListTile(
                    leading: const Icon(Icons.forum_outlined),
                    title: Text(scenario.title),
                    subtitle: Text(
                      '${scenario.description} · ${scenario.targetMinutes} 分钟',
                    ),
                    trailing: const Icon(Icons.play_arrow),
                    onTap: () async {
                      await Navigator.of(context).push(
                        MaterialPageRoute<void>(
                          builder: (_) => EnglishLiveSessionScreen(
                            gateway: widget.gateway,
                            scenario: scenario,
                          ),
                        ),
                      );
                      if (mounted) setState(_reload);
                    },
                  ),
                ),
              ),
              const SizedBox(height: 24),
              Text('最近练习', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              if (recent.isEmpty) const Text('还没有练习记录'),
              ...recent.map(
                (item) => ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(_scenarioTitle(item.scenarioId)),
                  subtitle: Text(
                    '${item.level.toUpperCase()} · ${item.turnCount} 轮',
                  ),
                  trailing: Text('${item.durationSeconds ~/ 60} 分钟'),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

String _scenarioTitle(String id) => switch (id) {
  'greetings' => '打招呼',
  'school' => '校园交流',
  'food_order' => '点餐',
  _ => '英语练习',
};

class EnglishLiveSessionScreen extends StatefulWidget {
  const EnglishLiveSessionScreen({
    super.key,
    required this.gateway,
    required this.scenario,
  });

  final EnglishPracticeGateway gateway;
  final EnglishScenario scenario;

  @override
  State<EnglishLiveSessionScreen> createState() =>
      _EnglishLiveSessionScreenState();
}

class _EnglishLiveSessionScreenState extends State<EnglishLiveSessionScreen>
    with WidgetsBindingObserver {
  final _recorder = AudioRecorder();
  WebSocket? _socket;
  StreamSubscription<dynamic>? _socketSubscription;
  StreamSubscription<Uint8List>? _recordSubscription;
  AudioSource? _playbackSource;
  SoundHandle? _playbackHandle;
  String? _sessionId;
  String _state = '准备中';
  bool _recording = false;
  bool _pressed = false;
  bool _closing = false;
  bool _playedCurrentStream = false;
  final List<int> _pcmBuffer = [];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    unawaited(_start());
  }

  Future<void> _start() async {
    try {
      final session = await widget.gateway.startSession(widget.scenario.id);
      _sessionId = session.id;
      final socket = await widget.gateway.connectSession(session.id);
      if (!mounted || _closing) {
        await socket.close();
        return;
      }
      _socket = socket;
      _socketSubscription = socket.listen(
        _onSocketMessage,
        onDone: () => _handleConnectionClosed(),
        onError: (_) => _handleConnectionClosed(),
      );
      await SoLoud.instance.init(
        sampleRate: 24000,
        channels: Channels.mono,
        bufferSize: 512,
      );
      _resetPlaybackStream();
    } on Object {
      if (mounted) setState(() => _state = '暂时无法开始，请返回重试');
      await _close(interrupted: true);
    }
  }

  void _onSocketMessage(dynamic message) {
    if (message is List<int>) {
      final source = _playbackSource;
      if (source == null) return;
      SoLoud.instance.addAudioDataStream(source, Uint8List.fromList(message));
      if (!_playedCurrentStream) {
        _playbackHandle = SoLoud.instance.play(source);
        _playedCurrentStream = true;
      }
      return;
    }
    if (message is! String) return;
    final decoded = jsonDecode(message);
    if (decoded is! Map) return;
    final type = decoded['type']?.toString();
    if (!mounted) return;
    setState(() {
      _state = switch (type) {
        'ready' => '准备好了',
        'listening' => '正在听',
        'thinking' => '正在想',
        'speaking' => '正在说',
        'interrupted' => '已停止播放',
        'completed' => '练习完成',
        'error' => '本轮没有听清，请再试一次',
        _ => _state,
      };
    });
  }

  void _resetPlaybackStream() {
    if (!SoLoud.instance.isInitialized) return;
    _playbackSource = SoLoud.instance.setBufferStream(
      maxBufferSizeDuration: const Duration(seconds: 10),
      bufferingType: BufferingType.released,
      bufferingTimeNeeds: 0.04,
      sampleRate: 24000,
      channels: Channels.mono,
      format: BufferType.s16le,
    );
    _playedCurrentStream = false;
    _playbackHandle = null;
  }

  Future<void> _stopPlayback() async {
    final handle = _playbackHandle;
    if (handle != null && SoLoud.instance.isInitialized) {
      await SoLoud.instance.stop(handle);
    }
    if (SoLoud.instance.isInitialized) {
      await SoLoud.instance.disposeAllSources();
      _resetPlaybackStream();
    }
  }

  Future<void> _beginSpeaking() async {
    if (_recording || _socket == null || _closing) return;
    await _stopPlayback();
    _socket!.add(
      jsonEncode({
        'schema_version': 'english-live-client-event.v1',
        'type': 'interrupt',
      }),
    );
    if (!await _recorder.hasPermission()) {
      if (mounted) setState(() => _state = '需要麦克风权限才能练习');
      await _close(interrupted: true);
      return;
    }
    if (!_pressed || _closing) return;
    try {
      final stream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
          echoCancel: true,
          noiseSuppress: true,
        ),
      );
      _socket!.add(
        jsonEncode({
          'schema_version': 'english-live-client-event.v1',
          'type': 'listening',
        }),
      );
      _recordSubscription = stream.listen(
        _sendPcm,
        onError: (_) => unawaited(_close(interrupted: true)),
        onDone: () {
          if (!_closing && _recording) {
            unawaited(_close(interrupted: true));
          }
        },
      );
      if (mounted) setState(() => _recording = true);
      if (!_pressed) await _endSpeaking();
    } on Object {
      if (mounted) setState(() => _state = '麦克风无法使用');
      await _close(interrupted: true);
    }
  }

  void _sendPcm(Uint8List chunk) {
    _pcmBuffer.addAll(chunk);
    while (_pcmBuffer.length >= 640) {
      _socket?.add(Uint8List.fromList(_pcmBuffer.sublist(0, 640)));
      _pcmBuffer.removeRange(0, 640);
    }
  }

  Future<void> _endSpeaking() async {
    if (!_recording) return;
    await _recorder.stop();
    await _recordSubscription?.cancel();
    _recordSubscription = null;
    _pcmBuffer.clear();
    _socket?.add(
      jsonEncode({
        'schema_version': 'english-live-client-event.v1',
        'type': 'audio_stream_end',
      }),
    );
    if (mounted) setState(() => _recording = false);
  }

  Future<void> _close({required bool interrupted}) async {
    if (_closing) return;
    _closing = true;
    _pressed = false;
    try {
      await _recorder.stop();
    } on Object {
      // Continue closing the network and playback resources.
    }
    try {
      await _recordSubscription?.cancel();
    } on Object {
      // Continue closing the network and playback resources.
    }
    _recordSubscription = null;
    _pcmBuffer.clear();
    final sessionId = _sessionId;
    if (sessionId != null) {
      try {
        _socket?.add(
          jsonEncode({
            'schema_version': 'english-live-client-event.v1',
            'type': interrupted ? 'interrupt' : 'complete',
          }),
        );
        await widget.gateway.completeSession(
          sessionId,
          interrupted: interrupted,
        );
      } on Object {
        // The server also closes active sessions on WebSocket disconnect.
      }
    }
    try {
      await _socketSubscription?.cancel();
    } on Object {
      // The underlying socket may already be closed.
    }
    try {
      await _socket?.close();
    } on Object {
      // The underlying socket may already be closed.
    }
    if (SoLoud.instance.isInitialized) {
      try {
        SoLoud.instance.deinit();
      } on Object {
        // Native playback teardown must not prevent recorder disposal.
      }
    }
  }

  void _handleConnectionClosed() {
    if (mounted && !_closing) {
      setState(() => _state = '网络已断开，练习已结束');
      unawaited(_close(interrupted: true));
    }
  }

  void _pressStart() {
    if (_pressed || _closing) return;
    _pressed = true;
    unawaited(_beginSpeaking());
  }

  void _pressEnd() {
    if (!_pressed) return;
    _pressed = false;
    unawaited(_endSpeaking());
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) {
      unawaited(_close(interrupted: true));
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    unawaited(_disposeResources());
    super.dispose();
  }

  Future<void> _disposeResources() async {
    await _close(interrupted: true);
    await _recorder.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        await _close(interrupted: true);
        if (context.mounted) Navigator.of(context).pop();
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(widget.scenario.title),
          actions: [
            IconButton(
              tooltip: '扬声器状态',
              onPressed: null,
              icon: const Icon(Icons.volume_up_outlined),
            ),
            TextButton.icon(
              onPressed: () async {
                await _close(interrupted: false);
                if (context.mounted) Navigator.of(context).pop();
              },
              icon: const Icon(Icons.stop_circle_outlined),
              label: const Text('结束'),
            ),
          ],
        ),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(_state, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 36),
              Semantics(
                button: true,
                label: '按住说话',
                child: Listener(
                  behavior: HitTestBehavior.opaque,
                  onPointerDown: (_) => _pressStart(),
                  onPointerUp: (_) => _pressEnd(),
                  onPointerCancel: (_) => _pressEnd(),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 120),
                    width: 152,
                    height: 152,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _recording
                          ? Theme.of(context).colorScheme.error
                          : Theme.of(context).colorScheme.primary,
                    ),
                    child: const Icon(Icons.mic, color: Colors.white, size: 58),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const Text('按住说话'),
            ],
          ),
        ),
      ),
    );
  }
}
