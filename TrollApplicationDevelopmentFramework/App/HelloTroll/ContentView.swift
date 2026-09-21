import SwiftUI

struct ContentView: View {
    var body: some View {
        NavigationView {
            List {
                Section(header: Text("TADF")) {
                    row("Framework", TADF.framework)
                    row("Channel", TADF.channel)
                    row("Min iOS", TADF.minIOS)
                }
                Section(header: Text("Identity")) {
                    row("Name", TADF.displayName)
                    row("Product", TADF.appName)
                    row("Bundle ID", TADF.bundleID)
                    row("Version", "\(TADF.version) (\(TADF.build))")
                }
                Section(header: Text("Capabilities")) {
                    ForEach(TADF.capabilityList, id: \.self) { cap in
                        Text(cap)
                            .font(.system(.body, design: .monospaced))
                    }
                }
                Section(header: Text("Install")) {
                    Text("Copy this framework, put Xcode sources in App/<name>/, set pack_source in trollapp.yml, then ./scripts/package_ipa.sh. IPA goes to work/<pack_source>/dist/.")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
            }
            .navigationBarTitle(TADF.displayName)
        }
        .navigationViewStyle(StackNavigationViewStyle())
    }

    private func row(_ title: String, _ value: String) -> some View {
        HStack {
            Text(title)
            Spacer()
            Text(value)
                .foregroundColor(.secondary)
                .multilineTextAlignment(.trailing)
        }
    }
}
