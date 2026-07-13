import SwiftUI

// MARK: - Programme webshop

struct ProgrammeView: View {
    @EnvironmentObject private var catalog: CatalogStore

    private let columns = [GridItem(.adaptive(minimum: 320), spacing: 20)]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(L10n["prog.title"])
                        .font(ANFont.display(28, weight: .semibold))
                        .foregroundStyle(AN.ink)
                    Text(L10n["prog.sub"])
                        .font(ANFont.text(14))
                        .foregroundStyle(AN.inkSoft)
                }

                LazyVGrid(columns: columns, spacing: 20) {
                    if catalog.loading && catalog.offers.isEmpty {
                        ForEach(0..<3, id: \.self) { _ in
                            SkeletonRow(height: 320)
                        }
                    } else {
                        ForEach(catalog.offers) { offer in
                            NavigationLink {
                                ProgrammeDetailView(offer: offer)
                            } label: {
                                OfferCard(offer: offer)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
            }
            .padding(20)
        }
        .background(AN.paper.ignoresSafeArea())
        .task { await catalog.load() }
        .refreshable { await catalog.load() }
    }
}

// MARK: - Offer card

struct OfferCard: View {
    let offer: Offer

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            photoHero
            VStack(alignment: .leading, spacing: 8) {
                Text(offer.name)
                    .font(ANFont.display(22, weight: .semibold))
                    .foregroundStyle(AN.ink)
                Text(offer.tagline)
                    .font(ANFont.text(13))
                    .foregroundStyle(AN.inkSoft)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                HStack(alignment: .firstTextBaseline) {
                    if offer.price > 0 {
                        Text(offer.priceText)
                            .font(ANFont.display(24, weight: .semibold))
                            .monospacedDigit()
                            .foregroundStyle(AN.ink)
                        Text(L10n["prog.once"])
                            .font(ANFont.text(12))
                            .foregroundStyle(AN.inkFaint)
                    } else {
                        Text(L10n["prog.onRequest"])
                            .font(ANFont.display(20, weight: .semibold))
                            .foregroundStyle(AN.ink)
                    }
                    Spacer()
                    Text(L10n["prog.details"]).anPill(AN.clay)
                }
                .padding(.top, 4)
            }
            .padding(16)
        }
        .anCard()
    }

    private var photoHero: some View {
        Color.clear
            .aspectRatio(4.0 / 3.0, contentMode: .fit)
            .overlay(
                Image(CatalogStore.photo(for: offer.key))
                    .resizable()
                    .scaledToFill()
            )
            .clipped()
            .overlay(alignment: .bottomTrailing) {
                Image("Emblem")
                    .resizable()
                    .scaledToFit()
                    .padding(8)
                    .frame(width: 54, height: 54)
                    .background(AN.cream)
                    .overlay(Rectangle().strokeBorder(Color.white, lineWidth: 2))
                    .padding(10)
            }
            .overlay(alignment: .topLeading) {
                if offer.key == "bloom" {
                    Text(L10n["prog.badge"])
                        .font(ANFont.text(10, weight: .semibold))
                        .tracking(1.2)
                        .foregroundStyle(AN.forestDeep)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .background(AN.goldBright)
                        .padding(10)
                }
            }
    }
}

// MARK: - Programme detail

struct ProgrammeDetailView: View {
    let offer: Offer

    @EnvironmentObject private var router: TabRouter
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL

    @State private var safariItem: SafariItem?

    private static let knownKeys = ["root", "bloom", "flourish", "grove"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                Color.clear
                    .aspectRatio(4.0 / 3.0, contentMode: .fit)
                    .overlay(
                        Image(CatalogStore.photo(for: offer.key))
                            .resizable()
                            .scaledToFill()
                    )
                    .clipped()
                    .overlay(Rectangle().strokeBorder(AN.hairline, lineWidth: 1))

                VStack(alignment: .leading, spacing: 6) {
                    Text(offer.name)
                        .font(ANFont.display(26, weight: .semibold))
                        .foregroundStyle(AN.ink)
                    Text(offer.tagline)
                        .font(ANFont.text(14))
                        .foregroundStyle(AN.inkSoft)
                }

                if Self.knownKeys.contains(offer.key) {
                    VStack(alignment: .leading, spacing: 12) {
                        SectionHeader(fig: "FIG. 01", title: L10n["prog.features"])
                        ForEach(1...3, id: \.self) { i in
                            HStack(alignment: .top, spacing: 10) {
                                Text("—")
                                    .font(ANFont.text(14, weight: .semibold))
                                    .foregroundStyle(AN.gold)
                                Text(L10n["prog.\(offer.key).f\(i)"])
                                    .font(ANFont.text(14))
                                    .foregroundStyle(AN.ink)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .padding(18)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .anCard()
                }

                if offer.key == "grove" {
                    Text(L10n["prog.grove.hint"])
                        .font(ANFont.display(15, italic: true))
                        .foregroundStyle(AN.inkSoft)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .padding(20)
        }
        .background(AN.paper.ignoresSafeArea())
        .navigationTitle(offer.name)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar(.visible, for: .navigationBar)
        .safeAreaInset(edge: .bottom, spacing: 0) { checkoutBar }
        .sheet(item: $safariItem) { item in
            SafariView(url: item.url)
        }
    }

    // MARK: Sticky checkout bar

    private var checkoutBar: some View {
        HStack(spacing: 16) {
            VStack(alignment: .leading, spacing: 1) {
                if offer.price > 0 {
                    Text(offer.priceText)
                        .font(ANFont.display(22, weight: .semibold))
                        .monospacedDigit()
                        .foregroundStyle(AN.ink)
                    Text(L10n["prog.once"])
                        .font(ANFont.text(11))
                        .foregroundStyle(AN.inkFaint)
                } else {
                    Text(L10n["prog.onRequest"])
                        .font(ANFont.display(17, weight: .semibold))
                        .foregroundStyle(AN.ink)
                }
            }
            Button(ctaTitle) {
                checkout()
            }
            .buttonStyle(.anPrimary)
        }
        .padding(16)
        .background(AN.cream)
        .overlay(alignment: .top) {
            Rectangle().fill(AN.hairline).frame(height: 1)
        }
    }

    private var hasBuyURL: Bool {
        guard let s = offer.buyUrl, !s.isEmpty else { return false }
        return true
    }

    private var ctaTitle: String {
        if hasBuyURL { return L10n["prog.buy"] }
        return offer.key == "grove" ? L10n["prog.enquire"] : L10n["prog.freeCall"]
    }

    private func checkout() {
        Haptics.tap()
        if let s = offer.buyUrl, !s.isEmpty, let url = URL(string: s) {
            if s.hasPrefix("http") {
                safariItem = SafariItem(url: url)
            } else {
                openURL(url) // e.g. mailto: enquiry links
            }
        } else if offer.key == "grove" {
            if let mail = URL(string: "mailto:team@auralisnatura.com?subject=The%20Grove") {
                openURL(mail)
            }
        } else {
            router.tab = .booking
            dismiss()
        }
    }
}
