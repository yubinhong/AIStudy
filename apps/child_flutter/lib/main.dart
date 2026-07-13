import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

const demoHouseholdId = '00000000-0000-0000-0000-000000000001';
const apiBaseUrl = String.fromEnvironment(
  'STUDY_API_URL',
  defaultValue: 'http://127.0.0.1:8000',
);

typedef ChildrenLoader = Future<List<Map<String, dynamic>>> Function();

Future<List<Map<String, dynamic>>> loadDemoChildren() async {
  final client = HttpClient();
  try {
    final request = await client.getUrl(
      Uri.parse('$apiBaseUrl/households/$demoHouseholdId/children'),
    );
    request.headers
      ..set('X-Demo-Household-Id', demoHouseholdId)
      ..set('X-Demo-Role', 'child');
    final response = await request.close();
    if (response.statusCode != HttpStatus.ok) return [];
    final payload = jsonDecode(await response.transform(utf8.decoder).join());
    if (payload is! List) return [];
    return payload.whereType<Map>().map(Map<String, dynamic>.from).toList();
  } finally {
    client.close(force: true);
  }
}

void main() {
  runApp(const StudyChildApp());
}

class StudyChildApp extends StatelessWidget {
  const StudyChildApp({super.key, this.loadChildren = loadDemoChildren});

  final ChildrenLoader loadChildren;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '家庭 AI 学习助手',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
      ),
      home: ChildProfileScreen(loadChildren: loadChildren),
    );
  }
}

class ChildProfileScreen extends StatefulWidget {
  const ChildProfileScreen({super.key, required this.loadChildren});

  final ChildrenLoader loadChildren;

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
      appBar: AppBar(title: const Text('家庭 AI 学习助手')),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _children,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          final children = snapshot.data ?? const <Map<String, dynamic>>[];
          final child = children.isEmpty ? null : children.first;
          return Center(
            child: Text(
              child == null
                  ? 'API 尚未连接'
                  : '${child['display_name'] ?? '合成孩子'}\n${child['curriculum_version'] ?? ''}',
              textAlign: TextAlign.center,
            ),
          );
        },
      ),
    );
  }
}
