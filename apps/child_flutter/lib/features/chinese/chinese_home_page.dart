import 'dart:math';

import 'package:flutter/material.dart';

import 'data/chinese_api_client.dart';
import 'domain/chinese_models.dart';

class ChineseHomePage extends StatefulWidget {
  const ChineseHomePage({
    super.key,
    required this.gateway,
    this.onPictureWriting,
    this.poemRandom,
  });

  final ChinesePracticeGateway gateway;
  final VoidCallback? onPictureWriting;
  final Random? poemRandom;

  @override
  State<ChineseHomePage> createState() => _ChineseHomePageState();
}

class _ChineseHomePageState extends State<ChineseHomePage> {
  late Future<_ChineseDashboard> _dashboard;
  bool _openingPoem = false;

  @override
  void initState() {
    super.initState();
    _dashboard = _loadDashboard();
  }

  Future<_ChineseDashboard> _loadDashboard() async {
    final results = await Future.wait<Object>([
      widget.gateway.loadContent(),
      widget.gateway.loadDueReviews(),
    ]);
    return _ChineseDashboard(
      content: results[0] as List<ChineseContentItem>,
      dueReviews: results[1] as List<ChineseReviewItem>,
    );
  }

  void _retry() => setState(() => _dashboard = _loadDashboard());

  Future<void> _openPoemPractice() async {
    if (_openingPoem) return;
    setState(() => _openingPoem = true);
    try {
      final latestItems = await widget.gateway.loadContent();
      if (!mounted) return;
      final poemItems = latestItems
          .where((item) => item.skill == 'poem')
          .toList(growable: false);
      if (poemItems.isEmpty) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('当前没有可抽查的古诗，请稍后重试。')));
        return;
      }
      final item = _pickPoemQuestion(
        poemItems,
        widget.poemRandom ?? Random.secure(),
      );
      await Navigator.of(context).push(
        MaterialPageRoute<void>(
          builder: (_) =>
              _ChinesePracticePage(gateway: widget.gateway, item: item),
        ),
      );
    } on ChinesePracticeException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) setState(() => _openingPoem = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('语文学习')),
      body: FutureBuilder<_ChineseDashboard>(
        future: _dashboard,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: FilledButton.icon(
                onPressed: _retry,
                icon: const Icon(Icons.refresh),
                label: const Text('重新加载'),
              ),
            );
          }
          final dashboard = snapshot.data;
          final items = dashboard?.content ?? const <ChineseContentItem>[];
          final poemItems = items
              .where((item) => item.skill == 'poem')
              .toList(growable: false);
          final contentByRevision = {
            for (final item in items) '${item.id}:${item.revision}': item,
          };
          final dueItems = (dashboard?.dueReviews ?? const <ChineseReviewItem>[])
              .map(
                (review) =>
                    contentByRevision['${review.contentId}:${review.contentRevision}'],
              )
              .whereType<ChineseContentItem>()
              .toList(growable: false);
          return ListView.separated(
            padding: const EdgeInsets.all(20),
            itemCount: 2 + (dueItems.isEmpty ? 0 : 1),
            separatorBuilder: (_, _) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              if (index == 0) {
                return Card(
                  child: ListTile(
                    leading: const Icon(Icons.edit_note_outlined),
                    title: const Text('看图写话'),
                    subtitle: const Text('拍一张图，先观察，再写一句'),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: widget.onPictureWriting,
                  ),
                );
              }
              final afterPictureWriting = index - 1;
              if (afterPictureWriting == 0 && dueItems.isNotEmpty) {
                return Card(
                  color: Theme.of(context).colorScheme.secondaryContainer,
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '到期复习',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        const SizedBox(height: 8),
                        Text('今天有 ${dueItems.length} 项语文内容需要重新作答。'),
                        const SizedBox(height: 10),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: dueItems
                              .map(
                                (item) => OutlinedButton(
                                  onPressed: () => Navigator.of(context).push(
                                    MaterialPageRoute<void>(
                                      builder: (_) => _ChinesePracticePage(
                                        gateway: widget.gateway,
                                        item: item,
                                        isReview: true,
                                      ),
                                    ),
                                  ),
                                  child: Text(item.title),
                                ),
                              )
                              .toList(growable: false),
                        ),
                      ],
                    ),
                  ),
                );
              }
              return Card(
                child: ListTile(
                  leading: const Icon(Icons.menu_book_outlined),
                  title: const Text('古诗抽查'),
                  subtitle: Text(
                    _openingPoem
                        ? '正在刷新当前题库'
                        : poemItems.isEmpty
                        ? '家长上传并审核教材后开放'
                        : '随机抽一首，选择下一句',
                  ),
                  trailing: const Icon(Icons.chevron_right),
                  enabled: poemItems.isNotEmpty && !_openingPoem,
                  onTap: poemItems.isEmpty || _openingPoem
                      ? null
                      : _openPoemPractice,
                ),
              );
            },
          );
        },
      ),
    );
  }
}

ChineseContentItem _pickPoemQuestion(
  List<ChineseContentItem> items,
  Random random,
) {
  if (items.isEmpty) {
    throw ArgumentError.value(items, 'items', 'at least one poem is required');
  }
  final groups = <String, List<ChineseContentItem>>{};
  for (final item in items) {
    // Each generated next-line question carries the poem title. Pick the
    // poem first so long poems do not appear more often just because they
    // generated more adjacent-line questions.
    final key = '${item.title}\u0000${item.passage ?? ''}';
    groups.putIfAbsent(key, () => <ChineseContentItem>[]).add(item);
  }
  final poem = groups.values.elementAt(random.nextInt(groups.length));
  return poem[random.nextInt(poem.length)];
}

class _ChinesePracticePage extends StatefulWidget {
  const _ChinesePracticePage({
    required this.gateway,
    required this.item,
    this.isReview = false,
  });

  final ChinesePracticeGateway gateway;
  final ChineseContentItem item;
  final bool isReview;

  @override
  State<_ChinesePracticePage> createState() => _ChinesePracticePageState();
}

class _ChinesePracticePageState extends State<_ChinesePracticePage> {
  final _answerController = TextEditingController();
  final _evidenceController = TextEditingController();
  final List<int> _ordered = [];
  late final DateTime _startedAt = DateTime.now();
  String? _choice;
  ChineseAttemptResult? _result;
  bool _submitting = false;

  @override
  void dispose() {
    _answerController.dispose();
    _evidenceController.dispose();
    super.dispose();
  }

  Map<String, dynamic>? _response() {
    final item = widget.item;
    if (item.skill == 'sentence' && item.options.isNotEmpty) {
      return _ordered.length == item.options.length
          ? {'tokens': _ordered.map((index) => item.options[index]).toList()}
          : null;
    }
    if (item.skill == 'reading') {
      if (_answerController.text.trim().isEmpty ||
          _evidenceController.text.trim().isEmpty) {
        return null;
      }
      return {
        'answer': _answerController.text.trim(),
        'evidence': _evidenceController.text.trim(),
      };
    }
    if (item.options.isNotEmpty) {
      return _choice == null ? null : {'choice': _choice};
    }
    return _answerController.text.trim().isEmpty
        ? null
        : {'text': _answerController.text.trim()};
  }

  Future<void> _submit() async {
    final response = _response();
    if (response == null) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('先完成当前题目，再提交。')));
      return;
    }
    setState(() => _submitting = true);
    try {
      final result = await widget.gateway.submitAttempt(
        widget.item,
        response,
        DateTime.now().difference(_startedAt).inMilliseconds,
      );
      if (mounted) setState(() => _result = result);
    } on ChinesePracticeException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final item = widget.item;
    return Scaffold(
      appBar: AppBar(title: Text(item.title)),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (item.passage case final passage?) ...[
            SelectableText(
              passage,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 20),
          ],
          Text(item.prompt, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 20),
          if (item.skill == 'sentence' && item.options.isNotEmpty)
            _SentenceOrder(
              options: item.options,
              ordered: _ordered,
              onChanged: () => setState(() {}),
            )
          else if (item.skill == 'reading') ...[
            TextField(
              controller: _answerController,
              decoration: const InputDecoration(labelText: '我的回答'),
              minLines: 2,
              maxLines: 4,
              maxLength: 1000,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _evidenceController,
              decoration: const InputDecoration(labelText: '文中的依据'),
              minLines: 2,
              maxLines: 4,
              maxLength: 1000,
            ),
          ] else if (item.options.isNotEmpty)
            SegmentedButton<String>(
              segments: item.options
                  .map(
                    (option) =>
                        ButtonSegment(value: option, label: Text(option)),
                  )
                  .toList(growable: false),
              selected: _choice == null ? const <String>{} : {_choice!},
              emptySelectionAllowed: true,
              onSelectionChanged: (value) =>
                  setState(() => _choice = value.firstOrNull),
            )
          else
            TextField(
              controller: _answerController,
              decoration: const InputDecoration(labelText: '我的回答'),
              maxLength: 1000,
            ),
          const SizedBox(height: 24),
          if (_result case final result?)
            Card(
              color: result.correct
                  ? Theme.of(context).colorScheme.secondaryContainer
                  : Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  result.correct
                      ? widget.isReview
                            ? '复习完成，已更新下一次复习时间。'
                            : '回答正确，已加入后续复习。'
                      : result.correctAnswer == null
                      ? _feedback(result.feedbackTags)
                      : '${_feedback(result.feedbackTags)}\n正确答案：${result.correctAnswer}',
                ),
              ),
            ),
          FilledButton.icon(
            onPressed: _submitting || _result != null ? null : _submit,
            icon: _submitting
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.check),
            label: const Text('提交回答'),
          ),
        ],
      ),
    );
  }
}

class _ChineseDashboard {
  const _ChineseDashboard({required this.content, required this.dueReviews});

  final List<ChineseContentItem> content;
  final List<ChineseReviewItem> dueReviews;
}

class _SentenceOrder extends StatelessWidget {
  const _SentenceOrder({
    required this.options,
    required this.ordered,
    required this.onChanged,
  });

  final List<String> options;
  final List<int> ordered;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: List<int>.generate(options.length, (index) => index)
              .where((index) => !ordered.contains(index))
              .map(
                (index) => ActionChip(
                  label: Text(options[index]),
                  onPressed: () {
                    ordered.add(index);
                    onChanged();
                  },
                ),
              )
              .toList(growable: false),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: ordered
              .map(
                (index) => InputChip(
                  label: Text(options[index]),
                  onDeleted: () {
                    ordered.remove(index);
                    onChanged();
                  },
                ),
              )
              .toList(growable: false),
        ),
      ],
    );
  }
}

String _feedback(List<String> tags) {
  if (tags.contains('evidence_missing')) return '再回到短文中，找出能支持回答的原句。';
  if (tags.contains('concept_missing')) return '想一想题目问的关键变化，再补充回答。';
  if (tags.contains('order_retry')) return '读一遍排好的句子，再调整词语顺序。';
  return '再仔细看一遍题目，然后重试。';
}
