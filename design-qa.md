# Design QA — Flutter 第 1/2/3 张原型

- source visual truth:
  - 第 1 张学习桌：`/Users/ybh/.codex/generated_images/019f5518-914e-7c22-aa74-c6721ef513e8/exec-2fd78472-a834-45ca-b405-3c00589143ce.png`
  - 第 2 张 OCR 确认：`/Users/ybh/.codex/generated_images/019f5518-914e-7c22-aa74-c6721ef513e8/exec-ec7ae090-1e15-45de-8620-b3df0fffbe96.png`
  - 第 3 张思考提示：`/Users/ybh/.codex/generated_images/019f5518-914e-7c22-aa74-c6721ef513e8/exec-a7562f3a-58d1-4099-8aa0-fd8b24b5e8a8.png`
- implementation evidence:
  - 修复前实体 iPad 照片：`/Users/ybh/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/yubinhong1990_ffc1/temp/RWTemp/2026-07/2f3418e050839363944a0b90a0e5b81e.jpg`
  - 修复后第 3 张实体 iPad 照片：`/Users/ybh/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/yubinhong1990_ffc1/temp/RWTemp/2026-07/ed6808f5f129391a7ad63d51bd50a2e0.jpg`
  - 模拟器 portrait smoke：`/tmp/study-ui-qa/.qa-ipad-mini-learning.png`
- 修复后实体 iPad：Flutter 已横屏运行，但 Flutter screenshot 对实体设备不支持
- 拍题输入页：相机入口已由用户在实体 iPad 上完成拍照、权限和“已选择题目照片”回归；相册选择仍待手工回归
- intended viewport: `1194 × 834` landscape tablet
- intended states: synthetic child `小禾` learning desk; OCR confirmation with synthetic worksheet photo and editable candidate text; fraction practice with thinking and hint actions

The iPad mini simulator rendered the learning desk successfully at `1488 × 2266` portrait. The screenshot was used for a smoke check, but it is not an equivalent comparison viewport.

## Findings

- [P1] Exact visual comparison remains blocked because the physical iPad can run the app but Flutter does not support screenshot capture for that device.
  Evidence: `flutter run -d 00008110-0011356E0E41801E --dart-define=STUDY_API_URL=http://192.168.100.158:8000` built, installed, and launched successfully; `devicectl device info displays` reports landscape bounds `2266 × 1488`; `flutter screenshot` returns `Screenshot not supported for 余斌宏的iPad`. The simulator screenshot was captured successfully but measures `1488 × 2266` portrait, not the target landscape viewport.
  Impact: exact typography, spacing, asset crop, and responsive behavior cannot be verified against the source image in this environment.
  Fix: use Xcode's connected-device screen viewer or a manually captured iPad screenshot, then compare the landscape app state at `1194 × 834` (or normalize the physical `2266 × 1488` capture). No signing or Apple account changes were made by the agent.

## Fidelity review from the supplied device photo

- Typography: hierarchy and Chinese copy are readable; `Synthetic Child A` is expected synthetic API data rather than the visual source's `小禾`.
- Spacing and layout rhythm: the supplied photo was portrait and therefore showed the compact stacked layout. The app now locks iOS to landscape; post-fix device metadata confirms `landscapeLeft` at `2266 × 1488`.
- Colors and tokens: mint/green primary actions, warm background, border, and coral secondary action are consistent with the source direction; the camera exposure makes exact color sampling unreliable.
- Image and asset fidelity: avatar and fraction illustration render with the intended crop and no placeholder asset is visible; the camera photo introduces glare and moiré that prevent pixel-level review.
- Copy and content: task title, progress, `继续学习`, `拍题`, and `稍后再做` are visible and usable; synthetic child naming is a data-fixture difference only.
- Third-screen interaction visibility: both hint buttons and `暂时跳过` remain visible on the landscape iPad photo; no P1/P2 overflow is evident in the supplied frame.

## Implementation Checklist

- [x] Implement first learning-desk screen in Flutter.
- [x] Implement second OCR confirmation screen with candidate text editing and confirmation state.
- [x] Implement third thinking-practice screen with two hint levels and thought-sharing state.
- [x] Add generated avatar and fraction illustration assets.
- [x] Add the synthetic worksheet photo asset and make `拍题` open the OCR flow.
- [x] Add a camera/gallery input page; selected local images enter the existing OCR confirmation screen without external upload.
- [x] Make `继续学习`, `拍题`, `稍后再做`, candidate editing, and confirmation interactive.
- [x] Lock iOS child app to landscape for the iPad primary-device boundary.
- [x] Run Flutter analyze and 6 Flutter widget/unit tests.
- [x] Capture a simulator smoke screenshot of the rendered learning desk.
- [ ] Capture both rendered screens at the source landscape viewport.
- [ ] Compare source and implementation, then resolve P0/P1/P2 drift.

## Comparison History

- Pass 1: supplied device photo showed the app in portrait, which differed from the landscape iPad product boundary. Fix applied in `apps/child_flutter/lib/main.dart` with iOS landscape orientation preferences.
- Pass 2: hot restart on the physical iPad succeeded; `devicectl device info displays` confirmed `2266 × 1488` and `landscapeLeft`. Exact post-fix screenshot comparison remains unavailable because Flutter reports screenshot unsupported for the physical device.
- Pass 3: third thinking-practice screen added and covered by widget interaction tests; physical-device visual comparison remains blocked by the same screenshot capture limitation.
- Pass 4: supplied landscape iPad photo shows the third screen with the equation, thinking panel, both hint actions, and skip action visible; camera framing/glare prevents exact pixel comparison.
- Pass 5: `image_picker 1.2.3` capture input was added and the physical iPad debug app was fully rebuilt and reinstalled; the user confirmed camera permission, capture, and the “已选择题目照片” state. Gallery permission/error recovery and signed upload/OCR client wiring remain pending.

## Final Result

final result: blocked
