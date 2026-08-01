# Child Flutter audio dependency review

Reviewed for ADR-0025 on 2026-07-29. Versions are exact in `pubspec.yaml` and `pubspec.lock`.

| Package | Purpose | License | Native/supply-chain notes |
| --- | --- | --- | --- |
| `record 7.1.1` | Foreground PCM16 microphone stream | BSD-3-Clause | Uses platform recorder implementations; no cloud SDK or analytics. Permission is requested only when the child holds the microphone control. |
| `flutter_soloud 4.0.13` | Low-latency 24 kHz PCM playback and immediate interruption | MIT | Bundles the SoLoud C/C++ engine under zlib/libpng and Signalsmith filters under MIT. It adds native build code on Android/iOS and a larger supply-chain/build surface. |

The downloaded package sources occupy about 932 KiB (`record`) and 61 MiB
(`flutter_soloud`) in the local pub cache; this is not the installed app size.
The 2026-07-29 release verification produced a 62 MiB universal Android APK
and a 23 MiB unsigned iOS `Runner.app`. A clean pre-feature baseline is not
available in the dirty worktree, so the dependency-specific delta remains
unmeasured and must be reviewed before opening the feature.
`flutter_soloud` 4.0.13 embeds the raw PCM buffer-stream API needed here;
higher-level file players do not provide the same bounded PCM streaming and
immediate interruption contract. No background audio/recording mode is added.

The upstream license files remain the authoritative notices bundled by pub.
Do not remove upstream license/source notices when redistributing native
sources or artifacts.
