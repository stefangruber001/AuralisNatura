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

    var priceText: String { price > 0 ? "€\(Int(price))" : "" }
}

struct OffersResponse: Decodable { let offers: [Offer] }

struct Doc: Decodable, Identifiable, Hashable {
    let key: String
    let name: String
    let type: String
    let date: String
    var id: String { key }
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
