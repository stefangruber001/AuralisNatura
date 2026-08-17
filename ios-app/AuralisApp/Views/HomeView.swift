import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var documents: DocumentsStore
    @EnvironmentObject private var router: TabRouter

    @State private var showIntake = false
    @State private var showReport = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                if session.isGuest {
                    guestHome
                } else if let me = session.me {
                    greeting(me)
                    heroCard(me)
                    actionCards(me)
                    if let wb = me.wellbeing, wb.hasData {
                        scalesCard(wb)
                    }
                    journeyCard(me)
                    if me.reportReady {
                        latestDocCard
                    }
                } else if session.meLoadFailed {
                    EmptyState(icon: "wifi.slash", text: L10n["error.network"],
                               retry: { Task { await session.refreshMe() } })
                        .padding(.top, 60)
                } else {
                    skeletons
                }
            }
            .padding(20)
        }
        .background(AN.paper.ignoresSafeArea())
        .refreshable {
            await session.refreshMe()
            await documents.load()
        }
        .task {
            guard !session.isGuest else { return }   // a guest has nothing to fetch
            if session.me == nil { await session.refreshMe() }
            if !documents.loaded { await documents.load() }
        }
        .sheet(isPresented: $showIntake) { IntakeFlow() }
        .navigationDestination(isPresented: $showReport) { ReportViewer() }
    }

    // MARK: Guest home — what this is, and the way in

    /// A prospect's first screen. It shows the practice honestly (who Desiree is,
    /// what the app does) and offers two real doors: the free introductory call
    /// and the programmes. No invented progress, no sample client, no numbers she
    /// has not given us.
    private var guestHome: some View {
        VStack(alignment: .leading, spacing: 22) {
            VStack(alignment: .leading, spacing: 8) {
                Text(L10n["guest.hello"])
                    .font(ANFont.display(27, weight: .semibold))
                    .foregroundStyle(AN.ink)
                    .fixedSize(horizontal: false, vertical: true)
                Text(L10n["guest.sub"])
                    .font(ANFont.text(14))
                    .foregroundStyle(AN.inkSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }

            // Desiree herself beside her credential line — a prospect meeting a
            // practice should meet the person. Square with a gold hairline: the
            // brand has no rounded corners, so no circular avatar either.
            HStack(alignment: .top, spacing: 14) {
                Image("PhotoDesiree")
                    .resizable()
                    .scaledToFill()
                    .frame(width: 56, height: 56)
                    .clipped()
                    .overlay(Rectangle().strokeBorder(AN.goldHair, lineWidth: 1))
                    .accessibilityHidden(true)   // the line beside it names her
                Text(L10n["guest.credential"])
                    .font(ANFont.text(12))
                    .foregroundStyle(AN.inkSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .anCard()

            Button {
                Haptics.tap()
                router.tab = .booking
            } label: {
                Text(L10n["guest.cta.call"])
            }
            .buttonStyle(.anPrimary)

            Button {
                Haptics.tap()
                router.tab = .programmes
            } label: {
                Label(L10n["guest.cta.programmes"], systemImage: "sparkles")
            }
            .buttonStyle(.anOutline)
            .frame(maxWidth: .infinity)

            LockedCard(title: L10n["guest.locked.title"],
                       sub: L10n["guest.locked.sub"],
                       items: [L10n["guest.locked.i1"], L10n["guest.locked.i2"],
                               L10n["guest.locked.i3"], L10n["guest.locked.i4"]],
                       ctaTitle: L10n["guest.cta.call"]) {
                router.tab = .booking
            }
        }
    }

    // MARK: Greeting

    private func greeting(_ me: Me) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(L10n.f("home.hello", me.firstName))
                .font(ANFont.display(28, weight: .semibold))
                .foregroundStyle(AN.ink)
            Text(L10n["home.sub"])
                .font(ANFont.text(14))
                .foregroundStyle(AN.inkSoft)
        }
    }

    // MARK: Hero — the progress band

    /// Where she stands and the single next thing to do. Derived from the
    /// server's stage, never from a local guess, so the band can't flatter.
    private func heroCard(_ me: Me) -> some View {
        let step = me.journeyStep
        let nx = nextAction(me)
        return ProgressBand(done: step, total: 4,
                            milestone: L10n["journey.step\(min(max(step, 1), 4)).sub"],
                            actionTitle: nx?.title, action: nx?.run)
    }

    /// One action, chosen for where she actually is. Waiting on Desiree is a
    /// legitimate state: it offers the calendar rather than inventing a task.
    private func nextAction(_ me: Me) -> (title: String, run: () -> Void)? {
        if !me.hasIntake {
            return (L10n["home.progress.cta.intake"], { showIntake = true })
        }
        if me.reportReady {
            return (L10n["home.progress.cta.report"], { showReport = true })
        }
        if me.sessions.isEmpty {
            return (L10n["home.progress.cta.book"], { router.tab = .booking })
        }
        return nil
    }

    // MARK: Actions

    private func actionCards(_ me: Me) -> some View {
        VStack(spacing: 12) {
            actionCard(icon: "square.and.pencil",
                       title: L10n["home.action.book"],
                       sub: L10n["home.action.book.sub"]) {
                router.tab = .booking
            }
            if !me.hasIntake {
                actionCard(icon: "list.bullet.clipboard",
                           title: L10n["home.action.intake"],
                           sub: L10n["home.action.intake.sub"]) {
                    showIntake = true
                }
            }
            programmeCard
        }
    }

    private func actionCard(icon: String, title: String, sub: String,
                            action: @escaping () -> Void) -> some View {
        Button {
            Haptics.tap()
            action()
        } label: {
            HStack(spacing: 14) {
                Image(systemName: icon)
                    .font(.system(size: 20, weight: .light))
                    .foregroundStyle(AN.clay)
                    .frame(width: 34)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(ANFont.text(16, weight: .semibold))
                        .foregroundStyle(AN.ink)
                    Text(sub)
                        .font(ANFont.text(13))
                        .foregroundStyle(AN.inkSoft)
                        .multilineTextAlignment(.leading)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(AN.inkFaint)
            }
            .padding(16)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .anCard()
    }

    private var programmeCard: some View {
        Button {
            Haptics.tap()
            router.tab = .programmes
        } label: {
            HStack(spacing: 14) {
                Image("PhotoNourish")
                    .resizable()
                    .scaledToFill()
                    .frame(width: 54, height: 54)
                    .clipped()
                    .overlay(Rectangle().strokeBorder(AN.hairline, lineWidth: 1))
                VStack(alignment: .leading, spacing: 2) {
                    Text(L10n["home.action.programmes"])
                        .font(ANFont.text(16, weight: .semibold))
                        .foregroundStyle(AN.ink)
                    Text(L10n["home.action.programmes.sub"])
                        .font(ANFont.text(13))
                        .foregroundStyle(AN.inkSoft)
                        .multilineTextAlignment(.leading)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(AN.inkFaint)
            }
            .padding(12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .anCard()
    }

    // MARK: Self-assessment (her own intake ratings — the report's baseline)

    private static let scaleOrder = ["energy", "sleep", "stress", "digestion", "mood", "movement"]

    private func scalesCard(_ wb: Wellbeing) -> some View {
        let keys = Self.scaleOrder.filter { wb.scales[$0] != nil }
            + wb.scales.keys.filter { !Self.scaleOrder.contains($0) }.sorted()
        return VStack(alignment: .leading, spacing: 14) {
            SectionHeader(fig: "FIG. 01", title: L10n["home.scales.title"])
            Text(L10n["home.scales.sub"])
                .font(ANFont.text(13))
                .foregroundStyle(AN.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
            VStack(spacing: 9) {
                ForEach(keys, id: \.self) { key in
                    ScaleRow(label: L10n["scale.\(key)"], value: wb.scales[key] ?? 0)
                }
            }
            .padding(.top, 2)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .anCard()
    }

    // MARK: Journey

    private func journeyCard(_ me: Me) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            SectionHeader(fig: "FIG. 02", title: L10n["home.journey.title"])
            JourneyTimeline(done: me.journeyStep)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .anCard()
    }

    // MARK: Latest document

    private var latestDocCard: some View {
        NavigationLink {
            ReportViewer()
        } label: {
            HStack(spacing: 14) {
                Image(systemName: "doc.text")
                    .font(.system(size: 20, weight: .light))
                    .foregroundStyle(AN.clay)
                    .frame(width: 34)
                VStack(alignment: .leading, spacing: 2) {
                    Text(L10n["home.latestDoc"])
                        .font(ANFont.text(16, weight: .semibold))
                        .foregroundStyle(AN.ink)
                    if let doc = documents.docs.first {
                        Text(doc.name)
                            .font(ANFont.text(13))
                            .foregroundStyle(AN.inkSoft)
                            .lineLimit(1)
                    }
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(AN.inkFaint)
            }
            .padding(16)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .anCard()
    }

    // MARK: Skeletons

    private var skeletons: some View {
        VStack(spacing: 16) {
            SkeletonRow(height: 34)
            SkeletonRow(height: 110)
            SkeletonRow(height: 72)
            SkeletonRow(height: 72)
            SkeletonRow(height: 180)
        }
    }
}
