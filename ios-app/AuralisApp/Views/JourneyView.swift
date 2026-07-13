import SwiftUI

/// "Mein Weg" — the client's journey: timeline, priorities & documents.
struct JourneyView: View {
    @EnvironmentObject private var session: SessionStore
    @EnvironmentObject private var documents: DocumentsStore

    @State private var showIntake = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                VStack(alignment: .leading, spacing: 4) {
                    Text(L10n["journey.title"])
                        .font(ANFont.display(28, weight: .semibold))
                        .foregroundStyle(AN.ink)
                    Text(L10n["journey.sub"])
                        .font(ANFont.text(14))
                        .foregroundStyle(AN.inkSoft)
                }

                if let me = session.me {
                    timelineCard(me)
                    if !me.hasIntake {
                        intakeCTA
                    }
                    if me.reportReady && !me.priorities.isEmpty {
                        prioritiesSection(me)
                    }
                } else if session.meLoadFailed {
                    EmptyState(icon: "wifi.slash", text: L10n["error.network"],
                               retry: { Task { await session.refreshMe() } })
                        .padding(.vertical, 40)
                } else {
                    SkeletonRow(height: 200)
                }

                documentsSection
            }
            .padding(20)
        }
        .background(AN.paper.ignoresSafeArea())
        .refreshable {
            await session.refreshMe()
            await documents.load()
        }
        .task {
            if !documents.loaded { await documents.load() }
        }
        .sheet(isPresented: $showIntake) { IntakeFlow() }
    }

    // MARK: Timeline

    private func timelineCard(_ me: Me) -> some View {
        JourneyTimeline(done: me.journeyStep)
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
            .anCard()
    }

    // MARK: Intake CTA

    private var intakeCTA: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(L10n["journey.intakeCta.title"])
                .font(ANFont.display(19, weight: .semibold))
                .foregroundStyle(AN.ink)
            Text(L10n["journey.intakeCta.sub"])
                .font(ANFont.text(14))
                .foregroundStyle(AN.inkSoft)
                .fixedSize(horizontal: false, vertical: true)
            Button(L10n["journey.intakeCta.button"]) {
                Haptics.tap()
                showIntake = true
            }
            .buttonStyle(.anGold)
            .padding(.top, 4)
        }
        .padding(18)
        .frame(maxWidth: .infinity, alignment: .leading)
        .anCard()
    }

    // MARK: Priorities & habits (once the report is ready)

    private func prioritiesSection(_ me: Me) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(fig: "FIG. 03", title: L10n["journey.priorities"])
            VStack(spacing: 12) {
                ForEach(me.priorities) { priority in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(priority.title)
                            .font(ANFont.text(15, weight: .semibold))
                            .foregroundStyle(AN.ink)
                        if let step = priority.firstStep, !step.isEmpty {
                            HStack(alignment: .top, spacing: 6) {
                                Text(L10n["journey.firstStep"] + ":")
                                    .font(ANFont.text(13, weight: .semibold))
                                    .foregroundStyle(AN.gold)
                                Text(step)
                                    .font(ANFont.text(13))
                                    .foregroundStyle(AN.inkSoft)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .anCard()
                }
            }
            if !me.habits.isEmpty {
                Text(L10n["journey.habits"])
                    .font(ANFont.text(13, weight: .semibold))
                    .foregroundStyle(AN.inkSoft)
                    .padding(.top, 4)
                VStack(alignment: .leading, spacing: 6) {
                    ForEach(me.habits, id: \.self) { habit in
                        HStack(alignment: .top, spacing: 10) {
                            Text("—")
                                .font(ANFont.text(13, weight: .semibold))
                                .foregroundStyle(AN.gold)
                            Text(habit)
                                .font(ANFont.text(13))
                                .foregroundStyle(AN.ink)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
            }
        }
    }

    // MARK: Documents

    private var documentsSection: some View {
        VStack(alignment: .leading, spacing: 14) {
            SectionHeader(fig: "FIG. 02", title: L10n["journey.docs"])
            if documents.failed && documents.docs.isEmpty {
                EmptyState(icon: "wifi.slash",
                           text: L10n["error.network"],
                           retry: { Task { await documents.load() } })
                    .anCard()
            } else if documents.loaded && documents.docs.isEmpty {
                Text(L10n["journey.docs.empty"])
                    .font(ANFont.text(14))
                    .foregroundStyle(AN.inkSoft)
                    .padding(18)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .anCard()
            } else if documents.docs.isEmpty {
                SkeletonRow(height: 64)
            } else {
                VStack(spacing: 0) {
                    ForEach(documents.docs) { doc in
                        NavigationLink {
                            ReportViewer()
                        } label: {
                            HStack(spacing: 14) {
                                Image(systemName: "doc.text")
                                    .font(.system(size: 18, weight: .light))
                                    .foregroundStyle(AN.clay)
                                    .frame(width: 28)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(doc.name)
                                        .font(ANFont.text(15, weight: .medium))
                                        .foregroundStyle(AN.ink)
                                        .lineLimit(1)
                                    Text(doc.date)
                                        .font(ANFont.text(12))
                                        .monospacedDigit()
                                        .foregroundStyle(AN.inkFaint)
                                }
                                Spacer()
                                Image(systemName: "chevron.right")
                                    .font(.system(size: 12, weight: .semibold))
                                    .foregroundStyle(AN.inkFaint)
                            }
                            .padding(14)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                        if doc.id != documents.docs.last?.id {
                            Rectangle().fill(AN.hairline).frame(height: 1)
                                .padding(.leading, 14)
                        }
                    }
                }
                .anCard()
            }
        }
    }
}
