import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

class SanitizedImageSelection {
  const SanitizedImageSelection({
    required this.bytes,
    required this.sha256,
    this.maskCount = 0,
  });

  final Uint8List bytes;
  final String sha256;
  final int maskCount;
}

typedef SanitizedPreviewRenderer =
    Future<SanitizedImageSelection> Function(
      Uint8List source,
      List<Rect> masks,
    );

class SanitizationPreviewScreen extends StatefulWidget {
  const SanitizationPreviewScreen({
    super.key,
    required this.image,
    this.onConfirmed,
    this.renderer,
  });

  final XFile image;
  final ValueChanged<SanitizedImageSelection>? onConfirmed;
  final SanitizedPreviewRenderer? renderer;

  @override
  State<SanitizationPreviewScreen> createState() =>
      _SanitizationPreviewScreenState();
}

class _SanitizationPreviewScreenState extends State<SanitizationPreviewScreen> {
  late final Future<Uint8List> _sourceBytes;
  final List<Rect> _masks = [];
  Rect? _draftMask;
  Offset? _dragStart;
  bool _rendering = false;

  @override
  void initState() {
    super.initState();
    _sourceBytes = widget.image.readAsBytes();
  }

  Rect _normalizedRect(Offset start, Offset end, Size size) {
    final left = start.dx < end.dx ? start.dx : end.dx;
    final top = start.dy < end.dy ? start.dy : end.dy;
    final right = start.dx > end.dx ? start.dx : end.dx;
    final bottom = start.dy > end.dy ? start.dy : end.dy;
    return Rect.fromLTRB(
      (left / size.width).clamp(0.0, 1.0),
      (top / size.height).clamp(0.0, 1.0),
      (right / size.width).clamp(0.0, 1.0),
      (bottom / size.height).clamp(0.0, 1.0),
    );
  }

  void _startMask(DragStartDetails details, Size size) {
    _dragStart = details.localPosition;
    setState(
      () => _draftMask = _normalizedRect(
        details.localPosition,
        details.localPosition,
        size,
      ),
    );
  }

  void _updateMask(DragUpdateDetails details, Size size) {
    final start = _dragStart;
    if (start == null) return;
    setState(
      () => _draftMask = _normalizedRect(start, details.localPosition, size),
    );
  }

  void _finishMask(DragEndDetails details) {
    final draft = _draftMask;
    _dragStart = null;
    _draftMask = null;
    if (draft == null || draft.width < 0.02 || draft.height < 0.02) {
      setState(() {});
      return;
    }
    setState(() => _masks.add(draft));
  }

  Future<SanitizedImageSelection> _renderSanitized(Uint8List source) async {
    final codec = await ui.instantiateImageCodec(source);
    final frame = await codec.getNextFrame();
    final image = frame.image;
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    canvas.drawImage(image, Offset.zero, Paint());
    final maskPaint = Paint()..color = Colors.black;
    for (final mask in _masks) {
      canvas.drawRect(
        Rect.fromLTRB(
          mask.left * image.width,
          mask.top * image.height,
          mask.right * image.width,
          mask.bottom * image.height,
        ),
        maskPaint,
      );
    }
    final picture = recorder.endRecording();
    final sanitized = await picture.toImage(image.width, image.height);
    final bytes = await sanitized.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    sanitized.dispose();
    picture.dispose();
    codec.dispose();
    if (bytes == null) {
      throw StateError('sanitized preview could not be encoded');
    }
    final data = bytes.buffer.asUint8List();
    return SanitizedImageSelection(
      bytes: Uint8List.fromList(data),
      sha256: sha256.convert(data).toString(),
      maskCount: _masks.length,
    );
  }

  Future<void> _confirm(Uint8List source) async {
    if (_rendering) return;
    setState(() => _rendering = true);
    try {
      final selection = widget.renderer == null
          ? await _renderSanitized(source)
          : await widget.renderer!(source, List.unmodifiable(_masks));
      if (!mounted) return;
      if (widget.onConfirmed case final callback?) {
        callback(selection);
        setState(() => _rendering = false);
      } else {
        Navigator.of(context).pop(selection);
      }
    } catch (_) {
      if (!mounted) return;
      setState(() => _rendering = false);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('脱敏预览暂时无法生成，请重新选择照片。')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final primary = Theme.of(context).colorScheme.primary;
    return Scaffold(
      appBar: AppBar(
        title: const Text('确认脱敏范围'),
        leading: IconButton(
          onPressed: _rendering ? null : () => Navigator.of(context).pop(),
          icon: const Icon(Icons.arrow_back_rounded),
          tooltip: '返回拍题',
        ),
      ),
      body: FutureBuilder<Uint8List>(
        future: _sourceBytes,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final source = snapshot.data!;
          return SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final compact = constraints.maxWidth < 900;
                return SingleChildScrollView(
                  padding: EdgeInsets.all(compact ? 20 : 36),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 960),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '先保护隐私，再识别题目',
                            style: TextStyle(
                              color: const Color(0xFF155B47),
                              fontSize: compact ? 30 : 38,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                          const SizedBox(height: 10),
                          const Text(
                            '原图只留在本机。请检查脱敏区域；可在照片上拖动涂抹姓名、学校、电话和背景信息。',
                            style: TextStyle(fontSize: 17, height: 1.45),
                          ),
                          const SizedBox(height: 22),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              color: const Color(0xFFF7F5EE),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: primary, width: 1.5),
                            ),
                            child: LayoutBuilder(
                              builder: (context, imageConstraints) {
                                final size = Size(
                                  imageConstraints.maxWidth,
                                  compact ? 300 : 480,
                                );
                                return SizedBox(
                                  key: const ValueKey('sanitization-canvas'),
                                  height: size.height,
                                  child: GestureDetector(
                                    onPanStart: (details) =>
                                        _startMask(details, size),
                                    onPanUpdate: (details) =>
                                        _updateMask(details, size),
                                    onPanEnd: _finishMask,
                                    child: Stack(
                                      fit: StackFit.expand,
                                      children: [
                                        Image.memory(
                                          source,
                                          fit: BoxFit.contain,
                                        ),
                                        CustomPaint(
                                          painter: _MaskPainter(
                                            _masks,
                                            _draftMask,
                                          ),
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                          const SizedBox(height: 14),
                          Text(
                            _masks.isEmpty
                                ? '还没有手动涂抹区域'
                                : '已添加 ${_masks.length} 个敏感区域',
                            style: TextStyle(color: primary, fontSize: 16),
                          ),
                          const SizedBox(height: 24),
                          Container(
                            padding: const EdgeInsets.all(16),
                            decoration: BoxDecoration(
                              color: const Color(0xFFEAF7F0),
                              borderRadius: BorderRadius.circular(16),
                            ),
                            child: const Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Icon(Icons.lock_outline_rounded),
                                SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    '确认后只会生成新的脱敏 PNG，并绑定当前副本哈希。当前页面不会上传原图。',
                                    style: TextStyle(fontSize: 15, height: 1.4),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 26),
                          SizedBox(
                            width: double.infinity,
                            child: FilledButton.icon(
                              onPressed: _rendering
                                  ? null
                                  : () => _confirm(source),
                              icon: _rendering
                                  ? const SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        color: Colors.white,
                                      ),
                                    )
                                  : const Icon(Icons.verified_user_outlined),
                              label: Text(
                                _rendering ? '正在生成脱敏副本……' : '确认脱敏并继续',
                              ),
                              style: FilledButton.styleFrom(
                                backgroundColor: primary,
                                minimumSize: const Size.fromHeight(64),
                                textStyle: const TextStyle(
                                  fontSize: 19,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                          ),
                          Center(
                            child: TextButton(
                              onPressed: _rendering
                                  ? null
                                  : () => Navigator.of(context).pop(),
                              child: const Text('重新选择照片'),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}

class _MaskPainter extends CustomPainter {
  const _MaskPainter(this.masks, this.draft);

  final List<Rect> masks;
  final Rect? draft;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.black.withValues(alpha: 0.88);
    final allMasks = [...masks];
    if (draft != null) {
      allMasks.add(draft!);
    }
    for (final mask in allMasks) {
      canvas.drawRect(
        Rect.fromLTRB(
          mask.left * size.width,
          mask.top * size.height,
          mask.right * size.width,
          mask.bottom * size.height,
        ),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_MaskPainter oldDelegate) =>
      oldDelegate.masks != masks || oldDelegate.draft != draft;
}
