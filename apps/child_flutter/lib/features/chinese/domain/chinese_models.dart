class ChineseContentItem {
  const ChineseContentItem({
    required this.id,
    required this.revision,
    required this.skill,
    required this.title,
    required this.prompt,
    required this.options,
    required this.sourceLabel,
    this.passage,
  });

  final String id;
  final int revision;
  final String skill;
  final String title;
  final String prompt;
  final List<String> options;
  final String sourceLabel;
  final String? passage;

  factory ChineseContentItem.fromJson(Map<String, dynamic> json) {
    final source = json['source'];
    final sourceMap = source is Map
        ? Map<String, dynamic>.from(source)
        : const <String, dynamic>{};
    return ChineseContentItem(
      id: json['id']?.toString() ?? '',
      revision: json['revision'] is int ? json['revision'] as int : 1,
      skill: json['skill']?.toString() ?? 'vocabulary',
      title: json['title']?.toString() ?? '语文练习',
      prompt: json['prompt']?.toString() ?? '',
      passage: json['passage']?.toString(),
      options: (json['options'] as List<dynamic>? ?? const <dynamic>[])
          .map((value) => value.toString())
          .toList(growable: false),
      sourceLabel: sourceMap['type'] == 'private_curriculum' ? '家庭教材' : '原创练习',
    );
  }
}

class ChineseAttemptResult {
  const ChineseAttemptResult({
    required this.correct,
    required this.score,
    required this.maxScore,
    required this.feedbackTags,
    this.correctAnswer,
  });

  final bool correct;
  final double score;
  final double maxScore;
  final List<String> feedbackTags;
  final String? correctAnswer;

  factory ChineseAttemptResult.fromJson(Map<String, dynamic> json) {
    final result = Map<String, dynamic>.from(json['result'] as Map);
    return ChineseAttemptResult(
      correct: result['correct'] == true,
      score: (result['score'] as num).toDouble(),
      maxScore: (result['max_score'] as num).toDouble(),
      feedbackTags:
          (result['feedback_tags'] as List<dynamic>? ?? const <dynamic>[])
              .map((value) => value.toString())
              .toList(growable: false),
      correctAnswer: result['correct_answer']?.toString(),
    );
  }
}

class ChineseReviewItem {
  const ChineseReviewItem({
    required this.contentId,
    required this.contentRevision,
    required this.dueAt,
    required this.skill,
  });

  final String contentId;
  final int contentRevision;
  final DateTime dueAt;
  final String skill;

  factory ChineseReviewItem.fromJson(Map<String, dynamic> json) {
    return ChineseReviewItem(
      contentId: json['content_id']?.toString() ?? '',
      contentRevision: json['content_revision'] is int
          ? json['content_revision'] as int
          : 1,
      dueAt:
          DateTime.tryParse(json['due_at']?.toString() ?? '') ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true),
      skill: json['skill']?.toString() ?? 'vocabulary',
    );
  }
}
