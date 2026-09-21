import NetworkExtension

/// Standard TADF Packet Tunnel: applies HTTP(S) proxy settings on a dummy
/// tunnel so the system VPN indicator is on while traffic uses the proxy.
final class PacketTunnelProvider: NEPacketTunnelProvider {
    private var reading = false

    override func startTunnel(
        options: [String: NSObject]?,
        completionHandler: @escaping (Error?) -> Void
    ) {
        let conf = (protocolConfiguration as? NETunnelProviderProtocol)?.providerConfiguration ?? [:]
        let host = (conf["proxyHost"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let port = (conf["proxyPort"] as? Int)
            ?? (conf["proxyPort"] as? NSNumber)?.intValue
            ?? 8080
        let mirrorHTTPS = (conf["mirrorHTTPS"] as? Bool)
            ?? (conf["mirrorHTTPS"] as? NSNumber)?.boolValue
            ?? true

        guard !host.isEmpty, (1...65535).contains(port) else {
            completionHandler(
                NSError(
                    domain: "PacketTunnel",
                    code: 1,
                    userInfo: [NSLocalizedDescriptionKey: "Missing proxy host/port"]
                )
            )
            return
        }

        let settings = NEPacketTunnelNetworkSettings(tunnelRemoteAddress: host)
        let ipv4 = NEIPv4Settings(addresses: ["198.18.0.1"], subnetMasks: ["255.255.255.255"])
        ipv4.includedRoutes = [
            NEIPv4Route(destinationAddress: "198.18.0.1", subnetMask: "255.255.255.255")
        ]
        settings.ipv4Settings = ipv4

        let proxy = NEProxySettings()
        proxy.httpEnabled = true
        proxy.httpServer = NEProxyServer(address: host, port: port)
        if mirrorHTTPS {
            proxy.httpsEnabled = true
            proxy.httpsServer = NEProxyServer(address: host, port: port)
        }
        proxy.matchDomains = [""]
        proxy.excludeSimpleHostnames = false
        proxy.exceptionList = ["localhost", "*.local", "127.0.0.1", "::1"]
        settings.proxySettings = proxy

        setTunnelNetworkSettings(settings) { [weak self] error in
            if let error {
                completionHandler(error)
                return
            }
            self?.startReadingPackets()
            completionHandler(nil)
        }
    }

    override func stopTunnel(
        with reason: NEProviderStopReason,
        completionHandler: @escaping () -> Void
    ) {
        reading = false
        completionHandler()
    }

    override func handleAppMessage(_ messageData: Data, completionHandler: ((Data?) -> Void)?) {
        completionHandler?(messageData)
    }

    private func startReadingPackets() {
        guard !reading else { return }
        reading = true
        readLoop()
    }

    private func readLoop() {
        guard reading else { return }
        packetFlow.readPackets { [weak self] _, _ in
            self?.readLoop()
        }
    }
}
