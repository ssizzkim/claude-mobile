import SwiftUI

@main
struct JogakApp: App {
    @StateObject private var store = Store()

    var body: some Scene {
        WindowGroup("조각") {
            ContentView()
                .environmentObject(store)
                .frame(minWidth: 720, minHeight: 480)
        }
        .commands {
            CommandGroup(replacing: .newItem) { }
        }
    }
}
