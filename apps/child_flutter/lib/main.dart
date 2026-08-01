import 'dart:convert';
import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

import 'capture_api_client.dart';
import 'auth_client.dart';
import 'english_practice.dart';
import 'privacy_sanitization_preview.dart';
import 'startup_transition.dart';

// Task recommendations remain available to parents but are not child-facing
// until their execution flow can present the assigned exercise directly.
const _todayTaskEntryVisible = false;

typedef ChildrenLoader = Future<List<Map<String, dynamic>>> Function();
typedef ChildLoginAction =
    Future<ChildLoginResult> Function(
      String baseUrl,
      String username,
      String password,
    );
typedef ChildPasswordChangeAction =
    Future<String> Function(
      String baseUrl,
      String token,
      String currentPassword,
      String newPassword,
    );
typedef ChildSessionStatusAction =
    Future<ChildSessionInfo> Function(String baseUrl, String token);
typedef ChildServiceHealthAction = Future<void> Function(String baseUrl);
typedef ChildLoggedIn =
    void Function(
      String baseUrl,
      String token,
      bool mustChangePassword,
      String username,
      String householdId,
    );

Future<List<Map<String, dynamic>>> loadChildrenWithToken(
  String baseUrl,
  String token,
  String householdId,
) async {
  if (token.isEmpty) return [];
  final client = HttpClient();
  try {
    final request = await client.getUrl(
      Uri.parse('$baseUrl/households/$householdId/children'),
    );
    request.headers.set('Authorization', 'Bearer $token');
    final response = await request.close();
    if (response.statusCode == HttpStatus.unauthorized) {
      throw const ChildSessionExpiredException();
    }
    if (response.statusCode != HttpStatus.ok) {
      throw const ChildAuthException('暂时无法读取孩子档案，请稍后重试。');
    }
    final payload = jsonDecode(await response.transform(utf8.decoder).join());
    if (payload is! List) {
      throw const ChildAuthException('服务端返回了无法识别的档案数据。');
    }
    return payload.whereType<Map>().map(Map<String, dynamic>.from).toList();
  } on ChildAuthException {
    rethrow;
  } on Object catch (error, stackTrace) {
    logChildNetworkFailure(
      operation: 'load_children',
      baseUrl: baseUrl,
      error: error,
      stackTrace: stackTrace,
    );
    throw ChildAuthException(childNetworkFailureMessage(baseUrl, error));
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
    this.passwordChangeAction,
    this.sessionStatusAction,
  });

  final ChildrenLoader? loadChildren;
  final ChildAuthStore? authStore;
  final ChildLoginAction? loginAction;
  final ChildPasswordChangeAction? passwordChangeAction;
  final ChildSessionStatusAction? sessionStatusAction;

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
          ? ChildAuthGate(
              store: authStore,
              loginAction: loginAction,
              passwordChangeAction: passwordChangeAction,
              sessionStatusAction: sessionStatusAction,
            )
          : StartupTransition(
              child: ChildProfileScreen(loadChildren: loadChildren!),
            ),
    );
  }
}

class ChildAuthGate extends StatefulWidget {
  const ChildAuthGate({
    super.key,
    this.store,
    this.loginAction,
    this.passwordChangeAction,
    this.sessionStatusAction,
  });

  final ChildAuthStore? store;
  final ChildLoginAction? loginAction;
  final ChildPasswordChangeAction? passwordChangeAction;
  final ChildSessionStatusAction? sessionStatusAction;

  @override
  State<ChildAuthGate> createState() => _ChildAuthGateState();
}

class _ChildAuthGateState extends State<ChildAuthGate> {
  late final ChildAuthStore _store;
  String _serverBaseUrl = defaultServerBaseUrl;
  String? _token;
  String? _username;
  String? _householdId;
  bool _mustChangePassword = false;
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
    String? username;
    String? householdId;
    var mustChangePassword = false;
    try {
      final savedServerBaseUrl = await _store.readServerBaseUrl();
      if (savedServerBaseUrl != null && savedServerBaseUrl.isNotEmpty) {
        serverBaseUrl = normalizeServerBaseUrl(savedServerBaseUrl);
      }
      token = await _store.readSessionToken();
      if (token != null && token.isNotEmpty) {
        final accounts = await _store.readSavedAccounts();
        for (final account in accounts) {
          if (account.sessionToken == token) {
            username = account.username;
            break;
          }
        }
        try {
          final session =
              await (widget.sessionStatusAction ?? _sessionStatusWithClient)(
                serverBaseUrl,
                token,
              );
          mustChangePassword = session.mustChangePassword;
          username ??= session.username;
          householdId = session.householdId;
          await _store.saveAccount(
            ChildSavedAccount(
              username: username,
              serverBaseUrl: serverBaseUrl,
              sessionToken: token,
            ),
          );
        } on ChildSessionExpiredException {
          await _store.clearSessionToken();
          token = null;
        } on ChildAuthException {
          // Keep the revocable session during a temporary network outage. The
          // profile screen will show its retryable unavailable state.
        }
      }
    } on ChildAuthException {
      await _store.clearSessionToken();
    } on Object {
      token = null;
    }
    if (!mounted) return;
    setState(() {
      _serverBaseUrl = serverBaseUrl;
      _token = token;
      _username = username;
      _householdId = householdId;
      _mustChangePassword = mustChangePassword;
      _loading = false;
    });
  }

  Future<void> _changeServer() async {
    await _store.clearSessionToken();
    if (!mounted) return;
    setState(() {
      _token = null;
      _username = null;
      _householdId = null;
      _mustChangePassword = false;
    });
  }

  Future<void> _logout() async {
    await _store.clearSessionToken();
    if (!mounted) return;
    setState(() {
      _token = null;
      _username = null;
      _householdId = null;
      _mustChangePassword = false;
    });
  }

  Future<void> _addAccount() async {
    await _store.clearSessionToken();
    if (!mounted) return;
    setState(() {
      _token = null;
      _username = null;
      _householdId = null;
      _mustChangePassword = false;
    });
  }

  Future<void> _switchAccount(ChildSavedAccount account) async {
    await _store.saveServerBaseUrl(account.serverBaseUrl);
    await _store.writeSessionToken(account.sessionToken);
    if (!mounted) return;
    setState(() {
      _serverBaseUrl = account.serverBaseUrl;
      _token = account.sessionToken;
      _username = account.username;
      _householdId = null;
      _mustChangePassword = false;
    });
  }

  Future<void> _replaceSavedSession(String oldToken, String newToken) async {
    final accounts = await _store.readSavedAccounts();
    for (final account in accounts) {
      if (account.sessionToken == oldToken) {
        await _store.saveAccount(
          ChildSavedAccount(
            username: account.username,
            serverBaseUrl: account.serverBaseUrl,
            sessionToken: newToken,
          ),
        );
        break;
      }
    }
  }

  void _passwordChanged(String newToken) {
    final oldToken = _token;
    setState(() {
      _token = newToken;
      _mustChangePassword = false;
    });
    if (oldToken != null) unawaited(_replaceSavedSession(oldToken, newToken));
  }

  Future<ChildSessionInfo> _sessionStatusWithClient(
    String baseUrl,
    String token,
  ) => ChildAuthClient(baseUrl: baseUrl).readSessionInfo(token);

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final token = _token;
    if (token != null && token.isNotEmpty) {
      if (_mustChangePassword) {
        return ChildPasswordChangeScreen(
          baseUrl: _serverBaseUrl,
          token: token,
          store: _store,
          changeAction: widget.passwordChangeAction,
          onChanged: _passwordChanged,
          onCancel: _changeServer,
        );
      }
      return StartupTransition(
        child: ChildProfileScreen(
          loadChildren: () =>
              loadChildrenWithToken(_serverBaseUrl, token, _householdId ?? ''),
          baseUrl: _serverBaseUrl,
          authorizationToken: token,
          username: _username,
          householdId: _householdId,
          onOpenAccount: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => ChildAccountScreen(
                store: _store,
                currentToken: token,
                currentUsername: _username,
                onAddAccount: _addAccount,
                onLogout: _logout,
                onSwitchAccount: _switchAccount,
              ),
            ),
          ),
          onLogout: _logout,
        ),
      );
    }
    return ChildLoginScreen(
      initialServerBaseUrl: _serverBaseUrl,
      store: _store,
      loginAction: widget.loginAction,
      onLoggedIn:
          (baseUrl, newToken, mustChangePassword, username, householdId) =>
              setState(() {
                _serverBaseUrl = baseUrl;
                _token = newToken;
                _username = username;
                _householdId = householdId;
                _mustChangePassword = mustChangePassword;
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
    this.healthAction,
  });

  final String initialServerBaseUrl;
  final ChildAuthStore store;
  final ChildLoggedIn onLoggedIn;
  final ChildLoginAction? loginAction;
  final ChildServiceHealthAction? healthAction;

  @override
  State<ChildLoginScreen> createState() => _ChildLoginScreenState();
}

class _ChildLoginScreenState extends State<ChildLoginScreen> {
  late final TextEditingController _serverBaseUrl;
  final _username = TextEditingController();
  final _password = TextEditingController();
  bool _pending = false;
  bool _checkingService = false;
  String? _error;
  String? _serviceStatus;
  bool _serviceAvailable = false;

  @override
  void initState() {
    super.initState();
    _serverBaseUrl = TextEditingController(text: widget.initialServerBaseUrl);
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkService());
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
      final result = await (widget.loginAction ?? _loginWithClient)(
        baseUrl,
        _username.text,
        _password.text,
      );
      await widget.store.writeSessionToken(result.token);
      await widget.store.saveAccount(
        ChildSavedAccount(
          username: result.username?.isNotEmpty == true
              ? result.username!
              : _username.text.trim(),
          serverBaseUrl: baseUrl,
          sessionToken: result.token,
        ),
      );
      if (mounted) {
        widget.onLoggedIn(
          baseUrl,
          result.token,
          result.mustChangePassword,
          result.username?.isNotEmpty == true
              ? result.username!
              : _username.text.trim(),
          result.householdId,
        );
      }
    } on ChildAuthException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) setState(() => _error = '无法保存服务端配置，请重试。');
    } finally {
      if (mounted) setState(() => _pending = false);
    }
  }

  Future<void> _checkService() async {
    if (_checkingService) return;
    setState(() {
      _checkingService = true;
      _serviceStatus = '正在检测学习服务…';
      _serviceAvailable = false;
    });
    try {
      final baseUrl = normalizeServerBaseUrl(_serverBaseUrl.text);
      await (widget.healthAction ?? _healthWithClient)(baseUrl);
      if (mounted) {
        setState(() {
          _serviceStatus = '学习服务已连接';
          _serviceAvailable = true;
        });
      }
    } on ChildAuthException catch (error) {
      if (mounted) setState(() => _serviceStatus = error.message);
    } on Object {
      if (mounted) setState(() => _serviceStatus = '学习服务检测失败，请重试。');
    } finally {
      if (mounted) setState(() => _checkingService = false);
    }
  }

  Future<void> _healthWithClient(String baseUrl) =>
      ChildAuthClient(baseUrl: baseUrl).checkHealth();

  Future<ChildLoginResult> _loginWithClient(
    String baseUrl,
    String username,
    String password,
  ) => ChildAuthClient(baseUrl: baseUrl).login(username, password);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                margin: EdgeInsets.zero,
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text(
                        '登录学习桌',
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.w700,
                        ),
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
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          Icon(
                            _serviceAvailable
                                ? Icons.check_circle_outline
                                : Icons.info_outline,
                            size: 18,
                            color: _serviceAvailable ? _mint : _muted,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _serviceStatus ?? '尚未检测学习服务',
                              style: TextStyle(
                                color: _serviceAvailable ? _deepGreen : _muted,
                                fontSize: 13,
                              ),
                            ),
                          ),
                          TextButton(
                            onPressed: _checkingService ? null : _checkService,
                            child: const Text('重新检测'),
                          ),
                        ],
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
                        autocorrect: false,
                        enableSuggestions: false,
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
        ),
      ),
    );
  }
}

class ChildPasswordChangeScreen extends StatefulWidget {
  const ChildPasswordChangeScreen({
    super.key,
    required this.baseUrl,
    required this.token,
    required this.store,
    required this.onChanged,
    required this.onCancel,
    this.changeAction,
  });

  final String baseUrl;
  final String token;
  final ChildAuthStore store;
  final ValueChanged<String> onChanged;
  final VoidCallback onCancel;
  final ChildPasswordChangeAction? changeAction;

  @override
  State<ChildPasswordChangeScreen> createState() =>
      _ChildPasswordChangeScreenState();
}

class _ChildPasswordChangeScreenState extends State<ChildPasswordChangeScreen> {
  final _currentPassword = TextEditingController();
  final _newPassword = TextEditingController();
  final _confirmPassword = TextEditingController();
  bool _pending = false;
  String? _error;

  @override
  void dispose() {
    _currentPassword.dispose();
    _newPassword.dispose();
    _confirmPassword.dispose();
    super.dispose();
  }

  Future<void> _changePassword() async {
    final currentPassword = _currentPassword.text;
    final newPassword = _newPassword.text;
    if (newPassword.length < 8) {
      setState(() => _error = '新密码至少需要 8 位。');
      return;
    }
    if (newPassword == currentPassword) {
      setState(() => _error = '新密码不能与初始密码相同。');
      return;
    }
    if (newPassword != _confirmPassword.text) {
      setState(() => _error = '两次输入的新密码不一致。');
      return;
    }
    setState(() {
      _pending = true;
      _error = null;
    });
    try {
      final token = await (widget.changeAction ?? _changeWithClient)(
        widget.baseUrl,
        widget.token,
        currentPassword,
        newPassword,
      );
      await widget.store.writeSessionToken(token);
      if (mounted) widget.onChanged(token);
    } on ChildAuthException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) setState(() => _error = '无法保存新登录状态，请重试。');
    } finally {
      if (mounted) setState(() => _pending = false);
    }
  }

  Future<String> _changeWithClient(
    String baseUrl,
    String token,
    String currentPassword,
    String newPassword,
  ) => ChildAuthClient(baseUrl: baseUrl).changePassword(
    token: token,
    currentPassword: currentPassword,
    newPassword: newPassword,
  );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const Text(
                        '先设置自己的密码',
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text('首次登录需要更换家长设置的初始密码。'),
                      const SizedBox(height: 20),
                      TextField(
                        controller: _currentPassword,
                        obscureText: true,
                        autocorrect: false,
                        enableSuggestions: false,
                        decoration: const InputDecoration(labelText: '当前初始密码'),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _newPassword,
                        obscureText: true,
                        autocorrect: false,
                        enableSuggestions: false,
                        decoration: const InputDecoration(
                          labelText: '新密码',
                          helperText: '至少 8 位',
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: _confirmPassword,
                        obscureText: true,
                        autocorrect: false,
                        enableSuggestions: false,
                        decoration: const InputDecoration(labelText: '再次输入新密码'),
                      ),
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        Text(_error!, style: const TextStyle(color: _coral)),
                      ],
                      const SizedBox(height: 20),
                      FilledButton(
                        onPressed: _pending ? null : _changePassword,
                        child: Text(_pending ? '保存中…' : '保存并进入学习桌'),
                      ),
                      TextButton(
                        onPressed: _pending ? null : widget.onCancel,
                        child: const Text('返回登录'),
                      ),
                    ],
                  ),
                ),
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
    this.username,
    this.householdId,
    this.onOpenAccount,
    this.onLogout,
  });

  final ChildrenLoader loadChildren;
  final String baseUrl;
  final String? authorizationToken;
  final String? username;
  final String? householdId;
  final VoidCallback? onOpenAccount;
  final VoidCallback? onLogout;

  @override
  State<ChildProfileScreen> createState() => _ChildProfileScreenState();
}

class _ChildProfileScreenState extends State<ChildProfileScreen> {
  late Future<List<Map<String, dynamic>>> _children;

  @override
  void initState() {
    super.initState();
    _children = widget.loadChildren();
  }

  @override
  void didUpdateWidget(covariant ChildProfileScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.baseUrl != widget.baseUrl ||
        oldWidget.authorizationToken != widget.authorizationToken ||
        oldWidget.username != widget.username) {
      _children = widget.loadChildren();
    }
  }

  void _retry() => setState(() => _children = widget.loadChildren());

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('家庭 AI 学习助手'),
        actions: [
          if (widget.onOpenAccount != null)
            IconButton(
              onPressed: widget.onOpenAccount,
              tooltip: '账号',
              icon: const Icon(Icons.account_circle_outlined),
            ),
        ],
      ),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _children,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            final error = snapshot.error;
            return _UnavailableScreen(
              message: error is ChildSessionExpiredException
                  ? '登录状态已失效，请返回登录后重试。'
                  : error is ChildAuthException
                  ? error.message
                  : '暂时无法连接学习服务，请检查网络后重试。',
              onRetry: _retry,
              onChangeServer: widget.onLogout,
            );
          }
          final children = snapshot.data ?? const <Map<String, dynamic>>[];
          final child = children.isEmpty ? null : children.first;
          if (child == null) {
            return _UnavailableScreen(
              message: '当前账号没有绑定孩子档案，请先在家长端完成绑定。',
              onRetry: _retry,
              onChangeServer: widget.onLogout,
            );
          }
          final displayName = child['display_name']?.toString() ?? '小禾';
          final captureClient = _buildCaptureClient(child);
          return SubjectSelectionScreen(
            displayName: displayName,
            englishGateway: _buildEnglishClient(child),
            mathBuilder: (_) => LearningDeskScreen(
              displayName: displayName,
              username: widget.username,
              curriculumVersion:
                  child['curriculum_version']?.toString() ?? '数学练习',
              captureClient: captureClient,
            ),
          );
        },
      ),
    );
  }

  CaptureApiClient? _buildCaptureClient(Map<String, dynamic> child) {
    final childId = child['id']?.toString();
    final token = widget.authorizationToken;
    final householdId = widget.householdId;
    if (childId == null ||
        childId.isEmpty ||
        token == null ||
        token.isEmpty ||
        householdId == null ||
        householdId.isEmpty) {
      return null;
    }
    return CaptureApiClient(
      baseUrl: widget.baseUrl,
      householdId: householdId,
      childId: childId,
      authorizationToken: token,
      accountUsername: widget.username,
    );
  }

  EnglishPracticeGateway? _buildEnglishClient(Map<String, dynamic> child) {
    final childId = child['id']?.toString();
    final token = widget.authorizationToken;
    final householdId = widget.householdId;
    if (childId == null ||
        childId.isEmpty ||
        token == null ||
        token.isEmpty ||
        householdId == null ||
        householdId.isEmpty) {
      return null;
    }
    return EnglishPracticeApiClient(
      baseUrl: widget.baseUrl,
      householdId: householdId,
      childId: childId,
      authorizationToken: token,
    );
  }
}

class ChildAccountScreen extends StatefulWidget {
  const ChildAccountScreen({
    super.key,
    required this.store,
    required this.currentToken,
    this.currentUsername,
    required this.onAddAccount,
    required this.onLogout,
    required this.onSwitchAccount,
  });

  final ChildAuthStore store;
  final String currentToken;
  final String? currentUsername;
  final Future<void> Function() onAddAccount;
  final Future<void> Function() onLogout;
  final Future<void> Function(ChildSavedAccount account) onSwitchAccount;

  @override
  State<ChildAccountScreen> createState() => _ChildAccountScreenState();
}

class _ChildAccountScreenState extends State<ChildAccountScreen> {
  late Future<List<ChildSavedAccount>> _accounts;
  bool _pending = false;

  @override
  void initState() {
    super.initState();
    _accounts = widget.store.readSavedAccounts();
  }

  Future<void> _run(Future<void> Function() action, {bool close = true}) async {
    if (_pending) return;
    setState(() => _pending = true);
    try {
      await action();
      if (close && mounted) Navigator.of(context).pop();
    } on Object catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('账号操作失败，请稍后重试（${error.runtimeType}）。')),
        );
      }
    } finally {
      if (mounted) setState(() => _pending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('账号')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            Card(
              child: ListTile(
                leading: const CircleAvatar(
                  backgroundColor: _lightMint,
                  child: Icon(Icons.person_outline, color: _deepGreen),
                ),
                title: const Text('当前账号'),
                subtitle: FutureBuilder<List<ChildSavedAccount>>(
                  future: _accounts,
                  builder: (context, snapshot) {
                    ChildSavedAccount? current;
                    for (final account in snapshot.data ?? const []) {
                      if (account.sessionToken == widget.currentToken) {
                        current = account;
                        break;
                      }
                    }
                    return Text(
                      current?.username ?? widget.currentUsername ?? '尚未读取用户名',
                    );
                  },
                ),
              ),
            ),
            const SizedBox(height: 24),
            Text('切换账号', style: _titleStyle(24)),
            const SizedBox(height: 10),
            FutureBuilder<List<ChildSavedAccount>>(
              future: _accounts,
              builder: (context, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Padding(
                    padding: EdgeInsets.all(20),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                final accounts = snapshot.data ?? const <ChildSavedAccount>[];
                if (accounts.isEmpty) {
                  return const Text('暂无其他已登录账号。');
                }
                return Column(
                  children: accounts
                      .map((account) {
                        final current =
                            account.sessionToken == widget.currentToken;
                        return Card(
                          child: ListTile(
                            leading: Icon(
                              current
                                  ? Icons.check_circle
                                  : Icons.person_outline,
                              color: current ? _mint : _muted,
                            ),
                            title: Text(account.username),
                            subtitle: Text(current ? '正在使用' : '已保存登录状态'),
                            trailing: current
                                ? null
                                : TextButton(
                                    onPressed: _pending
                                        ? null
                                        : () => _run(
                                            () =>
                                                widget.onSwitchAccount(account),
                                          ),
                                    child: const Text('切换'),
                                  ),
                          ),
                        );
                      })
                      .toList(growable: false),
                );
              },
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _pending ? null : () => _run(widget.onAddAccount),
              icon: const Icon(Icons.person_add_alt_1),
              label: const Text('添加账号'),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: _pending ? null : () => _run(widget.onLogout),
              icon: const Icon(Icons.logout),
              label: const Text('注销当前账号'),
            ),
          ],
        ),
      ),
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

String _initialQuestionPrompt(String questionText) {
  if (const ['飞走', '离开', '用掉', '吃掉', '卖出', '拿走'].any(questionText.contains)) {
    return '题目里有原来的数量和减少的数量。\n每次飞走后，数量发生了什么变化？';
  }
  if (const ['多多少', '少多少', '相差', '差多少'].any(questionText.contains)) {
    return '这道题在比较两个数量。\n先找出谁多、谁少，再想怎样求相差。';
  }
  if (questionText.contains('/') || questionText.contains('分母')) {
    return '两个分母一样吗？如果不一样，\n可以先做什么？';
  }
  return '先找出题目已经告诉我们的数量，\n再说一说最后要解决什么问题。';
}

class LearningDeskScreen extends StatefulWidget {
  const LearningDeskScreen({
    super.key,
    required this.displayName,
    required this.curriculumVersion,
    this.username,
    this.captureClient,
  });

  final String displayName;
  final String curriculumVersion;
  final String? username;
  final CaptureApiClient? captureClient;

  @override
  State<LearningDeskScreen> createState() => _LearningDeskScreenState();
}

class _TaskSchedule {
  const _TaskSchedule({required this.ready, required this.next});

  const _TaskSchedule.empty() : ready = const [], next = null;

  final List<Map<String, dynamic>> ready;
  final Map<String, dynamic>? next;
}

class _LearningDeskScreenState extends State<LearningDeskScreen> {
  late Future<_TaskSchedule> _tasks;
  bool _startingTask = false;

  @override
  void initState() {
    super.initState();
    _tasks = Future.value(const _TaskSchedule.empty());
    if (_todayTaskEntryVisible) _tasks = _loadTasks();
  }

  Future<_TaskSchedule> _loadTasks() async {
    final client = widget.captureClient;
    if (client == null) return const _TaskSchedule.empty();
    final all = await client.listTasks();
    final today = DateTime.now().toIso8601String().substring(0, 10);
    final active = all
        .where(
          (task) => const {'assigned', 'in_progress'}.contains(task['status']),
        )
        .toList(growable: false);
    final ready = active
        .where((task) {
          final scheduledFor = task['scheduled_for'];
          return scheduledFor is String && scheduledFor.compareTo(today) <= 0;
        })
        .toList(growable: false);
    final later =
        active
            .where((task) {
              final scheduledFor = task['scheduled_for'];
              return scheduledFor is String &&
                  scheduledFor.compareTo(today) > 0;
            })
            .toList(growable: false)
          ..sort(
            (left, right) => (left['scheduled_for'] as String).compareTo(
              right['scheduled_for'] as String,
            ),
          );
    return _TaskSchedule(
      ready: ready,
      next: later.isEmpty ? null : later.first,
    );
  }

  void _reloadTasks() {
    setState(() {
      _tasks = _loadTasks();
    });
  }

  void _openPreviewLearning() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => TutorHintScreen(displayName: _practiceName),
      ),
    );
  }

  String get _practiceName {
    final username = widget.username?.trim();
    return username == null || username.isEmpty ? widget.displayName : username;
  }

  Future<void> _openCaptureFlow() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) =>
            CaptureInputScreen(captureClient: widget.captureClient),
      ),
    );
    if (mounted && widget.captureClient != null && _todayTaskEntryVisible) {
      _reloadTasks();
    }
  }

  Future<void> _startTask(Map<String, dynamic> task) async {
    final client = widget.captureClient;
    if (client == null) {
      _openPreviewLearning();
      return;
    }
    setState(() => _startingTask = true);
    try {
      await client.prepareTaskSession(task);
      if (mounted) await _openCaptureFlow();
    } on CaptureApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(error.message),
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _startingTask = false);
    }
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
                    _buildMathEntryStrip(compact),
                    if (_todayTaskEntryVisible) ...[
                      SizedBox(height: compact ? 18 : 24),
                      _buildTaskArea(compact),
                      const SizedBox(height: 16),
                      TextButton(
                        onPressed: _showLaterMessage,
                        style: TextButton.styleFrom(foregroundColor: _coral),
                        child: const Text(
                          '稍后再做',
                          style: TextStyle(fontSize: 16),
                        ),
                      ),
                    ],
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildMathEntryStrip(bool compact) {
    final client = widget.captureClient;
    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(compact ? 14 : 18),
      decoration: BoxDecoration(
        color: _surface,
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(24),
      ),
      child: Row(
        children: [
          Expanded(
            child: _MathEntryButton(
              icon: Icons.psychology_outlined,
              label: '错题讲解',
              caption: '拍题后分步思考',
              onPressed: _openCaptureFlow,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: _MathEntryButton(
              icon: Icons.replay_rounded,
              label: '复习错题',
              caption: '到期或提前复习',
              onPressed: client == null
                  ? null
                  : () => Navigator.of(context).push(
                      MaterialPageRoute<void>(
                        builder: (_) => DueMistakesScreen(client: client),
                      ),
                    ),
            ),
          ),
          if (_todayTaskEntryVisible) ...[
            const SizedBox(width: 10),
            Expanded(
              child: _MathEntryButton(
                icon: Icons.today_outlined,
                label: '今日任务',
                caption: '按今天的安排学习',
                onPressed: _reloadTasks,
              ),
            ),
          ],
        ],
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
          Text(
            _todayLabel(),
            style: TextStyle(color: _deepGreen, fontSize: 18),
          ),
          const SizedBox(width: 22),
        ],
        const _OnlinePill(),
      ],
    );
  }

  String _todayLabel() {
    final now = DateTime.now();
    const weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'];
    return '${now.year}年${now.month}月${now.day}日  ${weekdays[now.weekday - 1]}';
  }

  Widget _buildTaskArea(bool compact) {
    if (widget.captureClient == null) return _buildTaskSurface(compact, null);
    return FutureBuilder<_TaskSchedule>(
      future: _tasks,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Padding(
            padding: EdgeInsets.all(48),
            child: CircularProgressIndicator(),
          );
        }
        if (snapshot.hasError) {
          return _TaskMessageCard(
            icon: Icons.cloud_off_rounded,
            title: '暂时无法读取今天的任务',
            message: '检查网络后可以重试，已经完成的学习记录不会丢失。',
            actionLabel: '重新加载',
            onPressed: _reloadTasks,
          );
        }
        final schedule = snapshot.data ?? const _TaskSchedule.empty();
        if (schedule.ready.isEmpty) {
          final next = schedule.next;
          if (next != null) {
            return _TaskMessageCard(
              icon: Icons.event_available_outlined,
              title: '下一项任务已安排',
              message:
                  '${next['title'] ?? '数学练习'}将在 ${_taskDateLabel(next['scheduled_for'])} 出现在今日任务。今天可以拍题或复习错题。',
              actionLabel: '拍题开始',
              onPressed: _openCaptureFlow,
            );
          }
          return _TaskMessageCard(
            icon: Icons.camera_alt_outlined,
            title: '今天还没有安排任务',
            message: '可以直接拍一道题，识别并确认后开始学习。',
            actionLabel: '拍题开始',
            onPressed: _openCaptureFlow,
          );
        }
        return Column(
          children: [
            for (var index = 0; index < schedule.ready.length; index++) ...[
              if (index > 0) const SizedBox(height: 16),
              _buildTaskSurface(compact, schedule.ready[index]),
            ],
          ],
        );
      },
    );
  }

  String _taskDateLabel(Object? value) {
    if (value is! String) return '计划日';
    final date = DateTime.tryParse(value);
    return date == null ? value : '${date.month}月${date.day}日';
  }

  Widget _buildTaskSurface(bool compact, Map<String, dynamic>? task) {
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
              Expanded(
                child: Text(
                  '今天的数学小任务',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: _titleStyle(compact ? 25 : 29),
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          const Divider(color: _border, height: 1),
          const SizedBox(height: 34),
          if (compact)
            _buildCompactTaskBody(task)
          else
            _buildWideTaskBody(task),
        ],
      ),
    );
  }

  Widget _buildWideTaskBody(Map<String, dynamic>? task) {
    if (task != null) {
      return Column(
        children: [
          _buildTaskDetails(task),
          const SizedBox(height: 30),
          _buildActions(task),
        ],
      );
    }
    return Column(
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(flex: 5, child: _FractionIllustration()),
            const SizedBox(width: 46),
            Expanded(flex: 7, child: _buildTaskDetails(task)),
          ],
        ),
        const SizedBox(height: 38),
        _buildActions(task),
      ],
    );
  }

  Widget _buildCompactTaskBody(Map<String, dynamic>? task) {
    if (task != null) {
      return Column(
        children: [
          _buildTaskDetails(task),
          const SizedBox(height: 28),
          _buildActions(task),
        ],
      );
    }
    return Column(
      children: [
        _FractionIllustration(height: 180),
        const SizedBox(height: 24),
        _buildTaskDetails(task),
        const SizedBox(height: 28),
        _buildActions(task),
      ],
    );
  }

  Widget _buildTaskDetails(Map<String, dynamic>? task) {
    final isPreview = task == null;
    final title = task?['title']?.toString() ?? '分数的加法';
    final status = task?['status'] == 'in_progress' ? '进行中' : '待开始';
    final knowledgePoint = task?['knowledge_point']?.toString();
    final reason = task?['reason']?.toString();
    final estimatedMinutes = task?['estimated_minutes'];
    final exercises = task?['exercises'] is List
        ? List<Map<String, dynamic>>.from(
            (task!['exercises'] as List).map(
              (item) => Map<String, dynamic>.from(item as Map),
            ),
          )
        : const <Map<String, dynamic>>[];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: _titleStyle(38)),
        const SizedBox(height: 12),
        Text(
          isPreview
              ? '学习目标：理解同分母分数加法的算理，\n能正确计算并解决简单问题。'
              : [
                  '数学任务 · $status',
                  if (estimatedMinutes is num)
                    '预计 ${estimatedMinutes.toInt()} 分钟',
                  if (exercises.isNotEmpty) '共 ${exercises.length} 题',
                  if (knowledgePoint != null && knowledgePoint.isNotEmpty)
                    '知识点：$knowledgePoint',
                  if (reason != null && reason.isNotEmpty) reason,
                ].join('\n'),
          style: const TextStyle(color: _muted, fontSize: 18, height: 1.55),
        ),
        if (!isPreview && exercises.isNotEmpty) ...[
          const SizedBox(height: 20),
          for (var index = 0; index < exercises.length; index++) ...[
            _TaskExerciseCard(
              exercise: exercises[index],
              index: index,
              client: widget.captureClient,
            ),
            if (index < exercises.length - 1) const SizedBox(height: 10),
          ],
        ],
        const SizedBox(height: 24),
        if (isPreview)
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
        if (isPreview) const SizedBox(height: 10),
        if (isPreview)
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

  Widget _buildActions(Map<String, dynamic>? task) {
    return Row(
      children: [
        Expanded(
          flex: 5,
          child: FilledButton(
            onPressed: _startingTask
                ? null
                : () =>
                      task == null ? _openPreviewLearning() : _startTask(task),
            style: _filledButtonStyle(),
            child: Text(
              _startingTask ? '正在准备……' : (task == null ? '继续学习' : '开始任务'),
            ),
          ),
        ),
        const SizedBox(width: 24),
        Expanded(
          flex: 2,
          child: OutlinedButton.icon(
            onPressed: _startingTask ? null : _openCaptureFlow,
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

class _TaskExerciseCard extends StatelessWidget {
  const _TaskExerciseCard({
    required this.exercise,
    required this.index,
    required this.client,
  });

  final Map<String, dynamic> exercise;
  final int index;
  final CaptureApiClient? client;

  Future<void> _showOriginalPage(
    BuildContext context,
    String snapshotId,
    int pageNumber,
  ) {
    final pageClient = client;
    if (pageClient == null) return Future<void>.value();
    return showDialog<void>(
      context: context,
      builder: (context) => Dialog(
        insetPadding: const EdgeInsets.all(24),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1000, maxHeight: 760),
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '教材第 $pageNumber 页原图',
                        style: _titleStyle(24),
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.of(context).pop(),
                      tooltip: '关闭',
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Expanded(
                  child: FutureBuilder<Uint8List>(
                    future: pageClient.loadCurriculumPageImage(
                      snapshotId,
                      pageNumber,
                    ),
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Center(child: CircularProgressIndicator());
                      }
                      if (snapshot.hasError || snapshot.data == null) {
                        return const Center(
                          child: Text(
                            '暂时无法打开教材原页，请检查网络后重试。',
                            style: TextStyle(color: _muted, fontSize: 18),
                          ),
                        );
                      }
                      return InteractiveViewer(
                        minScale: 0.8,
                        maxScale: 4,
                        child: Image.memory(
                          snapshot.data!,
                          fit: BoxFit.contain,
                          gaplessPlayback: true,
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final isMistake = exercise['source_type'] == 'mistake';
    final title = exercise['source_title']?.toString();
    final page = exercise['source_page'];
    final visualDescription = exercise['visual_description']?.toString();
    final requiresVisualContext = exercise['requires_visual_context'] == true;
    final snapshotId = exercise['snapshot_id']?.toString();
    final sourceLabel = isMistake
        ? '过往错题'
        : [
            title == null || title.isEmpty ? '教材练习' : title,
            if (page is num) '第 ${page.toInt()} 页',
          ].join(' · ');
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: _lightMint.withValues(alpha: 0.58),
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '第 ${index + 1} 题 · $sourceLabel',
            style: const TextStyle(
              color: _mint,
              fontSize: 15,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            exercise['question_text']?.toString() ?? '题目内容暂不可用',
            style: const TextStyle(
              color: _deepGreen,
              fontSize: 22,
              height: 1.45,
              fontWeight: FontWeight.w600,
            ),
          ),
          if (visualDescription != null &&
              visualDescription.trim().isNotEmpty) ...[
            const SizedBox(height: 10),
            Text(
              '图形信息：$visualDescription',
              style: const TextStyle(color: _muted, fontSize: 17, height: 1.45),
            ),
          ],
          if (requiresVisualContext && page is num) ...[
            const SizedBox(height: 8),
            Text(
              '这道题依赖教材图片，请打开第 ${page.toInt()} 页原图一起看。',
              style: const TextStyle(
                color: _mint,
                fontSize: 16,
                fontWeight: FontWeight.w700,
              ),
            ),
          ],
          if (client != null &&
              snapshotId != null &&
              snapshotId.isNotEmpty &&
              page is num) ...[
            const SizedBox(height: 10),
            OutlinedButton.icon(
              onPressed: () =>
                  _showOriginalPage(context, snapshotId, page.toInt()),
              icon: const Icon(Icons.image_outlined),
              label: Text('查看教材第 ${page.toInt()} 页原图'),
            ),
          ],
        ],
      ),
    );
  }
}

class _MathEntryButton extends StatelessWidget {
  const _MathEntryButton({
    required this.icon,
    required this.label,
    required this.caption,
    required this.onPressed,
  });

  final IconData icon;
  final String label;
  final String caption;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return OutlinedButton(
      onPressed: onPressed,
      style: OutlinedButton.styleFrom(
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        foregroundColor: _deepGreen,
        side: const BorderSide(color: _border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
      ),
      child: Row(
        children: [
          Icon(icon, color: _mint, size: 26),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  caption,
                  style: const TextStyle(color: _muted, fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class DueMistakesScreen extends StatefulWidget {
  const DueMistakesScreen({super.key, required this.client});

  final CaptureApiClient client;

  @override
  State<DueMistakesScreen> createState() => _DueMistakesScreenState();
}

class _DueMistakesScreenState extends State<DueMistakesScreen> {
  late Future<List<Map<String, dynamic>>> _mistakes;
  final Map<String, TextEditingController> _answers = {};

  @override
  void initState() {
    super.initState();
    _mistakes = widget.client.listReviewMistakes();
  }

  void _reload() =>
      setState(() => _mistakes = widget.client.listReviewMistakes());

  @override
  void dispose() {
    for (final controller in _answers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _review(String id, String outcome) async {
    final answer = _answers[id]?.text.trim() ?? '';
    if (answer.isEmpty) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('请先写下这次的答案或思路，再提交复习结果。')));
      return;
    }
    try {
      await widget.client.reviewMistake(
        id,
        outcome,
        answerSummary: answer,
        submittedAnswer: answer,
        evidenceConfirmed: true,
      );
      if (mounted) _reload();
    } on CaptureApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('复习错题')),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _mistakes,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('暂时无法读取复习内容：${snapshot.error}'));
          }
          final items = snapshot.data ?? const [];
          if (items.isEmpty) {
            return const Center(child: Text('还没有可复习的错题。'));
          }
          final showingEarly = items.every((item) {
            final schedule = item['schedule'];
            if (schedule is! Map) return false;
            final dueAt = DateTime.tryParse(
              schedule['due_at']?.toString() ?? '',
            );
            return dueAt != null && dueAt.isAfter(DateTime.now());
          });
          return ListView.separated(
            padding: const EdgeInsets.all(24),
            itemCount: items.length + (showingEarly ? 1 : 0),
            separatorBuilder: (_, _) => const SizedBox(height: 14),
            itemBuilder: (context, index) {
              if (showingEarly && index == 0) {
                return const Card(
                  color: _lightMint,
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('今天暂无到期错题，下面列出全部错题，可以提前复习。'),
                  ),
                );
              }
              final item = items[index - (showingEarly ? 1 : 0)];
              final mistake = item['mistake'] is Map
                  ? Map<String, dynamic>.from(item['mistake'] as Map)
                  : const <String, dynamic>{};
              final id = mistake['id']?.toString() ?? '';
              final question = item['question'] is Map
                  ? Map<String, dynamic>.from(item['question'] as Map)
                  : const <String, dynamic>{};
              final controller = _answers.putIfAbsent(
                id,
                TextEditingController.new,
              );
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('错题复习', style: _titleStyle(22)),
                      const SizedBox(height: 8),
                      Text(
                        question['question_text']?.toString() ?? '请回忆这道题的题目内容',
                        style: const TextStyle(fontSize: 22, height: 1.4),
                      ),
                      const SizedBox(height: 8),
                      Text(mistake['reason']?.toString() ?? '再检查一次思路'),
                      const SizedBox(height: 12),
                      TextField(
                        controller: controller,
                        minLines: 2,
                        maxLines: 5,
                        decoration: const InputDecoration(
                          labelText: '重新作答或写出思路',
                          border: OutlineInputBorder(),
                        ),
                      ),
                      const SizedBox(height: 14),
                      Wrap(
                        spacing: 8,
                        children: [
                          OutlinedButton(
                            onPressed: id.isEmpty
                                ? null
                                : () => _review(id, 'correct'),
                            child: const Text('这次会了'),
                          ),
                          TextButton(
                            onPressed: id.isEmpty
                                ? null
                                : () => _review(id, 'needs_review'),
                            child: const Text('还要再想想'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
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
      final sanitization = _sanitizationMetadata(sanitized);
      if (widget.captureClient == null) {
        await Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (context) => OcrConfirmationScreen(
              imageBytes: sanitized.bytes,
              sanitization: sanitization,
            ),
          ),
        );
      } else if (mounted) {
        await Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (context) => CaptureUploadProgressScreen(
              imageBytes: sanitized.bytes,
              sanitization: sanitization,
              captureClient: widget.captureClient!,
            ),
          ),
        );
      }
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

Map<String, dynamic> _sanitizationMetadata(SanitizedImageSelection selection) =>
    {
      'schema_version': 'privacy-sanitization.v1',
      'sanitizer_version': 'flutter-local-manual-v1',
      'safe_to_upload': true,
      'requires_confirmation': true,
      'sensitive_types': const <String>[],
      'region_count': selection.maskCount,
      'face_detected': false,
      'qr_detected': false,
      'barcode_detected': false,
      'blocked_reasons': const <String>[],
    };

typedef CaptureUploadAction = Future<CaptureUploadReceipt> Function();

class CaptureUploadProgressScreen extends StatefulWidget {
  const CaptureUploadProgressScreen({
    super.key,
    required this.imageBytes,
    required this.sanitization,
    required this.captureClient,
    this.uploadAction,
  });

  final Uint8List imageBytes;
  final Map<String, dynamic> sanitization;
  final CaptureApiClient captureClient;
  final CaptureUploadAction? uploadAction;

  @override
  State<CaptureUploadProgressScreen> createState() =>
      _CaptureUploadProgressScreenState();
}

class _CaptureUploadProgressScreenState
    extends State<CaptureUploadProgressScreen> {
  bool _pending = true;
  CaptureApiException? _error;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_upload);
  }

  Future<void> _upload() async {
    if (_pending == false) setState(() => _pending = true);
    setState(() => _error = null);
    try {
      final receipt =
          await (widget.uploadAction ??
              () => widget.captureClient.uploadAndStartImageAnalysisBytes(
                widget.imageBytes,
                sanitization: widget.sanitization,
              ))();
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => OcrConfirmationScreen(
            imageBytes: widget.imageBytes,
            uploadReceipt: receipt,
            sanitization: widget.sanitization,
            captureClient: widget.captureClient,
          ),
        ),
      );
    } on CaptureApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _pending = false;
        _error = error;
      });
    } on Object {
      if (!mounted) return;
      setState(() {
        _pending = false;
        _error = const CaptureApiException('照片上传失败，请检查网络后重试。');
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: Column(
                children: [
                  Text('正在处理题目照片', style: _titleStyle(30)),
                  const SizedBox(height: 12),
                  const Text(
                    '请保持当前页面，完成后会自动进入题目确认。',
                    style: TextStyle(color: _muted, fontSize: 17),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 24),
                  SizedBox(
                    height: 260,
                    width: double.infinity,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(22),
                      child: Image.memory(
                        widget.imageBytes,
                        fit: BoxFit.contain,
                      ),
                    ),
                  ),
                  const SizedBox(height: 28),
                  if (_pending) ...[
                    const CircularProgressIndicator(color: _mint),
                    const SizedBox(height: 16),
                    const Text(
                      '照片已完成脱敏，正在安全上传并启动识别……',
                      style: TextStyle(color: _deepGreen, fontSize: 18),
                      textAlign: TextAlign.center,
                    ),
                  ] else ...[
                    const Icon(
                      Icons.cloud_off_outlined,
                      color: _coral,
                      size: 42,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _error?.message ?? '上传失败，请重试。',
                      style: const TextStyle(color: _coral, fontSize: 17),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 18),
                    FilledButton.icon(
                      onPressed: _upload,
                      icon: const Icon(Icons.refresh),
                      label: const Text('重新上传'),
                    ),
                    TextButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('返回拍题'),
                    ),
                  ],
                ],
              ),
            ),
          ),
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
  const TutorHintScreen({
    super.key,
    this.displayName = '小禾',
    this.questionText = '3/4 + 1/8 = ?',
    this.verifiedQuestionId,
    this.captureClient,
    this.answerState = 'unclear',
    this.evidenceConfirmed = false,
  });

  final String displayName;
  final String questionText;
  final String? verifiedQuestionId;
  final CaptureApiClient? captureClient;
  final String answerState;
  final bool evidenceConfirmed;

  @override
  State<TutorHintScreen> createState() => _TutorHintScreenState();
}

class _TutorHintScreenState extends State<TutorHintScreen> {
  int _hintLevel = 0;
  bool _thoughtStarted = false;
  bool _hintLoading = false;
  String? _serverPrompt;
  String? _serverNextStep;
  String? _childAction;
  List<String> _solutionSteps = const [];
  String? _finalAnswer;
  String? _verification;
  String? _hintError;
  bool _completionSaving = false;
  bool _completed = false;
  String? _completionMessage;
  late final String _answerState;
  late final bool _evidenceConfirmed;

  @override
  void initState() {
    super.initState();
    _answerState = widget.answerState;
    _evidenceConfirmed = widget.evidenceConfirmed;
    if (widget.captureClient != null && widget.verifiedQuestionId != null) {
      Future<void>.microtask(_showHint);
    }
  }

  void _shareThought() {
    setState(() => _thoughtStarted = true);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('很好，先说说你准备从哪一步开始。'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  Future<void> _showHint() async {
    if (_hintLoading) return;
    final nextLevel = (_hintLevel + 1).clamp(1, 3).toInt();
    final client = widget.captureClient;
    final verifiedQuestionId = widget.verifiedQuestionId;
    if (client == null || verifiedQuestionId == null) {
      setState(() {
        _hintLevel = nextLevel;
        _hintError = null;
      });
      return;
    }
    setState(() {
      _hintLoading = true;
      _hintError = null;
    });
    try {
      final response = await client.createTutorHint(
        verifiedQuestionId: verifiedQuestionId,
        level: nextLevel,
        mode: const {'worked', 'blank'}.contains(_answerState)
            ? 'mistake_explanation'
            : 'guided_practice',
        answerState: _answerState,
        evidenceConfirmed: _evidenceConfirmed,
      );
      if (!mounted) return;
      setState(() {
        _hintLevel = nextLevel;
        _serverPrompt = response['prompt']?.toString();
        _serverNextStep = response['next_step']?.toString();
        _childAction = response['child_action']?.toString();
        _solutionSteps =
            (response['solution_steps'] as List?)
                ?.map((item) => item.toString())
                .toList(growable: false) ??
            const [];
        _finalAnswer = response['direct_answer']?.toString();
        _verification = response['verification']?.toString();
        _hintLoading = false;
      });
    } on CaptureApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _hintLoading = false;
        _hintError = error.message;
      });
    }
  }

  Future<void> _completeSession(String outcome) async {
    if (_completionSaving || _completed) return;
    if (outcome == 'needs_review' &&
        (!_evidenceConfirmed ||
            !const {'worked', 'blank'}.contains(_answerState))) {
      setState(() {
        _hintError = '请先在确认题目时选择“有作答”或“答题区为空”，才能加入复习。';
      });
      return;
    }
    final client = widget.captureClient;
    if (client == null) {
      setState(() {
        _completed = true;
        _completionMessage = outcome == 'needs_review' ? '已加入复习清单。' : '本题已完成。';
      });
      return;
    }
    setState(() {
      _completionSaving = true;
      _hintError = null;
    });
    try {
      if (_answerState != 'unclear') {
        await client.recordAttempt(
          answerSummary: '孩子已确认本题作答状态',
          answerState: _answerState,
          evidenceConfirmed: _evidenceConfirmed,
        );
      }
      await client.completeCurrentSession(outcome: outcome);
      if (!mounted) return;
      if (outcome == 'needs_review') {
        _returnToLearningDesk();
        return;
      }
      setState(() {
        _completionSaving = false;
        _completed = true;
        _completionMessage = outcome == 'needs_review'
            ? '已完成本题，并加入复习清单。'
            : '本题已完成，家长端会看到这次进度。';
      });
    } on CaptureApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _completionSaving = false;
        _hintError = error.message;
      });
    }
  }

  void _returnToLearningDesk() {
    Navigator.of(context).popUntil((route) => route.isFirst);
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
          Expanded(
            child: Text(
              '${widget.displayName}的数学练习',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: _titleStyle(29),
            ),
          ),
          const SizedBox(width: 18),
          const Text(
            '本次第 1 题',
            style: TextStyle(
              color: _deepGreen,
              fontSize: 22,
              fontWeight: FontWeight.w600,
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
          if (widget.questionText == '3/4 + 1/8 = ?')
            _FractionEquation(compact: compact)
          else
            SelectableText(
              widget.questionText,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: _deepGreen,
                fontSize: compact ? 30 : 42,
                height: 1.45,
                fontWeight: FontWeight.w600,
              ),
            ),
          SizedBox(height: compact ? 34 : 72),
        ],
      ),
    );
  }

  Widget _buildHintCard({required bool compact}) {
    final fallbackPrompt = switch (_hintLevel) {
      0 => _initialQuestionPrompt(widget.questionText),
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
          const SizedBox(height: 18),
          _buildAnswerStatePicker(),
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
            _thoughtStarted
                ? '你准备先从哪一步开始？'
                : (_serverPrompt ??
                      (_hintLoading ? '正在根据这道题准备第一步提示……' : fallbackPrompt)),
            style: TextStyle(
              color: _deepGreen,
              fontSize: compact ? 21 : 25,
              height: 1.55,
              fontWeight: FontWeight.w500,
            ),
          ),
          if (_serverNextStep != null && !_thoughtStarted) ...[
            const SizedBox(height: 12),
            Text(
              _serverNextStep!,
              style: const TextStyle(color: _muted, fontSize: 17, height: 1.45),
            ),
          ],
          if (_childAction != null && !_thoughtStarted) ...[
            const SizedBox(height: 12),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.edit_note_rounded, color: _mint, size: 24),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _childAction!,
                    style: const TextStyle(
                      color: _deepGreen,
                      fontSize: 17,
                      height: 1.45,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ],
          if (_solutionSteps.isNotEmpty) ...[
            const SizedBox(height: 24),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: _surface,
                border: Border.all(color: const Color(0xFFB5DCC9)),
                borderRadius: BorderRadius.circular(18),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('完整解答', style: _titleStyle(24)),
                  const SizedBox(height: 14),
                  for (var index = 0; index < _solutionSteps.length; index++)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: Text(
                        '${index + 1}. ${_solutionSteps[index]}',
                        style: const TextStyle(
                          color: _deepGreen,
                          fontSize: 18,
                          height: 1.5,
                        ),
                      ),
                    ),
                  if (_finalAnswer != null) ...[
                    const Divider(height: 24),
                    Text(
                      '答案：$_finalAnswer',
                      style: const TextStyle(
                        color: _deepGreen,
                        fontSize: 20,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                  if (_verification != null) ...[
                    const SizedBox(height: 10),
                    Text(
                      '验算：$_verification',
                      style: const TextStyle(
                        color: _muted,
                        fontSize: 17,
                        height: 1.45,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ],
          if (_hintError != null) ...[
            const SizedBox(height: 12),
            Text(
              _hintError!,
              style: const TextStyle(color: _coral, fontSize: 16, height: 1.4),
            ),
          ],
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
            icon: _solutionSteps.isNotEmpty
                ? Icons.home_outlined
                : Icons.search_rounded,
            label: _hintLoading
                ? '正在准备提示……'
                : (_solutionSteps.isNotEmpty
                      ? '返回学习桌'
                      : (_hintLevel >= 2 ? '查看完整解答' : '再给一点提示')),
            onPressed: _solutionSteps.isNotEmpty
                ? _returnToLearningDesk
                : _showHint,
            background: _solutionSteps.isNotEmpty
                ? const Color(0xFFEAF7F0)
                : const Color(0xFFFFFBF0),
            borderColor: _solutionSteps.isNotEmpty
                ? const Color(0xFFB5DCC9)
                : const Color(0xFFFFD979),
            iconColor: _solutionSteps.isNotEmpty
                ? _mint
                : const Color(0xFFD89E00),
          ),
          if (_thoughtStarted) ...[
            const SizedBox(height: 18),
            _HintActionButton(
              icon: Icons.check_circle_outline_rounded,
              label: _completionSaving ? '正在保存进度……' : '我会了，完成本题',
              onPressed: () => _completeSession('learned'),
              background: const Color(0xFFEAF7F0),
              borderColor: const Color(0xFF8BCDB1),
            ),
            const SizedBox(height: 12),
            TextButton.icon(
              onPressed: _completionSaving
                  ? null
                  : () => _completeSession('needs_review'),
              icon: const Icon(Icons.bookmark_add_outlined),
              label: const Text('还没完全会，加入复习'),
              style: TextButton.styleFrom(
                foregroundColor: _coral,
                textStyle: const TextStyle(fontSize: 17),
              ),
            ),
          ],
          if (_completed && _completionMessage != null) ...[
            const SizedBox(height: 16),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: _lightMint,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                _completionMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: _deepGreen,
                  fontSize: 17,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            const SizedBox(height: 14),
            _HintActionButton(
              icon: Icons.home_outlined,
              label: '返回学习桌',
              onPressed: _returnToLearningDesk,
              background: const Color(0xFFEAF7F0),
              borderColor: const Color(0xFF8BCDB1),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildAnswerStatePicker() {
    const states = <String, String>{
      'worked': '有作答',
      'blank': '确认空白',
      'unclear': '还不确定',
      'answer_area_missing': '没拍到作答区',
    };
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          '已识别并确认的作答状态',
          style: TextStyle(
            color: _muted,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
          decoration: BoxDecoration(
            color: _surface,
            border: Border.all(color: _mint),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            states[_answerState] ?? '还不确定',
            style: const TextStyle(
              color: _deepGreen,
              fontSize: 16,
              fontWeight: FontWeight.w700,
            ),
          ),
        ),
      ],
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
    this.sanitization,
    this.captureClient,
  });

  final String? imagePath;
  final Uint8List? imageBytes;
  final CaptureUploadReceipt? uploadReceipt;
  final Map<String, dynamic>? sanitization;
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
  bool _retrying = false;
  bool _remoteFinished = false;
  late CaptureUploadReceipt? _activeReceipt;
  String? _resultId;
  String? _candidateId;
  String? _remoteMessage;
  Map<String, dynamic>? _questionExtraction;
  Map<String, dynamic>? _verifiedQuestion;
  String _answerState = 'unclear';

  CaptureUploadReceipt? get _receipt => _activeReceipt;

  bool get _hasImageAnalysis =>
      _receipt?.imageAnalysisJobId?.isNotEmpty == true;

  bool get _hasRemoteJob => _receipt?.hasRemoteOcr == true || _hasImageAnalysis;

  bool get _hasRecognizedCandidate =>
      _candidateId != null || _questionExtraction != null;

  bool get _remotePending => _hasRemoteJob && !_remoteFinished;

  @override
  void initState() {
    super.initState();
    _activeReceipt = widget.uploadReceipt;
    _textController = TextEditingController(
      text: _receipt == null
          ? '3 + 4 = ?'
          : (_receipt!.hasRemoteOcr
                ? '等待本地 OCR 结果'
                : (_hasImageAnalysis ? '等待视觉识别结果' : '请检查题目并填写题目内容')),
    );
    if (_receipt?.hasRemoteOcr == true) {
      Future<void>.microtask(_loadRemoteOcr);
    } else if (_hasImageAnalysis) {
      Future<void>.microtask(_loadRemoteImageAnalysis);
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
    final receipt = _receipt;
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
          _remoteFinished = true;
          _editing = true;
          _textController.text = '';
          _remoteMessage = '本地 OCR 仍在处理中，请稍后重试或手工填写。';
        });
        return;
      }
      final result = payload['result'];
      final candidates = payload['candidates'];
      if (result is! Map || candidates is! List || candidates.isEmpty) {
        setState(() {
          _remoteLoading = false;
          _remoteFinished = true;
          _editing = true;
          _textController.text = '';
          _remoteMessage = 'OCR 没有返回候选，请稍后重试。';
        });
        return;
      }
      final candidate = candidates.first;
      if (candidate is! Map) {
        setState(() {
          _remoteLoading = false;
          _remoteFinished = true;
          _editing = true;
          _textController.text = '';
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
          _remoteFinished = true;
          _editing = true;
          _textController.text = '';
          _remoteMessage = 'OCR 候选暂时无法确认，请稍后重试。';
        });
        return;
      }
      setState(() {
        _remoteLoading = false;
        _remoteFinished = true;
        _resultId = resultId;
        _candidateId = candidateId;
        _textController.text = text;
        _remoteMessage = '识别结果已返回，请人工确认。';
      });
    } on CaptureApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _remoteLoading = false;
        _remoteFinished = true;
        _editing = true;
        _textController.text = '';
        _remoteMessage = error.message;
      });
    }
  }

  Future<void> _loadRemoteImageAnalysis() async {
    final receipt = _receipt;
    final client = widget.captureClient;
    if (receipt == null || client == null) return;
    if (mounted) {
      setState(() {
        _remoteLoading = true;
        _remoteMessage = '正在安全识别题目，完成后仍需要你确认……';
      });
    }
    try {
      final record = await client.waitForQuestionExtraction(receipt);
      if (!mounted) return;
      if (record == null) {
        setState(() {
          _remoteLoading = false;
          _remoteFinished = true;
          _editing = true;
          _textController.text = '';
          _remoteMessage = '识别时间较长，请手工填写，或返回后重新拍题。';
        });
        return;
      }
      final extractionValue = record['extraction'];
      if (extractionValue is! Map) {
        throw const CaptureApiException('视觉识别结果格式不正确，请重新拍题。');
      }
      final extraction = Map<String, dynamic>.from(extractionValue);
      final questionText = extraction['question_text']?.toString().trim();
      if (questionText == null || questionText.isEmpty) {
        throw const CaptureApiException('没有识别到题目内容，请换一张更清晰的照片。');
      }
      setState(() {
        _remoteLoading = false;
        _remoteFinished = true;
        _questionExtraction = extraction;
        _answerState =
            const {
              'worked',
              'blank',
              'unclear',
              'answer_area_missing',
            }.contains(extraction['answer_state'])
            ? extraction['answer_state'].toString()
            : 'unclear';
        _textController.text = questionText;
        _remoteMessage = '视觉识别结果已返回，请逐字检查后确认。';
      });
    } on CaptureApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _remoteLoading = false;
        _remoteFinished = true;
        _editing = true;
        _textController.text = '';
        _remoteMessage = '${error.message} 也可以手工填写题目。';
      });
    }
  }

  Future<void> _confirmText() async {
    if (_confirmed) {
      _startTutor();
      return;
    }
    final receipt = _receipt;
    if (receipt != null) {
      if (_remotePending || widget.captureClient == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('题目仍在识别中，请稍候再确认。'),
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
        if (_hasImageAnalysis && _questionExtraction != null) {
          _verifiedQuestion = await widget.captureClient!
              .verifyQuestionExtraction(
                receipt: receipt,
                questionText: _textController.text.trim(),
                extraction: _questionExtraction!,
                answerState: _answerState,
                evidenceConfirmed:
                    _answerState == 'worked' || _answerState == 'blank',
              );
        } else if (_editing || _candidateId == null) {
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
      } on Object catch (error, stackTrace) {
        logChildNetworkFailure(
          operation: 'confirm_question',
          baseUrl: widget.captureClient!.baseUrlForDiagnostics,
          error: error,
          stackTrace: stackTrace,
        );
        if (!mounted) return;
        setState(() => _confirming = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('确认请求未完成，请稍后重试。'),
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

  void _startTutor() {
    final verifiedQuestionId = _verifiedQuestion?['id']?.toString();
    if (_receipt != null &&
        (verifiedQuestionId == null || verifiedQuestionId.isEmpty)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('当前题目还没有形成已确认学习记录，请重新确认题目。'),
          behavior: SnackBarBehavior.floating,
        ),
      );
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => TutorHintScreen(
          displayName:
              widget.captureClient?.accountUsername?.trim().isNotEmpty == true
              ? widget.captureClient!.accountUsername!.trim()
              : '同学',
          questionText: _textController.text.trim(),
          verifiedQuestionId: verifiedQuestionId,
          captureClient: widget.captureClient,
          answerState:
              _verifiedQuestion?['answer_state']?.toString() ?? _answerState,
          evidenceConfirmed: _verifiedQuestion?['evidence_confirmed'] == true,
        ),
      ),
    );
  }

  Future<void> _retryRecognition() async {
    final client = widget.captureClient;
    final bytes = widget.imageBytes;
    final receipt = _receipt;
    if (client == null || bytes == null || receipt == null || _retrying) return;
    final retryNonce = DateTime.now().microsecondsSinceEpoch.toRadixString(16);
    setState(() {
      _retrying = true;
      _remoteLoading = true;
      _remoteFinished = false;
      _remoteMessage = '正在重新提交当前照片……';
      _editing = false;
      _confirmed = false;
      _resultId = null;
      _candidateId = null;
      _questionExtraction = null;
      _verifiedQuestion = null;
      _answerState = 'unclear';
      _textController.text = '';
    });
    try {
      final nextReceipt = receipt.hasRemoteOcr
          ? await client.uploadAndEnqueueBytes(
              bytes,
              ocrMode: receipt.ocrMode,
              retryNonce: retryNonce,
            )
          : await client.uploadAndStartImageAnalysisBytes(
              bytes,
              sanitization:
                  widget.sanitization ??
                  {
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
              retryNonce: retryNonce,
            );
      if (!mounted) return;
      setState(() {
        _activeReceipt = nextReceipt;
        _retrying = false;
        _remoteLoading = false;
      });
      if (nextReceipt.hasRemoteOcr) {
        await _loadRemoteOcr();
      } else {
        await _loadRemoteImageAnalysis();
      }
    } on CaptureApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _retrying = false;
        _remoteLoading = false;
        _remoteFinished = true;
        _editing = true;
        _remoteMessage = error.message;
      });
    }
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
        Expanded(flex: 6, child: _buildReviewPanel(compact: false)),
      ],
    );
  }

  Widget _buildCompactContent() {
    return Column(
      children: [
        _buildPhotoPanel(),
        const SizedBox(height: 24),
        _buildReviewPanel(compact: true),
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
            _receipt != null
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
          if (_receipt != null) ...[
            const SizedBox(height: 14),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: _lightMint,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Text(
                _receipt!.hasRemoteOcr
                    ? '已完成私有上传，OCR 任务已排队（${_receipt!.ocrJobStatus}）。'
                    : '已完成私有上传，视觉识别任务状态：${_receipt!.imageAnalysisStatus ?? '等待处理'}。',
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

  Widget _buildReviewPanel({required bool compact}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('先确认题目', style: _titleStyle(40)),
        const SizedBox(height: 12),
        Text(
          _remotePending
              ? '请看一眼，识别结果是否正确？'
              : (_hasRecognizedCandidate
                    ? '识别候选已返回，请人工确认后再开始学习。'
                    : '请检查照片并填写题目内容。'),
          style: const TextStyle(color: _deepGreen, fontSize: 18, height: 1.4),
        ),
        const SizedBox(height: 28),
        SizedBox(
          height: compact ? 210 : 290,
          child: TextField(
            controller: _textController,
            readOnly: _remotePending || !_editing,
            onTap: _editing ? null : _editText,
            maxLines: null,
            expands: true,
            textAlignVertical: TextAlignVertical.top,
            keyboardType: TextInputType.multiline,
            style: const TextStyle(
              color: _deepGreen,
              fontSize: 28,
              fontWeight: FontWeight.w600,
              height: 1.35,
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
              hintText: '可上下滑动查看全部题目文字',
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 24,
                vertical: 18,
              ),
              enabledBorder: _inputBorder(_mint),
              focusedBorder: _inputBorder(_mint, width: 2),
              border: _inputBorder(_mint),
            ),
          ),
        ),
        const SizedBox(height: 8),
        const Text(
          '题目较长时可在框内上下拖动查看，确认前请逐字核对。',
          style: TextStyle(color: _muted, fontSize: 14),
        ),
        if (_questionExtraction != null) ...[
          const SizedBox(height: 20),
          const Align(
            alignment: Alignment.centerLeft,
            child: Text(
              '系统识别到的作答状态（如不正确可修改）',
              style: TextStyle(
                color: _deepGreen,
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children:
                const <String, String>{
                  'worked': '有作答',
                  'blank': '确认空白',
                  'unclear': '看不清楚',
                  'answer_area_missing': '没拍到作答区',
                }.entries.map((entry) {
                  return ChoiceChip(
                    label: Text(entry.value),
                    selected: _answerState == entry.key,
                    onSelected: _confirming
                        ? null
                        : (selected) {
                            if (!selected) return;
                            setState(() => _answerState = entry.key);
                          },
                  );
                }).toList(),
          ),
          const SizedBox(height: 6),
          Text(
            _answerState == 'worked'
                ? '检测到答题痕迹，讲解会优先检查已有步骤。'
                : _answerState == 'blank'
                ? '答题区清晰且为空，讲解会从理解题意开始。'
                : _answerState == 'answer_area_missing'
                ? '当前照片未包含答题区，建议重新拍摄完整区域。'
                : '作答区域暂时无法可靠判断，建议检查照片或重新选择。',
            style: const TextStyle(color: _muted, fontSize: 14, height: 1.4),
          ),
        ],
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
                        ? (_remoteMessage ?? '识别完成后仍需你人工确认，系统不会直接代答。')
                        : (_confirmed
                              ? '这只是识别候选，接下来会进入学习步骤。'
                              : (_remoteMessage ?? 'AI 识别可能出错，请仔细核对后再继续。')),
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
              _confirming
                  ? '正在确认题目……'
                  : _remotePending
                  ? (_remoteLoading ? '正在识别……' : '等待识别结果')
                  : (_confirmed ? '开始学习' : (_editing ? '保存修改' : '确认题目')),
            ),
          ),
        ),
        if (_hasRemoteJob &&
            widget.captureClient != null &&
            widget.imageBytes != null &&
            _remoteFinished &&
            !_hasRecognizedCandidate &&
            !_confirmed) ...[
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _retrying ? null : _retryRecognition,
              icon: const Icon(Icons.refresh_rounded),
              label: Text(_retrying ? '正在重新识别……' : '重新识别当前照片'),
              style: OutlinedButton.styleFrom(
                foregroundColor: _mint,
                side: const BorderSide(color: _mint, width: 1.5),
                minimumSize: const Size.fromHeight(58),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                ),
              ),
            ),
          ),
          const SizedBox(height: 4),
          TextButton.icon(
            onPressed: _retrying ? null : () => Navigator.of(context).pop(),
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('重新拍题'),
            style: TextButton.styleFrom(
              foregroundColor: _deepGreen,
              textStyle: const TextStyle(fontSize: 16),
            ),
          ),
        ],
        Center(
          child: TextButton(
            onPressed: _remotePending || _confirming || _retrying
                ? null
                : _editText,
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

class _TaskMessageCard extends StatelessWidget {
  const _TaskMessageCard({
    required this.icon,
    required this.title,
    required this.message,
    required this.actionLabel,
    required this.onPressed,
  });

  final IconData icon;
  final String title;
  final String message;
  final String actionLabel;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(40),
      decoration: BoxDecoration(
        color: _surface,
        border: Border.all(color: _border),
        borderRadius: BorderRadius.circular(28),
      ),
      child: Column(
        children: [
          Icon(icon, color: _mint, size: 52),
          const SizedBox(height: 16),
          Text(title, style: _titleStyle(27), textAlign: TextAlign.center),
          const SizedBox(height: 10),
          Text(
            message,
            style: const TextStyle(color: _muted, fontSize: 17, height: 1.45),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 320),
            child: FilledButton(onPressed: onPressed, child: Text(actionLabel)),
          ),
        ],
      ),
    );
  }
}

class _UnavailableScreen extends StatelessWidget {
  const _UnavailableScreen({
    required this.message,
    required this.onRetry,
    this.onChangeServer,
  });

  final String message;
  final VoidCallback onRetry;
  final VoidCallback? onChangeServer;

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
            Text('学习服务暂时不可用', style: _titleStyle(24)),
            const SizedBox(height: 8),
            Text(
              message,
              style: TextStyle(color: _muted, fontSize: 16),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 20),
            FilledButton(onPressed: onRetry, child: const Text('重试')),
            if (onChangeServer != null)
              TextButton(
                onPressed: onChangeServer,
                child: const Text('更改服务端地址'),
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
