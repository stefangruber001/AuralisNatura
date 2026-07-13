import SwiftUI

struct HomeView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var documents: DocumentsStore
    @EnvironmentObject private var router: TabRouter

    @State private var showIntake = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                if let me = session.me {
                    greeting(me)
                    heroCard(me)
                    actionCards(me)
                    journeyCard(me)
                    if me.reportReady {
                        latestDocCard
                    }
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
            if session.me == nil { await session.refreshMe() }
            if !documents.loaded { await documents.load() }
        }
        .sheet(isPresented: $showIntake) { IntakeFlow() }
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

    // MARK: Hero (KPI milestones; brand colour only in the numbers)

    private func heroCard(_ me: Me) -> some View {
        let step = me.journeyStep
        return HStack(spacing: 0) {
            KPITile(value: "\(step)/4", label: L10n["home.kpi.steps"])
            kpiDivider
            if let score = me.wellbeing?.score {
                KPITile(value: "\(score)", label: L10n["home.kpi.balance"], accent: AN.gold)
            } else {
                KPITile(value: me.hasIntake ? "✓" : "–", label: L10n["home.kpi.intake"])
            }
            kpiDivider
            KPITile(value: me.reportReady ? L10n["home.report.ready"] : L10n["home.report.pending"],
                    label: L10n["home.kpi.report"])
        }
        .padding(.vertical, 22)
        .padding(.horizontal, 12)
        .background(alignment: .bottomTrailing) {
            Image("Emblem")
                .resizable()
                .scaledToFit()
                .frame(width: 90, height: 90)
                .opacity(0.07)
                .padding(4)
        }
        .anCard()
    }

    private var kpiDivider: some View {
        Rectangle().fill(AN.hairline).frame(width: 1, height: 38)
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

    // MARK: Journey

    private func journeyCard(_ me: Me) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            SectionHeader(fig: "FIG. 01", title: L10n["home.journey.title"])
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
