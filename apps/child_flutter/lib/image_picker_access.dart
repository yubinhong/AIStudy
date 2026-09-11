import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';

const studyAppSettingsChannel = MethodChannel('study/app_settings');

@immutable
class ImagePickerFailurePresentation {
  const ImagePickerFailurePresentation({
    required this.message,
    this.canOpenSettings = false,
  });

  final String message;
  final bool canOpenSettings;
}

ImagePickerFailurePresentation describeImagePickerFailure(
  PlatformException error,
  ImageSource source,
) {
  switch (error.code) {
    case 'camera_access_denied':
      return const ImagePickerFailurePresentation(
        message: '相机权限已关闭。请打开“设置”，允许 Study Child 使用相机后重试。',
        canOpenSettings: true,
      );
    case 'camera_access_restricted':
      return const ImagePickerFailurePresentation(
        message: '相机被“屏幕使用时间”或设备管理限制，请由家长解除限制。',
      );
    case 'photo_access_denied':
      return const ImagePickerFailurePresentation(
        message: '照片权限已关闭。请打开“设置”，允许 Study Child 访问照片后重试。',
        canOpenSettings: true,
      );
    case 'photo_access_restricted':
      return const ImagePickerFailurePresentation(
        message: '照片访问被“屏幕使用时间”或设备管理限制，请由家长解除限制。',
      );
    case 'no_available_camera':
      return const ImagePickerFailurePresentation(
        message: '当前没有可用相机，请改用“从相册选择”。',
      );
    case 'multiple_request':
      return const ImagePickerFailurePresentation(message: '图片入口正在打开，请稍等后再试。');
    default:
      return ImagePickerFailurePresentation(
        message: source == ImageSource.camera
            ? '暂时无法打开相机，请稍后再试。'
            : '暂时无法打开相册，请稍后再试。',
      );
  }
}

Future<bool> openStudyAppSettings({
  MethodChannel channel = studyAppSettingsChannel,
}) async {
  try {
    return await channel.invokeMethod<bool>('open') ?? false;
  } on MissingPluginException {
    return false;
  } on PlatformException {
    return false;
  }
}
