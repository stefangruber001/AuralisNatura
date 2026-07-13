import Foundation
import Security
import LocalAuthentication

/// Minimal SecItem wrapper. Token stored as a plain generic password;
/// credentials for Face ID login stored behind `.biometryCurrentSet`.
enum Keychain {
    private static let service = "com.auralisnatura.app"

    struct Credentials: Codable {
        let id: String
        let password: String
    }

    // MARK: Generic password primitives

    @discardableResult
    static func save(_ data: Data, account: String, access: SecAccessControl? = nil) -> Bool {
        delete(account: account)
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: data
        ]
        if let access {
            query[kSecAttrAccessControl as String] = access
        } else {
            query[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        }
        return SecItemAdd(query as CFDictionary, nil) == errSecSuccess
    }

    static func read(account: String, context: LAContext? = nil) -> Data? {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        if let context {
            query[kSecUseAuthenticationContext as String] = context
        }
        var out: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &out) == errSecSuccess else { return nil }
        return out as? Data
    }

    static func delete(account: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account
        ]
        SecItemDelete(query as CFDictionary)
    }

    // MARK: Session token

    static var token: String? {
        read(account: "token").flatMap { String(data: $0, encoding: .utf8) }
    }

    static func setToken(_ token: String?) {
        if let token {
            save(Data(token.utf8), account: "token")
        } else {
            delete(account: "token")
        }
    }

    // MARK: Face ID credentials

    @discardableResult
    static func saveCredentials(_ credentials: Credentials) -> Bool {
        guard let data = try? JSONEncoder().encode(credentials) else { return false }
        var error: Unmanaged<CFError>?
        guard let access = SecAccessControlCreateWithFlags(
            nil,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            .biometryCurrentSet,
            &error
        ) else { return false }
        return save(data, account: "credentials", access: access)
    }

    /// Blocks while Face ID runs — call off the main thread.
    static func readCredentials(reason: String) -> Credentials? {
        let context = LAContext()
        context.localizedReason = reason
        guard let data = read(account: "credentials", context: context) else { return nil }
        return try? JSONDecoder().decode(Credentials.self, from: data)
    }

    static func deleteCredentials() {
        delete(account: "credentials")
    }
}
