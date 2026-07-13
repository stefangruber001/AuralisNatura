import Foundation

extension Notification.Name {
    static let sessionExpired = Notification.Name("an.sessionExpired")
}

enum APIError: Error {
    case unauthorized
    case network
    case conflict
    case server(String)

    var message: String {
        switch self {
        case .unauthorized:    return L10n["error.unauthorized"]
        case .network:         return L10n["error.network"]
        case .conflict:        return L10n["error.conflict"]
        case .server(let msg): return msg.isEmpty ? L10n["error.server"] : msg
        }
    }
}

/// Thin JSON client for api.auralisnatura.com. Stateless apart from the
/// shared URLSession; the bearer token is read from the Keychain per request.
final class APIClient: @unchecked Sendable {
    static let shared = APIClient()

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    private init() {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 15
        cfg.waitsForConnectivity = false
        session = URLSession(configuration: cfg)

        decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
    }

    var baseURL: URL {
        #if DEBUG
        if let s = UserDefaults.standard.string(forKey: "api_base"),
           let url = URL(string: s) {
            return url
        }
        #endif
        // Constant, guaranteed-valid URL.
        return URL(string: "https://api.auralisnatura.com") ?? URL(fileURLWithPath: "/")
    }

    // MARK: Public API

    func get<T: Decodable>(_ path: String, auth: Bool = true) async throws -> T {
        let data = try await run(request(path, auth: auth), authed: auth)
        return try decode(data)
    }

    func post<B: Encodable, R: Decodable>(_ path: String, body: B, auth: Bool = true) async throws -> R {
        var req = request(path, auth: auth)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try? encoder.encode(body)
        let data = try await run(req, authed: auth)
        return try decode(data)
    }

    /// Raw bytes (e.g. the report PDF, authorised via a short-lived query token).
    func getRaw(_ path: String, query: [URLQueryItem] = [], auth: Bool = false) async throws -> Data {
        try await run(request(path, query: query, auth: auth), authed: auth)
    }

    // MARK: Internals

    private func request(_ path: String, query: [URLQueryItem] = [], auth: Bool) -> URLRequest {
        var url = baseURL.appending(path: path)
        if !query.isEmpty { url.append(queryItems: query) }
        var req = URLRequest(url: url)
        if auth, let token = Keychain.token {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return req
    }

    private func run(_ req: URLRequest, authed: Bool) async throws -> Data {
        let data: Data
        let resp: URLResponse
        do {
            (data, resp) = try await session.data(for: req)
        } catch {
            if error is CancellationError { throw error }
            throw APIError.network
        }
        guard let http = resp as? HTTPURLResponse else { throw APIError.network }
        switch http.statusCode {
        case 200..<300:
            return data
        case 401:
            if authed {
                NotificationCenter.default.post(name: .sessionExpired, object: nil)
            }
            throw APIError.unauthorized
        case 409:
            throw APIError.conflict
        default:
            let msg = (try? JSONDecoder().decode([String: String].self, from: data))?["error"] ?? ""
            throw APIError.server(msg)
        }
    }

    private func decode<T: Decodable>(_ data: Data) throws -> T {
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.server("")
        }
    }
}
