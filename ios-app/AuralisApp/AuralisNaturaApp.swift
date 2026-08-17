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

/// Root gate: three doors, not two.
///
/// A signed-in client gets the app. A *returning* client who has been signed in
/// on this device before gets the sign-in screen, so she is never made to hunt
/// for it. Someone who has never signed in gets the app in guest mode — the
/// listing has to lead somewhere, and Apple asks for exactly this in 5.1.1(v):
/// let people use the app without a login where the core isn't account-bound.
struct SessionGate: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var settings: SettingsStore

    /// Sign-in first only for someone who has had a session and hasn't since
    /// asked to browse; everyone else lands in the app.
    private var showsSignIn: Bool {
        !session.isLoggedIn && SessionStore.hadSession && !session.browsingAsGuest
    }

    var body: some View {
        ZStack {
            if showsSignIn {
                LoginView()
                    .transition(.opacity)
            } else {
                MainTabView()
                    .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: showsSignIn)
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
