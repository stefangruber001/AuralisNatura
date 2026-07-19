import SwiftUI
import CoreText

@main
struct AuralisNaturaApp: App {
    @StateObject private var toasts: ToastStore
    @StateObject private var session: SessionStore
    @StateObject private var settings = SettingsStore()
    @StateObject private var catalog = CatalogStore()
    @StateObject private var documents = DocumentsStore()
    @StateObject private var router = TabRouter()
    @StateObject private var avatar = AvatarStore()

    init() {
        Self.registerFonts()
        let toastStore = ToastStore()
        _toasts = StateObject(wrappedValue: toastStore)
        _session = StateObject(wrappedValue: SessionStore(toasts: toastStore))
    }

    var body: some Scene {
        WindowGroup {
            SessionGate()
                .environmentObject(toasts)
                .environmentObject(session)
                .environmentObject(settings)
                .environmentObject(catalog)
                .environmentObject(documents)
                .environmentObject(router)
                .environmentObject(avatar)
                .preferredColorScheme(.light)
        }
    }

    private static func registerFonts() {
        // Depending on how Xcode copies the synchronized folder, the TTFs may sit
        // under Fonts/ or flat in the bundle root — register whichever exists.
        let inFolder = Bundle.main.urls(forResourcesWithExtension: "ttf", subdirectory: "Fonts") ?? []
        let flat = Bundle.main.urls(forResourcesWithExtension: "ttf", subdirectory: nil) ?? []
        let urls = inFolder.isEmpty ? flat : inFolder
        guard !urls.isEmpty else { return }
        CTFontManagerRegisterFontURLs(urls as CFArray, .process, true, nil)
    }
}

/// Root gate: login vs. main app, session-expiry aware, toast overlay on top.
struct SessionGate: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var settings: SettingsStore

    var body: some View {
        ZStack {
            if session.isLoggedIn {
                MainTabView()
                    .transition(.opacity)
            } else {
                LoginView()
                    .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: session.isLoggedIn)
        .overlay { ToastOverlay() }
        .alert(L10n["login.saveCreds.title"], isPresented: credentialOfferShown) {
            Button(L10n["login.saveCreds.yes"]) { session.acceptCredentialOffer() }
            Button(L10n["login.saveCreds.no"], role: .cancel) { session.declineCredentialOffer() }
        } message: {
            Text(L10n["login.saveCreds.msg"])
        }
        .id(settings.lang) // rebuild the tree when the language changes
    }

    /// Alerts always dismiss through a button, so the setter is a no-op.
    private var credentialOfferShown: Binding<Bool> {
        Binding(
            get: { session.pendingCredentialOffer != nil },
            set: { _ in }
        )
    }
}
