import Foundation

// MARK: - Responses (decoded with .convertFromSnakeCase)

struct LoginResponse: Decodable {
    let token: String
    let clientId: String
    let name: String
    let language: String
}

struct Me: Decodable {
    let clientId: String
    let name: String
    let language: String
    let stage: String
    let hasIntake: Bool
    let reportReady: Bool
    let created: String?
    let wellbeing: Wellbeing?
    let priorities: [Priority]
    let habits: [String]

    enum CodingKeys: String, CodingKey {
        case clientId, name, language, stage, hasIntake, reportReady,
             created, wellbeing, priorities, habits, sessions
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        clientId    = try c.decode(String.self, forKey: .clientId)
        name        = try c.decodeIfPresent(String.self, forKey: .name) ?? ""
        language    = try c.decodeIfPresent(String.self, forKey: .language) ?? "de"
        stage       = try c.decodeIfPresent(String.self, forKey: .stage) ?? "invited"
        hasIntake   = try c.decodeIfPresent(Bool.self, forKey: .hasIntake) ?? false
        reportReady = try c.decodeIfPresent(Bool.self, forKey: .reportReady) ?? false
        created     = try c.decodeIfPresent(String.self, forKey: .created)
        wellbeing   = try c.decodeIfPresent(Wellbeing.self, forKey: .wellbeing)
        priorities  = try c.decodeIfPresent([Priority].self, forKey: .priorities) ?? []
        habits      = try c.decodeIfPresent([String].self, forKey: .habits) ?? []
        sessions    = try c.decodeIfPresent([SessionRow].self, forKey: .sessions) ?? []
    }

    /// Her confirmed upcoming programme calls. The server has returned these since
    /// the session planner shipped (portal/server/app.py:381-398); the app simply
    /// never decoded them, so anything wanting to show or remind about a session
    /// was reading a field that did not exist.
    var sessions: [SessionRow] = []

    /// Completed journey steps 1…4 (Zugang → Fragebogen → Vorbereitung → Bericht).
    var journeyStep: Int { Me.journeyStep(for: stage, hasIntake: hasIntake) }

    static func journeyStep(for stage: String, hasIntake: Bool) -> Int {
        switch stage {
        case "sent", "done":            return 4
        case "prep", "draft", "review": return 3
        case "intake":                  return 2
        default:                        return hasIntake ? 2 : 1
        }
    }

    var firstName: String {
        name.split(separator: " ").first.map(String.init) ?? name
    }
}

struct Wellbeing: Decodable {
    /// 1–5 self-assessment scales (energy/sleep/stress/digestion); may be empty.
    let scales: [String: Int]
    let score: Int?

    enum CodingKeys: String, CodingKey { case scales, score }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        scales = try c.decodeIfPresent([String: Int].self, forKey: .scales) ?? [:]
        score  = try c.decodeIfPresent(Int.self, forKey: .score)
    }

    var hasData: Bool { !scales.isEmpty }
}

struct Priority: Decodable, Identifiable, Hashable {
    let title: String
    let firstStep: String?
    var id: String { title }
}

struct Offer: Decodable, Identifiable, Hashable {
    let key: String
    let name: String
    let price: Double
    let tagline: String
    let buyUrl: String?
    var id: String { key }

    /// Display copy is the APP's, not the server's.
    ///
    /// The server localises names but its taglines come straight from
    /// config.json, which only holds the German master — so an English reader
    /// saw "Clarity · Tiefen-Erstanalyse". And when the server was unreachable
    /// the offline list took over with hard-coded German names. Copy lives in
    /// L10n, keyed by the offer key; the server owns price, buy_url and which
    /// offers exist. A package this build has no copy for still shows, using
    /// whatever the server called it.
    var displayName: String { L10n.opt("prog.\(key).name") ?? name }
    var displayTagline: String { L10n.opt("prog.\(key).tagline") ?? tagline }

    /// "199 €" in German and Spanish, "€199" in English — the symbol's side and
    /// the separators are the locale's business, not ours. It used to be a
    /// hard-coded "€\(Int(price))", which is the English convention shown to
    /// everyone, and silently truncated any non-integer price.
    var priceText: String {
        guard price > 0 else { return "" }
        let f = NumberFormatter()
        f.numberStyle = .currency
        f.currencyCode = "EUR"
        f.locale = Locale(identifier: L10n.localeIdentifier)
        f.maximumFractionDigits = price == price.rounded() ? 0 : 2
        return f.string(from: NSNumber(value: price)) ?? "€\(Int(price))"
    }
}

struct OffersResponse: Decodable { let offers: [Offer] }

struct Doc: Decodable, Identifiable, Hashable {
    let key: String
    let name: String
    let type: String
    let date: String
    var id: String { key }
    /// The same ISO string the server sends ("2026-08-17"), read in the client's
    /// own convention instead of raw.
    var dateLabel: String {
        let parse = DateFormatter()
        parse.dateFormat = "yyyy-MM-dd"
        parse.locale = Locale(identifier: "en_US_POSIX")
        guard let d = parse.date(from: String(date.prefix(10))) else { return date }
        let out = DateFormatter()
        out.locale = Locale(identifier: L10n.localeIdentifier)
        out.dateStyle = .medium
        out.timeStyle = .none
        return out.string(from: d)
    }
}

struct DocumentsResponse: Decodable { let documents: [Doc] }

struct Slot: Decodable, Hashable {
    let utc: String
    let local: String
}

struct Day: Decodable, Identifiable, Hashable {
    let date: String
    let label: String
    let slots: [Slot]
    var id: String { date }
}

struct SlotsResponse: Decodable {
    let timezone: String
    let days: [Day]
}

struct ReportTokenResponse: Decodable { let token: String }

struct OkResponse: Decodable { let ok: Bool }

// MARK: - Request bodies (encoded with .convertToSnakeCase)

struct EmptyBody: Encodable {}

struct LoginBody: Encodable {
    let clientId: String
    let password: String
}

struct IntakeBody: Encodable {
    struct Scales: Encodable {
        let energy: Int
        let sleep: Int
        let stress: Int
        let digestion: Int
    }
    struct Consent: Encodable {
        let coachingNotMedical: Bool
        let gdprHealthData: Bool
    }
    let goal: String
    let whyNow: String
    let b: Scales
    let language: String
    let redFlags: [String]
    let consent: Consent
}

struct ChangePasswordBody: Encodable {
    let current: String
    let newPassword: String
    enum CodingKeys: String, CodingKey {
        case current
        case newPassword = "new"
    }
}


/// One confirmed upcoming programme call, as the portal sends it.
/// Server shape (portal/server/app.py:385-389): label, when, utc.
struct SessionRow: Codable, Identifiable, Hashable {
    let label: String        // localised, e.g. "Wochengespräch 2"
    let when: String         // already formatted in the client's language
    let utc: String          // ISO 8601, for scheduling and sorting
    var id: String { utc + label }
}


/// One Impulse article, already flattened to this client's language by the server.
struct Article: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let body: String
    let publishedAt: String
    let audience: String

    private enum CodingKeys: String, CodingKey {
        case id, title, body, publishedAt = "published_at", audience
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id          = try c.decode(String.self, forKey: .id)
        title       = try c.decodeIfPresent(String.self, forKey: .title) ?? ""
        body        = try c.decodeIfPresent(String.self, forKey: .body) ?? ""
        publishedAt = try c.decodeIfPresent(String.self, forKey: .publishedAt) ?? ""
        audience    = try c.decodeIfPresent(String.self, forKey: .audience) ?? "clients"
    }

    /// Blank-line separated, the way she writes it in the console.
    var paragraphs: [String] {
        body.components(separatedBy: "\n\n")
            .map { $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    var teaser: String { paragraphs.first ?? body }

    /// dd.MM.yyyy from the ISO timestamp, without pulling in a formatter.
    /// The reader's date convention, not Germany's. This was hand-assembled as
    /// dd.MM.yyyy for everyone, so an English reader saw "17.08.2026".
    var dateLabel: String {
        let iso = String(publishedAt.prefix(10))
        let parse = DateFormatter()
        parse.dateFormat = "yyyy-MM-dd"
        parse.locale = Locale(identifier: "en_US_POSIX")
        guard let date = parse.date(from: iso) else { return "" }
        let out = DateFormatter()
        out.locale = Locale(identifier: L10n.localeIdentifier)
        out.dateStyle = .long
        out.timeStyle = .none
        return out.string(from: date)
    }
}

struct JournalResponse: Codable {
    let articles: [Article]
}
