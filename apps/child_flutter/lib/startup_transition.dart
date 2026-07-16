import 'package:flutter/material.dart';

/// A short first-frame transition that lets the real home screen initialize
/// behind it. The animation is finite and is skipped when reduced motion is on.
class StartupTransition extends StatefulWidget {
  const StartupTransition({
    super.key,
    required this.child,
    this.duration = const Duration(milliseconds: 1200),
  });

  final Widget child;
  final Duration duration;

  @override
  State<StartupTransition> createState() => _StartupTransitionState();
}

class _StartupTransitionState extends State<StartupTransition>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  bool _started = false;
  bool _complete = false;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(duration: widget.duration, vsync: this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    if (MediaQuery.disableAnimationsOf(context)) {
      _controller.value = 1;
      _complete = true;
      return;
    }
    _controller.forward().whenComplete(_finish);
  }

  void _finish() {
    if (!mounted || _complete) return;
    setState(() => _complete = true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        IgnorePointer(
          ignoring: !_complete,
          child: ExcludeSemantics(excluding: !_complete, child: widget.child),
        ),
        if (!_complete)
          FadeTransition(
            opacity: Tween<double>(begin: 1, end: 0).animate(
              CurvedAnimation(
                parent: _controller,
                curve: const Interval(0.72, 1, curve: Curves.easeOut),
              ),
            ),
            child: _StartupSurface(controller: _controller),
          ),
      ],
    );
  }
}

class _StartupSurface extends StatelessWidget {
  const _StartupSurface({required this.controller});

  final AnimationController controller;

  @override
  Widget build(BuildContext context) {
    final entrance = CurvedAnimation(
      parent: controller,
      curve: const Interval(0, 0.58, curve: Curves.easeOutBack),
    );
    return Semantics(
      key: const ValueKey('startup-transition'),
      label: '正在准备学习桌',
      child: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFFF0FBF6), Color(0xFFFFFCF7)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: FadeTransition(
                opacity: entrance,
                child: ScaleTransition(
                  scale: Tween<double>(begin: 0.84, end: 1).animate(entrance),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 96,
                        height: 96,
                        decoration: BoxDecoration(
                          color: const Color(0xFF35B58F),
                          borderRadius: BorderRadius.circular(30),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x3335B58F),
                              blurRadius: 28,
                              offset: Offset(0, 12),
                            ),
                          ],
                        ),
                        child: const Icon(
                          Icons.auto_stories_rounded,
                          color: Colors.white,
                          size: 48,
                        ),
                      ),
                      const SizedBox(height: 24),
                      const Text(
                        '家庭 AI 学习助手',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Color(0xFF124D3F),
                          fontSize: 28,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 0.4,
                        ),
                      ),
                      const SizedBox(height: 10),
                      const Text(
                        '正在准备今天的学习桌…',
                        style: TextStyle(
                          color: Color(0xFF6C7872),
                          fontSize: 16,
                        ),
                      ),
                      const SizedBox(height: 28),
                      SizedBox(
                        width: 176,
                        child: AnimatedBuilder(
                          animation: controller,
                          builder: (context, child) => LinearProgressIndicator(
                            value: Curves.easeInOut.transform(controller.value),
                            minHeight: 5,
                            borderRadius: BorderRadius.circular(999),
                            backgroundColor: const Color(0xFFD9E9DE),
                            color: const Color(0xFF35B58F),
                          ),
                        ),
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
