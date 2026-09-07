import Flutter
import Network
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  private var localNetworkConnections: [UUID: NWConnection] = [:]

  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
    let channel = FlutterMethodChannel(
      name: "study/local_network",
      binaryMessenger: engineBridge.applicationRegistrar.messenger()
    )
    channel.setMethodCallHandler { [weak self] call, result in
      guard call.method == "prepare" else {
        result(FlutterMethodNotImplemented)
        return
      }
      guard
        let arguments = call.arguments as? [String: Any],
        let host = arguments["host"] as? String,
        !host.isEmpty,
        let portValue = arguments["port"] as? Int,
        let port = NWEndpoint.Port(rawValue: UInt16(clamping: portValue))
      else {
        result(FlutterError(
          code: "invalid_arguments",
          message: "A valid host and port are required.",
          details: nil
        ))
        return
      }
      self?.prepareLocalNetworkAccess(host: host, port: port, result: result)
    }
  }

  private func prepareLocalNetworkAccess(
    host: String,
    port: NWEndpoint.Port,
    result: @escaping FlutterResult
  ) {
    let identifier = UUID()
    let connection = NWConnection(host: NWEndpoint.Host(host), port: port, using: .tcp)
    localNetworkConnections[identifier] = connection
    var completed = false

    func finish(_ reachable: Bool) {
      guard !completed else { return }
      completed = true
      connection.stateUpdateHandler = nil
      connection.cancel()
      localNetworkConnections.removeValue(forKey: identifier)
      result(reachable)
    }

    connection.stateUpdateHandler = { state in
      switch state {
      case .ready:
        finish(true)
      case .failed:
        finish(false)
      case .cancelled:
        finish(false)
      default:
        break
      }
    }
    connection.start(queue: .main)
    DispatchQueue.main.asyncAfter(deadline: .now() + 20) {
      finish(false)
    }
  }
}
