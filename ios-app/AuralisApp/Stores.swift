import SwiftUI
import Combine
import LocalAuthentication

// MARK: - Session

@MainActor
final class SessionStore: ObservableObject {
    @Published private(set) var token: String?
    @Published private(set) var me: Me?
    @Published var busy = false
    @Published var pendingCredentialOffer: Keychain.Credentials?

    let toasts: ToastStore
    private let api = APIClient.shared
    private var bag = Set<AnyCancellable>()

    var isLoggedIn: Bool { token != nil }

    init(toasts: ToastStore) {
        self.toasts = toasts
        token = Keychain.token
        NotificationCenter.default.publisher(for: .sessionExpired)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in self?.expire() }
            .store(in: &bag)
    }

    func login(id: String, password: String) async throws {
        busy = true
        defer { busy = false }
        let resp: LoginResponse = try await api.post(
            "/api/login",
            body: LoginBody(clientId: id, password: password),
            auth: false
        )
        Keychain.setToken(resp.token)
        token = resp.token
        await refreshMe()
        offerFaceIDIfAppropriate(id: id, password: password)
    }

    func loginWithBiometrics() async {
        busy = true
        let reason = L10n["login.faceid.reason"]
        let credentials = await Task.detached(priority: .userInitiated) {
            Keychain.readCredentials(reason: reason)
        }.value
        busy = false
        guard let credentials else {
            toasts.show(L10n["login.faceid.failed"], kind: .error)
            return
        }
        do {
            try await login(id: credentials.id, password: credentials.password)
        } catch {
            toasts.show((error as? APIError)?.message ?? L10n["error.generic"], kind: .error)
        }
    }

    func refreshMe() async {
        guard token != nil else { return }
        do {
            me = try await api.get("/api/me")
        } catch {
            // Keep the last known state; a 401 is handled via .sessionExpired.
        }
    }

    private func offerFaceIDIfAppropriate(id: String, password: String) {
        let defaults = UserDefaults.standard
        guard SettingsStore.biometricsAvailable,
              !defaults.bool(forKey: "an_creds_saved"),
              !defaults.bool(forKey: "an_creds_declined") else { return }
        pendingCredentialOffer = Keychain.Credentials(id: id, password: password)
    }

    func acceptCredentialOffer() {
        guard let credentials = pendingCredentialOffer else { return }
        pendingCredentialOffer = nil
        if Keychain.saveCredentials(credentials) {
            UserDefaults.standard.set(true, forKey: "an_creds_saved")
            toasts.show(L10n["login.faceid.saved"])
        }
    }

    func declineCredentialOffer() {
        guard pendingCredentialOffer != nil else { return }
        pendingCredentialOffer = nil
        UserDefaults.standard.set(true, forKey: "an_creds_declined")
    }

    func expire() {
        guard token != nil else { return }
        logout()
        toasts.show(L10n["session.expired"], kind: .error)
    }

    func logout() {
        Keychain.setToken(nil)
        token = nil
        me = nil
    }
}

// MARK: - Settings

@MainActor
final class SettingsStore: ObservableObject {
    @Published var lang: String {
        didSet { UserDefaults.standard.set(lang, forKey: "an_lang") }
    }
    @Published var faceIDEnabled: Bool {
        didSet { UserDefaults.standard.set(faceIDEnabled, forKey: "an_faceid") }
    }

    static var biometricsAvailable: Bool {
        var error: NSError?
        return LAContext().canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
    }

    init() {
        lang = UserDefaults.standard.string(forKey: "an_lang") ?? L10n.defaultLanguage
        faceIDEnabled = (UserDefaults.standard.object(forKey: "an_faceid") as? Bool) ?? true
    }
}

// MARK: - Catalog (offers)

@MainActor
final class CatalogStore: ObservableObject {
    @Published var offers: [Offer] = []
    @Published var loading = false

    func load() async {
        loading = offers.isEmpty
        defer { loading = false }
        do {
            let resp: OffersResponse = try await APIClient.shared.get("/api/app/offers", auth: false)
            offers = resp.offers.isEmpty ? Self.fallback : resp.offers
        } catch {
            if offers.isEmpty { offers = Self.fallback }
        }
    }

    static func photo(for key: String) -> String {
        switch key {
        case "root":     return "PhotoNourish"
        case "bloom":    return "PhotoTea"
        case "flourish": return "PhotoConsult"
        default:         return "PhotoPortrait"
        }
    }

    /// Offline-safe static list matching the /api/app/offers shape.
    static var fallback: [Offer] {
        [
            Offer(key: "root", name: "The Root Session", price: 198,
                  tagline: L10n["prog.root.tagline"], buyUrl: nil),
            Offer(key: "bloom", name: "The Bloom", price: 398,
                  tagline: L10n["prog.bloom.tagline"], buyUrl: nil),
            Offer(key: "flourish", name: "The Flourishing", price: 798,
                  tagline: L10n["prog.flourish.tagline"], buyUrl: nil),
            Offer(key: "grove", name: "The Grove", price: 0,
                  tagline: L10n["prog.grove.tagline"], buyUrl: nil)
        ]
    }
}

// MARK: - Documents

@MainActor
final class DocumentsStore: ObservableObject {
    @Published var docs: [Doc] = []
    @Published var loaded = false
    @Published var failed = false

    func load() async {
        do {
            let resp: DocumentsResponse = try await APIClient.shared.get("/api/my/documents")
            docs = resp.documents
            failed = false
        } catch {
            failed = docs.isEmpty
        }
        loaded = true
    }
}

// MARK: - Tab routing

@MainActor
final class TabRouter: ObservableObject {
    enum Tab: Hashable {
        case home, programmes, booking, journey, profile
    }
    @Published var tab: Tab = .home
}
