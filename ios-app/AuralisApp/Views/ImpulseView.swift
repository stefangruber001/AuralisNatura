import SwiftUI

/// Impulse — Desiree's editorial channel.
///
/// Two doors into the same feed. Signed in, `/api/app/journal` serves the
/// client's own language, resolved server-side from her record so there is
/// nothing to choose here. Not signed in, `/api/public/journal` serves only the
/// articles marked public: that is guest mode, and it exists because the App
/// Store listing pointed at a login wall, so a prospect who downloaded the app
/// could see nothing at all.
///
/// Read state stays on the device. Which impulse someone opened is an inference
/// about her health interests — Article 9 data — so it is never sent anywhere.
struct ImpulseView: View {
    /// true when reached from the login screen without an account.
    var guestMode: Bool = false

    @EnvironmentObject private var settings: SettingsStore
    @State private var articles: [Article] = []
    @State private var failed = false
    @State private var loading = true

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                masthead
                if loading && articles.isEmpty {
                    VStack(spacing: 12) {
                        ForEach(0..<3, id: \.self) { _ in SkeletonRow() }
                    }
                    .padding(20)
                } else if failed && articles.isEmpty {
                    EmptyState(icon: "wifi.slash", text: L10n["imp.failed"],
                               retry: { Task { await load() } })
                        .padding(20)
                } else if articles.isEmpty {
                    EmptyState(icon: "leaf", text: L10n["imp.empty"], retry: nil)
                        .padding(20)
                } else {
                    ForEach(articles) { a in
                        NavigationLink { ImpulseReader(article: a) } label: { cell(a) }
                            .buttonStyle(.plain)
                    }
                    ending
                }
            }
        }
        .background(AN.paper.ignoresSafeArea())
        .task { await load() }
    }

    // The v2 dark band: near-vertical wash, gold-bright kicker, seal bleeding
    // off the trailing edge at 10%.
    private var masthead: some View {
        ZStack(alignment: .bottomTrailing) {
            LinearGradient(colors: [AN.forestSoft, AN.forest, AN.forestDeep],
                           startPoint: .top, endPoint: .bottom)
            Image("Emblem")
                .resizable().scaledToFit()
                .frame(width: 190, height: 190)
                .opacity(0.10)
                .offset(x: 58, y: 48)
                .allowsHitTesting(false)
            VStack(alignment: .leading, spacing: 8) {
                Text(L10n["imp.kicker"])
                    .font(ANFont.text(10))
                    .tracking(2.2)
                    .foregroundStyle(AN.goldBright)
                Text(L10n["imp.title"])
                    .font(ANFont.display(26))
                    .foregroundStyle(AN.cream)
                Text(guestMode ? L10n["imp.lead.guest"] : L10n["imp.lead"])
                    .font(ANFont.text(14))
                    .foregroundStyle(AN.sageSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 22)
            .padding(.vertical, 26)
        }
        .clipped()
        .overlay(alignment: .bottom) { Rectangle().fill(AN.goldHair).frame(height: 1) }
    }

    /// Text-first. Never a cropped hero: her typography is baked into the
    /// server-rendered canvas, so cropping it cuts her own words.
    private func cell(_ a: Article) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                if !settings.impulseSeen.contains(a.id) {
                    Rectangle().fill(AN.clay).frame(width: 6, height: 6)
                }
                Text(a.dateLabel)
                    .font(ANFont.text(10)).tracking(1.6)
                    .foregroundStyle(AN.inkFaint)
            }
            if !a.title.isEmpty {
                Text(a.title)
                    .font(ANFont.display(19))
                    .foregroundStyle(AN.ink)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Text(a.teaser)
                .font(ANFont.text(14))
                .foregroundStyle(AN.inkSoft)
                .lineLimit(3)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(AN.cream)
        .overlay(alignment: .top) { Rectangle().fill(AN.gold).frame(height: 2) }
        .overlay(Rectangle().strokeBorder(AN.hairline, lineWidth: 1))
        .padding(.horizontal, 16)
        .padding(.top, 14)
    }

    /// A finite feed says so, rather than spinning forever.
    private var ending: some View {
        HStack(spacing: 10) {
            Rectangle().fill(AN.goldHair).frame(width: 26, height: 1)
            Text(L10n["imp.end"]).font(ANFont.text(9)).tracking(1.8)
                .foregroundStyle(AN.inkFaint)
            Rectangle().fill(AN.goldHair).frame(width: 26, height: 1)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 28)
    }

    private func load() async {
        loading = true
        defer { loading = false }
        do {
            // both feeds follow the language she is READING in, not the one
            // stored on her record — she may have switched the app to English
            let path = guestMode
                ? "/api/public/journal?lang=\(L10n.lang)"
                : "/api/app/journal?lang=\(L10n.lang)"
            let r: JournalResponse = try await APIClient.shared.get(path, auth: !guestMode)
            articles = r.articles
            failed = false
        } catch {
            failed = true
        }
    }
}

/// The reader. One column, generous measure, no chrome competing with the words.
struct ImpulseReader: View {
    let article: Article
    @EnvironmentObject private var settings: SettingsStore

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text(article.dateLabel)
                    .font(ANFont.text(10)).tracking(1.8)
                    .foregroundStyle(AN.clay)
                if !article.title.isEmpty {
                    Text(article.title)
                        .font(ANFont.display(28))
                        .foregroundStyle(AN.ink)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Rectangle().fill(AN.gold).frame(width: 34, height: 2)
                ForEach(Array(article.paragraphs.enumerated()), id: \.offset) { _, p in
                    Text(p)
                        .font(ANFont.text(16))
                        .foregroundStyle(AN.inkSoft)
                        .lineSpacing(6)
                        .fixedSize(horizontal: false, vertical: true)
                }
                byline
                scopeFooter
            }
            .padding(22)
        }
        .background(AN.paper.ignoresSafeArea())
        .toolbar(.visible, for: .navigationBar)
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { settings.markImpulseSeen(article.id) }
    }

    private var byline: some View {
        HStack(spacing: 10) {
            Image("Emblem").resizable().scaledToFit().frame(width: 26, height: 26)
            // Fixed key: the credential must never drift into "Dr. med." or a
            // protected title through a copy edit.
            Text(L10n["brand.byline"])
                .font(ANFont.text(10)).tracking(1.4)
                .foregroundStyle(AN.inkFaint)
        }
        .padding(.top, 6)
    }

    /// Compiled in, not stored per article — so no console edit can drop it.
    private var scopeFooter: some View {
        Text(L10n["imp.scope"])
            .font(ANFont.text(11))
            .foregroundStyle(AN.inkFaint)
            .fixedSize(horizontal: false, vertical: true)
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(AN.paper2)
            .overlay(alignment: .leading) { Rectangle().fill(AN.clay).frame(width: 2) }
    }
}
