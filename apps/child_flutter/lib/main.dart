import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import 'capture_api_client.dart';
import 'auth_client.dart';
import 'privacy_sanitization_preview.dart';
import 'startup_transition.dart';

const defaultHouseholdId = '00000000-0000-0000-0000-000000000001';
const captureSessionId = String.fromEnvironment('STUDY_CAPTURE_SESSION_ID');

typedef ChildrenLoader = Future<List<Map<String, dynamic>>> Function();
typedef ChildLoginAction =
    Future<String> Function(String baseUrl, String username, String password);
typedef ChildLoggedIn = void Function(String baseUrl, String token);

Future<List<Map<String, dynamic>>> loadChildrenWithToken(
  String baseUrl,
  String token,
) async {
  if (token.isEmpty) return [];
  final client = HttpClient();
  try {
    final request = await client.getUrl(
      Uri.parse('$baseUrl/households/$defaultHouseholdId/children'),
    );
    request.headers.set('Authorization', 'Bearer $token');
    final response = await request.close();
    if (response.statusCode != HttpStatus.ok) return [];
    final payload = jsonDecode(await response.transform(utf8.decoder).join());
    if (payload is! List) return [];
    return payload.whereType<Map>().map(Map<String, dynamic>.from).toList();
  } finally {
    client.close(force: true);
  }
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (Platform.isIOS) {
    await SystemChrome.setPreferredOrientations(const [
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
  }
  runApp(const StudyChildApp());
}

class StudyChildApp extends StatelessWidget {
  const StudyChildApp({
    super.key,
    this.loadChildren,
    this.authStore,
    this.loginAction,
  });

  final ChildrenLoader? loadChildren;
  final ChildAuthStore? authStore;
  final ChildLoginAction? loginAction;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '家庭 AI 学习助手',
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: const ColorScheme.light(
          primary: _mint,
          onPrimary: Colors.white,
          secondary: _deepGreen,
          onSecondary: Colors.white,
          surface: _surface,
          onSurface: _deepGreen,
          error: _coral,
        ),
        scaffoldBackgroundColor: _background,
        splashFactory: InkSparkle.splashFactory,
      ),
      home: loadChildren == null
          ? ChildAuthGate(store: authStore, loginAction: loginAction)
          : StartupTransition(
              child: ChildProfileScreen(loadChildren: loadChildren!),
            ),
    );
  }
}

class ChildAuthGate extends StatefulWidget {
  const ChildAuthGate({super.key, this.store, this.loginAction});

  final ChildAuthStore? store;
  final ChildLoginAction? loginAction;

  @override
  State<ChildAuthGate> createState() => _ChildAuthGateState();
}

class _ChildAuthGateState extends State<ChildAuthGate> {
  late final ChildAuthStore _store;
  String _serverBaseUrl = defaultServerBaseUrl;
  String? _token;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _store = widget.store ?? const SecureChildAuthStore();
    _restore();
  }

  Future<void> _restore() async {
    String serverBaseUrl = defaultServerBaseUrl;
    String? token;
    try {
      final savedServerBaseUrl = await _store.readServerBaseUrl();
      if (savedServerBaseUrl != null && savedServerBaseUrl.isNotEmpty) {
        serverBaseUrl = normalizeServerBaseUrl(savedServerBaseUrl);
      }
      token = await _store.readSessionToken();
    } on ChildAuthException {
      await _store.clearSessionToken();
    } on Object {
      token = null;
    }
    if (!mounted) return;
    setState(() {
      _serverBaseUrl = serverBaseUrl;
      _token = token;
      _loading = false;
    });
  }

  Future<void> _changeServer() async {
    await _store.clearSessionToken();
    if (!mounted) return;
    setState(() => _token = null);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final token = _token;
    if (token != null && token.isNotEmpty) {
      return StartupTransition(
        child: ChildProfileScreen(
          loadChildren: () => loadChildrenWithToken(_serverBaseUrl, token),
          baseUrl: _serverBaseUrl,
          authorizationToken: token,
          onChangeServer: _changeServer,
        ),
      );
    }
    return ChildLoginScreen(
      initialServerBaseUrl: _serverBaseUrl,
      store: _store,
      loginAction: widget.loginAction,
      onLoggedIn: (baseUrl, newToken) => setState(() {
        _serverBaseUrl = baseUrl;
        _token = newToken;
      }),
    );
  }
}

class ChildLoginScreen extends StatefulWidget {
  const ChildLoginScreen({
    super.key,
    required this.initialServerBaseUrl,
    required this.store,
    required this.onLoggedIn,
    this.loginAction,
  });

  final String initialServerBaseUrl;
  final ChildAuthStore store;
  final ChildLoggedIn onLoggedIn;
  final ChildLoginAction? loginAction;

  @override
  State<ChildLoginScreen> createState() => _ChildLoginScreenState();
}

class _ChildLoginScreenState extends State<ChildLoginScreen> {
  late final TextEditingController _serverBaseUrl;
  final _username = TextEditingController();
  final _password = TextEditingController();
  bool _pending = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _serverBaseUrl = TextEditingController(text: widget.initialServerBaseUrl);
  }

  @override
  void dispose() {
    _serverBaseUrl.dispose();
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    setState(() {
      _pending = true;
      _error = null;
    });
    try {
      final baseUrl = await widget.store.saveServerBaseUrl(_serverBaseUrl.text);
      final token = await (widget.loginAction ?? _loginWithClient)(
        baseUrl,
        _username.text,
        _password.text,
      );
      await widget.store.writeSessionToken(token);
      if (mounted) widget.onLoggedIn(baseUrl, token);
    } on ChildAuthException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) setState(() => _error = '无法保存服务端配置，请重试。');
    } finally {
      if (mounted) setState(() => _pending = false);
    }
  }

  Future<String> _loginWithClient(
    String baseUrl,
    String username,
    String password,
  ) => ChildAuthClient(baseUrl: baseUrl).login(username, password);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: Card(
            margin: const EdgeInsets.all(24),
            child: Padding(
              padding: const EdgeInsets.all(28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    '登录学习桌',
                    style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  const Text('使用家长创建的孩子账号登录。'),
                  const SizedBox(height: 20),
                  TextField(
                    key: const ValueKey('server-base-url'),
                    controller: _serverBaseUrl,
                    keyboardType: TextInputType.url,
                    autocorrect: false,
                    enableSuggestions: false,
                    decoration: const InputDecoration(
                      labelText: '服务端地址',
                      helperText: '例如 http://192.168.1.4:8000',
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _username,
                    decoration: const InputDecoration(labelText: '用户名'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _password,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: '密码'),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(_error!, style: const TextStyle(color: _coral)),
                  ],
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _pending ? null : _login,
                    child: Text(_pending ? '登录中…' : '登录'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class ChildProfileScreen extends StatefulWidget {
  const ChildProfileScreen({
    super.key,
    required this.loadChildren,
    this.baseUrl = defaultServerBaseUrl,
    this.authorizationToken,
    this.onChangeServer,
  });

  final ChildrenLoader loadChildren;
  final String baseUrl;
  final String? authorizationToken;
  final VoidCallback? onChangeServer;

  @override
  State<ChildProfileScreen> createState() => _ChildProfileScreenState();
}

class _ChildProfileScreenState extends State<ChildProfileScreen> {
  late final Future<List<Map<String, dynamic>>> _children;

  @override
  void initState() {
    super.initState();
    _children = widget.loadChildren();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('家庭 AI 学习助手'),
        actions: [
          if (widget.onChangeServer != null)
            TextButton(
              onPressed: widget.onChangeServer,
              child: const Text('更换服务端'),
            ),
        ],
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _children,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          final children = snapshot.data ?? const <Map<String, dynamic>>[];
          final child = children.isEmpty ? null : children.first;
          if (child == null) {
            return const _UnavailableScreen();
          }
          return LearningDeskScreen(
            displayName: child['display_name']?.toString() ?? '小禾',
            curriculumVersion:
                child['curriculum_version']?.toString() ?? '数学练习',
            captureClient: _buildCaptureClient(child),
          );
        },
      ),
    );
  }

  CaptureApiClient? _buildCaptureClient(Map<String, dynamic> child) {
    final childId = child['id']?.toString();
    final token = widget.authorizationToken;
    if (captureSessionId.isEmpty ||
        childId == null ||
        childId.isEmpty ||
        token == null ||
        token.isEmpty) {
      return null;
    }
    return CaptureApiClient(
      baseUrl: widget.baseUrl,
      householdId: defaultHouseholdId,
      childId: childId,
      sessionId: captureSessionId,
      authorizationToken: token,
    );
  }
}

const _background = Color(0xFFFFFCF7);
const _surface = Color(0xFFFFFFFF);
const _deepGreen = Color(0xFF124D3F);
const _mint = Color(0xFF35B58F);
const _lightMint = Color(0xFFE8F5EE);
const _border = Color(0xFFD9E9DE);
const _muted = Color(0xFF6C7872);
const _coral = Color(0xFFF17968);

class LearningDeskScreen extends StatefulWidget {
  const LearningDeskScreen({
    super.key,
    required this.displayName,
    required this.curriculumVersion,
    this.captureClient,
  });

  final String displayName;
  final String curriculumVersion;
  final CaptureApiClient? captureClient;

  @override
  State<LearningDeskScreen> createState() => _LearningDeskScreenState();
}

class _LearningDeskScreenState extends State<LearningDeskScreen> {
  void _startLearning() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (context) => const TutorHintScreen()),
    );
  }

  void _openCaptureFlow() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) =>
            CaptureInputScreen(captureClient: widget.captureClient),
      ),
    );
  }

  void _showLaterMessage() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('已保留今天的任务，随时可以回来继续。'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: RepaintBoundary(
        key: const ValueKey('learning-desk'),
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 900;
              return SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(
                  compact ? 20 : 42,
                  compact ? 20 : 28,
                  compact ? 20 : 42,
                  compact ? 20 : 28,
                ),
                child: Column(
                  children: [
                    _buildHeader(compact),
                    SizedBox(height: compact ? 22 : 28),
                    _buildTaskSurface(compact),
                    const SizedBox(height: 16),
                    TextButton(
                      onPressed: _showLaterMessage,
                      style: TextButton.styleFrom(foregroundColor: _coral),
                      child: const Text('稍后再做', style: TextStyle(fontSize: 16)),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildHeader(bool compact) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        ClipOval(
          child: Image.asset(
            'assets/ui/child_avatar.png',
            width: compact ? 52 : 64,
            height: compact ? 52 : 64,
            fit: BoxFit.cover,
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${widget.displayName}的学习桌',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: _titleStyle(compact ? 27 : 34),
              ),
              const SizedBox(height: 4),
              const Text(
                '专注每一步，进步看得见',
                style: TextStyle(color: _muted, fontSize: 17, height: 1.3),
              ),
            ],
          ),
        ),
        if (!compact) ...[
          const Text(
            '2026年7月14日  星期二',
            style: TextStyle(color: _deepGreen, fontSize: 18),
          ),
          const SizedBox(width: 22),
        ],
        const _OnlinePill(),
      ],
    );
  }

  Widget _buildTaskSurface(bool compact) {
    return Container(
      width: double.infinity,
      padding: EdgeInsets.fromLTRB(
        compact ? 22 : 46,
        28,
        compact ? 22 : 46,
        26,
      ),
      decoration: BoxDecoration(
        color: _surface,
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 62,
                height: 62,
                decoration: const BoxDecoration(
                  color: _lightMint,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.menu_book_rounded,
                  color: _deepGreen,
                  size: 34,
                ),
              ),
              const SizedBox(width: 18),
              Text('今天的数学小任务', style: _titleStyle(compact ? 25 : 29)),
            ],
          ),
          const SizedBox(height: 24),
          const Divider(color: _border, height: 1),
          const SizedBox(height: 34),
          if (compact) _buildCompactTaskBody() else _buildWideTaskBody(),
        ],
      ),
    );
  }

  Widget _buildWideTaskBody() {
    return Column(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(flex: 5, child: _FractionIllustration()),
            const SizedBox(width: 46),
            Expanded(flex: 7, child: _buildTaskDetails()),
          ],
        ),
        const SizedBox(height: 38),
        _buildActions(),
      ],
    );
  }

  Widget _buildCompactTaskBody() {
    return Column(
      children: [
        _FractionIllustration(height: 180),
        const SizedBox(height: 24),
        _buildTaskDetails(),
        const SizedBox(height: 28),
        _buildActions(),
      ],
    );
  }

  Widget _buildTaskDetails() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('分数的加法', style: _titleStyle(38)),
        const SizedBox(height: 12),
        const Text(
          '学习目标：理解同分母分数加法的算理，\n能正确计算并解决简单问题。',
          style: TextStyle(color: _muted, fontSize: 18, height: 1.55),
        ),
        const SizedBox(height: 24),
        RichText(
          text: const TextSpan(
            style: TextStyle(color: _deepGreen, fontSize: 22),
            children: [
              TextSpan(text: '第 '),
              TextSpan(
                text: '2',
                style: TextStyle(
                  color: _mint,
                  fontSize: 30,
                  fontWeight: FontWeight.w700,
                ),
              ),
              TextSpan(text: ' 题 / 共 4 题'),
            ],
          ),
        ),
        const SizedBox(height: 10),
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: const LinearProgressIndicator(
            value: 0.5,
            minHeight: 14,
            backgroundColor: _lightMint,
            valueColor: AlwaysStoppedAnimation<Color>(_mint),
          ),
        ),
      ],
    );
  }

  Widget _buildActions() {
    return Row(
      children: [
        Expanded(
          flex: 5,
          child: FilledButton(
            onPressed: _startLearning,
            style: _filledButtonStyle(),
            child: const Text('继续学习'),
          ),
        ),
        const SizedBox(width: 24),
        Expanded(
          flex: 2,
          child: OutlinedButton.icon(
            onPressed: _openCaptureFlow,
            icon: const Icon(Icons.camera_alt_outlined, size: 28),
            label: const Text('拍题'),
            style: OutlinedButton.styleFrom(
              foregroundColor: _mint,
              side: const BorderSide(color: _mint, width: 1.5),
              minimumSize: const Size.fromHeight(72),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(22),
              ),
              textStyle: const TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class CaptureInputScreen extends StatefulWidget {
  const CaptureInputScreen({super.key, this.captureClient});

  final CaptureApiClient? captureClient;

  @override
  State<CaptureInputScreen> createState() => _CaptureInputScreenState();
}

class _CaptureInputScreenState extends State<CaptureInputScreen> {
  final ImagePicker _picker = ImagePicker();
  bool _isPicking = false;

  Future<void> _pickImage(ImageSource source) async {
    setState(() => _isPicking = true);
    try {
      final image = await _picker.pickImage(
        source: source,
        maxWidth: 2400,
        maxHeight: 2400,
        imageQuality: 90,
      );
      if (!mounted || image == null) return;
      final sanitized = await Navigator.of(context)
          .push<SanitizedImageSelection>(
            MaterialPageRoute<SanitizedImageSelection>(
              builder: (context) => SanitizationPreviewScreen(image: image),
            ),
          );
      if (!mounted || sanitized == null) return;
      CaptureUploadReceipt? uploadReceipt;
      if (widget.captureClient != null) {
        try {
          uploadReceipt = await widget.captureClient!
              .uploadAndStartImageAnalysisBytes(
                sanitized.bytes,
                sanitization: {
                  'schema_version': 'privacy-sanitization.v1',
                  'sanitizer_version': 'flutter-local-manual-v1',
                  'safe_to_upload': true,
                  'requires_confirmation': true,
                  'sensitive_types': const <String>[],
                  'region_count': sanitized.maskCount,
                  'face_detected': false,
                  'qr_detected': false,
                  'barcode_detected': false,
                  'blocked_reasons': const <String>[],
                },
              );
        } on CaptureApiException catch (error) {
          if (!mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(error.message),
              behavior: SnackBarBehavior.floating,
            ),
          );
          return;
        }
      }
      if (!mounted) return;
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (context) => OcrConfirmationScreen(
            imageBytes: sanitized.bytes,
            uploadReceipt: uploadReceipt,
            captureClient: widget.captureClient,
          ),
        ),
      );
    } on PlatformException {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('暂时无法打开图片入口，请稍后再试。'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (mounted) setState(() => _isPicking = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 900;
            return SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(
                compact ? 22 : 52,
                compact ? 22 : 36,
                compact ? 22 : 52,
                compact ? 22 : 36,
              ),
              child: Column(
                children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: () => Navigator.of(context).pop(),
                      icon: const Icon(Icons.arrow_back_rounded),
                      label: const Text('返回学习桌'),
                      style: TextButton.styleFrom(
                        foregroundColor: _mint,
                        textStyle: const TextStyle(fontSize: 17),
                      ),
                    ),
                  ),
                  SizedBox(height: compact ? 18 : 34),
                  Icon(
                    Icons.camera_alt_outlined,
                    color: _mint,
                    size: compact ? 54 : 72,
                  ),
                  const SizedBox(height: 18),
                  Text('拍题', style: _titleStyle(compact ? 30 : 40)),
                  const SizedBox(height: 10),
                  const Text(
                    '拍清楚题目，先确认识别结果，再开始学习。',
                    style: TextStyle(color: _muted, fontSize: 18),
                    textAlign: TextAlign.center,
                  ),
                  SizedBox(height: compact ? 30 : 48),
                  ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 720),
                    child: Row(
                      children: [
                        Expanded(
                          child: _CaptureChoiceButton(
                            icon: Icons.camera_alt_outlined,
                            label: '拍照',
                            onPressed: _isPicking
                                ? null
                                : () => _pickImage(ImageSource.camera),
                          ),
                        ),
                        const SizedBox(width: 18),
                        Expanded(
                          child: _CaptureChoiceButton(
                            icon: Icons.photo_library_outlined,
                            label: '从相册选择',
                            onPressed: _isPicking
                                ? null
                                : () => _pickImage(ImageSource.gallery),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 22),
                  TextButton(
                    onPressed: _isPicking
                        ? null
                        : () => Navigator.of(context).push(
                            MaterialPageRoute<void>(
                              builder: (context) =>
                                  const OcrConfirmationScreen(),
                            ),
                          ),
                    style: TextButton.styleFrom(
                      foregroundColor: _deepGreen,
                      textStyle: const TextStyle(fontSize: 17),
                    ),
                    child: const Text('使用示例题目'),
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}

class _CaptureChoiceButton extends StatelessWidget {
  const _CaptureChoiceButton({
    required this.icon,
    required this.label,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton.icon(
      onPressed: onPressed,
      icon: Icon(icon, size: 30),
      label: Text(label),
      style: OutlinedButton.styleFrom(
        foregroundColor: _mint,
        side: const BorderSide(color: _mint, width: 1.5),
        minimumSize: const Size.fromHeight(76),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        textStyle: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class TutorHintScreen extends StatefulWidget {
  const TutorHintScreen({super.key});

  @override
  State<TutorHintScreen> createState() => _TutorHintScreenState();
}

class _TutorHintScreenState extends State<TutorHintScreen> {
  int _hintLevel = 0;
  bool _thoughtStarted = false;

  void _shareThought() {
    setState(() => _thoughtStarted = true);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('很好，先说说你准备从哪一步开始。'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _showHint() {
    setState(() => _hintLevel = (_hintLevel + 1).clamp(1, 3).toInt());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            _buildPracticeHeader(),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final compact = constraints.maxWidth < 900;
                  return SingleChildScrollView(
                    padding: EdgeInsets.fromLTRB(
                      compact ? 20 : 36,
                      compact ? 20 : 28,
                      compact ? 20 : 36,
                      compact ? 20 : 14,
                    ),
                    child: compact
                        ? _buildCompactContent()
                        : _buildWideContent(),
                  );
                },
              ),
            ),
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              style: TextButton.styleFrom(
                foregroundColor: _deepGreen,
                textStyle: const TextStyle(
                  fontSize: 17,
                  decoration: TextDecoration.underline,
                  decorationStyle: TextDecorationStyle.dashed,
                ),
              ),
              child: const Text('暂时跳过'),
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }

  Widget _buildPracticeHeader() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(38, 20, 38, 18),
      decoration: const BoxDecoration(
        color: _surface,
        border: Border(bottom: BorderSide(color: _border)),
      ),
      child: Row(
        children: [
          const Icon(Icons.eco_rounded, color: _mint, size: 42),
          const SizedBox(width: 14),
          Text('小禾的数学练习', style: _titleStyle(29)),
          const Spacer(),
          RichText(
            text: const TextSpan(
              style: TextStyle(color: _deepGreen, fontSize: 22),
              children: [
                TextSpan(text: '第 '),
                TextSpan(
                  text: '2',
                  style: TextStyle(
                    color: _mint,
                    fontSize: 30,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                TextSpan(text: ' 题 / 4 题'),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWideContent() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(child: _buildQuestionCard(compact: false)),
        const SizedBox(width: 18),
        Expanded(child: _buildHintCard(compact: false)),
      ],
    );
  }

  Widget _buildCompactContent() {
    return Column(
      children: [
        _buildQuestionCard(compact: true),
        const SizedBox(height: 18),
        _buildHintCard(compact: true),
      ],
    );
  }

  Widget _buildQuestionCard({required bool compact}) {
    return Container(
      padding: EdgeInsets.fromLTRB(
        compact ? 22 : 34,
        compact ? 22 : 30,
        compact ? 22 : 34,
        compact ? 24 : 30,
      ),
      decoration: BoxDecoration(
        color: _surface,
        border: Border.all(color: const Color(0xFFF0EDE5)),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        children: [
          Align(
            alignment: Alignment.center,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
              decoration: BoxDecoration(
                color: _lightMint,
                borderRadius: BorderRadius.circular(24),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.lightbulb_outline_rounded,
                    color: _deepGreen,
                    size: 25,
                  ),
                  SizedBox(width: 9),
                  Text(
                    '先自己想一想',
                    style: TextStyle(
                      color: _deepGreen,
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
          SizedBox(height: compact ? 34 : 72),
          _FractionEquation(compact: compact),
          SizedBox(height: compact ? 34 : 72),
        ],
      ),
    );
  }

  Widget _buildHintCard({required bool compact}) {
    final prompt = switch (_hintLevel) {
      0 => '两个分母一样吗？如果不一样，\n可以先做什么？',
      1 => '先说一说：题目告诉了我们什么？\n最后要找什么？',
      2 => '把 4 和 8 变成同一个分母，\n你准备先写哪一步？',
      _ => '完成算式后检查一下：\n答案真的回答了题目吗？',
    };
    return Container(
      padding: EdgeInsets.fromLTRB(
        compact ? 22 : 42,
        compact ? 22 : 34,
        compact ? 22 : 42,
        compact ? 24 : 38,
      ),
      decoration: BoxDecoration(
        color: const Color(0xFFF3FAF6),
        border: Border.all(color: const Color(0xFFE7F1EA)),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildPracticeTabs(),
          SizedBox(height: compact ? 28 : 58),
          Row(
            children: [
              const Icon(Icons.cloud_rounded, color: _mint, size: 42),
              const SizedBox(width: 14),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('先想一想', style: _titleStyle(compact ? 28 : 34)),
                  const SizedBox(height: 7),
                  Container(
                    width: compact ? 142 : 190,
                    height: 4,
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFC94D),
                      borderRadius: BorderRadius.circular(4),
                    ),
                  ),
                ],
              ),
            ],
          ),
          SizedBox(height: compact ? 26 : 40),
          Text(
            _thoughtStarted ? '你准备先从哪一步开始？' : prompt,
            style: TextStyle(
              color: _deepGreen,
              fontSize: compact ? 21 : 25,
              height: 1.55,
              fontWeight: FontWeight.w500,
            ),
          ),
          SizedBox(height: compact ? 26 : 42),
          _HintActionButton(
            icon: Icons.psychology_outlined,
            label: _thoughtStarted ? '继续说下去' : '我想到了',
            onPressed: _shareThought,
            background: const Color(0xFFEAF7F0),
            borderColor: const Color(0xFFB5DCC9),
          ),
          const SizedBox(height: 18),
          _HintActionButton(
            icon: Icons.search_rounded,
            label: '再给一点提示',
            onPressed: _showHint,
            background: const Color(0xFFFFFBF0),
            borderColor: const Color(0xFFFFD979),
            iconColor: const Color(0xFFD89E00),
          ),
        ],
      ),
    );
  }

  Widget _buildPracticeTabs() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Text('题目', style: TextStyle(color: _muted, fontSize: 18)),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: Text('•', style: TextStyle(color: _muted, fontSize: 20)),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 9),
          decoration: BoxDecoration(
            color: _surface,
            border: Border.all(color: _mint, width: 1.5),
            borderRadius: BorderRadius.circular(24),
          ),
          child: const Text(
            '思考',
            style: TextStyle(
              color: _deepGreen,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 20),
          child: Text('•', style: TextStyle(color: _muted, fontSize: 20)),
        ),
        const Text('记录', style: TextStyle(color: _muted, fontSize: 18)),
      ],
    );
  }
}

class _FractionEquation extends StatelessWidget {
  const _FractionEquation({required this.compact});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    final size = compact ? 64.0 : 82.0;
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _FractionTerm(numerator: '3', denominator: '4', size: size),
        _EquationOperator('+', size: size * 0.72),
        _FractionTerm(numerator: '1', denominator: '8', size: size),
        _EquationOperator('=', size: size * 0.72),
        Text(
          '?',
          style: TextStyle(
            color: _deepGreen,
            fontSize: size * 1.35,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

class _FractionTerm extends StatelessWidget {
  const _FractionTerm({
    required this.numerator,
    required this.denominator,
    required this.size,
  });

  final String numerator;
  final String denominator;
  final double size;

  @override
  Widget build(BuildContext context) {
    final textStyle = TextStyle(
      color: _deepGreen,
      fontSize: size,
      height: 0.95,
      fontWeight: FontWeight.w500,
    );
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(numerator, style: textStyle),
        Container(
          width: size * 1.08,
          height: 3,
          margin: const EdgeInsets.symmetric(vertical: 7),
          color: _deepGreen,
        ),
        Text(denominator, style: textStyle),
      ],
    );
  }
}

class _EquationOperator extends StatelessWidget {
  const _EquationOperator(this.symbol, {required this.size});

  final String symbol;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 22),
      child: Text(
        symbol,
        style: TextStyle(
          color: _deepGreen,
          fontSize: size,
          fontWeight: FontWeight.w400,
        ),
      ),
    );
  }
}

class _HintActionButton extends StatelessWidget {
  const _HintActionButton({
    required this.icon,
    required this.label,
    required this.onPressed,
    required this.background,
    required this.borderColor,
    this.iconColor = _deepGreen,
  });

  final IconData icon;
  final String label;
  final VoidCallback onPressed;
  final Color background;
  final Color borderColor;
  final Color iconColor;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton.icon(
        onPressed: onPressed,
        icon: Icon(icon, color: iconColor, size: 38),
        label: Text(label),
        style: OutlinedButton.styleFrom(
          backgroundColor: background,
          foregroundColor: _deepGreen,
          side: BorderSide(color: borderColor, width: 1.5),
          minimumSize: const Size.fromHeight(82),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
          textStyle: const TextStyle(fontSize: 24, fontWeight: FontWeight.w600),
        ),
      ),
    );
  }
}

class OcrConfirmationScreen extends StatefulWidget {
  const OcrConfirmationScreen({
    super.key,
    this.imagePath,
    this.imageBytes,
    this.uploadReceipt,
    this.captureClient,
  });

  final String? imagePath;
  final Uint8List? imageBytes;
  final CaptureUploadReceipt? uploadReceipt;
  final CaptureApiClient? captureClient;

  @override
  State<OcrConfirmationScreen> createState() => _OcrConfirmationScreenState();
}

class _OcrConfirmationScreenState extends State<OcrConfirmationScreen> {
  late final TextEditingController _textController;
  bool _editing = false;
  bool _confirmed = false;
  bool _remoteLoading = false;
  bool _confirming = false;
  String? _resultId;
  String? _candidateId;
  String? _remoteMessage;

  bool get _remotePending =>
      widget.uploadReceipt?.hasRemoteOcr == true && _candidateId == null;

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController(
      text: widget.uploadReceipt == null
          ? '3 + 4 = ?'
          : (widget.uploadReceipt!.hasRemoteOcr
                ? '等待本地 OCR 结果'
                : '请检查题目并填写题目内容'),
    );
    if (widget.uploadReceipt?.hasRemoteOcr == true) {
      Future<void>.microtask(_loadRemoteOcr);
    }
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  void _editText() {
    if (_remotePending || _confirming) return;
    setState(() {
      _editing = true;
      _confirmed = false;
    });
    _textController.selection = TextSelection(
      baseOffset: 0,
      extentOffset: _textController.text.length,
    );
  }

  Future<void> _loadRemoteOcr() async {
    final receipt = widget.uploadReceipt;
    final client = widget.captureClient;
    if (receipt == null || client == null) return;
    if (mounted) {
      setState(() {
        _remoteLoading = true;
        _remoteMessage = '正在等待本地 OCR 结果……';
      });
    }
    try {
      final payload = await client.waitForOcrResult(
        receipt,
        timeout: const Duration(seconds: 15),
      );
      if (!mounted) return;
      if (payload == null) {
        setState(() {
          _remoteLoading = false;
          _remoteMessage = '本地 OCR 仍在处理中，请稍后重试。';
        });
        return;
      }
      final result = payload['result'];
      final candidates = payload['candidates'];
      if (result is! Map || candidates is! List || candidates.isEmpty) {
        setState(() {
          _remoteLoading = false;
          _remoteMessage = 'OCR 没有返回候选，请稍后重试。';
        });
        return;
      }
      final candidate = candidates.first;
      if (candidate is! Map) {
        setState(() {
          _remoteLoading = false;
          _remoteMessage = 'OCR 候选暂时无法读取，请稍后重试。';
        });
        return;
      }
      final resultId = result['id']?.toString();
      final candidateId = candidate['id']?.toString();
      final text = candidate['text']?.toString().trim();
      if (resultId == null ||
          resultId.isEmpty ||
          candidateId == null ||
          candidateId.isEmpty ||
          text == null ||
          text.isEmpty) {
        setState(() {
          _remoteLoading = false;
          _remoteMessage = 'OCR 候选暂时无法确认，请稍后重试。';
        });
        return;
      }
      setState(() {
        _remoteLoading = false;
        _resultId = resultId;
        _candidateId = candidateId;
        _textController.text = text;
        _remoteMessage = '识别结果已返回，请人工确认。';
      });
    } on CaptureApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _remoteLoading = false;
        _remoteMessage = error.message;
      });
    }
  }

  Future<void> _confirmText() async {
    final receipt = widget.uploadReceipt;
    if (receipt != null) {
      if (_remotePending || widget.captureClient == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('本地 OCR 仍在处理中，请稍候再确认。'),
            behavior: SnackBarBehavior.floating,
          ),
        );
        return;
      }
      if (_confirming) return;
      if (_textController.text.trim().isEmpty) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('请先填写题目，再继续。'),
            behavior: SnackBarBehavior.floating,
          ),
        );
        return;
      }
      setState(() => _confirming = true);
      try {
        if (_editing || receipt.hasRemoteOcr == false || _candidateId == null) {
          await widget.captureClient!.correctCapture(
            receipt: receipt,
            correctedText: _textController.text.trim(),
          );
        } else {
          await widget.captureClient!.confirmOcrCandidate(
            receipt: receipt,
            resultId: _resultId!,
            candidateId: _candidateId!,
          );
        }
        if (!mounted) return;
        FocusManager.instance.primaryFocus?.unfocus();
        setState(() {
          _confirming = false;
          _editing = false;
          _confirmed = true;
          _remoteMessage = '题目已确认，可以开始学习。';
        });
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('题目已确认，可以开始学习。'),
            behavior: SnackBarBehavior.floating,
          ),
        );
      } on CaptureApiException catch (error) {
        if (!mounted) return;
        setState(() => _confirming = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error.message),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
      return;
    }
    if (_textController.text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('请先填写题目，再继续。'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      _editing = false;
      _confirmed = true;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('题目已确认，可以开始学习。'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: RepaintBoundary(
        key: const ValueKey('ocr-confirmation'),
        child: SafeArea(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final compact = constraints.maxWidth < 900;
              return SingleChildScrollView(
                padding: EdgeInsets.fromLTRB(
                  compact ? 20 : 38,
                  compact ? 20 : 28,
                  compact ? 20 : 38,
                  compact ? 20 : 24,
                ),
                child: Column(
                  children: [
                    _buildProgress(compact),
                    SizedBox(height: compact ? 22 : 34),
                    if (compact)
                      _buildCompactContent()
                    else
                      _buildWideContent(),
                    const SizedBox(height: 20),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(Icons.arrow_back_rounded),
                        label: const Text('返回拍题'),
                        style: TextButton.styleFrom(
                          foregroundColor: _mint,
                          textStyle: const TextStyle(fontSize: 17),
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildProgress(bool compact) {
    return Row(
      children: [
        Expanded(child: _StepItem(label: '拍题', number: 1, done: true)),
        _StepLine(active: !_confirmed, compact: compact),
        Expanded(
          child: _StepItem(
            label: '确认题目',
            number: 2,
            active: !_confirmed,
            done: _confirmed,
          ),
        ),
        _StepLine(active: _confirmed, compact: compact),
        Expanded(
          child: _StepItem(label: '开始学习', number: 3, active: _confirmed),
        ),
      ],
    );
  }

  Widget _buildWideContent() {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(flex: 5, child: _buildPhotoPanel()),
        const SizedBox(width: 52),
        Expanded(flex: 6, child: _buildReviewPanel()),
      ],
    );
  }

  Widget _buildCompactContent() {
    return Column(
      children: [
        _buildPhotoPanel(),
        const SizedBox(height: 24),
        _buildReviewPanel(),
      ],
    );
  }

  Widget _buildPhotoPanel() {
    return Container(
      padding: const EdgeInsets.fromLTRB(22, 22, 22, 24),
      decoration: BoxDecoration(
        color: _surface,
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.uploadReceipt != null
                ? '题目照片已上传'
                : (widget.imagePath == null ? '题目照片（示例）' : '已选择题目照片'),
            style: _titleStyle(20),
          ),
          const SizedBox(height: 18),
          Container(
            height: 520,
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFF7F5EE),
              borderRadius: BorderRadius.circular(18),
            ),
            child: DecoratedBox(
              decoration: BoxDecoration(
                border: Border.all(color: _mint, width: 2),
                borderRadius: BorderRadius.circular(14),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: widget.imageBytes != null
                    ? Image.memory(widget.imageBytes!, fit: BoxFit.contain)
                    : widget.imagePath == null
                    ? Image.asset(
                        'assets/ui/synthetic_math_photo.png',
                        fit: BoxFit.cover,
                      )
                    : Image.file(File(widget.imagePath!), fit: BoxFit.cover),
              ),
            ),
          ),
          if (widget.uploadReceipt != null) ...[
            const SizedBox(height: 14),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: _lightMint,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Text(
                widget.uploadReceipt!.hasRemoteOcr
                    ? '已完成私有上传，OCR 任务已排队（${widget.uploadReceipt!.ocrJobStatus}）。'
                    : '已完成私有上传；视觉解析尚未启用，请人工填写并确认题目。',
                style: const TextStyle(
                  color: _deepGreen,
                  fontSize: 15,
                  height: 1.4,
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildReviewPanel() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('先确认题目', style: _titleStyle(40)),
        const SizedBox(height: 12),
        Text(
          _remotePending
              ? '请看一眼，识别结果是否正确？'
              : (widget.uploadReceipt == null ||
                        widget.uploadReceipt!.hasRemoteOcr == false
                    ? '请检查照片并填写题目内容。'
                    : '识别候选已返回，请人工确认后再开始学习。'),
          style: const TextStyle(color: _deepGreen, fontSize: 18, height: 1.4),
        ),
        const SizedBox(height: 28),
        TextField(
          controller: _textController,
          readOnly: _remotePending || !_editing,
          onTap: _editing ? null : _editText,
          style: const TextStyle(
            color: _deepGreen,
            fontSize: 32,
            fontWeight: FontWeight.w600,
          ),
          decoration: InputDecoration(
            filled: true,
            fillColor: _surface,
            suffixIcon: IconButton(
              onPressed: _remotePending || _confirming ? null : _editText,
              icon: const Icon(Icons.edit_outlined, size: 28),
              color: _mint,
              tooltip: '重新修改',
            ),
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 24,
              vertical: 18,
            ),
            enabledBorder: _inputBorder(_mint),
            focusedBorder: _inputBorder(_mint, width: 2),
            border: _inputBorder(_mint),
          ),
        ),
        const SizedBox(height: 18),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 28,
              height: 28,
              decoration: const BoxDecoration(
                color: _coral,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.priority_high_rounded,
                color: Colors.white,
                size: 20,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _remotePending ? '等待识别结果' : (_confirmed ? '已确认' : '需要你确认'),
                    style: const TextStyle(
                      color: _coral,
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _remotePending
                        ? (_remoteMessage ?? '本地 OCR 完成后仍需你人工确认，系统不会直接代答。')
                        : (_confirmed
                              ? '这只是识别候选，接下来会进入学习步骤。'
                              : 'AI 识别可能出错，请仔细核对后再继续。'),
                    style: const TextStyle(
                      color: _muted,
                      fontSize: 15,
                      height: 1.45,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 34),
        SizedBox(
          width: double.infinity,
          child: FilledButton(
            onPressed: _remotePending || _confirming ? null : _confirmText,
            style: _filledButtonStyle(),
            child: Text(
              _remotePending
                  ? (_remoteLoading ? '正在识别……' : '等待识别结果')
                  : (_editing ? '保存修改' : '确认题目'),
            ),
          ),
        ),
        Center(
          child: TextButton(
            onPressed: _remotePending || _confirming ? null : _editText,
            style: TextButton.styleFrom(
              foregroundColor: _mint,
              textStyle: const TextStyle(fontSize: 17),
            ),
            child: const Text('重新修改'),
          ),
        ),
      ],
    );
  }
}

class _StepItem extends StatelessWidget {
  const _StepItem({
    required this.label,
    required this.number,
    this.active = false,
    this.done = false,
  });

  final String label;
  final int number;
  final bool active;
  final bool done;

  @override
  Widget build(BuildContext context) {
    final color = active || done ? _mint : _muted;
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: done ? _mint : (active ? _surface : Colors.transparent),
            border: Border.all(color: color, width: 1.5),
            shape: BoxShape.circle,
          ),
          child: Center(
            child: done
                ? const Icon(Icons.check_rounded, color: Colors.white, size: 24)
                : Text(
                    '$number',
                    style: TextStyle(
                      color: color,
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          label,
          style: TextStyle(
            color: color,
            fontSize: 16,
            fontWeight: active ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
      ],
    );
  }
}

class _StepLine extends StatelessWidget {
  const _StepLine({required this.active, required this.compact});

  final bool active;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        height: 2,
        margin: EdgeInsets.symmetric(horizontal: compact ? 4 : 12),
        color: active ? _mint : _border,
      ),
    );
  }
}

OutlineInputBorder _inputBorder(Color color, {double width = 1.5}) =>
    OutlineInputBorder(
      borderRadius: BorderRadius.circular(18),
      borderSide: BorderSide(color: color, width: width),
    );

class _FractionIllustration extends StatelessWidget {
  const _FractionIllustration({this.height = 270});

  final double height;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFFF5FBF7),
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Image.asset(
        'assets/ui/fraction_addition.png',
        fit: BoxFit.contain,
      ),
    );
  }
}

class _OnlinePill extends StatelessWidget {
  const _OnlinePill();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
      decoration: BoxDecoration(
        color: _lightMint,
        borderRadius: BorderRadius.circular(22),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.circle, color: _mint, size: 11),
          SizedBox(width: 8),
          Text('在线', style: TextStyle(color: _deepGreen, fontSize: 16)),
        ],
      ),
    );
  }
}

class _UnavailableScreen extends StatelessWidget {
  const _UnavailableScreen();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off_rounded, color: _muted, size: 48),
            const SizedBox(height: 16),
            Text('API 尚未连接', style: _titleStyle(24)),
            const SizedBox(height: 8),
            const Text(
              '连接后就能看到今天的数学小任务。',
              style: TextStyle(color: _muted, fontSize: 16),
            ),
          ],
        ),
      ),
    );
  }
}

TextStyle _titleStyle(double size) => TextStyle(
  color: _deepGreen,
  fontSize: size,
  fontWeight: FontWeight.w700,
  height: 1.15,
  letterSpacing: -0.3,
);

ButtonStyle _filledButtonStyle() => FilledButton.styleFrom(
  backgroundColor: _mint,
  foregroundColor: Colors.white,
  disabledBackgroundColor: _lightMint,
  disabledForegroundColor: _muted,
  minimumSize: const Size.fromHeight(72),
  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
  textStyle: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
);
