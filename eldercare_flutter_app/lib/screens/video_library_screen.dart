import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

class VideoLibraryScreen extends StatefulWidget {
  const VideoLibraryScreen({Key? key}) : super(key: key);

  @override
  State<VideoLibraryScreen> createState() => _VideoLibraryScreenState();
}

class _VideoLibraryScreenState extends State<VideoLibraryScreen> {
  final User? currentUser = FirebaseAuth.instance.currentUser;
  final db = FirebaseFirestore.instance;
  String? selectedElderId;
  List<Map<String, dynamic>> videos = [];
  bool isLoading = false;
  bool hasError = false;
  String errorMessage = '';

  @override
  void initState() {
    super.initState();
    _loadEldersAndVideos();
  }

  Future<void> _loadEldersAndVideos() async {
    if (currentUser == null) return;

    setState(() => isLoading = true);

    try {
      // Get caregiver's profile to find assigned elders
      final caregiverDoc = await db
          .collection('users')
          .doc(currentUser!.uid)
          .get();

      if (!caregiverDoc.exists) {
        setState(() {
          hasError = true;
          errorMessage = 'Caregiver profile not found';
          isLoading = false;
        });
        return;
      }

      final elderIds = List<String>.from(
        caregiverDoc['assigned_elders'] ?? []
      );

      if (elderIds.isEmpty) {
        setState(() {
          hasError = true;
          errorMessage = 'No elders assigned';
          isLoading = false;
        });
        return;
      }

      // Select first elder
      if (mounted) {
        setState(() => selectedElderId = elderIds.first);
      }

      // Load videos for selected elder
      await _loadVideosForElder(elderIds.first);

    } catch (e) {
      if (mounted) {
        setState(() {
          hasError = true;
          errorMessage = 'Error loading data: $e';
          isLoading = false;
        });
      }
    }
  }

  Future<void> _loadVideosForElder(String elderId) async {
    try {
      setState(() => isLoading = true);

      final videoDocs = await db
          .collection('videos')
          .where('elder_id', isEqualTo: elderId)
          .orderBy('timestamp', descending: true)
          .get();

      if (mounted) {
        setState(() {
          videos = videoDocs.docs.map((doc) {
            final data = doc.data();
            return {
              'id': doc.id,
              'filename': data['filename'] ?? 'Unknown',
              'timestamp': (data['timestamp'] as Timestamp).toDate(),
              'duration_seconds': data['duration_seconds'] ?? 0,
              'filepath': data['filepath'] ?? '',
              'size_mb': data['size_mb'] ?? 0.0,
            };
          }).toList();
          isLoading = false;
          hasError = false;
          errorMessage = '';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          hasError = true;
          errorMessage = 'Error loading videos: $e';
          isLoading = false;
        });
      }
    }
  }

  Future<void> _downloadVideo(String videoId, String filename) async {
    // Construct download URL
    const String baseUrl = 'http://10.110.185.106:5000';
    final downloadUrl = '$baseUrl/api/videos/download/$videoId';

    try {
      final uri = Uri.parse(downloadUrl);
      
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Downloading: $filename'),
              duration: const Duration(seconds: 2),
            ),
          );
        }
      } else {
        throw 'Could not launch $downloadUrl';
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Download failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _deleteVideo(String videoId) async {
    try {
      await db.collection('videos').doc(videoId).delete();

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Video deleted successfully'),
            duration: Duration(seconds: 2),
          ),
        );
        // Reload videos
        if (selectedElderId != null) {
          await _loadVideosForElder(selectedElderId!);
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Delete failed: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  void _showDeleteConfirmation(String videoId, String filename) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Video'),
        content: Text('Are you sure you want to delete "$filename"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              _deleteVideo(videoId);
            },
            child: const Text('Delete', style: TextStyle(color: Colors.red)),
          ),
        ],
      ),
    );
  }

  Widget _buildVideoCard(Map<String, dynamic> video) {
    final df = DateFormat('MMM dd, yyyy HH:mm');
    final duration = Duration(seconds: video['duration_seconds'] as int);
    final durationStr = '${duration.inMinutes}:${(duration.inSeconds % 60).toString().padLeft(2, '0')}';

    return Card(
      child: ListTile(
        leading: const Icon(Icons.videocam, color: Colors.blue, size: 32),
        title: Text(
          video['filename'],
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.bold),
        ),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const SizedBox(height: 4),
            Text(df.format(video['timestamp'])),
            Text(
              'Duration: $durationStr • Size: ${(video['size_mb'] as double).toStringAsFixed(1)} MB',
              style: const TextStyle(fontSize: 12, color: Colors.grey),
            ),
          ],
        ),
        trailing: PopupMenuButton(
          itemBuilder: (context) => [
            PopupMenuItem(
              child: const Row(
                children: [
                  Icon(Icons.download, color: Colors.blue),
                  SizedBox(width: 8),
                  Text('Download'),
                ],
              ),
              onTap: () {
                Future.delayed(
                  const Duration(milliseconds: 100),
                  () => _downloadVideo(video['id'], video['filename']),
                );
              },
            ),
            PopupMenuItem(
              child: const Row(
                children: [
                  Icon(Icons.play_arrow, color: Colors.green),
                  SizedBox(width: 8),
                  Text('Play'),
                ],
              ),
              onTap: () {
                Future.delayed(
                  const Duration(milliseconds: 100),
                  () => _showVideoPlayer(video),
                );
              },
            ),
            PopupMenuItem(
              child: const Row(
                children: [
                  Icon(Icons.delete, color: Colors.red),
                  SizedBox(width: 8),
                  Text('Delete'),
                ],
              ),
              onTap: () {
                Future.delayed(
                  const Duration(milliseconds: 100),
                  () => _showDeleteConfirmation(video['id'], video['filename']),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  void _showVideoPlayer(Map<String, dynamic> video) {
    // For now, show a message - in production, integrate video_player package
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(video['filename']),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.play_circle_outline, size: 64, color: Colors.blue),
            const SizedBox(height: 16),
            Text('📹 Video Player'),
            const SizedBox(height: 8),
            Text(
              'This video is available for download.\n\n'
              'Click "Download" to save to your device,\n'
              'then open with your video player app.',
            ),
            const SizedBox(height: 16),
            Text(
              'File: ${video['filename']}',
              style: const TextStyle(fontStyle: FontStyle.italic),
            ),
            Text(
              'Size: ${(video['size_mb'] as double).toStringAsFixed(1)} MB',
              style: const TextStyle(fontStyle: FontStyle.italic),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
          ElevatedButton(
            onPressed: () {
              Navigator.pop(context);
              _downloadVideo(video['id'], video['filename']);
            },
            child: const Text('Download Now'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('📹 Video Library'),
        backgroundColor: Colors.blue.shade700,
        elevation: 0,
      ),
      body: isLoading
          ? const Center(
              child: CircularProgressIndicator(),
            )
          : hasError
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, size: 64, color: Colors.red),
                      const SizedBox(height: 16),
                      Text(
                        'Error: $errorMessage',
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 16),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _loadEldersAndVideos,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : videos.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const Icon(
                            Icons.videocam_off,
                            size: 64,
                            color: Colors.grey,
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            'No videos recorded yet',
                            style: TextStyle(
                              fontSize: 18,
                              color: Colors.grey,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(
                            'Videos will appear here after fall detection\nor manual recording is triggered.',
                            textAlign: TextAlign.center,
                            style: TextStyle(
                              fontSize: 14,
                              color: Colors.grey.shade600,
                            ),
                          ),
                        ],
                      ),
                    )
                  : ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12,
                            vertical: 8,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.blue.shade50,
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.blue.shade200),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Total Videos',
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.blue,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                '${videos.length} videos available',
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        ...videos.map(_buildVideoCard),
                      ],
                    ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {
          if (selectedElderId != null) {
            _loadVideosForElder(selectedElderId!);
          }
        },
        tooltip: 'Refresh',
        child: const Icon(Icons.refresh),
      ),
    );
  }
}
