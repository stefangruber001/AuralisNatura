import SwiftUI
import Combine
import LocalAuthentication
import UIKit

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

    /// Browsing without an account. Guest is simply "no token" — there is no
    /// anonymous session to mint, nothing to store, and nothing about a guest
    /// ever reaches the server beyond the two public endpoints.
    var isGuest: Bool { token == nil }

    /// Has this device ever been signed in? A returning client should land on the
    /// sign-in screen, not in the shop — only a first-time visitor gets the guest
    /// app as the front door.
    static var hadSession: Bool { UserDefaults.standard.bool(forKey: "an_had_session") }

    /// Set when a guest chooses to browse, so the choice survives a relaunch and
    /// she is not thrown back at the login wall she just stepped past.
    @Published var browsingAsGuest = UserDefaults.standard.bool(forKey: "an_guest_chosen")

    func chooseGuestBrowsing() {
        UserDefaults.standard.set(true, forKey: "an_guest_chosen")
        browsingAsGuest = true
    }

    /// Back to the sign-in screen from guest browsing. `an_had_session` is set so
    /// the gate shows the form even for someone who has never signed in here —
    /// otherwise a first-time visitor tapping "Sign in" would bounce straight back.
    func leaveGuestBrowsing() {
        UserDefaults.standard.set(false, forKey: "an_guest_chosen")
        UserDefaults.standard.set(true, forKey: "an_had_session")
        browsingAsGuest = false
    }

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
        UserDefaults.standard.set(true, forKey: "an_had_session")
        // Clear the guest choice, or a later logout would drop her into the shop
        // instead of the sign-in screen she expects.
        UserDefaults.standard.set(false, forKey: "an_guest_chosen")
        browsingAsGuest = false
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

    /// True when we have no profile AND the last load failed (offline at launch) —
    /// views show an error/retry state instead of eternal skeletons.
    @Published private(set) var meLoadFailed = false

    func refreshMe() async {
        guard token != nil else { return }
        do {
            me = try await api.get("/api/me?lang=\(L10n.lang)")
            meLoadFailed = false
        } catch {
            // Keep the last known state; a 401 is handled via .sessionExpired.
            meLoadFailed = (me == nil)
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
        meLoadFailed = false
        // let per-client caches (documents, …) clear themselves — privacy: the next
        // account on this device must never see the previous client's data
        NotificationCenter.default.post(name: .sessionClosed, object: nil)
    }
}

extension Notification.Name {
    static let sessionClosed = Notification.Name("an.sessionClosed")
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

    /// Impulse articles already opened. Deliberately device-local: which
    /// article someone read is an inference about her health interests, so it
    /// is never sent to the server.
    @Published var impulseSeen: [String] = [] {
        didSet { UserDefaults.standard.set(impulseSeen, forKey: "an_imp_seen") }
    }

    func markImpulseSeen(_ id: String) {
        guard !impulseSeen.contains(id) else { return }
        impulseSeen = Array((impulseSeen + [id]).suffix(200))
    }

    init() {
        lang = UserDefaults.standard.string(forKey: "an_lang") ?? L10n.defaultLanguage
        faceIDEnabled = (UserDefaults.standard.object(forKey: "an_faceid") as? Bool) ?? true
        impulseSeen = UserDefaults.standard.stringArray(forKey: "an_imp_seen") ?? []
    }
}

// MARK: - Catalog (offers)

@MainActor
final class CatalogStore: ObservableObject {
    @Published var offers: [Offer] = []
    @Published var loading = false
    private var usingFallback = false

    func load() async {
        loading = offers.isEmpty
        defer { loading = false }
        do {
            // the server localises the names from ?lang= and defaults to German —
            // without this an English or Spanish reader saw German programme names
            let resp: OffersResponse = try await APIClient.shared.get(
                "/api/app/offers?lang=\(L10n.lang)", auth: false)
            var list = resp.offers.isEmpty ? Self.fallback : resp.offers
            // the server intentionally omits the corporate "grove" offer (enquiry-only);
            // the app still shows it as the 4th card
            if !list.contains(where: { $0.key == "grove" }),
               let grove = Self.fallback.first(where: { $0.key == "grove" }) {
                list.append(grove)
            }
            offers = list
            usingFallback = resp.offers.isEmpty
        } catch {
            // recompute the fallback so taglines follow the current language
            if offers.isEmpty || usingFallback {
                offers = Self.fallback
                usingFallback = true
            }
        }
    }

    /// Assets are built from their masters by ios-app/scripts/build_photo_assets.py
    /// — 4:3 landscape to match the card hero, with a real 1x/2x/3x ladder.
    static func photo(for key: String) -> String {
        switch key {
        case "root":     return "PhotoNourish"
        case "bloom":    return "PhotoTea"
        case "flourish": return "PhotoBowl"
        default:         return "PhotoPortrait"
        }
    }

    /// Offline-safe static list matching the /api/app/offers shape.
    static var fallback: [Offer] {
        [
            // names and taglines resolve through displayName/displayTagline, so
            // these literals are only ever a last resort for an unknown key
            Offer(key: "root", name: L10n["prog.root.name"], price: 199,
                  tagline: L10n["prog.root.tagline"], buyUrl: nil),
            Offer(key: "bloom", name: L10n["prog.bloom.name"], price: 399,
                  tagline: L10n["prog.bloom.tagline"], buyUrl: nil),
            Offer(key: "flourish", name: L10n["prog.flourish.name"], price: 899,
                  tagline: L10n["prog.flourish.tagline"], buyUrl: nil),
            Offer(key: "grove", name: L10n["prog.grove.name"], price: 0,
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
    private var bag = Set<AnyCancellable>()

    init() {
        // privacy: wipe this client's cached documents the moment the session closes
        NotificationCenter.default.publisher(for: .sessionClosed)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in self?.reset() }
            .store(in: &bag)
    }

    func reset() {
        docs = []; loaded = false; failed = false
    }

    func load() async {
        do {
            let resp: DocumentsResponse = try await APIClient.shared.get(
                "/api/my/documents?lang=\(L10n.lang)")
            docs = resp.documents
            failed = false
        } catch {
            failed = docs.isEmpty
        }
        loaded = true
    }
}

// MARK: - Profile avatar

/// The client's own profile photo. Stored locally (Documents), keyed by client
/// ID so a different account on the same device never sees another client's
/// picture. The in-memory image is dropped on sign-out; the file is kept so the
/// same client sees their photo again after re-login.
@MainActor
final class AvatarStore: ObservableObject {
    @Published private(set) var image: UIImage?
    private var currentId: String?
    private var bag = Set<AnyCancellable>()

    init() {
        NotificationCenter.default.publisher(for: .sessionClosed)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in self?.image = nil; self?.currentId = nil }
            .store(in: &bag)
    }

    private func fileURL(for id: String) -> URL {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        let safe = id.replacingOccurrences(of: "/", with: "_")
        return dir.appendingPathComponent("an-avatar-\(safe).jpg")
    }

    /// Load the stored photo for a client (no-op if already loaded for this id).
    func load(for id: String) {
        guard !id.isEmpty else { return }
        if currentId == id, image != nil { return }
        currentId = id
        if let data = try? Data(contentsOf: fileURL(for: id)), let img = UIImage(data: data) {
            image = img
        } else {
            image = nil
        }
    }

    /// Persist newly picked image data (downscaled) for a client.
    func save(_ data: Data, for id: String) {
        guard !id.isEmpty, let picked = UIImage(data: data) else { return }
        let resized = picked.anDownscaled(maxDimension: 512)
        guard let jpeg = resized.jpegData(compressionQuality: 0.85) else { return }
        try? jpeg.write(to: fileURL(for: id), options: .atomic)
        currentId = id
        image = resized
    }

    func remove(for id: String) {
        guard !id.isEmpty else { return }
        try? FileManager.default.removeItem(at: fileURL(for: id))
        image = nil
    }
}

private extension UIImage {
    /// Downscale so the longest side is at most `maxDimension` (keeps aspect).
    func anDownscaled(maxDimension: CGFloat) -> UIImage {
        let longest = Swift.max(size.width, size.height)
        guard longest > maxDimension, longest > 0 else { return self }
        let scale = maxDimension / longest
        let newSize = CGSize(width: size.width * scale, height: size.height * scale)
        let format = UIGraphicsImageRendererFormat.default()
        format.scale = 1
        return UIGraphicsImageRenderer(size: newSize, format: format).image { _ in
            draw(in: CGRect(origin: .zero, size: newSize))
        }
    }
}

// MARK: - Tab routing

@MainActor
final class TabRouter: ObservableObject {
    enum Tab: Hashable {
        case home, programmes, booking, impulse, profile
    }
    @Published var tab: Tab = .home
}
